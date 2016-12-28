import os

from homely._engine2 import Engine, Helper, getengine, getrepoinfo
from homely._utils import _homepath2real, _repopath2real

__all__ = ["mkdir", "symlink"]


def mkdir(path):
    path = _homepath2real(path)
    getengine().run(MakeDir(path))


def symlink(target, linkname=None):
    # expand <target> to a path relative to the current repo
    target = _repopath2real(target, getrepoinfo().localrepo)

    # if [linkname] is omited, assume the symlink goes into $HOME/ at the top
    # level
    if linkname is None:
        linkname = os.path.join(os.environ.get('HOME'),
                                os.path.basename(target))
    else:
        linkname = _homepath2real(linkname)
    getengine().run(MakeSymlink(target, linkname))


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


class MakeSymlink(Helper):
    def __init__(self, target, linkname):
        assert target.startswith('/')
        assert linkname.startswith('/')
        self._target = target
        self._linkname = linkname
        assert self._target != self._linkname

    def getclaims(self):
        return []

    def getcleaner(self):
        return

    def isdone(self):
        return (os.path.islink(self._linkname) and
                os.readlink(self._linkname) == self._target)

    @property
    def description(self):
        return "Create symlink %s -> %s" % (self._linkname, self._target)

    def makechanges(self):
        assert not os.path.exists(self._linkname)
        os.symlink(self._target, self._linkname)

    def affectspath(self, path):
        return path == self._linkname

    def pathsownable(self):
        return {self._linkname: Engine.TYPE_LINK}
