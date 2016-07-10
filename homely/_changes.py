import os
from copy import deepcopy
import simplejson

from homely._utils import filereplacer

WHERE_TOP = "TOP"
WHERE_END = "END"
WHERE_ANY = "ANY"


class ChangeManager(object):
    _changelogpath = None

    def __init__(self, changelogpath):
        self._changelogpath = changelogpath
        self._prevchanges = {}
        self._newchanges = {}
        if os.path.exists(changelogpath):
            with open(changelogpath, 'r') as f:
                self._prevchanges = simplejson.loads(f.read())

    def _writechanges(self):
        # merge all changes together
        combined = deepcopy(self._prevchanges)
        for path, changes in self._newchanges.items():
            if path not in combined:
                combined[path] = []
            combined[path].extend(changes)
        dumped = simplejson.dumps(combined)
        with open(self._changelogpath, 'w') as f:
            f.write(dumped)

    def _addchange(self, path, info):
        if path not in self._newchanges:
            self._newchanges[path] = []
        pathchanges = self._newchanges.setdefault(path, [])
        if info not in pathchanges:
            pathchanges.append(info)

    def lineinfile(self, path, contents, where=WHERE_ANY):
        # record the fact that we're putting this line into this file
        # NOTE: using a list instead of tuple because the value will be
        # JSONified
        self._addchange(path, ["lineinfile", contents])
        self._writechanges()

        # FIXME: respect the existing line endings
        NL = "\n"

        # the content wasn't found in the file, so we'll have to add it
        with filereplacer(path) as (tmp, orig):
            seen = False
            # if the new line goes at the top, write it out first
            if where == WHERE_TOP:
                tmp.write(contents)
                tmp.write(NL)
                seen = True
            if orig is not None:
                # read through the original file and look for a line to replace
                for line in orig.readlines():
                    if line.strip() == contents:
                        # skip the line if it's already been seen before, or it
                        # needs to move to the end of the file
                        if seen or where == WHERE_END:
                            continue
                        seen = True
                    tmp.write(line)
            if not seen:
                assert where in (WHERE_END, WHERE_ANY)
                tmp.write(contents)
                tmp.write(NL)

    def blockinfile(self, path, pre, post, lines, where=WHERE_ANY):
        # record the fact that we're putting this block into this file
        # NOTE: using a list instead of tuple because the value will be
        # JSONified
        self._addchange(path, ["blockinfile", pre, post, lines])
        self._writechanges()

        # FIXME: respect the existing line endings
        NL = "\n"

        with filereplacer(path) as (tmp, orig):
            seen = False
            if where == WHERE_TOP:
                tmp.write(pre)
                tmp.write(NL)
                for add in lines:
                    tmp.write(add)
                    tmp.write(NL)
                tmp.write(post)
                tmp.write(NL)
                seen = True
            if orig is not None:
                lookforend = False
                for line in orig.readlines():
                    if lookforend:
                        if line.strip() == post:
                            lookforend = False
                        continue
                    if line.strip() == pre:
                        lookforend = True
                        if seen or where == WHERE_END:
                            continue
                        # OK THIS IS IT PUT IN OUR NEW CONENTT
                        tmp.write(pre)
                        tmp.write(NL)
                        for add in lines:
                            tmp.write(add)
                            tmp.write(NL)
                        tmp.write(post)
                        tmp.write(NL)
                        seen = True
                        continue
                    # just copy the line as-is
                    tmp.write(line)
            if not seen:
                tmp.write(pre)
                tmp.write(NL)
                for add in lines:
                    tmp.write(add)
                    tmp.write(NL)
                tmp.write(post)
                tmp.write(NL)

    def cleanup(self):
        # go through prevchanges and back out any changes that aren't present
        # any more
        for path in self._prevchanges:
            self._cleanuppath(path)

    def _cleanuppath(self, path):
        prevchanges = self._prevchanges[path]
        newchanges = self._newchanges.setdefault(path, [])
        for change in prevchanges:
            if newchanges and self._newchangesupercedes(change, newchanges):
                continue
            self._backout(path, change)
        # blank out the changes for this file and write out the new change
        # history
        self._prevchanges[path] = []
        self._writechanges()

    def _backout(self, path, change):
        if change[0] == "lineinfile":
            if not os.path.exists(path):
                return
            with filereplacer(path) as (tmp, orig):
                for line in orig:
                    if line.strip() == change[1]:
                        continue
                    tmp.write(line)
            return
        if change[0] == "blockinfile":
            if not os.path.exists(path):
                return
            with filereplacer(path) as (tmp, orig):
                pre, post, addlines = change[1:]
                findpost = False
                for line in orig:
                    if findpost:
                        if line.strip() == post:
                            findpost = False
                        continue
                    if line.strip() == pre:
                        findpost = True
                        continue
                    # copy any line not skipped
                    tmp.write(line)
            return
        assert False, "Unexpected change type %r" % (change[0], )

    def _newchangesupercedes(self, change, newchanges):
        if change[0] == "lineinfile":
            for newchange in newchanges:
                if newchange[0] == "lineinfile":
                    # if they are both "lineinfile" changes and they have the
                    # same content, then the new change supercedes the old
                    if newchange[1] == change[1]:
                        return True
                else:
                    assert False, "Unexpected change %r" % (newchange, )

            # none of the new changes superceded the old change
            return False

        if change[0] == "blockinfile":
            # the change can be superceded by another "blockinfile" with the
            # same pre/post
            for newchange in newchanges:
                if newchange[:2] == change[:2]:
                    return True
            # no other types of changes can currently supercede a "blockinfile"
            return False

        assert False, "Unexpected change type %r" % (change[0], )
