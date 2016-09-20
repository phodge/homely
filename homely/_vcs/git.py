import re
import os

import homely._vcs
from homely._errors import ConnectionError
from homely._utils import _expandpath
from homely._ui import system


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
        code, _, err = system(cmd,
                              cwd=self.repo_path,
                              stderr=True,
                              expectexit=(0,1))
        if code == 0:
            return

        assert code == 1
        needle = b'fatal: Could not read from remote repository.'
        if needle in err:
            raise ConnectionError()

        raise SystemError("Unexpected output from 'git pull': {}".format(err))

    def clonetopath(self, dest):
        origin = self.repo_path
        system(['git', 'clone', origin, dest])

    def getrepoid(self):
        assert not self.isremote
        cmd = ['git', 'rev-list', '--max-parents=0', 'HEAD']
        stdout = system(cmd, cwd=self.repo_path, stdout=True)[1]
        return stdout.rstrip().decode('utf-8')

    @staticmethod
    def shortid(repoid):
        return repoid[0:8]

    def isdirty(self):
        cmd = ['git', 'status', '--porcelain']
        out = system(cmd, cwd=self.repo_path, stdout=True)[1]
        for line in out.split(b'\n'):
            if len(line) and not line.startswith(b'?? '):
                return True
        return False
