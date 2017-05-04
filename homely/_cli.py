import os
import sys
import time

from click import UsageError, argument, echo, group, option, version_option

from homely import version
from homely._errors import (ERR_NO_COMMITS, ERR_NOT_A_REPO, JsonError,
                            NotARepo, RepoHasNoCommitsError)
from homely._ui import (PROMPT_ALWAYS, PROMPT_NEVER, addfromremote, note,
                        run_update, setallowpull, setverbose, setwantprompt,
                        warn)
from homely._utils import (FAILFILE, OUTFILE, PAUSEFILE, STATUSCODES, RepoInfo,
                           RepoListConfig, UpdateStatus, getstatus, mkcfgdir,
                           saveconfig)
from homely._vcs import getrepohandler

CMD = os.path.basename(sys.argv[0])


class Fatal(Exception):
    pass


def _globals(command):
    def proxy(verbose, alwaysprompt, neverprompt, **kwargs):
        # handle these global options
        setverbose(verbose)
        if alwaysprompt:
            if neverprompt:
                raise UsageError("--alwaysprompt and --neverprompt options"
                                 " cannot be used together")
            setwantprompt(PROMPT_ALWAYS)
        elif neverprompt:
            setwantprompt(PROMPT_NEVER)
        # pass all other arguments on to the command
        command(**kwargs)
    proxy.__name__ = command.__name__
    proxy.__doc__ = command.__doc__
    proxy = option('-a', '--alwaysprompt', is_flag=True,
                   help="Always prompt the user to answer questions, even"
                   " named questions that they have answered on previous runs"
                   )(proxy)
    proxy = option('-n', '--neverprompt', is_flag=True,
                   help="Never prompt the user to answer questions. Questions"
                   " will be answered automatically using the user's previous"
                   " answer or the `noprompt` value.")(proxy)
    proxy = option('-v', '--verbose', 'verbose', is_flag=True,
                   help="Produce extra output")(proxy)
    return proxy


version_message = (
    "%(prog)s {}, running on python {}.{}.{}"
    .format(version, *sys.version_info[0:3])
)


@group()
@version_option(message=version_message)
def homely():
    """
    Single-command dotfile installation.
    """


@homely.command()
# FIXME: add the ability to install multiple things at once
@argument('repo_path')
@argument('dest_path', required=False)
@_globals
def add(repo_path, dest_path):
    '''
    Registers a git repository with homely so that it will run its `HOMELY.py`
    script on each invocation of `homely update`. `homely add` also immediately
    executes a `homely update` so that the dotfiles are installed straight
    away. If the git repository is hosted online, a local clone will be created
    first.

    REPO_PATH
        A path to a local git repository, or the URL for a git repository
        hosted online. If REPO_PATH is a URL, then it should be in a format
        accepted by `git clone`. If REPO_PATH is a URL, you may also specify
        DEST_PATH.
    DEST_PATH
        If REPO_PATH is a URL, then the local clone will be created at
        DEST_PATH. If DEST_PATH is omitted then the path to the local clone
        will be automatically derived from REPO_PATH.
    '''
    mkcfgdir()
    try:
        repo = getrepohandler(repo_path)
    except NotARepo as err:
        echo("ERROR: {}: {}".format(ERR_NOT_A_REPO, err.repo_path))
        sys.exit(1)

    # if the repo isn't on disk yet, we'll need to make a local clone of it
    if repo.isremote:
        localrepo, needpull = addfromremote(repo, dest_path)
    elif dest_path:
        raise UsageError("DEST_PATH is only for repos hosted online")
    else:
        try:
            repoid = repo.getrepoid()
        except RepoHasNoCommitsError as err:
            echo("ERROR: {}".format(ERR_NO_COMMITS))
            sys.exit(1)
        localrepo = RepoInfo(repo, repoid, None)
        needpull = False

    # if we don't have a local repo, then there is nothing more to do
    if not localrepo:
        return

    # remember this new local repo
    with saveconfig(RepoListConfig()) as cfg:
        cfg.add_repo(localrepo)
    success = run_update([localrepo], pullfirst=needpull, cancleanup=True)
    if not success:
        sys.exit(1)


@homely.command()
@option('--format', '-f',
        help="Format string for the output, which will be passed through"
        " str.format(). You may use the following named replacements:"
        "\n%(repoid)s"
        "\n%(localpath)s"
        "\n%(canonical)s")
@_globals
def repolist(format):
    cfg = RepoListConfig()
    for info in cfg.find_all():
        vars_ = dict(
            repoid=info.repoid,
            localpath=info.localrepo.repo_path,
            canonical=(info.canonicalrepo.repo_path
                       if info.canonicalrepo else '')
        )
        print(format % vars_)


@homely.command()
@argument('identifier', nargs=-1)
@_globals
def forget(identifier):
    '''
    Tells homely to forget about a dotfiles repository that was previously
    added. You can then run `homely update` to have homely perform automatic
    cleanup of anything that was installed by that dotfiles repo.

    REPO
        This should be the path to a local dotfiles repository that has already
        been registered using `homely add`. You may specify multiple REPOs to
        remove at once.
    '''
    errors = False
    for one in identifier:
        cfg = RepoListConfig()
        info = cfg.find_by_any(one, "ilc")
        if not info:
            warn("No repos matching %r" % one)
            errors = True
            continue

        # update the config ...
        note("Removing record of repo [%s] at %s" % (
            info.shortid(), info.localrepo.repo_path))
        with saveconfig(RepoListConfig()) as cfg:
            cfg.remove_repo(info.repoid)

    # if there were errors, then don't try and do an update
    if errors:
        sys.exit(1)


