from click import echo

from homely._errors import HelperError
from homely._utils import RepoInfo, RepoScriptConfig


def clone_online_repo(repo_path):
    assert len(repo_path)
    raise Exception("TODO: git clone the repo")  # noqa
    raise Exception("TODO: return the path to the local copy of the repo")  # noqa
    # FIXME: check to see if the repo already exists locally
    # FIXME: suggest a good default location for the local clone of the repo
    return local_path


class Engine(object):
    _info = None
    _oldthings = None
    _newthings = None
    _newids = None
    _section = []
    _sections_seen = None
    _only = None
    _skip = None

    def __init__(self, info):
        assert isinstance(info, RepoInfo)
        self._info = info
        self._newthings = []
        self._newids = {}
        self._sections_seen = set()

    def getrepoinfo(self):
        return self._info

    def add(self, thing):
        self._newthings.append(thing)
        self._newids[thing.uniqueid] = None
        if len(self._section):
            thing.setsection('/'.join(self._section))

    def pushsection(self, name):
        self._section.append(name)
        self._sections_seen.add('/'.join(self._section))

    def popsection(self, name):
        assert self._section.pop() == name

    def onlysections(self, sections):
        self._only = sections
        for s in sections:
            if s not in self._sections_seen:
                raise HelperError("Unknown section %r" % s)

    def skipsections(self, sections):
        self._skip = sections
        for s in sections:
            if s not in self._sections_seen:
                raise HelperError("Unknown section %r" % s)

    def execute(self):
        # go through things that were seen in this config last time
        cfg = RepoScriptConfig(self._info)
        for oldthing in cfg.getthings():
            if oldthing.uniqueid not in self._newids:
                # if the thing isn't here any more, we want to remove it
                changes = cfg.getprevchanges(oldthing.uniqueid)
                cfg.removething(oldthing)
                if oldthing.iscleanable():
                    echo("REVERSING: %s" % oldthing.descchanges())
                    oldthing.undochanges(changes)
                cfg.writejson()

        cfg.clearthings()
        for thing in self._newthings:
            cfg.addthing(thing)
        cfg.writejson()

        prevsection = None

        for thing in self._newthings:
            # if we're only doing some sections, make sure this thing is in the
            # required section
            section = thing.getsection()
            if section != prevsection:
                echo("Entering section %r" % section)
            prevsection = section

            skip = False
            if self._only and section not in self._only:
                skip = True
            if self._skip and section in self._skip:
                skip = True
            if skip:
                echo("SKIPPING: %s" % thing.descchanges())
                continue

            if thing.isdone():
                echo("ALREADY DONE: %s" % thing.descchanges())
                continue

            echo("DOING: %s" % thing.descchanges())
            changes = thing.makechanges(cfg.getprevchanges(thing.uniqueid))
            cfg.setchanges(thing.uniqueid, changes)
            cfg.writejson()

    def rollback(self):
        cfg = RepoScriptConfig(self._info)
        for oldthing in cfg.getthings():
            # if the thing isn't here any more, we want to remove it
            prevchanges = cfg.getprevchanges(oldthing.uniqueid)
            cfg.removething(oldthing)
            if oldthing.iscleanable():
                oldthing.undochanges(prevchanges)
            cfg.writejson()


_ENGINE = None


def getengine():
    return _ENGINE


def initengine(info):
    global _ENGINE
    _ENGINE = Engine(info)
    return _ENGINE
