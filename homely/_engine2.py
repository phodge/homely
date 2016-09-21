import os
import simplejson

from homely._errors import CleanupConflict, CleanupObstruction, HelperError
from homely._utils import (
    isnecessarypath,
    ENGINE2_CONFIG_PATH,
    RepoInfo,
    FactConfig,
)
from homely._ui import note, warn


_ENGINE = None
_REPO = None


def initengine():
    global _ENGINE
    _ENGINE = Engine(ENGINE2_CONFIG_PATH)
    return _ENGINE


def resetengine():
    global _ENGINE
    _ENGINE = None


def getengine():
    assert _ENGINE is not None
    return _ENGINE


def setrepoinfo(info):
    assert info is None or isinstance(info, RepoInfo)
    global _REPO
    _REPO = info


def getrepoinfo():
    return _REPO


def _exists(path):
    return os.path.exists(path) or os.path.islink(path)


class _AccessibleFacts(object):
    _facts = None

    def _setfact(self, name, value):
        if self._facts is None:
            self._facts = FactConfig()
        self._facts.jsondata[name] = value
        self._facts.writejson()

    def _clearfact(self, name):
        if self._facts is None:
            self._facts = FactConfig()
        self._facts.jsondata.pop(name, None)
        self._facts.writejson()

    def _getfact(self, name, *args):
        if self._facts is None:
            self._facts = FactConfig()
        if len(args):
            return self._facts.jsondata.get(name, *args)
        return self._facts.jsondata[name]


class Helper(_AccessibleFacts):
    _facts = None

    def getcleaner(self):
        raise NotImplementedError("%s needs to implement .getcleaner()" %
                                  self.__class__.__name__)

    def getclaims(self):
        raise NotImplementedError("%s needs to implement .getclaims() -> []" %
                                  self.__class__.__name__)

    def isdone(self):
        raise NotImplementedError("%s needs to implement .isdone()" %
                                  self.__class__.__name__)

    def makechanges(self):
        raise NotImplementedError("%s needs to implement .makechanges()" %
                                  self.__class__.__name__)

    @property
    def description(self):
        raise NotImplementedError("%s needs to define @property .description" %
                                  self.__class__.__name__)

    def pathsownable(self):
        '''
        Return a dict of {PATH: TYPE} where TYPE is one of:
        - Engine.TYPE_FILE_PART
        - Engine.TYPE_FILE_ALL
        - Engine.TYPE_FOLDER_ONLY
        - Engine.TYPE_FOLDER_ALL
        - Engine.TYPE_LINK
        '''
        raise NotImplementedError("%s needs to implement .pathsownable()" %
                                  self.__class__.__name__)

    def affectspath(self, path):
        raise NotImplementedError("%s needs to implement .affectspath(path)" %
                                  self.__class__.__name__)


def cleanerfromdict(data):
    # import the module
    from importlib import import_module
    # FIXME: handle an ImportError here in case the module disappears
    module = import_module(data["module"])

    # get the class from the module
    # FIXME: also need to handle this nicely
    class_ = getattr(module, data["class"])

    # now load up the cleaner
    # FIXME: handle exceptions when the cleaner can't be loaded nicely
    return class_.fromdict(data["params"])


class Cleaner(_AccessibleFacts):
    def fulldict(self):
        return {
            "module": self.__class__.__module__,
            "class": self.__class__.__name__,
            "params": self.asdict(),
        }

    def asdict(self):
        raise NotImplementedError(
            "%s needs to define .asdict() and "
            "@classmethod .fromdict(class_, data)" %
            self.__class__.__name__)

    @classmethod
    def fromdict(class_, data):
        raise NotImplementedError(
            "%s needs to define .asdict() and "
            "@classmethod .fromdict(class_, data)" %
            class_.__name__)

    @property
    def description(self):
        raise NotImplementedError("%s needs to define @property .description" %
                                  self.__class__.__name__)

    def needsclaims(self):
        raise NotImplementedError(
            "%s needs to implement .needsclaims() -> []" %
            self.__class__.__name__)

    def wantspath(self, path):
        raise NotImplementedError("%s needs to implement .wantspath()" %
                                  self.__class__.__name__)

    def issame(self, other):
        return self.__class__ == other.__class__ and self.__eq__(other)

    def __eq__(self, other):
        raise NotImplementedError("%s needs to implement .__eq__(other)" %
                                  self.__class__.__name__)

    def __ne__(self, other):
        return not self.__eq__(other)

    def makechanges(self):
        raise NotImplementedError("%s needs to implement .makechanges()" %
                                  self.__class__.__name__)


