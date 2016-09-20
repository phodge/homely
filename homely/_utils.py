import contextlib
import subprocess
import os
import re
import tempfile
from itertools import chain
from functools import partial
from os.path import join, exists

import simplejson

from homely._errors import JsonError
from homely._vcs import Repo, fromdict


try:
    import asyncio
except ImportError:
    asyncio = None


ROOT = join(os.environ['HOME'], '.homely')
REPO_CONFIG_PATH = join(ROOT, 'repos.json')
ENGINE2_CONFIG_PATH = join(ROOT, 'engine2.json')
FACT_CONFIG_PATH = join(ROOT, 'facts.json')

# contains the PID of the currently running homely process
RUNFILE = join(ROOT, "update-running")
# written to when a complete update is finished successfully
TIMEFILE = join(ROOT, "update-time")
# contains the name of the section currently being executed by 'homely update'
SECTIONFILE = join(ROOT, "update-section")
# this file is touched when a 'homely update' of using all sections is
# unsuccessful
FAILFILE = join(ROOT, "update-failed")
# this file is used to control the pause/unpause state
PAUSEFILE = join(ROOT, "update-paused")
# contains the output of the last 'homely autoupdate' run
OUTFILE = join(ROOT, "autoupdate-output.txt")


_urlregex = re.compile(r"^[a-zA-Z0-9+\-.]{2,20}://")


def mkcfgdir():
    if not exists(ROOT):
        os.mkdir(ROOT)


def _expandpath(path):
    if path.startswith('~'):
        path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    if not (path.startswith('/') or _urlregex.match(path)):
        path = os.path.realpath(path)
    return path


def _repopath2real(path, repo):
    assert isinstance(repo, Repo)
    assert not path.endswith('/')
    assert not repo.isremote
    if path.startswith('~'):
        path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    if not _urlregex.match(path):
        if not path.startswith('/'):
            path = join(repo.repo_path, path)
        path = os.path.realpath(path)
    return path


def _homepath2real(path):
    assert not path.endswith('/')
    # expand ~
    if path.startswith('~'):
        path = os.path.expanduser(path)
    # expand variables
    path = os.path.expandvars(path)
    head = path.split(os.sep, 1)[0]
    # paths relative to the current dir are not allowed
    assert head != '.', 'Relative path not allowed'
    if not (head in ('', '..') or _urlregex.match(path)):
        path = join(os.environ['HOME'], path)
    return path


def run(cmd, stdout=None, stderr=None, **kwargs):
    """
    A blocking wrapper around subprocess.Popen(), but with a simpler interface
    for the stdout/stderr arguments:

    stdout=False / stderr=False
        stdout/stderr will be redirected to /dev/null (or discarded in some
        other suitable manner)
    stdout=True / stderr=True
        stdout/stderr will be captured and returned as a list of lines.
    stdout=None
        stdout will be redirected to the python process's stdout, which may be
        a tty (same as using stdout=subprocess.None)
    stderr=None:
        stderr will be redirected to the python process's stderr, which may be
        a tty (same as using stderr=subprocess.None)
    stderr="STDOUT"
        Same as using stderr=subprocess.STDOUT

    The return value will be a tuple of (exitcode, stdout, stderr)

    If stdout and/or stderr were not captured, they will be None instead.
    """
    devnull = None
    try:
        stdoutfilter = None
        stderrfilter = None

        wantstdout = False
        wantstderr = False
        if stdout is False:
            devnull = open('/dev/null', 'w')
            stdout = devnull
        elif stdout is True:
            stdout = subprocess.PIPE
            wantstdout = True
        elif callable(stdout):
            stdoutfilter = partial(stdout)
            stdout = subprocess.PIPE
        else:
            assert stdout is None, "Invalid stdout %r" % stdout

        if stderr is False:
            if devnull is None:
                devnull = open('/dev/null', 'w')
            stderr = devnull
        elif stderr is True:
            stderr = subprocess.PIPE
            wantstderr = True
        elif stderr == "STDOUT":
            stderr = subprocess.STDOUT
        elif callable(stderr):
            stderrfilter = partial(stderr)
            stderr = subprocess.PIPE
        else:
            assert stderr is None, "Invalid stderr %r" % stderr

        if (stdoutfilter or stderrfilter) and asyncio:
            # run background process asynchronously and filter output as
            # it is running
            exitcode, out, err, = _runasync(stdoutfilter,
                                            stderrfilter,
                                            cmd,
                                            stdout=stdout,
                                            stderr=stderr,
                                            **kwargs)
            if not wantstdout:
                out = None
            if not wantstderr:
                err = None
            return exitcode, out, err

        proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr, **kwargs)
        out, err = proc.communicate()
        if not wantstdout:
            if stdoutfilter:
                stdoutfilter(out, True)
            out = None
        if not wantstderr:
            if stderrfilter:
                stderrfilter(err, True)
            err = None
        return proc.returncode, out, err
    finally:
        if devnull is not None:
            devnull.close()


