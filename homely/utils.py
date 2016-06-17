import os
import subprocess

import simplejson


REPO_CONFIG_PATH = os.path.join(os.environ.get('HOME'),
                                '.homely',
                                'repos.json')


class RepoError(Exception):
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

    def find_repo(self, hash_or_path):
        for repo in self.repos:
            if hash_or_path in (repo["commithash"], repo["localpath"]):
                return repo["commithash"], repo["localpath"]

    def find_all(self):
        for repo in self.repos:
            yield repo["commithash"], repo["localpath"]


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

    @classmethod
    def load_from_identifier(class_, identifier):
        cfg = RepoConfig()

