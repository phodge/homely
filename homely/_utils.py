import contextlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import timedelta
from enum import Enum
from functools import partial
from io import TextIOWrapper
from itertools import chain
from os.path import exists, join
from typing import (IO, Any, Generic, Iterable, Iterator, Literal, Optional,
                    Sequence, TypedDict, TypeVar, Union)

from typing_extensions import NotRequired

from homely._asyncioutils import _runasync
from homely._errors import JsonError
from homely._vcs import Repo, fromdict


def _loadmodule(name: str, file_path: str) -> object:
    spec = importlib.util.spec_from_file_location(name, file_path)
    if spec is None:
        raise ImportError(f"Cannot find module spec for {name} at {file_path}")
    if spec.loader is None:
        raise Exception(f"No loader for module {name} at {file_path}")

    module = importlib.util.module_from_spec(spec)

    # Crucial step: Register the module in sys.modules *before* execution
    # This prevents issues with relative imports within the module
    sys.modules[name] = module

    # Execute the module's code in its own namespace
    try:
        spec.loader.exec_module(module)
    except Exception:
        # If execution fails, remove the module from sys.modules
        del sys.modules[name]
        raise

    return module


# for python3, we open text files with universal newline support
opentext = partial(open, newline="")

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


def mkcfgdir() -> None:
    if not exists(ROOT):
        os.mkdir(ROOT)


def _expandpath(path: str) -> str:
    if path.startswith('~'):
        path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    if not (path.startswith('/') or _urlregex.match(path)):
        path = os.path.realpath(path)
    return path


def _repopath2real(path: str, repo: Repo) -> str:
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


def _homepath2real(path: str) -> str:
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


def run(
    cmd: Sequence[str | os.PathLike],
    stdout: int | bool | IO | None = None,
    stderr: int | bool | Literal["STDOUT"] | TextIOWrapper | None = None,
    **kwargs: Any,
) -> tuple[int, Optional[list[str]], Optional[list[str]]]:
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

        if (stdoutfilter or stderrfilter):
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


def haveexecutable(name: str) -> bool:
    exitcode = run(['which', name], stdout=False, stderr=False)[0]
    if exitcode == 0:
        return True
    if exitcode == 1:
        return False
    raise SystemError("Unexpected return value from 'which {}'".format(name))


T = TypeVar("T")


class JsonConfig(Generic[T]):
    jsonpath: str
    jsondata: T

    def __init__(self) -> None:
        # load up the default json until we know that we can load something
        # from the file
        self.jsondata = self.defaultjson()

        if not os.path.exists(self.jsonpath):
            return
        try:
            with open(self.jsonpath, 'r') as f:
                data = f.read()
                if not len(data):
                    return
                self.jsondata = json.loads(data)
                self.checkjson()
        except json.JSONDecodeError:
            raise JsonError("%s does not contain valid JSON" % self.jsonpath)

    def checkjson(self) -> None:
        """
        Child classes should override this method to check if self.jsondata is
        sane.
        """
        raise Exception("This method needs to be overridden")

    def defaultjson(self) -> T:
        """
        Child classes should override this method to return the default json
        object for when the config file doesn't exist yet.
        """
        raise Exception("This method needs to be overridden")

    def writejson(self) -> None:
        # make dirs needed for config file
        parentdir = os.path.dirname(self.jsonpath)
        if not os.path.exists(parentdir):
            os.makedirs(parentdir, mode=0o755)
        # write the config file now
        dumped = json.dumps(self.jsondata, indent=' ' * 4)
        with open(self.jsonpath, 'w') as f:
            f.write(dumped)


class RepoListEntry(TypedDict):
    repoid: str
    localrepo: str
    localpath: str
    canonicalpath: NotRequired[str]
    canonicalrepo: NotRequired[str]