class Engine(object):
    # possible actions to take when a conflict occurs between cleaners
    RAISE = "__raise__"
    WARN = "__warn__"
    ASK = "__ask__"
    POSTPONE = "__postpone__"

    TYPE_FILE_ALL = "whole_file"
    TYPE_FILE_PART = "file"
    TYPE_FOLDER_ALL = "dir_and_children"
    TYPE_FOLDER_ONLY = "directory"
    TYPE_LINK = "symlink"

    def __init__(self, cfgpath):
        super(Engine, self).__init__()
        self._cfgpath = cfgpath
        self._old_cleaners = []
        self._new_cleaners = []
        self._helpers = []
        self._old_paths_owned = {}
        self._new_paths_owned = {}
        self._postponed = set()
        # keep track of which things we created ourselves
        self._created = set()
        self._only = set()
        self._section = None
        # another way of keeping track of things we've claimed
        self._claims = set()

        try:
            with open(cfgpath, 'r') as f:
                raw = f.read()
                data = simplejson.loads(raw)
                if not isinstance(data, dict):
                    raise Exception("Invalid json in %s" % cfgpath)
                for item in data.get('cleaners', []):
                    cleaner = cleanerfromdict(item)
                    if cleaner is None:
                        warn("No cleaner for %s" % repr(item))
                    else:
                        self._old_cleaners.append(cleaner)
                self._old_paths_owned = data.get('paths_owned', {})
                for path in data.get('paths_postponed', []):
                    if path in self._old_paths_owned:
                        self._postponed.add(path)
                for path in data.get('paths_created', []):
                    if path in self._old_paths_owned:
                        self._created.add(path)
        except FileNotFoundError:
            pass

    def _savecfg(self):
        # start with the old cleaners
        cleaners = [c.fulldict() for c in self._old_cleaners]
        # append any new cleaners
        cleaners.extend([c.fulldict() for c in self._new_cleaners])
        paths_owned = {}
        for path in self._old_paths_owned:
            paths_owned[path] = self._old_paths_owned[path]
        for path in self._new_paths_owned:
            paths_owned[path] = self._new_paths_owned[path]
        data = dict(cleaners=cleaners,
                    paths_owned=paths_owned,
                    paths_postponed=list(self._postponed),
                    paths_created=list(self._created),
                    )
        dumped = simplejson.dumps(data, indent=' ' * 4)
        with open(self._cfgpath, 'w') as f:
            f.write(dumped)

    def _removecleaner(self, cleaner):
        # remove the cleaner from the list if it already exists
        self._old_cleaners = [
            oldc for oldc in self._old_cleaners
            if not oldc.issame(cleaner)
        ]

    def _addcleaner(self, cleaner):
        # add a cleaner (it is guaranteed not to exist in the old list)
        # NOTE we need to make sure it is only added once
        for c in self._new_cleaners:
            if c.issame(cleaner):
                return
        self._new_cleaners.append(cleaner)

    def onlysections(self, names):
        self._only.update(names)

    def pushsection(self, name):
        if self._section is not None:
            raise Exception("Cannot nest section %r inside section %r" %
                            (name, self._section))
        self._section = name
        return name in self._only or not len(self._only)

    def popsection(self, name):
        assert self._section == name
        self._section = None

    def run(self, helper):
        assert isinstance(helper, Helper)

        cfg_modified = False

        # what claims does this helper make?
        self._claims.update(*helper.getclaims())

        # get a cleaner for this helper
        cleaner = helper.getcleaner()
        if cleaner is not None:
            cfg_modified = True

            # remove the cleaner from the list of old cleaners
            self._removecleaner(cleaner)

            # add the cleaner to the list of new cleaners
            self._addcleaner(cleaner)

        for path, type_ in helper.pathsownable().items():
            cfg_modified = True
            self._new_paths_owned[path] = type_
            self._old_paths_owned.pop(path, None)

        # if the helper isn't already done, tell it to do its thing now
        if not helper.isdone():
            with note("{}: Running ...".format(helper.description)):
                # take ownership of any paths that don't exist yet!
                for path, type_ in helper.pathsownable().items():
                    if type_ in (self.TYPE_FILE_ALL, self.TYPE_FOLDER_ALL):
                        exists = path in self._created
                    elif type_ in (self.TYPE_FILE_PART, self.TYPE_FOLDER_ONLY):
                        exists = os.path.exists(path)
                    else:
                        exists = os.path.islink(path)
                    if not exists:
                        self._created.add(path)
                        cfg_modified = True

                if cfg_modified:
                    # save the updated config before we try anything
                    self._savecfg()
                    cfg_modified = False

                try:
                    helper.makechanges()
                except HelperError as err:
                    warn("Failed: %s" % err.args[0])
        else:
            note("{}: Already done".format(helper.description))
        self._helpers.append(helper)

        # save the config now if we were successful
        if cfg_modified:
            # save the updated config before we try anything
            self._savecfg()

    def cleanup(self, conflicts):
        assert conflicts in (self.RAISE, self.WARN, self.POSTPONE, self.ASK)
        note("CLEANING UP %d items ..." % (
            len(self._old_cleaners) + len(self._created)))
        stack = list(self._old_cleaners)
        affected = []
        while len(stack):
            deferred = []
            for cleaner in stack:
                # TODO: do we still need this complexity?
                self._removecleaner(cleaner)
                self._tryclean(cleaner, conflicts, affected)
                self._savecfg()

            assert len(deferred) < len(stack), "Every cleaner wants to go last"
            stack = deferred

        # all old cleaners should now be finished, or delayed
        assert len(self._old_cleaners) == 0

        # re-run any helpers that touch the affected files
        for path in affected:
            for helper in self._helpers:
                if helper.affectspath(path) and not helper.isdone():
                    note("REDO: %s" % helper.description)
                    helper.makechanges()

        # now, clean up the old paths we found
        while len(self._old_paths_owned):
            before = len(self._old_paths_owned)
            for path in list(self._old_paths_owned.keys()):
                type_ = self._old_paths_owned[path]
                self._trycleanpath(path, type_, conflicts)
            if len(self._old_paths_owned) >= before:
                raise Exception("All paths want to delay cleaning")

    def pathstoclean(self):
        ret = {}
        for path, type_ in self._old_paths_owned.items():
            if path in self._created:
                ret[path] = type_
        for path, type_ in self._new_paths_owned.items():
            if path in self._created:
                ret[path] = type_
        return ret

    def _tryclean(self, cleaner, conflicts, affected):
        # if the cleaner is not needed, we get rid of it
        # FIXME try/except around the isneeded() call
        if not cleaner.isneeded():
            note("{}: Not needed".format(cleaner.description))
            return

        # run the cleaner now
        with note("Cleaning: {}".format(cleaner.description)):
            # if there are still helpers with claims over things the cleaner wants
            # to remove, then the cleaner needs to wait
            for claim in cleaner.needsclaims():
                if claim in self._claims:
                    note("Postponed: Something else claimed %r" % claim)
                    self._addcleaner(cleaner)
                    return

            try:
                affected.extend(cleaner.makechanges())
            except CleanupObstruction as err:
                why = err.args[0]
                if conflicts == self.RAISE:
                    raise
                if conflicts == self.POSTPONE:
                    note("Postponed: %s" % why)
                    # add the cleaner back in
                    self._addcleaner(cleaner)
                    return
                # NOTE: eventually we'd like to ask the user what to do, but
                # for now we just issue a warning
                assert conflicts in (self.WARN, self.ASK)
                warn("Aborted: %s" % err.why)

    def _trycleanpath(self, path, type_, conflicts):
        def _discard():
            note("    Forgetting about %s %s" % (type_, path))
            self._old_paths_owned.pop(path)
            self._postponed.discard(path)
            self._created.discard(path)
            self._savecfg()

        def _remove():
            # remove the thing
            if type_ == self.TYPE_FOLDER_ONLY:
                # TODO: what do we do if the folder isn't empty?
                with note("Removing dir %s" % path):
                    try:
                        os.rmdir(path)
                    except OSError as err:
                        from errno import ENOTEMPTY
                        if err.errno == ENOTEMPTY:
                            warn("Directory not empty: {}".format(path))
                        else:
                            raise
            elif type_ == self.TYPE_FILE_ALL:
                note("Removing {}".format(path))
                os.unlink(path)
            elif type_ == self.TYPE_FILE_PART:
                if os.stat(path).st_size == 0:
                    note("Removing empty {}".format(path))
                    os.unlink(path)
                else:
                    note("Refusing to remove non-empty {}".format(path))
            else:
                note("Removing link {}".format(path))
                os.unlink(path)
            _discard()

        def _postpone():
            with note("Postponing cleanup of path: {}".format(path)):
                self._postponed.add(path)
                assert path not in self._new_paths_owned
                self._new_paths_owned[path] = type_
                self._old_paths_owned.pop(path)
                self._savecfg()

        # if we didn't create the path, then we don't need to clean it up
        if path not in self._created:
            return _discard()

        # if the path no longer exists, we have nothing to do
        if not _exists(path):
            return _discard()

        # if the thing has the wrong type, we'll issue an note() and just skip
        if type_ in (self.TYPE_FILE_PART, self.TYPE_FILE_ALL):
            correcttype = os.path.isfile(path)
        elif type_ in (self.TYPE_FOLDER_ONLY, self.TYPE_FOLDER_ALL):
            correcttype = os.path.isdir(path)
        else:
            assert type_ == self.TYPE_LINK
            correcttype = os.path.islink(path)
        if not correcttype:
            with note("Ignoring: Won't remove {} as it is no longer a {}"
                      .format(path, type_)):
                return _discard()

        # work out if there is another path we need to remove first
        for otherpath in self._old_paths_owned:
            if otherpath != path and isnecessarypath(path, otherpath):
                # If there's another path we need to do first, then don't do
                # anything just yet. NOTE: there is an assertion to ensure that
                # we can't get stuck in an infinite loop repeatedly not
                # removing things.
                return

        # if any helpers want the path, don't delete it
        wantedby = None
        for c in self._new_cleaners:
            if c.wantspath(path):
                wantedby = c
                break

        if not wantedby:
            for otherpath in self._new_paths_owned:
                if isnecessarypath(path, otherpath):
                    wantedby = otherpath

        if wantedby:
            # if we previously postponed this path, keep postponing it
            # while there are still things hanging around that want it
            if path in self._postponed:
                return _postpone()
            if conflicts == self.ASK:
                raise Exception("TODO: ask the user what to do")  # noqa
                # NOTE: options are:
                # A) postpone until it can run later
                # B) discard it
            if conflicts == self.RAISE:
                raise CleanupConflict(conflictpath=path, pathwanter=wantedby)
            if conflicts == self.POSTPONE:
                return _postpone()
            assert conflicts == self.WARN
            warn("Conflict cleaning up path: {}".format(path))
            return _discard()

        # if nothing else wants this path, clean it up now
        return _remove()
