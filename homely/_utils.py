import contextlib
import subprocess
from itertools import chain
import os
import tempfile

import simplejson

from homely._errors import JsonError
from homely._vcs import Repo, fromdict

CONFIG_DIR = os.path.join(os.environ['HOME'], '.homely')
REPO_CONFIG_PATH = os.path.join(CONFIG_DIR, 'repos.json')
ENGINE2_CONFIG_PATH = os.path.join(CONFIG_DIR, 'engine2.json')
FACT_CONFIG_PATH = os.path.join(CONFIG_DIR, 'facts.json')


def _resolve(path):
    return os.path.realpath(os.path.expanduser(path))


def haveexecutable(name):
    try:
        otuput = subprocess.check_output(['which', name])
        return True
    except subprocess.CalledProcessError as err:
        if err.returncode == 1:
            return False
        print(output)
        raise


class JsonConfig(object):
    jsonpath = None
    jsondata = None

    def __init__(self):
        try:
            with open(self.jsonpath, 'r') as f:
                data = f.read()
                if not len(data):
                    raise FileNotFoundError(None)
                self.jsondata = simplejson.loads(data)
                self.checkjson()
        except FileNotFoundError:
            self.jsondata = self.defaultjson()
        except simplejson.JSONDecodeError:
            raise JsonError("%s does not contain valid JSON" % self.jsonpath)

    def checkjson(self):
        """
        Child classes should override this method to check if self.jsondata is
        sane.
        """
        raise Exception("This method needs to be overridden")

    def defaultjson(self):
        """
        Child classes should override this method to return the default json
        object for when the config file doesn't exist yet.
        """
        raise Exception("This method needs to be overridden")

    def writejson(self):
        # make dirs needed for config file
        os.makedirs(os.path.dirname(self.jsonpath), mode=0o755, exist_ok=True)
        # write the config file now
        dumped = simplejson.dumps(self.jsondata, indent=' ' * 4)
        with open(self.jsonpath, 'w') as f:
            f.write(dumped)


class RepoListConfig(JsonConfig):
    jsonpath = REPO_CONFIG_PATH
    jsondata = None

    def defaultjson(self):
        return []

    def checkjson(self):
        assert isinstance(self.jsondata, list)
        for row in self.jsondata:
            assert 'repoid' in row
            assert 'localrepo' in row
            assert 'localpath' in row
            if 'canonicalpath' in row:
                assert 'canonicalrepo' in row

    def add_repo(self, info):
        assert isinstance(info, RepoInfo)
        modified = False
        for row in self.jsondata:
            if row["repoid"] == info.repoid:
                row.update(self._infotodict(info))
                modified = True
                break
        if not modified:
            self.jsondata.append(self._infotodict(info))

    @staticmethod
    def _infotodict(info):
        assert isinstance(info, RepoInfo)
        ret = {
            "repoid": info.repoid,
            "localpath": info.localrepo.repo_path,
            "localrepo": info.localrepo.asdict(),
        }
        if info.canonicalrepo is not None:
            ret["canonicalpath"] = info.canonicalrepo.repo_path
            ret["canonicalrepo"] = info.canonicalrepo.asdict()
        return ret

    def _infofromdict(self, row):
        localrepo = fromdict(row["localrepo"])
        assert localrepo is not None
        if row.get("canonicalpath"):
            canonical = fromdict(row["canonicalrepo"])
        else:
            canonical = None
        return RepoInfo(
            localrepo,
            row["repoid"],
            canonical,
        )

    def remove_repo(self, repoid):
        newdata = []
        for row in self.jsondata:
            if row["repoid"] != repoid:
                newdata.append(row)
        self.jsondata = newdata

    def find_by_id(self, repoid):
        """
        Returns the repo with the specified <repoid>
        """
        for row in self.jsondata:
            if repoid == row["repoid"]:
                return self._infofromdict(row)

    def find_by_localpath(self, path):
        """
        Returns the repo with the specified local <path>
        """
        # note that the paths in self.jsondata were already _resolve()'d in the
        # class' __init__()
        resolved = _resolve(path)
        for row in self.jsondata:
            if resolved == os.path.realpath(row["localpath"]):
                return self._infofromdict(row)

    def find_by_canonical(self, repo_path):
        for row in self.jsondata:
            if repo_path == row.get("canonicalpath"):
                return self._infofromdict(row)

    def find_by_any(self, identifier, how):
        """
        how should be a string with any or all of the characters "ilc"
        """
        if "i" in how:
            match = self.find_by_id(identifier)
            if match:
                return match
        if "l" in how:
            match = self.find_by_localpath(identifier)
            if match:
                return match
        if "c" in how:
            match = self.find_by_canonical(identifier)
            if match:
                return match

    def find_all(self):
        for row in self.jsondata:
            yield self._infofromdict(row)

    def repo_count(self):
        return len(self.jsondata)


