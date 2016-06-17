#!/usr/bin/env python3
# FIXME: use nice try/except to catch any import errors and provide a nice warning about modules
# that are missing
import os
import subprocess
import sys
import contextlib


# FILES:
# ~/.terraform/repos.json
REPO_CONFIG_PATH = os.path.join(os.environ.get('HOME'), '.terraform', 'repos.json')


_import_errors = []

@contextlib.contextmanager
def importcatch():
    try:
        yield
    except ImportError as err:
        _import_errors.append(err.name)

with importcatch(): import simplejson
with importcatch(): from click import echo, group, argument, option


class Fatal(Exception):
    def __init__(self, message, *args, **kwargs):
        self.message = message
        super(Fatal, self).__init__(*args, **kwargs)


class RepoError(Fatal):
    pass


class RepoConfig(object):
    def __init__(self):
        # load existing cfg file
        self.repos = []
        try:
            with open(REPO_CONFIG_PATH, 'r') as f:
                obj = simplejson.loads(f.read())
                # FIXME: sanity check on the decoded object
                self.repos = obj
        except FileNotFoundError as err:
            pass

    def add_repo(self, info):
        assert isinstance(info, RepoInfo)
        commithash = info.commithash
        modified = False
        for repo in self.repos:
            if repo["commithash"] == commithash:
                # change the local path in the config
                repo["localpath"] = info.localpath
                modified = True
                break
        if not modified:
            self.repos.append({"commithash": info.commithash, "localpath": info.localpath})
        # make dirs needed for repo config
        makeit = os.path.dirname(REPO_CONFIG_PATH)
        os.makedirs(makeit, mode=0o755, exist_ok=True)
        with open(REPO_CONFIG_PATH, 'w') as f:
            f.write(simplejson.dumps(self.repos, indent=' ' * 4))


class RepoInfo(object):
    localpath = None
    commithash = None

    def __init__(self, path):
        # make sure the path is valid
        if not os.path.exists(path):
            raise RepoError("%s does not exist" % path)
        if not os.path.exists(os.path.join(path, '.git')):
            raise RepoError("%s is not a valid git repo" % path)
        self.localpath = path
        # ask git for the commit hash
        cmd = ['git', '-C', path]
        cmd.extend(['log', '--pretty=%H', '-1'])
        self.commithash = subprocess.check_output(cmd).rstrip().decode('utf-8')
        

def heading(message):
    echo(message)
    echo("=" * len(message))
    echo("")


@group()
def tf():
    """
    Single-command dotfile installation.
    """
    pass


@tf.command()
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


@tf.command()
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


@tf.command()
@argument('repo_path', required=False)
def update(repo_path):
    raise Exception("TODO: git pull and run the terraform script")  # noqa


@tf.command()
@option('--daily', is_flag=True, help="Update interactively daily")
@option('--weekly', is_flag=True, help="Update interactively weekly")
@option('--monthly', is_flag=True, help="Update interactively monthly")
def updatecheck():
    '''
    Interactively update all your repos on a regular basis.
    E.g., add this to your ~/.bashrc:

        terraform updatecheck --weekly
    '''
    raise Exception("TODO: check timestamp in ~/.terraform/last-check")  # noqa
    raise Exception("TODO: update all repos if necessary")  # noqa
    raise Exception("TODO: put new timestamp in ~/.terraform/last-check")  # noqa

def main():
    try:
        if len(_import_errors):
            raise Fatal("Missing required modules: %s" % ",".join(_import_errors))
        # FIXME: always ensure git is installed first
        tf()
    except Fatal as err:
        echo("ERROR: %s" % err.message, err=True)
        sys.exit(1)
