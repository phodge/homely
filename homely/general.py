import os

from homely.engine import add
from homely.utils import filereplacer


def lineinfile(filename, contents, prefix=None, regex=None):
    filename = os.path.expanduser(filename)
    obj = LineInFile(filename=filename, contents=contents)
    if prefix is not None:
        obj.findprefix(prefix)
    elif regex is not None:
        obj.findregex(regex)
    add(obj)


class UpdateHelper(object):
    _kwargs = None
    uniqueid = None

    def __init__(self, **kwargs):
        self._kwargs = kwargs
        items = [self.__class__.__name__]
        for key in sorted(self._kwargs):
            items.extend([key, self._kwargs[key]])
        self.uniqueid = repr(items)

    def asdict(self):
        return {"class": self.__class__.__name__, "kwargs": self._kwargs}


class LineInFile(UpdateHelper):
    _filename = None
    _contents  = None
    _findprefix = None
    _findregex = None

    def __init__(self, **kwargs):
        super(LineInFile, self).__init__(**kwargs)
        self._filename = kwargs["filename"]
        self._contents  = kwargs["contents"]

    def findprefix(self, prefix):
        self._findprefix = prefix

    def findregex(self, regex):
        self._findregex = regex

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