class RepoScriptConfig(JsonConfig):
    jsondata = None

    def __init__(self, info):
        assert isinstance(info, RepoInfo)
        self.jsonpath = os.path.join(CONFIG_DIR,
                                     'repos',
                                     info.repoid + '.json')
        super(RepoScriptConfig, self).__init__()

    @staticmethod
    def remove(info):
        assert isinstance(info, RepoInfo)
        os.unlink(os.path.join(CONFIG_DIR, 'repos', info.repoid + '.json'))

    def defaultjson(self):
        # TODO: prevthings and prevchanges are not needed with the new engine
        return {
            # a list of things that were installed on the last run
            "prevthings": [],
            "prevchanges": {},
            "questions": {},
        }

    def checkjson(self):
        pass

    def getthings(self):
        import homely.general
        import homely.install
        modules = [homely.general, homely.install]
        for thing in self.jsondata['prevthings']:
            class_ = thing["class"]
            identifiers = thing["identifiers"]
            for module in modules:
                if hasattr(module, class_):
                    yield getattr(module, class_).fromidentifiers(identifiers)
                    break
            else:
                raise Exception("No modules own %s" % class_)

    def clearthings(self):
        self.jsondata["prevthings"] = []
        return self.jsondata["prevchanges"]

    @staticmethod
    def _asdict(thing):
        return {"class": thing.__class__.__name__,
                "identifiers": thing.identifiers}

    def addthing(self, thing):
        self.jsondata["prevthings"].append(self._asdict(thing))
        self.jsondata["prevchanges"].setdefault(thing.uniqueid, {})

    def removething(self, thing):
        thingdict = self._asdict(thing)
        prevthings = [t for t in self.jsondata["prevthings"] if t != thingdict]
        assert (len(self.jsondata["prevthings"]) - len(prevthings)) == 1
        del self.jsondata["prevchanges"][thing.uniqueid]

    def setchanges(self, uniqueid, changes):
        self.jsondata["prevchanges"][uniqueid] = changes

    def getprevchanges(self, uniqueid):
        return self.jsondata["prevchanges"].get(uniqueid, {})

    def getquestionanswer(self, name):
        return self.jsondata["questions"].get(name, None)

    def setquestionanswer(self, name, value):
        self.jsondata["questions"][name] = value


class FactConfig(JsonConfig):
    jsonpath = FACT_CONFIG_PATH

    def checkjson(self):
        pass

    def defaultjson(self):
        return {}


@contextlib.contextmanager
def saveconfig(cfg):
    assert isinstance(cfg, JsonConfig)
    yield cfg
    cfg.writejson()


class RepoInfo(object):
    def __init__(self, localrepo, repoid, canonicalrepo=None):
        if localrepo is not None:
            assert isinstance(localrepo, Repo)
            assert not localrepo.isremote
        if canonicalrepo is not None:
            assert isinstance(canonicalrepo, Repo)
            assert canonicalrepo.isremote
            assert canonicalrepo.iscanonical

        self.localrepo = localrepo
        self.canonicalrepo = canonicalrepo
        self.repoid = repoid

    def shortid(self):
        return self.localrepo.shortid(self.repoid)


