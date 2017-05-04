import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime

import homely._utils
from homely._errors import ERR_NO_SCRIPT, ConnectionError, InputError
from homely._utils import (FAILFILE, RUNFILE, SECTIONFILE, TIMEFILE, RepoInfo,
                           RepoListConfig, RepoScriptConfig, UpdateStatus,
                           tmpdir)
from homely._vcs import Repo

# try and get a function for quoting shell args
try:
    from shlex import quote as shellquote
except ImportError:
    try:
        from pipes import quote as shellquote
    except ImportError:
        def shellquote(data):
            if data.isalnum():
                return data
            return "'{}'".format(data
                                 .replace('\\', '\\\\')
                                 .replace("'", "\\'"))


_VERBOSE = False
_ALLOWPULL = True
_WANTPROMPT = None
PROMPT_NEVER = "NEVER"
PROMPT_ALWAYS = "ALWAYS"

# cached result of allowinteractive() call
_ALLOW_INTERACTIVE = None


_OUTSTREAM = sys.stdout
_ERRSTREAM = sys.stderr


def setstreams(outstream, errstream):
    global _OUTSTREAM, _ERRSTREAM
    _OUTSTREAM = outstream
    _ERRSTREAM = errstream


def setwantprompt(value):
    assert value in (PROMPT_NEVER, PROMPT_ALWAYS)
    global _WANTPROMPT
    _WANTPROMPT = value


def setverbose(value):
    global _VERBOSE
    _VERBOSE = bool(value)


def setallowpull(value):
    global _ALLOWPULL
    _ALLOWPULL = bool(value)


_INDENT = 0
_NOTECOUNT = {}


class note(object):
    sep = '   '
    dash = '- '

    def __init__(self, message, dash=None):
        super(note, self).__init__()
        self._log(self._getstream(), message, dash=dash)

    def _getstream(self):
        return _OUTSTREAM

    def _unicodelog(self, stream, message, dash=None):
        indent = ('  ' * (_INDENT - 1)) if _INDENT > 0 else ''
        dash = dash or (self.dash if _INDENT > 0 else '')
        stream.write('[{}] {} {}{}{}\n'.format(
            datetime.now().strftime('%c'), self.sep, indent, dash, message))
        stream.flush()
        try:
            _NOTECOUNT[self.__class__.__name__] += 1
        except KeyError:
            _NOTECOUNT[self.__class__.__name__] = 1

    def _asciilog(self, stream, message, dash=None):
        if isinstance(message, unicode):  # noqa: F821
            message = message.encode('utf-8')
        return self._unicodelog(stream, message, dash)

    _log = _asciilog if sys.version_info[0] < 3 else _unicodelog

    def __enter__(self):
        global _INDENT
        _INDENT += 1

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _INDENT
        _INDENT -= 1


class head(note):
    sep = ':::'


class warn(note):
    sep = 'ERR'
    dash = '  '

    def _getstream(self):
        return _ERRSTREAM


class noconn(warn):
    sep = 'N/C'


class dirty(warn):
    sep = '!!!'


def _writepidfile():
    if sys.version_info[0] < 3:
        # Note: py2 doesn't have a way to open a file in 'x' mode so we just
        # have to accept that a race condition is possible, although unlikely.
        if not os.path.exists(RUNFILE):
            with open(RUNFILE, 'w') as f:
                f.write(str(os.getpid()))
            return True
        with open(RUNFILE) as f:
            warn("Update is already running (PID={})".format(f.read().strip()))
        return False

    # python3 allows us to create the pid file without race conditions
    try:
        with open(RUNFILE, 'x') as f:
            f.write(str(os.getpid()))
        return True
    except FileExistsError:  # noqa: F821
        with open(RUNFILE, 'r') as f:
            pid = f.read().strip()
        warn("Update is already running (PID={})".format(pid))
        return False