class RepoListConfig(JsonConfig[list[RepoListEntry]]):
    jsonpath = REPO_CONFIG_PATH

    def defaultjson(self) -> list[RepoListEntry]:
        return []

    def checkjson(self) -> None:
        assert isinstance(self.jsondata, list)
        for row in self.jsondata:
            assert 'repoid' in row
            assert 'localrepo' in row
            assert 'localpath' in row
            if 'canonicalpath' in row:
                assert 'canonicalrepo' in row

    def add_repo(self, info: "RepoInfo") -> None:
        modified = False
        for row in self.jsondata:
            if row["repoid"] == info.repoid:
                row.update(self._infotodict(info))
                modified = True
                break
        if not modified:
            self.jsondata.append(self._infotodict(info))

    @staticmethod
    def _infotodict(info: "RepoInfo") -> RepoListEntry:
        assert info.localrepo is not None  # TODO: can we get rid of this assertion?
        ret: RepoListEntry = {
            "repoid": info.repoid,
            "localpath": info.localrepo.repo_path,
            "localrepo": info.localrepo.asdict(),
        }
        if info.canonicalrepo is not None:
            ret["canonicalpath"] = info.canonicalrepo.repo_path
            ret["canonicalrepo"] = info.canonicalrepo.asdict()
        return ret

    def _infofromdict(self, row: RepoListEntry) -> "RepoInfo":
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

    def remove_repo(self, repoid: str) -> None:
        newdata = []
        for row in self.jsondata:
            if row["repoid"] != repoid:
                newdata.append(row)
        self.jsondata = newdata

    def find_by_id(self, repoid: str) -> Optional["RepoInfo"]:
        """
        Returns the repo with the specified <repoid>
        """
        for row in self.jsondata:
            if repoid == row["repoid"]:
                return self._infofromdict(row)

        return None

    def find_by_localpath(self, path: str) -> Optional["RepoInfo"]:
        """
        Returns the repo with the specified local <path>
        """
        # note that the paths in self.jsondata were already _homepath2real()'d
        # in the class' __init__()
        resolved = _homepath2real(path.rstrip('/'))
        for row in self.jsondata:
            if resolved == os.path.realpath(row["localpath"]):
                return self._infofromdict(row)

        return None

    def find_by_canonical(self, repo_path: str) -> Optional["RepoInfo"]:
        for row in self.jsondata:
            if repo_path == row.get("canonicalpath"):
                return self._infofromdict(row)

        return None

    def find_by_any(self, identifier: str, how: str) -> Optional["RepoInfo"]:
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

        return None

    def find_all(self) -> Iterable["RepoInfo"]:
        for row in self.jsondata:
            yield self._infofromdict(row)

    def repo_count(self) -> int:
        return len(self.jsondata)


class RepoScriptConfigData(TypedDict):
    questions: dict[str, bool]


class RepoScriptConfig(JsonConfig[RepoScriptConfigData]):
    def __init__(self, info: "RepoInfo") -> None:
        self.jsonpath = join(ROOT, 'repos', info.repoid + '.json')
        super(RepoScriptConfig, self).__init__()

    @staticmethod
    def remove(info: "RepoInfo") -> None:
        os.unlink(join(ROOT, 'repos', info.repoid + '.json'))

    def defaultjson(self) -> RepoScriptConfigData:
        return {
            "questions": {},
        }

    def checkjson(self) -> None:
        pass

    def getquestionanswer(self, name: str) -> Optional[bool]:
        return self.jsondata["questions"].get(name, None)

    def setquestionanswer(self, name: str, value: bool) -> None:
        self.jsondata["questions"][name] = value


# FIXME: avoid use of Any for FactConfig generic
class FactConfig(JsonConfig[dict[str, Any]]):
    jsonpath = FACT_CONFIG_PATH

    def checkjson(self) -> None:
        pass

    def defaultjson(self) -> dict[str, Any]:
        return {}


T_JC = TypeVar("T_JC", bound=JsonConfig)


@contextlib.contextmanager
def saveconfig(cfg: T_JC) -> Iterator[T_JC]:
    yield cfg
    cfg.writejson()


