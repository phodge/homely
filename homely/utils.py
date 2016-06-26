import contextlib
import os
import subprocess

import simplejson

from homely._errors import JsonError, RepoError

CONFIG_DIR = os.path.join(os.environ.get('HOME'), '.homely')
REPO_CONFIG_PATH = os.path.join(CONFIG_DIR, 'repos.json')


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
        except FileNotFoundError as err:
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
        with open(self.jsonpath, 'w') as f:
            f.write(simplejson.dumps(self.jsondata, indent=' ' * 4))


class RepoListConfig(JsonConfig):
    jsonpath = REPO_CONFIG_PATH
    jsondata = None

    def defaultjson(self):
        return []

    def checkjson(self):
        assert isinstance(self.jsondata, list)
        for entry in self.jsondata:
            assert 'commithash' in entry
            assert 'localpath' in entry

    def add_repo(self, info):
        assert isinstance(info, RepoInfo)
        commithash = info.commithash
        modified = False
        for repo in self.jsondata:
            if repo["commithash"] == commithash:
                # change the local path in the config
                repo["localpath"] = info.localpath
                modified = True
                break
        if not modified:
            self.jsondata.append({"commithash": info.commithash,
                                  "localpath": info.localpath})

    def find_repo(self, hash_or_path):
        for repo in self.jsondata:
            if hash_or_path in (repo["commithash"], repo["localpath"]):
                return RepoInfo(repo["localpath"], repo["commithash"])

    def find_all(self):
        for repo in self.jsondata:
            yield RepoInfo(repo["localpath"], repo["commithash"])


class RepoScriptConfig(JsonConfig):
    jsondata = None

    def __init__(self, info):
        self.jsonpath = os.path.join(CONFIG_DIR,
                                     'repos',
                                     info.commithash + '.json')
        super(RepoScriptConfig, self).__init__()

    def defaultjson(self):
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

    @staticmethod
    def _asdict(thing):
        return {"class": thing.__class__.__name__,
                "identifiers": thing.identifiers}

    def addthing(self, thing, changes):
        self.jsondata["prevthings"].append(self._asdict(thing))
        self.jsondata["prevchanges"][thing.uniqueid] = changes

    def removething(self, thing):
        thingdict = self._asdict(thing)
        prevthings = [t for t in self.jsondata["prevthings"] if t != thingdict]
        assert (len(self.jsondata["prevthings"]) - len(prevthings)) == 1
        del self.jsondata["prevchanges"][thing.uniqueid]

    def getprevchanges(self, uniqueid):
        return self.jsondata["prevchanges"].get(uniqueid, {})

    def getquestionanswer(self, name):
        return self.jsondata["questions"].get(name, None)

    def setquestionanswer(self, name, value):
        self.jsondata["questions"][name] = value


@contextlib.contextmanager
def saveconfig(cfg):
    assert isinstance(cfg, JsonConfig)
    yield cfg
    cfg.writejson()


class RepoInfo(object):
    localpath = None
    commithash = None

    def __init__(self, path, commithash=None):
        # make sure the path is valid
        if not os.path.exists(path):
            raise RepoError("%s does not exist" % path)
        if not os.path.exists(os.path.join(path, '.git')):
            raise RepoError("%s is not a valid git repo" % path)
        self.localpath = path
        if commithash is None:
            # ask git for the commit hash
            cmd = ['git', 'rev-list', '--max-parents=0', 'HEAD']
            self.commithash = (subprocess.check_output(cmd, cwd=path)
                               .rstrip()
                               .decode('utf-8'))
        else:
            self.commithash = commithash

    @property
    def shorthash(self):
        return self.commithash[0:8]


@contextlib.contextmanager
def filereplacer(filepath):
    """
    This context manager yields two file pointers:

    orig:
        a file descriptor as if you had used open(filepath)
    tmp:
        a file descriptor as if you had used open(tempfile.mkstemp(), 'w')

    Note that upon successful exiting of the context manager, the file
    nominated by filepath will be replaced by the temp file. This will be done
    using file renames, so it is as close to atomic as we can get it.

    If the context block raises an exception, the original file is not changed,
    and the temp file is deleted.
    """
    import shutil
    # create the tmp dir if it doesn't exist yet
    tmpdir = os.path.join(CONFIG_DIR, 'tmp')
    os.makedirs(tmpdir, mode=0o700, exist_ok=True)
    tmpname = os.path.join(tmpdir, os.path.basename(filepath))
    try:
        if os.path.exists(filepath):
            shutil.copy2(filepath, tmpname)
        with open(tmpname, 'w') as tmp:
            try:
                with open(filepath, 'r') as orig:
                    yield tmp, orig
            except FileNotFoundError:
                yield tmp, None
    except:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmpname)
        raise
    with contextlib.suppress(FileNotFoundError):
        os.unlink(filepath)
    os.rename(tmpname, filepath)