def run_update(infos, pullfirst, only=None, cancleanup=None):
    from homely._engine2 import initengine, resetengine, setrepoinfo

    assert cancleanup is not None
    if only is None:
        only = []
    elif len(only):
        assert len(infos) <= 1
    global _CURRENT_REPO
    errors = False

    if not _writepidfile():
        return False

    isfullupdate = False
    if (cancleanup and
            (not len(only)) and
            len(infos) == RepoListConfig().repo_count()):
        isfullupdate = True

        # remove the fail file if it is still hanging around
        if os.path.exists(FAILFILE):
            os.unlink(FAILFILE)

    try:
        # write the section file with the current section name
        _write(SECTIONFILE, "<preparing>")

        engine = initengine()

        for info in infos:
            setrepoinfo(info)
            assert isinstance(info, RepoInfo)
            _CURRENT_REPO = info
            localrepo = info.localrepo
            with entersection(os.path.basename(localrepo.repo_path)), \
                    head("Updating from {} [{}]".format(
                        localrepo.repo_path, info.shortid())):
                if pullfirst:
                    with note("Pulling changes for {}".format(
                            localrepo.repo_path)):
                        if localrepo.isdirty():
                            dirty("Aborting - uncommitted changes")
                        else:
                            try:
                                localrepo.pullchanges()
                            except ConnectionError:
                                noconn("Could not connect to remote server")

                # make sure the HOMELY.py script exists
                pyscript = os.path.join(localrepo.repo_path, 'HOMELY.py')
                if not os.path.exists(pyscript):
                    warn("{}: {}".format(ERR_NO_SCRIPT, localrepo.repo_path))
                    continue

                if len(only):
                    engine.onlysections(only)

                try:
                    homely._utils._loadmodule('HOMELY', pyscript)
                except Exception as err:
                    import traceback
                    tb = traceback.format_exc()
                    warn(str(err))
                    for line in tb.split('\n'):
                        warn(line)

                # Remove 'HOMELY' from sys modules so it is ready for the next
                # run. Note that if the call to load_module() failed then the
                # HOMELY module might not be present.
                sys.modules.pop('HOMELY', None)

        setrepoinfo(None)

        if isfullupdate:
            if _NOTECOUNT.get('warn'):
                note("Automatic Cleanup not possible due to previous warnings")
            else:
                _write(SECTIONFILE, "<cleaning up>")
                engine.cleanup(engine.WARN)

        resetengine()
        os.unlink(SECTIONFILE)
    except KeyboardInterrupt:
        errors = True
        raise
    except Exception as err:
        warn(str(err))
        import traceback
        tb = traceback.format_exc()
        for line in tb.split('\n'):
            warn(line)
        errors = True
    finally:
        warncount = _NOTECOUNT.get('warn')
        noconncount = _NOTECOUNT.get('noconn')
        dirtycount = _NOTECOUNT.get('dirty')
        if isfullupdate:
            if errors or warncount:
                # touch the FAILFILE if there were errors or warnings
                with open(FAILFILE, 'w') as f:
                    pass
            elif noconncount:
                with open(FAILFILE, 'w') as f:
                    f.write(UpdateStatus.NOCONN)
            elif dirtycount:
                with open(FAILFILE, 'w') as f:
                    f.write(UpdateStatus.DIRTY)
            _write(TIMEFILE, time.strftime("%H:%M"))
        if os.path.exists(RUNFILE):
            os.unlink(RUNFILE)

    return not (errors or warncount or noconncount or dirtycount)


def allowpull():
    return _ALLOWPULL


def allowinteractive():
    global _ALLOW_INTERACTIVE
    if _ALLOW_INTERACTIVE is None:
        _ALLOW_INTERACTIVE = True
        if _WANTPROMPT == PROMPT_NEVER:
            _ALLOW_INTERACTIVE = False
        elif not (sys.__stdin__.isatty() and sys.stderr.isatty()):
            _ALLOW_INTERACTIVE = False
    return _ALLOW_INTERACTIVE


