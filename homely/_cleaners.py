import os

from homely._engine2 import Cleaner, cleaner
from homely._utils import isnecessarypath, filereplacer, NoChangesNeeded


CLEANLINEINFILE_v1 = "homely:cleanlineinfile"
CLEANBLOCKINFILE_v1 = "homely:cleanblockinfile"


@cleaner
class CleanLineInFile(Cleaner):
    def __init__(self, filename, contents):
        self._filename = filename
        self._contents = contents

    @property
    def description(self):
        return "Remove line from %s: %r" % (self._filename, self._contents)

    def asdict(self):
        return dict(type=CLEANLINEINFILE_v1,
                    filename=self._filename,
                    contents=self._contents,
                    )

    @classmethod
    def fromdict(class_, data):
        if data["type"] == CLEANLINEINFILE_v1:
            return class_(data["filename"], data["contents"])

    def __eq__(self, other):
        return (other._filename == self._filename and
                other._contents == self._contents)

    def isneeded(self):
        if not os.path.exists(self._filename):
            return False
        with open(self._filename) as f:
            for line in f:
                if line.rstrip("\r\n") == self._contents:
                    return True
        return False

    def wantspath(self, path):
        return path == self._filename or isnecessarypath(path, self._filename)

    def makechanges(self):
        # if the file doesn't exist, we don't need to make changes
        assert os.path.exists(self._filename)

        with filereplacer(self._filename) as (tmp, origlines, NL):
            # if the file doesn't exist any more, then no changes are needed
            changed = False
            if origlines is not None:
                for line in origlines:
                    if line == self._contents:
                        changed = True
                    else:
                        tmp.write(line)
                        tmp.write(NL)
            if not changed:
                raise NoChangesNeeded()

        return [self._filename] if changed else []


@cleaner
class CleanBlockInFile(Cleaner):
    def __init__(self, filename, prefix, suffix):
        self._filename = filename
        self._prefix = prefix
        self._suffix = suffix

    @property
    def description(self):
        return "Remove lines from %s: %r...%r" % (
            self._filename,
            self._prefix,
            self._suffix,
        )

    def asdict(self):
        return dict(type=CLEANBLOCKINFILE_v1,
                    filename=self._filename,
                    prefix=self._prefix,
                    suffix=self._suffix,
                    )

    @classmethod
    def fromdict(class_, data):
        if data["type"] == CLEANBLOCKINFILE_v1:
            return class_(data["filename"],
                          data["prefix"],
                          data["suffix"])

    def __eq__(self, other):
        return (other._filename == self._filename and
                other._prefix == self._prefix and
                other._suffix == self._suffix)

    def isneeded(self):
        # the cleaner is needed if both the prefix and the suffix are found in
        # the file, in the correct order
        if not os.path.exists(self._filename):
            return False

        haveprefix = False

        with open(self._filename) as f:
            for line in [l.rstrip("\r\n") for l in f]:
                if line == self._prefix:
                    haveprefix = True
                elif line == self._suffix and haveprefix:
                    return True

        return False

    def wantspath(self, path):
        return path == self._filename or isnecessarypath(path, self._filename)

    def makechanges(self):
        assert os.path.exists(self._filename)

        with filereplacer(self._filename) as (tmp, origlines, NL):
            changed = False
            findsuffix = False
            for line in origlines:
                if findsuffix:
                    if line == self._suffix:
                        findsuffix = False
                        changed = True
                elif line == self._prefix:
                    findsuffix = True
                else:
                    tmp.write(line)
                    tmp.write(NL)
            if findsuffix or not changed:
                # we couldn't find the suffix ... don't change the file
                raise NoChangesNeeded()

        return [self._filename] if changed else []
