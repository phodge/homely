import os
import subprocess
import sys
import tempfile

from importlib.machinery import SourceFileLoader

from click import echo, ClickException

from homely._errors import RepoError, HelperError
from homely._utils import RepoInfo, RepoListConfig, RepoScriptConfig, GitHubURL
from homely._engine import initengine, getengine


_ALLOWINTERACTIVE = True
_VERBOSE = False


def verbecho(message):
    # FIXME: handling of verbecho() is a horrible mess
    if _VERBOSE:
        sys.stdout.write("INFO: ")
        sys.stdout.write(message)
        sys.stdout.write("\n")


def heading(message):
    sys.stdout.write(message)
    sys.stdout.write("\n")
    sys.stdout.write("=" * len(message))
    sys.stdout.write("\n")


def warning(message):
    sys.stderr.write("WARNING: ")
    sys.stderr.write(message)
    sys.stderr.write("\n")


def run_update(info, pullfirst, allowinteractive,
               verbose=False, only=None, skip=None):
    global _ALLOWINTERACTIVE, _VERBOSE
    _VERBOSE = verbose
    _ALLOWINTERACTIVE = allowinteractive
    assert isinstance(info, RepoInfo)
    heading("Updating from %s [%s]" % (info.localpath, info.shorthash))
    if pullfirst:
        # FIXME: warn if there are oustanding changes in the repo
        # FIXME: allow the user to configure whether they want to use 'git
        # pull' or some other command to update the repo
        sys.stdout.write("%s: Retrieving updates using git pull\n" %
                         info.localpath)
        cmd = ['git', 'pull']
        subprocess.check_call(cmd, cwd=info.localpath)
    else:
        # FIXME: notify the user if there are oustanding changes in the repo
        pass

    # make sure the HOMELY.py script exists
    pyscript = os.path.join(info.localpath, 'HOMELY.py')
    if not os.path.exists(pyscript):
        raise RepoError("%s does not exist" % pyscript)

    engine = initengine(info)
    source = SourceFileLoader('__imported_by_homely', pyscript)
    try:
        source.load_module()
        if only is not None and len(only):
            engine.onlysections(only)
        if skip is not None and len(skip):
            engine.skipsections(skip)
        engine.execute()
    except HelperError as err:
        sys.stderr.write("ERROR: %s\n" % str(err))
        sys.exit(1)


def isinteractive():
    '''
    Returns True if the script is being run in a context where the user can
    provide input interactively. Otherwise, False is returned.
    '''
    return _ALLOWINTERACTIVE and sys.__stdin__.isatty() and sys.stderr.isatty()


def addfromurl(repo_path, dest_path, verbose, interactive):
    rlist = RepoListConfig()

    # is it a github url?
    ghurl = GitHubURL.loadfromurl(repo_path)
    clone_path = repo_path
    if ghurl:
        # abort if we have already added this repo before
        match = rlist.find_by_ghurl(ghurl)
        if match:
            echo("Repo [%s] from %s has already been added" %
                 (match.shorthash, match.githuburl.ashttps()))
            return

        clone_path = repo_path

    # figure out where the temporary clone should be moved to
    confirm_path = False
    if dest_path is None:
        if ghurl:
            base = ghurl.getname()
        else:
            base = os.path.basename(repo_path.rstrip('/'))
            if base.endswith('.git'):
                base = base[0:-4]
        dest_path = os.path.join(os.environ.get('HOME'), base)
        confirm_path = interactive

    tmpdir = None
    try:
        tmpdir = tempfile.TemporaryDirectory()

        # clone the repo to a temporary location
        verbecho("Cloning %s to %s")
        subprocess.check_call(['git', 'clone', clone_path, tmpdir.name])

        # find out the first commit id
        commithash = RepoInfo.getfirsthash(tmpdir.name)

        # if we recognise the first commit id, record the githuburl onto the
        # repo info so we don't have to download it again
        match = rlist.find_repo(commithash)
        if match is not None:
            echo("Repo [%s] from has already been added" % match.shorthash)
            if ghurl:
                match.githuburl = ghurl
                rlist.add_repo(match)
                rlist.writejson()
            return

        if os.path.exists(dest_path):
            # if the dest path is the same repo, then we just need to do a git
            # pull in that dir
            try:
                desthash = RepoInfo.getfirsthash(dest_path)
                if desthash != commithash:
                    raise Exception("Repo with hash %s already exists" %
                                    desthash)
                # run a git pull in that repo
                echo("Using git pull in %s" % dest_path)
                subprocess.check_call(['git', 'pull'], cwd=dest_path)
            except:
                echo("Can't clone into %s - path already exists" % dest_path,
                     err=True)
                raise
        # ask the user if this path is ok?
        elif confirm_path and not yesno('Clone into %s?' % dest_path,
                                        True, None):
            # FIXME: how would click library like me to exit(1) here?
            sys.exit(1)
        else:
            os.rename(tmpdir.name, dest_path)
    finally:
        if tmpdir and os.path.exists(tmpdir.name):
            tmpdir.cleanup()

    # add the local repo to our config
    return RepoInfo(dest_path, commithash, ghurl)


def addfromlocal(repo_path, verbose, interactive):
    repo_path = repo_path.rstrip('/')
    rlist = RepoListConfig()

    # the repo must exist
    if not os.path.exists(repo_path):
        raise ClickException("Repo %s does not exist" % repo_path)
    if not os.path.exists(os.path.join(repo_path, '.git')):
        raise ClickException("%s is not a git repo" % repo_path)

    # find out the first commit id
    commithash = RepoInfo.getfirsthash(repo_path)

    # if we recognise the first commit id, then we are already done
    match = rlist.find_repo(commithash)
    if match is not None:
        echo("Repo [%s] from %s has already been added" %
             (match.shorthash, repo_path))
        return

    # need to add the local repo to our config
    return RepoInfo(repo_path, commithash)


def yesno(prompt, default, recommended=None):
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

    info = getengine().getrepoinfo()
    cfg = RepoScriptConfig(info)

    previous_value = cfg.getquestionanswer(name)
    if previous_value is not None:
        if previous_value not in (True, False):
            # FIXME: issue a warning about the old value of [name] not being
            # compatible
            previous_value = None

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
