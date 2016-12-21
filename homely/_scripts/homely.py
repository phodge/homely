import os
import sys
import time

from click import (ClickException, UsageError, argument, echo, group, option,
                   version_option)

from homely import version
from homely._errors import JsonError, RepoError
from homely._ui import (PROMPT_ALWAYS, PROMPT_NEVER, addfromremote,
                        allowinteractive, note, run_update, setallowpull,
                        setverbose, setwantprompt, warn, yesno)
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
                   help="Product extra output")(proxy)
    return proxy


@group()
@version_option(version, message="%(prog)s %(version)s")
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
    Install a new repo on your system
    '''
    mkcfgdir()
    repo = getrepohandler(repo_path)
    if not repo:
        raise ClickException("No handler for repo at %s" % repo_path)

    # if the repo isn't on disk yet, we'll need to make a local clone of it
    if repo.isremote:
        localrepo, needpull = addfromremote(repo, dest_path)
    elif dest_path:
        raise UsageError("DEST_PATH is only for repos hosted online")
    else:
        needpull = False
        localrepo = RepoInfo(
            repo,
            repo.getrepoid(),
            None,
        )

    # if we don't have a local repo, then there is nothing more to do
    if not localrepo:
        return

    # remember this new local repo
    with saveconfig(RepoListConfig()) as cfg:
        cfg.add_repo(localrepo)
    success = run_update([localrepo],
                         pullfirst=needpull,
                         cancleanup=True)
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
@option('--force', '-f', is_flag=True,
        help="Do not ask the user for confirmation before removing a repo that"
        " still exists on disk. You must use --force if you have also used"
        " --neverprompt.")
@option('--update', '-u', is_flag=True,
        help="Perform update/cleanup of all repos after removal.")
@_globals
def remove(identifier, force, update):
    '''
    Remove repo identified by IDENTIFIER. IDENTIFIER can be a path to a repo or
    a commit hash or a canonical url.
    '''
    errors = False
    removed = False
    for one in identifier:
        cfg = RepoListConfig()
        info = cfg.find_by_any(one, "ilc")
        if not info:
            warn("No repos matching %r" % one)
            errors = True
            continue

        # if the local repo still exists, then we need to prompt if the user
        # hasn't used force mode
        if os.path.isdir(info.localrepo.repo_path) and not force:
            if not allowinteractive():
                warn("Use --force to remove a repo that still exists on disk")
                errors = True
                continue

            prompt = "Are you sure you want to remove repo [%s] %s?" % (
                info.localrepo.shortid(info.repoid), info.localrepo.repo_path)
            if not yesno(None, prompt, False):
                continue

        # update the config ...
        note("Removing record of repo [%s] at %s" % (
            info.shortid(), info.localrepo.repo_path))
        with saveconfig(RepoListConfig()) as cfg:
            cfg.remove_repo(info.repoid)
        removed = True

    # if there were errors, then don't try and do an update
    if errors:
        sys.exit(1)

    if not removed:
        return

    # ask the user if they would like to update everything now?
    if (not update) and allowinteractive():
        prompt = ("Files created by old repos will not be removed until you"
                  " perform an update of all other repos. Would you like to "
                  " do this now?")
        update = yesno(None, prompt, False)

    if update:
        # run an update with all remaining repos
        all_repos = cfg.find_all()
        success = run_update(list(all_repos), pullfirst=True, cancleanup=True)
        if not success:
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
    Git pull the specified REPOs and then re-run them.

    Each REPO must be a repoid or localpath from
    ~/.homely/repos.json.
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
    import daemon
    with daemon.DaemonContext(), open(OUTFILE, 'w') as f:
        try:
            from homely._ui import setstreams
            setstreams(f, f)
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
    except (Fatal, RepoError, JsonError) as err:
        echo("ERROR: %s" % err, err=True)
        sys.exit(1)
    finally:
        try:
            import asyncio
            asyncio.get_event_loop().close()
        except ImportError:
            pass
