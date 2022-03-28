import os
import time
from copy import copy

from homely._engine2 import Cleaner, Engine, Helper, getengine, getrepoinfo
from homely._errors import HelperError
from homely._utils import (NoChangesNeeded, _homepath2real, _repopath2real,
                           filereplacer, isnecessarypath)

__all__ = [
    "mkdir",
    "symlink",
    "lineinfile",
    "blockinfile",
    "WHERE_TOP",
    "WHERE_BOT",
    "WHERE_ANY",
    "WHERE_END",
]


WHERE_TOP = "__TOP__"
WHERE_BOT = "__BOT__"
WHERE_ANY = "__ANY__"
WHERE_END = WHERE_BOT  # TODO: remove this deprecated alias


def download(url, dest, expiry=None):
    # possible values of expiry:
    # 0:     always download again
    # -1:    never download again
    # <int>: download again when file is <int> seconds old
    if expiry is None:
        expiry = 60 * 60 * 24 * 14
    getengine().run(Download(url, _homepath2real(dest), expiry))


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
        # allow the symlink to end with '/'
        if linkname.endswith('/'):
            linkname = linkname + os.path.basename(target)
        linkname = _homepath2real(linkname)
    getengine().run(MakeSymlink(target, linkname))


def lineinfile(filename, contents, where=None):
    filename = _homepath2real(filename)
    obj = LineInFile(filename, contents, where)
    getengine().run(obj)


def blockinfile(filename, lines, *args, **kwargs):
    if len(args) < 2:
        # handle the new call signature
        where = args[0] if len(args) else None
        prefix = kwargs.pop('prefix', None)
        suffix = kwargs.pop('suffix', None)
        assert not len(kwargs)
    else:
        # assume the old call signature used by my repos
        # TODO: remove this deprecated alternate call signature
        prefix, suffix = args
        where = kwargs.pop('where', None)
        assert not len(kwargs)
    filename = _homepath2real(filename)
    obj = BlockInFile(filename, lines, where, prefix, suffix)
    getengine().run(obj)


class Download(Helper):
    def __init__(self, url, dest, expiry):
        assert dest.startswith('/')
        assert type(expiry) is int and expiry >= -1
        self._url = url
        self._dest = dest
        self._expiry = expiry

    def getclaims(self):
        return []

    def getcleaner(self):
        return

    def isdone(self):
        if not os.path.exists(self._dest):
            return False

        if self._expiry == -1:
            return True  # file never expires

        if self._expiry == 0:
            return False  # file always expires

        cutoff = time.time() - self._expiry
        mtime = os.stat(self._dest).st_mtime
        return mtime >= cutoff

    @property
    def description(self):
        return "Download %s to %s" % (self._url, self._dest)

    def makechanges(self):
        import requests
        r = requests.get(self._url)
        if r.status_code != 200:
            raise HelperError("Download of %s failed: %s"
                              % (self._url, r.status_code))
        with open(self._dest, 'wb') as f:
            f.write(r.content)

    def affectspath(self, path):
        return path == self._dest

    def pathsownable(self):
        return {self._dest: Engine.TYPE_FILE_ALL}


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
        if self._target == self._linkname:
            raise ValueError("target and linkname must be different paths")

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


class LineInFile(Helper):
    def __init__(self, filename, contents, where=None):
        super(LineInFile, self).__init__()
        self._filename = filename
        self._contents = contents
        if not len(contents):
            raise Exception("LineInFile cannot work with empty contents")
        if "\n" in contents or "\r" in contents:
            raise Exception("LineInFile contents cannot include linebreaks")
        if contents.strip() != contents:
            raise Exception(
                "LineInFile contents cannot start or end with whitespace")
        if where is None:
            where = WHERE_ANY
        self._where = where

    @property
    def description(self):
        pos = ""
        if self._where == WHERE_TOP:
            pos = " (at top)"
        elif self._where == WHERE_END:
            pos = " (at end)"
        return "Add line to %s: %r%s" % (self._filename, self._contents, pos)

    def getcleaner(self):
        return CleanLineInFile(self._filename, self._contents)

    def isdone(self):
        if not os.path.exists(self._filename):
            return False
        foundat = []
        linecount = 0
        with open(self._filename) as f:
            for line in f.readlines():
                linecount += 1
                if line.rstrip('\r\n') == self._contents:
                    foundat.append(linecount)
        # if the line appears multiple times, we count it as NOT done
        if len(foundat) != 1:
            return False
        if self._where == WHERE_TOP:
            return foundat[0] == 1
        if self._where == WHERE_END:
            return foundat[0] == linecount
        return True

    def makechanges(self):
        # the content wasn't found in the file, so we'll have to add it
        with filereplacer(self._filename) as (tmp, origlines, NL):
            seen = False
            # if the new line goes at the top, write it out first
            if self._where == WHERE_TOP:
                tmp.write(self._contents)
                tmp.write(NL)
                seen = True
            # read through the original file and look for a line to replace
            if origlines is not None:
                for line in origlines:
                    if line == self._contents:
                        # skip the line if it's already been seen before, or it
                        # needs to move to the end of the file
                        if seen or self._where == WHERE_END:
                            continue
                        seen = True
                    tmp.write(line)
                    tmp.write(NL)
            if not seen:
                assert self._where in (WHERE_END, WHERE_ANY)
                tmp.write(self._contents)
                tmp.write(NL)

    def pathsownable(self):
        return {self._filename: Engine.TYPE_FILE_PART}

    def affectspath(self, path):
        return path == self._filename

    def getclaims(self):
        return []


