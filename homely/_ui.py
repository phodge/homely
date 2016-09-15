import os
import sys
import time
from importlib.machinery import SourceFileLoader
from contextlib import contextmanager

from homely._errors import HelperError
from homely._utils import (
    RepoInfo, RepoListConfig, RepoScriptConfig, tmpdir,
    RUNFILE, FAILFILE, TIMEFILE, SECTIONFILE,
)
from homely._vcs import Repo


_INTERACTIVE = False
_VERBOSE = False
_FRAGILE = False
_ALLOWPULL = True


_OUTSTREAM = sys.stdout
_ERRSTREAM = sys.stderr


def setstreams(outstream, errstream):
    global _OUTSTREAM, _ERRSTREAM
    _OUTSTREAM = outstream
    _ERRSTREAM = errstream


def setinteractive(value):
    global _INTERACTIVE
    assert value in (True, False, "ASSUME")
    _INTERACTIVE = value


def setverbose(value):
    global _VERBOSE
    _VERBOSE = bool(value)


def setfragile(value):
    global _FRAGILE
    _FRAGILE = bool(value)


def setallowpull(value):
    global _ALLOWPULL
    _ALLOWPULL = bool(value)


def note(message):
    sys.stdout.write("INFO: ")
    sys.stdout.write(message)
    sys.stdout.write("\n")
    sys.stdout.flush()


def debug(message):
    if _VERBOSE:
        sys.stdout.write("DEBUG: ")
        sys.stdout.write(message)
        sys.stdout.write("\n")
        sys.stdout.flush()


def heading(message):
    sys.stdout.write(message)
    sys.stdout.write("\n")
    sys.stdout.write("=" * len(message))
    sys.stdout.write("\n")
    sys.stdout.flush()


def warning(message):
    if _FRAGILE:
        raise Exception(message)
    sys.stderr.write("WARNING: ")
    sys.stderr.write(message)
    sys.stderr.write("\n")
    sys.stderr.flush()


def run_update(infos, pullfirst, only=None, cancleanup=None):
    from homely._engine2 import initengine, resetengine, setrepoinfo

    assert cancleanup is not None
    if only is None:
        only = []
    elif len(only):
        assert len(infos) <= 1
    global _CURRENT_REPO
    errors = False

    # create the runfile now
    try:
        with open(RUNFILE, 'x') as f:
            f.write(str(os.getpid()))
    except FileExistsError:
        with open(RUNFILE, 'r') as f:
            pid = f.read().strip()
        warning("Updating is already running (PID={})".format(pid))
        return False

    isfullupdate = False
    if (cancleanup
            and (not len(only))
            and len(infos) == RepoListConfig().repo_count()):
        isfullupdate = True
        # remove the failfile
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
            with entersection(os.path.basename(localrepo.repo_path)):
                heading("Updating from %s [%s]" %
                        (localrepo.repo_path, info.shortid()))
                if pullfirst:
                    if localrepo.isdirty():
                        warning("Can't use %r in %s: uncommitted changes" % (
                            localrepo.pulldesc, localrepo.repo_path))
                    else:
                        note("Running %r in %s" %
                             (localrepo.pulldesc, localrepo.repo_path))
                        localrepo.pullchanges()

                # make sure the HOMELY.py script exists
                pyscript = os.path.join(localrepo.repo_path, 'HOMELY.py')
                if not os.path.exists(pyscript):
                    warning("%s does not exist" % pyscript)
                    errors = True
                    continue

                if len(only):
                    engine.onlysections(only)

                source = SourceFileLoader('__imported_by_homely', pyscript)
                try:
                    source.load_module()
                except HelperError as err:
                    warning(str(err))
                    errors = True

        setrepoinfo(None)

        if isfullupdate and not errors:
            _write(SECTIONFILE, "<cleaning up>")
            engine.cleanup(engine.RAISE)

        resetengine()
        os.unlink(SECTIONFILE)
    except (Exception, KeyboardInterrupt) as err:
        errors = True
        raise
    finally:
        if isfullupdate:
            if errors:
                # touch the FAILFILE if there were errors
                with open(FAILFILE, 'w') as f:
                    pass
            else:
                _write(TIMEFILE, time.strftime("%H:%M"))
        if os.path.exists(RUNFILE):
            os.unlink(RUNFILE)

    return not errors


def isinteractive():
    '''
    Returns True if the script is being run in a context where the user can
    provide input interactively. Otherwise, False is returned.
    '''
    return _INTERACTIVE and sys.__stdin__.isatty() and sys.stderr.isatty()


def allowpull():
    return _ALLOWPULL


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


def yesno(prompt, default, recommended=None):
    assert _INTERACTIVE
    if default is True:
        options = "Y/n"
    elif default is False:
        options = "y/N"
    else:
        options = "y/n"

    rec = ""
    if recommended is not None:
        rec = "[recommended=%s] " % ("Y" if recommended else "N")

    while True:
        input_ = input("%s %s[%s]: " % (prompt, rec, options))
        if input_ == "" and default is not None:
            return default
        if input_.lower() in ("y", "yes"):
            return True
        if input_.lower() in ("n", "no"):
            return False
        # if the user's input is invalid, ask them again
        if input_ == "":
            sys.stderr.write("ERROR: An answer is required\n")
        else:
            sys.stderr.write("ERROR: Invalid answer: %r\n" % (input_, ))


# this needs to be set in order for things to work correctly
_CURRENT_REPO = None


def setcurrentrepo(info):
    assert isinstance(info, RepoInfo)
    global _CURRENT_REPO
    _CURRENT_REPO = info


def yesnooption(name, prompt, default=None):
    '''
    Ask the user for a yes/no answer to question [prompt]. Store the result as
    option [name].

    If [default] is provided, it will be displayed as the recommended answer.
    If the user doesn't provide an answer, then [default] will be used.

    If the user has already answered this question, the previous value
    (retrieved using the [name]) will be used as the default answer.
    '''
    if default is not None:
        assert default in (True, False)

    cfg = RepoScriptConfig(_CURRENT_REPO)

    previous_value = cfg.getquestionanswer(name)
    if previous_value is not None:
        if previous_value not in (True, False):
            # FIXME: issue a warning about the old value of [name] not being
            # compatible
            previous_value = None
        elif _INTERACTIVE == "ASSUME":
            return previous_value

    if not isinteractive():
        # non-interactive - return the previous value
        if previous_value is None:
            # no value has been provided ... we can't proceed
            raise HelperError("Run homely update manually"
                              " to answer the question: '%s'" % prompt)
        return previous_value

    choice = yesno("[%s] %s" % (name, prompt), previous_value, default)
    cfg.setquestionanswer(name, choice)
    cfg.writejson()
    return choice


def _write(path, content):
    with open(path + ".new", 'w') as f:
        f.write(content)
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
