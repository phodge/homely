import os
import re

import homely._vcs
from homely._errors import ConnectionError, RepoError, RepoHasNoCommitsError
from homely._utils import _expandpath, run
from homely.system import execute


class Repo(homely._vcs.Repo):
    type = homely._vcs.HANDLER_GIT_v1
    pulldesc = 'git pull'

    @classmethod
    def frompath(class_, repo_path):
        if os.path.isdir(repo_path):
            if not os.path.isdir(os.path.join(repo_path, '.git')):
                return
            return class_(_expandpath(repo_path),
                          isremote=False,
                          iscanonical=False,
                          suggestedlocal=None
                          )
        if (repo_path.startswith('ssh://') or
                repo_path.startswith('https://') or
                repo_path.startswith('git@')):
            m = re.match(r'^(https://|git@)github\.com[/:]([^/]+)/([^/]+)',
                         repo_path)
            if not m:
                return
            _, user, name = m.groups()
            if name.endswith('.git'):
                name = name[0:-4]
            canonical = 'https://github.com/%s/%s.git' % (user, name)
            return class_(repo_path,
                          isremote=True,
                          iscanonical=repo_path == canonical,
                          suggestedlocal=name,
                          )

    def pullchanges(self):
        assert not self.isremote
        cmd = ['git', 'pull']
        code, _, err = execute(cmd,
                               cwd=self.repo_path,
                               stderr=True,
                               expectexit=(0, 1))
        if code == 0:
            return

        assert code == 1
        needle = b'fatal: Could not read from remote repository.'
        if needle in err:
            raise ConnectionError()

        raise SystemError("Unexpected output from 'git pull': {}".format(err))

    def clonetopath(self, dest):
        origin = self.repo_path
        execute(['git', 'clone', origin, dest])

    def getrepoid(self):
        assert not self.isremote
        cmd = ['git', 'rev-list', '--max-parents=0', 'HEAD']
        returncode, stdout = run(cmd,
                                 cwd=self.repo_path,
                                 stdout=True,
                                 stderr="STDOUT")[:2]
        if returncode == 0:
            return self._getfirsthash(stdout)
        if returncode != 128:
            raise Exception("Unexpected returncode {} from git rev-list"
                            .format(returncode))

        if b"ambiguous argument 'HEAD'" not in stdout:
            raise Exception("Unexpected exitcode {}".format(returncode))

        # there's no HEAD revision, so we'll do the command again with
        # --all instead
        cmd = ['git', 'rev-list', '--max-parents=0', '--all']
        # use run() instead of execute() so that we don't print script output
        returncode, stdout = run(cmd,
                                 cwd=self.repo_path,
                                 stdout=True,
                                 stderr="STDOUT")[:2]
        if returncode == 0:
            if stdout == b'':
                raise RepoHasNoCommitsError()
            return self._getfirsthash(stdout)
        if returncode != 129:
            raise Exception("Unexpected returncode {} from git rev-list"
                            .format(returncode))
        if b"usage: git rev-list" in stdout:
            raise RepoHasNoCommitsError()

        raise SystemError("Unexpected exitcode {}".format(returncode))

    def _getfirsthash(self, stdout):
        stripped = stdout.rstrip().decode('utf-8')
        if '\n' in stripped:
            raise RepoError("Git repo has multiple initial commits")
        return stripped

    @staticmethod
    def shortid(repoid):
        return repoid[0:8]

    def isdirty(self):
        cmd = ['git', 'status', '--porcelain']
        out = execute(cmd, cwd=self.repo_path, stdout=True)[1]
        for line in out.split(b'\n'):
            if len(line) and not line.startswith(b'?? '):
                return True
        return False
