import io
import os
from contextlib import contextmanager
from importlib.machinery import SourceFileLoader

from homely._engine2 import Engine, Helper, getengine, getrepoinfo
from homely._ui import entersection, warn
# allow importing from outside
from homely._utils import haveexecutable  # noqa
from homely._utils import _homepath2real, _repopath2real
# TODO: remove these deprecated aliases which I'm still using in my homely
# repos. Note that the cleaners will need some sort of special handling in
# cleanerfromdict() if ever we want to remove these imports
from homely.files import (WHERE_ANY, WHERE_BOT, WHERE_END, WHERE_TOP,  # noqa
                          CleanBlockInFile, CleanLineInFile, blockinfile,
                          download, lineinfile, mkdir, symlink)


def run(updatehelper):
    getengine().run(updatehelper)


_include_num = 0


def include(pyscript):
    path = _repopath2real(pyscript, getrepoinfo().localrepo)
    if not os.path.exists(path):
        warn("{} not found at {}".format(pyscript, path))
        return

    global _include_num
    _include_num += 1

    source = SourceFileLoader('__imported_by_homely_{}'.format(_include_num),
                              path)
    try:
        with entersection("/" + pyscript):
            source.load_module()
    except Exception as err:
        warn("Error while including {}: {}".format(pyscript, str(err)))


def section(func):
    name = func.__name__
    engine = getengine()
    try:
        with entersection(":" + name + "()"):
            if engine.pushsection(name):
                func()
    finally:
        engine.popsection(name)


@contextmanager
def writefile(filename):
    stream = None
    try:
        stream = io.StringIO('foo')
        yield stream
        stream.seek(0)
        getengine().run(WriteFile(_homepath2real(filename), stream.read()))
    finally:
        if stream:
            stream.close()


class WriteFile(Helper):
    def __init__(self, filename, contents, canoverwrite=False):
        self._filename = filename
        self._contents = contents
        self._canoverwrite = canoverwrite

    @property
    def description(self):
        return "Write file %s" % self._filename

    def getcleaner(self):
        # no cleaner needed
        pass

    def isdone(self):
        if os.path.islink(self._filename):
            return False
        try:
            with open(self._filename, 'r') as f:
                if f.read() == self._contents:
                    return True
        except FileNotFoundError:
            pass
        return False

    def makechanges(self):
        assert not os.path.islink(self._filename)
        with open(self._filename, 'w') as f:
            f.write(self._contents)

    def pathsownable(self):
        return {self._filename: Engine.TYPE_FILE_ALL}

    def affectspath(self, path):
        return path == self._filename

    def getclaims(self):
        return []