class CleanLineInFile(Cleaner):
    def __init__(self, filename, contents):
        self._filename = filename
        self._contents = contents

    @property
    def description(self):
        return "Remove line from %s: %r" % (self._filename, self._contents)

    def asdict(self):
        return dict(filename=self._filename, contents=self._contents)

    @classmethod
    def fromdict(class_, data):
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

    def needsclaims(self):
        return []


class BlockInFile(Helper):
    def __init__(self, filename, lines, where, prefix, suffix):
        if os.path.basename(filename) == '.vimrc' or filename.endswith('.vim'):
            commentstart = '"'
        else:
            commentstart = '#'

        if prefix is None:
            prefix = '{} start of content added by homely'.format(commentstart)
        if suffix is None:
            suffix = '{} end of content added by homely'.format(commentstart)

        # FIXME: make BlockInFile() raise an exception if the same
        # prefix/suffix are used multiple times

        self._filename = filename
        self._lines = lines
        self._prefix = prefix
        self._suffix = suffix
        self._where = WHERE_ANY if where is None else where

    @property
    def description(self):
        pos = {WHERE_TOP: "top of ", WHERE_END: "end of ", WHERE_ANY: ""}
        return "Add %d lines to %s%s: %r...%r" % (
            2 + len(self._lines),
            pos[self._where],
            self._filename,
            self._prefix,
            self._suffix,
        )

    def getcleaner(self):
        return CleanBlockInFile(self._filename,
                                self._prefix,
                                self._suffix,
                                )

    def isdone(self):
        if not os.path.exists(self._filename):
            return False

        # look to see if our contents appear in the file
        with open(self._filename) as f:
            firstline = True
            count = 0
            expect = None
            prev = None
            for line in f:
                stripped = line.rstrip('\r\n')
                if firstline and self._where == WHERE_TOP:
                    if stripped != self._prefix:
                        return False
                if expect is not None:
                    if stripped != expect.pop(0):
                        return False
                    if len(expect):
                        prev = "INNER"
                    else:
                        prev = "SUFFIX"
                        count += 1
                elif stripped == self._prefix:
                    expect = copy(self._lines)
                    expect.extend(self._suffix)
                    prev = "PREFIX"
                else:
                    prev = "OTHER"
        if self._where == WHERE_END and prev != "SUFFIX":
            return False
        return count == 1

    def makechanges(self):
        with filereplacer(self._filename) as (tmp, origlines, NL):
            findsuffix = False
            found = False

            def _writeall():
                tmp.write(self._prefix)
                tmp.write(NL)
                for line in self._lines:
                    tmp.write(line)
                    tmp.write(NL)
                tmp.write(self._suffix)
                tmp.write(NL)

            if self._where == WHERE_TOP:
                _writeall()
                found = True
            if origlines is not None:
                for line in origlines:
                    if findsuffix:
                        # while we're looking for the suffix, discard any other
                        # lines we encounter
                        # encountered into a temporary holding area
                        if line != self._suffix:
                            continue

                        # We've found the suffix! If we're allowed to write the
                        # block out anywhere, and we haven't written it out
                        # yet write it out here, now
                        if self._where == WHERE_ANY and not found:
                            _writeall()
                            found = True
                        findsuffix = False
                        continue

                    if line == self._prefix:
                        findsuffix = True
                        continue

                    tmp.write(line)
                    tmp.write(NL)

            if findsuffix:
                # FIXME: some sort of exception that we can handle nicely
                raise Exception(
                    "Error in %s: Found prefix %r but not suffix %r" % (
                        self._filename,
                        self._prefix,
                        self._suffix,
                    ))

            # if we haven't found the block yet, write it out now
            if not found:
                _writeall()

    def affectspath(self, path):
        return path == self._filename

    def pathsownable(self):
        return {self._filename: Engine.TYPE_FILE_PART}

    def getclaims(self):
        return []


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
        return dict(filename=self._filename,
                    prefix=self._prefix,
                    suffix=self._suffix)

    @classmethod
    def fromdict(class_, data):
        return class_(data["filename"], data["prefix"], data["suffix"])

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

    def needsclaims(self):
        return []