@homely.command()
@argument('identifiers', nargs=-1, metavar="REPO")
@option('--nopull', is_flag=True,
        help="Do not use `git pull` or other things that require internet"
        " access")
@option('--only', '-o', multiple=True,
        help="Only process the named sections (whole names only)")
@_globals
def update(identifiers, nopull, only):
    '''
    Performs a `git pull` in each of the repositories registered with
    `homely add`, runs all of their HOMELY.py scripts, and then performs
    automatic cleanup as necessary.

    REPO
        This should be the path to a local dotfiles repository that has already
        been registered using `homely add`. If you specify one or more `REPO`s
        then only the HOMELY.py scripts from those repositories will be run,
        and automatic cleanup will not be performed (automatic cleanup is only
        possible when homely has done an update of all repositories in one go).
        If you do not specify a REPO, all repositories' HOMELY.py scripts will
        be run.

    The --nopull and --only options are useful when you are working on your
    HOMELY.py script - the --nopull option stops you from wasting time checking
    the internet for the same updates on every run, and the --only option
    allows you to execute only the section you are working on.
    '''
    mkcfgdir()
    setallowpull(not nopull)

    cfg = RepoListConfig()
    if len(identifiers):
        updatedict = {}
        for identifier in identifiers:
            repo = cfg.find_by_any(identifier, "ilc")
            if repo is None:
                hint = "Try running %s add /path/to/this/repo first" % CMD
                raise Fatal("Unrecognised repo %s (%s)" % (identifier, hint))
            updatedict[repo.repoid] = repo
        updatelist = updatedict.values()
        cleanup = len(updatelist) == cfg.repo_count()
    else:
        updatelist = list(cfg.find_all())
        cleanup = True
    success = run_update(updatelist,
                         pullfirst=not nopull,
                         only=only,
                         cancleanup=cleanup)
    if not success:
        sys.exit(1)


@homely.command()
@option('--pause', is_flag=True,
        help="Pause automatic updates. This can be useful while you are"
        " working on your HOMELY.py script")
@option('--unpause', is_flag=True, help="Un-pause automatic updates")
@option('--outfile', is_flag=True,
        help="Prints the _path_ of the file containing the output of the"
        " previous 'homely update' run that was initiated by autoupdate.")
@option('--daemon', is_flag=True,
        help="Starts a 'homely update' daemon process, as long as it hasn't"
        " been run too recently")
@option('--clear', is_flag=True,
        help="Clear any previous update error so that autoupdate can initiate"
        " updates again.")
@_globals
def autoupdate(**kwargs):
    options = ('pause', 'unpause', 'outfile', 'daemon', 'clear')
    action = None
    for name in options:
        if kwargs[name]:
            if action is not None:
                raise UsageError("--%s and --%s options cannot be combined"
                                 % (action, name))
            action = name

    if action is None:
        raise UsageError("Either %s must be used"
                         % (" or ".join("--{}".format(o) for o in options)))

    mkcfgdir()
    if action == "pause":
        with open(PAUSEFILE, 'w'):
            pass
        return

    if action == "unpause":
        if os.path.exists(PAUSEFILE):
            os.unlink(PAUSEFILE)
        return

    if action == "clear":
        if os.path.exists(FAILFILE):
            os.unlink(FAILFILE)
        return

    if action == "outfile":
        print(OUTFILE)
        return

    # is an update necessary?
    assert action == "daemon"

    # check if we're allowed to start an update
    status, mtime, _ = getstatus()
    if status == UpdateStatus.FAILED:
        print("Can't start daemon - previous update failed")
        sys.exit(1)
    if status == UpdateStatus.PAUSED:
        print("Can't start daemon - updates are paused")
        sys.exit(1)
    if status == UpdateStatus.RUNNING:
        print("Can't start daemon - an update is already running")
        sys.exit(1)

    # abort the update if it hasn't been long enough
    interval = 20 * 60 * 60
    if mtime is not None and (time.time() - mtime) < interval:
        print("Can't start daemon - too soon to start another update")
        sys.exit(1)

    assert status in (UpdateStatus.OK,
                      UpdateStatus.NEVER,
                      UpdateStatus.NOCONN)

    oldcwd = os.getcwd()
    import daemon
    with daemon.DaemonContext(), open(OUTFILE, 'w') as f:
        try:
            from homely._ui import setstreams
            setstreams(f, f)

            # we need to chdir back to the old working directory or  imports
            # will be broken!
            if sys.version_info[0] < 3:
                os.chdir(oldcwd)

            cfg = RepoListConfig()
            run_update(list(cfg.find_all()),
                       pullfirst=True,
                       cancleanup=True)
        except Exception:
            import traceback
            f.write(traceback.format_exc())
            raise


@homely.command()
@_globals
def updatestatus():
    """
    Returns an exit code indicating the state of the current or previous
    'homely update' process. The exit code will be one of the following:
      0  ..  No 'homely update' process is running.
      2  ..  A 'homely update' process has never been run.
      3  ..  A 'homely update' process is currently running.
      4  ..  Updates using 'autoupdate' are currently paused.
      5  ..  The most recent update raised Warnings or failed altogether.
      1  ..  (An unexpected error occurred trying to get the status.)
    """
    status = getstatus()[0]
    sys.exit(STATUSCODES[status])


def main():
    try:
        # FIXME: always ensure git is installed first
        homely()
    except (Fatal, JsonError) as err:
        echo("ERROR: %s" % err, err=True)
        sys.exit(1)
    finally:
        try:
            import asyncio
            asyncio.get_event_loop().close()
        except ImportError:
            pass


if __name__ == '__main__':
    main()
