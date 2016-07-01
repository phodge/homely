import os
import re
import contextlib

from homely._errors import HelperError
from homely._engine import getengine
from homely._utils import filereplacer
from homely._ui import warning


def add(updatehelper):
    getengine().add(updatehelper)


@contextlib.contextmanager
def section(name):
    if re.match('[^A-Za-z0-9_:\-\[\]<>]', name):
        raise HelperError("%r is not a valid section name" % name)

    getengine().pushsection(name)
    yield
    getengine().popsection(name)


def mkdir(path):
    path = os.path.expanduser(path)
    getengine().add(MakeDir(path=path))


def lineinfile(filename, contents, prefix=None, regex=None):
    filename = os.path.expanduser(filename)
    obj = LineInFile(filename=filename, contents=contents)
    if prefix is not None:
        obj.findprefix(prefix)
    elif regex is not None:
        obj.findregex(regex)
    getengine().add(obj)


def symlink(source, dest=None):
    # if [source] doesn't start with '/', assume it is relative to the repo
    if not source.startswith('/'):
        info = getengine().getrepoinfo()
        source = os.path.join(info.localpath, source)
    # if [dest] is omited, assume the symlink goes into $HOME/ at the top level
    if dest is None:
        dest = os.path.join(os.environ.get('HOME'), os.path.basename(source))
    helper = MakeSymlink(source, dest)
    getengine().add(helper)


class UpdateHelper(object):
    _section = None

    @property
    def identifiers(self):
        raise NotImplementedError(
            "%s needs to implement @property identifiers()" %
            self.__class__.__name__)

    @classmethod
    def fromidentifiers(class_, identifiers):
        prototype = "@classmethod fromidentifiers(class_, identifiers)"
        raise NotImplementedError("%s needs to implement %s" %
                                  (class_.__name__, prototype))

    @property
    def uniqueid(self):
        identifiers = self.identifiers
        items = [self.__class__.__name__]
        for key in sorted(identifiers):
            items.extend([key, identifiers[key]])
        return repr(items)

    def setsection(self, name):
        self._section = name

    def getsection(self):
        return self._section

    def iscleanable(self):
        raise NotImplementedError("%s needs to implement iscleanable()" %
                                  (self.__class__.__name__))

    def isdone(self):
        raise NotImplementedError("%s needs to implement isdone()" %
                                  (self.__class__.__name__))

    def makechanges(self, prevchanges):
        prototype = "makechanges(self, prevchanges)"
        raise NotImplementedError("%s needs to implement %s" %
                                  (self.__class__.__name__, prototype))

    def undochanges(self, prevchanges):
        prototype = "undochanges(self, prevchanges)"
        raise NotImplementedError("%s needs to implement %s" %
                                  (self.__class__.__name__, prototype))


class MakeDir(UpdateHelper):
    _path = None

    def __init__(self, path):
        self._path = path

    @property
    def identifiers(self):
        return dict(path=self._path)

    @classmethod
    def fromidentifiers(class_, identifiers):
        return class_(identifiers["path"])

    def iscleanable(self):
        return os.path.isdir(self._path)

    def isdone(self):
        return os.path.isdir(self._path)

    def descchanges(self):
        return "Creating directory %s" % self._path

    def makechanges(self, prevchanges):
        if os.path.islink(self._path):
            raise HelperError("%s is already a symlink" % self._path)

        changes = {
            "dirs_created": prevchanges.get("dirs_created", []),
        }

        check = []
        path = self._path
        prev = None
        while path != prev:
            prev = path
            check.insert(0, path)
            path = os.path.dirname(path)
        for path in check:
            if os.path.isdir(path):
                continue
            if os.path.exists(self._path):
                raise HelperError("%s already exists" % self._path)
            changes["dirs_created"].append(path)
            os.makedirs(path)

        return changes

    def undochanges(self, prevchanges):
        if self._path in prevchanges["dirs_created"]:
            # ensure the folder is empty before deleting it
            if len(os.listdir(self._path)):
                warning("Refusing to clean up non-empty folder %s" %
                        self._path)
            else:
                os.rmdir(self._path)


class MakeSymlink(UpdateHelper):
    def __init__(self, source, dest):
        self._dest = dest
        self._source = source

    @property
    def identifiers(self):
        return dict(source=self._source, dest=self._dest)

    @classmethod
    def fromidentifiers(class_, identifiers):
        return class_(identifiers['source'], identifiers["dest"])

    def iscleanable(self):
        return os.path.islink(self._dest)

    def isdone(self):
        return (os.path.islink(self._dest) and
                os.readlink(self._dest) == self._source)

    def descchanges(self):
        return "Creating symlink %s -> %s" % (self._dest, self._source)

    def makechanges(self, prevchanges):
        if os.path.islink(self._dest):
            current = os.readlink(self._dest)
            if current == self._source:
                return prevchanges
            raise HelperError("%s is already a symlink to %s" %
                              (self._dest, current))

        if os.path.exists(self._dest):
            raise HelperError("Can't create symlink %s: a file already exists"
                              " at that path" % (self._dest, current))

        changes = {
            "links_created": prevchanges.get("links_created", []),
        }
        os.symlink(self._source, self._dest)
        changes["links_created"].append([self._source, self._dest])
        return changes

    def undochanges(self, prevchanges):
        if not os.path.islink(self._dest):
            return
        if os.readlink(self._dest) == self._source:
            os.unlink(self._dest)
        else:
            warning("Refusing to clean up symlink %s which now points to"
                    " %s" % (self._dest, os.readlink(self._dest)))


class LineInFile(UpdateHelper):
    _filename = None
    _contents = None
    _findprefix = None
    _findregex = None

    def __init__(self, filename, contents):
        super(LineInFile, self).__init__()
        self._filename = filename
        self._contents = contents

    def findprefix(self, prefix):
        self._findprefix = prefix

    def findregex(self, regex):
        self._findregex = regex

    @property
    def identifiers(self):
        return dict(filename=self._filename,
                    contents=self._contents)

    @classmethod
    def fromidentifiers(class_, identifiers):
        return class_(identifiers["filename"], identifiers["contents"])

    def isdone(self):
        try:
            with open(self._filename) as f:
                for line in f.readlines():
                    if line.rstrip() == self._contents:
                        return True
        except FileNotFoundError:
            pass
        return False

    def descchanges(self):
        return "Adding line to %s: %s" % (self._filename, self._contents)

    def makechanges(self, prevchanges):
        changes = {
            "old_line": None,
        }

        if self._findprefix:
            def matchline(line):
                return line.startswith(self._findprefix)
        elif self._findregex:
            # FIXME: implement regex matching
            raise Exception("FIXME: implement regex")  # noqa
        else:
            def matchline(line):
                return line.rstrip() == self._contents

        with filereplacer(self._filename) as (tmp, orig):
            modified = False
            if orig is not None:
                # read through the original file and look for a line to replace
                for line in orig.readlines():
                    if not modified and matchline(line):
                        modified = True
                        tmp.write(self._contents)
                        # FIXME: respect the existing lines' line endings!
                        tmp.write("\n")
                        if "old_line" not in changes:
                            changes["old_line"] = line.rstrip()
                    else:
                        tmp.write(line)
            # if we didn't write out the new line by replacing parts of the
            # original, then we'll just have to pop the new line on the end
            if not modified:
                tmp.write(self._contents)
                # FIXME: respect the existing lines' line endings!
                tmp.write("\n")
                changes["old_line"] = None

        return changes
