import os
import shutil

import homely._vcs
from homely._ui import note
from homely._utils import _expandpath

PREFIX = 'homely.test.repo://'
MARKERFILE = 'homely.test.repo'
ORIGINFILE = '.origin'
DIRTYFILE = '.dirty'


class Repo(homely._vcs.Repo):
    type = homely._vcs.HANDLER_TESTHANDLER_v1
    pulldesc = 'fake repo pull'

    @classmethod
    def frompath(class_, repo_path):
        if repo_path.startswith(PREFIX):
            dirpart = repo_path[len(PREFIX):]
            return class_(repo_path,
                          isremote=True,
                          iscanonical=dirpart == os.path.realpath(dirpart),
                          suggestedlocal=None,
                          )

        if not os.path.isdir(repo_path):
            return

        if not os.path.exists(os.path.join(repo_path, MARKERFILE)):
            return

        return class_(_expandpath(repo_path),
                      isremote=False,
                      iscanonical=False,
                      suggestedlocal=None)

    def clonetopath(self, dest_path):
        assert not os.path.exists(dest_path)
        os.mkdir(dest_path)
        with open(os.path.join(dest_path, ORIGINFILE), 'w') as f:
            f.write(self.repo_path)
        origin = self.repo_path
        if origin.startswith(PREFIX):
            origin = origin[len(PREFIX):]
        self._pull(origin, dest_path)

    def _pull(self, origin, local):
        # delete every local file except the special ones
        for thing in os.listdir(local):
            if thing not in (ORIGINFILE, MARKERFILE, DIRTYFILE):
                destroyme = os.path.join(local, thing)
                if os.path.isdir(destroyme):
                    note('rmtree %s' % destroyme)
                    shutil.rmtree(destroyme)
                else:
                    note('rm -f %s' % destroyme)
                    os.unlink(destroyme)

        # now copy stuff across
        for thing in os.listdir(origin):
            if thing in (ORIGINFILE, DIRTYFILE):
                continue
            src = os.path.join(origin, thing)
            dst = os.path.join(local, thing)
            if os.path.isdir(src):
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    def pullchanges(self):
        assert not self.isdirty()
        with open(os.path.join(self.repo_path, ORIGINFILE), 'r') as f:
            origin = f.read().strip()
            if origin.startswith(PREFIX):
                origin = origin[len(PREFIX):]
        self._pull(origin, self.repo_path)

    def getrepoid(self):
        assert not self.isremote
        with open(os.path.join(self.repo_path, MARKERFILE), 'r') as f:
            return f.read().strip()

    @staticmethod
    def shortid(repoid):
        return repoid[0:5]

    def isdirty(self):
        assert not self.isremote
        return os.path.exists(os.path.join(self.repo_path, DIRTYFILE))
