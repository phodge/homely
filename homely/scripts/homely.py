#!/usr/bin/env python3
import os
import sys

from click import echo, group, argument, option

from homely._utils import (
    RepoError, JsonError, RepoListConfig, RepoInfo, saveconfig
)
from homely._ui import run_update
from homely._engine import clone_online_repo


# FILES:
# ~/.homely/repos.json
CMD = os.path.basename(sys.argv[0])


class Fatal(Exception):
    pass


@group()
def homely():
    """
    Single-command dotfile installation.
    """
    pass


@homely.command()
@argument('repo_path')
@option('-v', '--verbose', is_flag=True)
def add(repo_path, verbose):
    '''
    Install a new repo on your system
    '''
    pull_required = True
    if repo_path.startswith('ssh://') or repo_path.startswith('https://'):
        repo_path = clone_online_repo(repo_path)
        pull_required = False
    # add the local repo to our config
    info = RepoInfo(repo_path)
    with saveconfig(RepoListConfig()) as cfg:
        cfg.add_repo(info)
    run_update(info,
               pullfirst=pull_required,
               allowinteractive=True,
               verbose=verbose)


@homely.command()
@argument('repo')
def remove(repo):
    '''
    Remove repo identified by IDENTIFIER. IDENTIFIER can be a path to a repo or
    a commit hash.
    '''
    raise Exception("TODO: remove the repo")  # noqa


@homely.command()
@argument('identifiers', nargs=-1, metavar="REPO")
@option('--nopull', is_flag=True)
@option('--nointeractive', is_flag=True)
@option('-v', '--verbose', is_flag=True)
def update(identifiers, nopull, nointeractive, verbose):
    '''
    Git pull the specified REPOs and then re-run them.

    Each REPO must be a commithash or localpath from
    ~/.homely/repos.json.
    '''
    cfg = RepoListConfig()
    if len(identifiers):
        updatelist = []
        for identifier in identifiers:
            info = cfg.find_repo(identifier)
            if info is None:
                hint = "Try running %s add /path/to/this/repo first" % CMD
                raise Fatal("Unrecognised repo %s (%s)" % (identifier, hint))
            updatelist.append(info)
    else:
        updatelist = list(cfg.find_all())
    for info in updatelist:
        run_update(info,
                   pullfirst=not nopull,
                   allowinteractive=not nointeractive,
                   verbose=verbose)


@homely.command()
@option('--daily', is_flag=True, help="Update interactively daily")
@option('--weekly', is_flag=True, help="Update interactively weekly")
@option('--monthly', is_flag=True, help="Update interactively monthly")
def updatecheck():
    '''
    Interactively update all your repos on a regular basis.
    E.g., add this to your ~/.bashrc:

        homely updatecheck --weekly
    '''
    raise Exception("TODO: check timestamp in ~/.homely/last-check")  # noqa
    raise Exception("TODO: update all repos if necessary")  # noqa
    raise Exception("TODO: put new timestamp in ~/.homely/last-check")  # noqa


@homely.command()
def repotest():
    '''
    Test REPO's HOMELY.py for errors.
    '''
    raise Exception("TODO: implement this")  # noqa


def main():
    try:
        # FIXME: always ensure git is installed first
        homely()
    except (Fatal, RepoError, JsonError) as err:
        echo("ERROR: %s" % err, err=True)
        sys.exit(1)