class RepoInfo:
    def __init__(
        self,
        localrepo: Optional[Repo],
        repoid: str,
        canonicalrepo: Optional[Repo] = None,
    ):
        if localrepo is not None:
            assert not localrepo.isremote
        if canonicalrepo is not None:
            assert canonicalrepo.isremote
            assert canonicalrepo.iscanonical

        self.localrepo: Optional[Repo] = localrepo
        self.canonicalrepo: Optional[Repo] = canonicalrepo
        self.repoid: str = repoid

    def shortid(self) -> str:
        assert self.localrepo is not None  # FIXME: remove this assertion
        return self.localrepo.shortid(self.repoid)


class NoChangesNeeded(Exception):
    """See filereplacer() for more info"""


@contextlib.contextmanager
def filereplacer(filepath: str) -> Iterator[tuple[TextIOWrapper, Optional[Iterable[str]], str]]:
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
    # create the tmp dir if it doesn't exist yet
    tmpdir = join(ROOT, 'tmp')
    if not os.path.exists(tmpdir):
        os.makedirs(tmpdir, mode=0o700)
    tmpname = join(tmpdir, os.path.basename(filepath))
    try:
        if exists(filepath):
            shutil.copy2(filepath, tmpname)
        with opentext(tmpname, 'w') as tmp:
            if os.path.exists(filepath):
                with opentext(filepath, 'r') as orig:
                    NL = "\n"
                    origlines: Iterable[str] = []
                    firstline = None
                    for firstline in orig:
                        break
                    if firstline is not None:
                        stripped = firstline.rstrip('\r\n')
                        NL = firstline[len(stripped):]
                        assert NL in ("\r", "\n", "\r\n"), "Bad NL %r" % NL
                        origlines = chain(
                            [stripped],
                            (line.rstrip('\r\n') for line in orig),
                        )
                    yield tmp, origlines, NL
            else:
                yield tmp, None, "\n"
    except NoChangesNeeded:
        if os.path.exists(tmpname):
            os.unlink(tmpname)
    except Exception:
        if os.path.exists(tmpname):
            os.unlink(tmpname)
        raise
    if os.path.exists(filepath):
        os.unlink(filepath)
    shutil.move(tmpname, filepath)


def isnecessarypath(parent: str, child: str) -> bool:
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
def tmpdir(name: str) -> Iterator[str]:
    assert '/' not in name, "Invalid name %r" % name
    tmp = None
    try:
        tmp = tempfile.mkdtemp()
        yield join(tmp, name)
    finally:
        if tmp and exists(tmp):
            shutil.rmtree(tmp)


class UpdateStatus(Enum):
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


def getstatus() -> tuple[UpdateStatus, Optional[float], Optional[str]]:
    """Get the status of the previous 'homely update', or any 'homely update'
    that may be running in another process.
    """
    if exists(RUNFILE):
        with open(SECTIONFILE) as f:
            section = f.read().strip()
        # what section?
        return UpdateStatus.RUNNING, os.stat(RUNFILE).st_mtime, section
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
            if content == UpdateStatus.NOCONN.value:
                return UpdateStatus.NOCONN, mtime, None
            elif content == UpdateStatus.DIRTY.value:
                return UpdateStatus.DIRTY, mtime, None
        return UpdateStatus.FAILED, mtime, None

    if mtime is None:
        return UpdateStatus.NEVER, None, None

    return UpdateStatus.OK, mtime, None


def _time_interval_to_delta(input: Union[str, timedelta]) -> timedelta:
    if isinstance(input, timedelta):
        return input

    m = re.match(r'^([\d]+)([dwh])$', input)
    if not m:
        raise ValueError("Invalid time interval {!r}".format(input))

    quantity, type_ = m.groups()
    if type_ == 'd':
        return timedelta(days=int(quantity))
    if type_ == 'w':
        return timedelta(weeks=int(quantity))
    if type_ == 'h':
        return timedelta(hours=int(quantity))

    raise ValueError("Invalid time interval {!r}".format(input))