class NoChangesNeeded(Exception):
    """See filereplacer() for more info"""


@contextlib.contextmanager
def filereplacer(filepath):
    """
    This context manager yields two file pointers:

    origlines:
        a generator that yields lines from the original file
    tmp:
        a file descriptor as if you had used open(tempfile.mkstemp(), 'w')
    NL:
        one of "\n", "\r\n" or "\r" depending on what is encountered first in
        orig. If orig is empty or doesn't exist, then "\n" is used.

    Note that upon successful exiting of the context manager, the file
    nominated by filepath will be replaced by the temp file. This will be done
    using file renames, so it is as close to atomic as we can get it.

    If the context block raises an exception, the original file is not changed,
    and the temp file is deleted.

    If the context block raises a NoChangesNeeded exception, then any changes
    to tmpfile are discarded.
    """
    import shutil
    # create the tmp dir if it doesn't exist yet
    tmpdir = os.path.join(CONFIG_DIR, 'tmp')
    os.makedirs(tmpdir, mode=0o700, exist_ok=True)
    tmpname = os.path.join(tmpdir, os.path.basename(filepath))
    try:
        if os.path.exists(filepath):
            shutil.copy2(filepath, tmpname)
        with open(tmpname, 'w', newline="") as tmp:
            try:
                with open(filepath, 'r', newline="") as orig:
                    NL = "\n"
                    origlines = []
                    firstline = None
                    for firstline in orig:
                        break
                    if firstline is not None:
                        stripped = firstline.rstrip('\r\n')
                        NL = firstline[len(stripped):]
                        assert NL in ("\r", "\n", "\r\n"), "Bad NL %r" % NL
                        origlines = chain([stripped],
                                          (l.rstrip('\r\n') for l in orig))
                    yield tmp, origlines, NL
            except FileNotFoundError:
                yield tmp, None, "\n"
    except NoChangesNeeded:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmpname)
    except:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmpname)
        raise
    with contextlib.suppress(FileNotFoundError):
        os.unlink(filepath)
    os.rename(tmpname, filepath)


def isnecessarypath(parent, child):
    """
    returns True if the file, directory or symlink <parent> is required to
    exist in order for the path <child> to refer to a valid filesystem entry.

    Examples:

    If <parent> refers to a file, and <child> refers to the same file, then
    <parent> must exist in order for <child> to be valid.

    If <parent> refers to a directory, and <child> refers to the same directory
    or anything under that directory, then <parent> must exist in order for
    <child> to be valid.

    If <parent> is a symlink to a directory, and <child> refers to something in
    that directory *and contains the symlink <parent> in its path*, then
    <parent> must continue to exist in order for <child> to be valid.
    """
    assert parent.startswith('/')
    assert child.startswith('/')
    # resolve all symlinks in the parent (except for the final part itself)
    head, tail = os.path.split(parent)
    # expand the head part out to its real path
    head = os.path.realpath(head)
    fullparent = os.path.realpath(parent)
    assert len(tail), "Can't use isancestor() on path ending in /: %s" % parent
    prefix = '/'
    parts = child.split('/')
    while len(parts):
        prefix = os.path.realpath(os.path.join(prefix, parts.pop(0)))
        common = os.path.commonprefix([prefix, head])

        # if at any time we stumble upon the parent as we are reconstructing
        # the path, then we are dependent on the parent
        if prefix == fullparent and len(parts):
            return True

        # if they refer to the same thing up to this point, check to see if the
        # next parts are also the same
        if len(common) == len(head):
            # if the next item of child's path is the tail of parent, then they
            # must refer to the same thing
            if len(parts) and tail == parts[0]:
                return True

    return False


@contextlib.contextmanager
def tmpdir(name):
    assert '/' not in name, "Invalid name %r" % name
    tmp = None
    try:
        tmp = tempfile.TemporaryDirectory()
        yield os.path.join(tmp.name, name)
    finally:
        if tmp and os.path.exists(tmp.name):
            tmp.cleanup()