def addfromremote(repo, dest_path):
    assert isinstance(repo, Repo) and repo.isremote

    rlist = RepoListConfig()

    if repo.iscanonical:
        # abort if we have already added this repo before
        match = rlist.find_by_canonical(repo.repo_path)
        if match:
            note("Repo [%s] from %s has already been added" %
                 (match.shortid(), repo.repo_path))
            return match, True

    # figure out where the temporary clone should be moved to after it is
    # created
    if dest_path is None:
        assert repo.suggestedlocal is not None
        dest_path = os.path.join(os.environ["HOME"], repo.suggestedlocal)

    with tmpdir(os.path.basename(dest_path)) as tmp:
        # clone the repo to a temporary location
        note("HOME: %s" % os.environ["HOME"])
        note("tmp:  %s" % tmp)
        note("Cloning %s to tmp:%s" % (repo.repo_path, tmp))
        repo.clonetopath(tmp)

        # find out the first commit id
        localrepo = repo.frompath(tmp)
        assert isinstance(localrepo, repo.__class__)
        tmprepoid = localrepo.getrepoid()

        # if we recognise the repo, record the canonical path onto
        # the repo info so we don't have to download it again
        match = rlist.find_by_id(tmprepoid)
        if match is not None:
            note("Repo [%s] from has already been added" %
                 match.localrepo.shortid(tmprepoid))
            if repo.iscanonical:
                match.canonicalrepo = repo
                rlist.add_repo(match)
                rlist.writejson()
            return match, True

        if os.path.exists(dest_path):
            destrepo = localrepo.frompath(dest_path)

            if not destrepo:
                # TODO: use a different type of exception here
                raise Exception("DEST_PATH %s already exists" % dest_path)

            # check that the repo there is the right repo
            destid = destrepo.getrepoid()
            if destid != tmprepoid:
                # TODO: this should be a different type of exception
                raise Exception("Repo with id [%s] already exists at %s" %
                                (destrepo.getrepoid(False), dest_path))

            # we can use the repo that already exists at dest_path
            note("Using the existing repo [%s] at %s" %
                 (destrepo.shortid(destid), dest_path))
            return RepoInfo(destrepo, destid), True

        # move our temporary clone into the final destination
        os.rename(tmp, dest_path)

    destrepo = localrepo.frompath(dest_path)
    assert destrepo is not None
    info = RepoInfo(destrepo,
                    destrepo.getrepoid(),
                    repo if repo.iscanonical else None,
                    )
    return info, False


def yesno(name, prompt, default=None, recommended=None, noprompt=None):
    assert default in (None, True, False)
    assert recommended in (None, True, False)
    assert noprompt in (None, True, False)

    # can we look up a previous value?
    previous_value = None
    if name is not None:
        cfg = RepoScriptConfig(_CURRENT_REPO)
        previous_value = cfg.getquestionanswer(name)

    if previous_value is not None:
        if _WANTPROMPT != PROMPT_ALWAYS:
            assert previous_value in (True, False)
            return previous_value
        default = previous_value

    if not allowinteractive():
        if noprompt is not None:
            return noprompt

        raise InputError("Run homely update manually to answer the question"
                         ": {}".format(prompt))

    if default is True:
        options = "Y/n"
    elif default is False:
        options = "y/N"
    else:
        options = "y/n"

    retval = None
    rec = ""
    if recommended is not None:
        rec = "[recommended={}] ".format("Y" if recommended else "N")

    input_ = raw_input if sys.version_info[0] < 3 else input  # noqa: F821

    while True:
        answer = input_("{} {} {} : ".format(prompt, rec, options))
        if answer == "" and default is not None:
            retval = default
            break
        if answer.lower() in ("y", "yes"):
            retval = True
            break
        if answer.lower() in ("n", "no"):
            retval = False
            break
        # if the user's input is invalid, ask them again
        if answer == "":
            sys.stderr.write("ERROR: An answer is required\n")
        else:
            sys.stderr.write("ERROR: Invalid answer: {}\n" % (repr(answer), ))

    if name is not None:
        cfg.setquestionanswer(name, retval)
        cfg.writejson()

    return retval


# this needs to be set in order for things to work correctly
_CURRENT_REPO = None


def setcurrentrepo(info):
    assert isinstance(info, RepoInfo)
    global _CURRENT_REPO
    _CURRENT_REPO = info


def _write(path, content):
    with open(path + ".new", 'w') as f:
        f.write(content)
    if sys.version_info[0] < 3:
        # use the less-reliable os.rename() on python2
        os.rename(path + ".new", path)
    else:
        os.replace(path + ".new", path)


_PREV_SECTION = []
_CURRENT_SECTION = ""


@contextmanager
def entersection(name):
    global _CURRENT_SECTION, _PREV_SECTION
    _PREV_SECTION.append(_CURRENT_SECTION)
    try:
        # update the section name and put it in the file
        _CURRENT_SECTION = _CURRENT_SECTION + name
        _write(SECTIONFILE, _CURRENT_SECTION)
        yield
    finally:
        # restore the previous section name
        _CURRENT_SECTION = _PREV_SECTION.pop()
        _write(SECTIONFILE, _CURRENT_SECTION)
