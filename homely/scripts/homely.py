#!/usr/bin/env python3
import os
import subprocess
import sys

from click import echo, group, argument, option

from homely.utils import RepoError, RepoConfig, RepoInfo
from homely.engine import run_update, clone_online_repo


# FILES:
# ~/.homely/repos.json
CMD = os.path.basename(sys.argv[0])


class Fatal(Exception):
    pass


def heading(message):
    echo(message)
    echo("=" * len(message))
    echo("")


@group()
def homely():
    """
    Single-command dotfile installation.
    """
    pass


@homely.command()
@argument('repo_path')
def add(repo_path):
    '''
    Install a new repo on your system
    '''
    pull_required = True
    if repo_path.startswith('ssh://') or repo_path.startswith('https://'):
        repo_path = clone_online_repo(repo_path)
        pull_required = False
    # add the local repo to 
    info = RepoInfo(repo_path)
    cfg = RepoConfig()
    cfg.add_repo(info)
    run_update(info, pull_first=pull_required)


@homely.command()
@argument('repo')
def remove(repo):
    '''
    Remove repo identified by IDENTIFIER. IDENTIFIER can be a path to a repo or a commit hash.
    '''
    raise Exception("TODO: remove the repo")  # noqa


@homely.command()
@argument('identifiers', nargs=-1, metavar="REPO")
def update(identifiers):
    '''
    Git pull the specified REPOs and then re-run them.

    Each REPO must be a commithash or localpath from
    ~/.homely/repos.json.
    '''
    cfg = RepoConfig()
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
    for commithash, localpath in updatelist:
        raise Exception("TODO: git pull and run the homely script")  # noqa


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

def main():
    try:
        # FIXME: always ensure git is installed first
        homely()
    except (Fatal, RepoError) as err:
        echo("ERROR: %s" % err, err=True)
        sys.exit(1)