def _runasync(stdoutfilter, stderrfilter, cmd, **kwargs):
    assert asyncio is not None

    @asyncio.coroutine
    def _runandfilter(loop, cmd, **kwargs):
        def factory():
            return FilteringProtocol(asyncio.streams._DEFAULT_LIMIT, loop)

        class FilteringProtocol(asyncio.subprocess.SubprocessStreamProtocol):
            _stdout = b""
            _stderr = b""

            def pipe_data_received(self, fd, data):
                if fd == 1:
                    if stdoutfilter:
                        self._stdout = stdoutfilter(self._stdout + data, False)
                    else:
                        self.stdout.feed_data(data)
                elif fd == 2:
                    if stderrfilter:
                        self._stderr = stderrfilter(self._stderr + data, False)
                    else:
                        self.stderr.feed_data(data)
                else:
                    raise Exception("Unexpected fd %r" % fd)

            def pipe_connection_lost(self, fd, exc):
                if fd == 1:
                    if stdoutfilter and self._stdout:
                        stdoutfilter(self._stdout, True)
                elif fd == 2:
                    if stderrfilter and self._stderr:
                        stderrfilter(self._stderr, True)
                return super().pipe_connection_lost(fd, exc)

        transport, protocol = yield from loop.subprocess_exec(factory,
                                                              *cmd,
                                                              **kwargs)
        process = asyncio.subprocess.Process(transport, protocol, loop)

        # now wait for the process to complete
        out, err = yield from process.communicate()
        return process.returncode, out, err

    _exception = None

    def handleexception(loop, context):
        nonlocal _exception
        if _exception is None:
            _exception = context["exception"]

    # FIXME: probably shouldn't be using the main loop here
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handleexception)
    result = loop.run_until_complete(_runandfilter(loop, cmd, **kwargs))
    if _exception:
        raise _exception
    return result


def haveexecutable(name):
    exitcode = run(['which', name], stdout=False, stderr=False)[0]
    if exitcode == 0:
        return True
    if exitcode == 1:
        return False
    raise SystemError("Unexpected return value from 'which {}'".format(name))


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
        # note that the paths in self.jsondata were already _homepath2real()'d
        # in the class' __init__()
        resolved = _homepath2real(path)
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
        self.jsonpath = join(ROOT, 'repos', info.repoid + '.json')
        super(RepoScriptConfig, self).__init__()

    @staticmethod
    def remove(info):
        assert isinstance(info, RepoInfo)
        os.unlink(join(ROOT, 'repos', info.repoid + '.json'))

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
    tmpdir = join(ROOT, 'tmp')
    os.makedirs(tmpdir, mode=0o700, exist_ok=True)
    tmpname = join(tmpdir, os.path.basename(filepath))
    try:
        if exists(filepath):
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
        prefix = os.path.realpath(join(prefix, parts.pop(0)))
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
        yield join(tmp.name, name)
    finally:
        if tmp and exists(tmp.name):
            tmp.cleanup()


class UpdateStatus(object):
    OK = "ok"
    NEVER = "never"
    RUNNING = "running"
    FAILED = "failed"
    NOCONN = "noconn"
    DIRTY = "dirty"
    PAUSED = "paused"


STATUSCODES = {
    UpdateStatus.OK: 0,
    UpdateStatus.NEVER: 2,
    UpdateStatus.RUNNING: 3,
    UpdateStatus.FAILED: 4,
    UpdateStatus.NOCONN: 5,
    UpdateStatus.DIRTY: 6,
    UpdateStatus.PAUSED: 7,
}


def getstatus():
    """Get the status of the previous 'homely update', or any 'homely update'
    that may be running in another process.
    """
    if exists(RUNFILE):
        mtime = os.stat(RUNFILE).st_mtime
        with open(SECTIONFILE) as f:
            section = f.read().strip()
        # what section?
        return UpdateStatus.RUNNING, mtime, section
    if exists(PAUSEFILE):
        return UpdateStatus.PAUSED, None, None

    mtime = None
    if exists(TIMEFILE):
        mtime = os.stat(TIMEFILE).st_mtime

    if exists(FAILFILE):
        if not mtime:
            mtime = os.stat(FAILFILE).st_mtime
        # TODO: return a different error code when the error was inability to
        # contact one or more remote servers
        with open(FAILFILE) as f:
            content = f.read().strip()
            if content == UpdateStatus.NOCONN:
                return UpdateStatus.NOCONN, mtime, None
            elif content == UpdateStatus.DIRTY:
                return UpdateStatus.DIRTY, mtime, None
        return UpdateStatus.FAILED, mtime, None

    if mtime is None:
        return UpdateStatus.NEVER, None, None

    return UpdateStatus.OK, mtime, None
