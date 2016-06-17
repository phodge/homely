#!/usr/bin/env python3
import os
import subprocess
import sys

from click import echo, group, argument, option

from homely.utils import RepoError, RepoConfig, RepoInfo


# FILES:
# ~/.homely/repos.json
REPO_CONFIG_PATH = os.path.join(os.environ.get('HOME'), '.homely', 'repos.json')


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
    update_repo(info, pull_first=pull_required)


@homely.command()
@argument('identifier')
def remove(identifier):
    '''
    Remove repo identified by IDENTIFIER. IDENTIFIER can be a path to a repo or a commit hash.
    '''
    raise Exception("TODO: remove the repo")  # noqa


def clone_online_repo(repo_path):
    raise Exception("TODO: git clone the repo")  # noqa
    raise Exception("TODO: return the path to the local copy of the repo")  # noqa
    # FIXME: check to see if the repo already exists locally
    # FIXME: suggest a good default location for the local clone of the repo
    return local_path


def update_repo(info, pull_first):
    heading("Updating %s" % info.localpath)
    if pull_first:
        # FIXME: warn if there are oustanding changes in the repo
        # FIXME: allow the user to configure whether they want to use 'git pull' or some other
        # command to update the repo
        echo("%s: Retrieving updates using git pull" % info.localpath)
        cmd = ['git', '-C', path, 'pull']
        subprocess.check_call(cmd)
    else:
        # FIXME: notify the user if there are oustanding changes in the repo
        pass
    assert isinstance(info, RepoInfo)


@homely.command()
@argument('repo_path', required=False)
def update(repo_path):
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
