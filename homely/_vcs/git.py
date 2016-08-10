import re
import os
import subprocess

import homely._vcs
from homely._utils import _resolve


class Repo(homely._vcs.Repo):
    type = homely._vcs.HANDLER_GIT_v1
    pulldesc = 'git pull'

    @classmethod
    def frompath(class_, repo_path):
        if os.path.isdir(repo_path):
            if not os.path.isdir(os.path.join(repo_path, '.git')):
                return
            return class_(_resolve(repo_path),
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
        subprocess.check_call(cmd, cwd=self.repo_path)

    def clonetopath(self, dest):
        origin = self.repo_path
        subprocess.check_call(['git', 'clone', origin, dest])

    def getrepoid(self):
        assert not self.isremote
        cmd = ['git', 'rev-list', '--max-parents=0', 'HEAD']
        return (subprocess.check_output(cmd, cwd=self.repo_path)
                .rstrip()
                .decode('utf-8'))

    @staticmethod
    def shortid(repoid):
        return repoid[0:8]

    def isdirty(self):
        cmd = ['git', 'status', '--porcelain']
        out = subprocess.check_output(cmd,
                                      cwd=self.repo_path,
                                      stderr=subprocess.STDOUT)
        for line in out.split(b'\n'):
            if len(line) and not line.startswith(b'?? '):
                return True
        return False
