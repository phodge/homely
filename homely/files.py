import os

from homely._engine2 import Engine, Helper, getengine
from homely._utils import _homepath2real


__all__ = ["mkdir"]


def mkdir(path):
    path = _homepath2real(path)
    getengine().run(MakeDir(path))


class MakeDir(Helper):
    _path = None

    def __init__(self, path):
        super(MakeDir, self).__init__()
        self._path = path

    @property
    def description(self):
        return "Create dir %s" % self._path

    def getcleaner(self):
        return

    def isdone(self):
        return os.path.exists(self._path) and os.path.isdir(self._path)

    def makechanges(self):
        os.mkdir(self._path)

    def affectspath(self, path):
        return path == self._path

    def pathsownable(self):
        return {self._path: Engine.TYPE_FOLDER_ONLY}

    def getclaims(self):
        return []
