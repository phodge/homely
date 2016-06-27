from click import echo

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

    def __init__(self, info):
        assert isinstance(info, RepoInfo)
        self._info = info
        self._newthings = []
        self._newids = {}

    def getrepoinfo(self):
        return self._info

    def add(self, thing):
        self._newthings.append(thing)
        self._newids[thing.uniqueid] = None

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
            if thing.isdone():
                continue
            echo(thing.descchanges())
            changes = thing.makechanges(cfg.getprevchanges(thing.uniqueid))
            cfg.addthing(thing, changes)
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


def init(info):
    global _ENGINE
    _ENGINE = Engine(info)


def add(thing):
    _ENGINE.add(thing)


def currentrepoinfo():
    return _ENGINE.getrepoinfo()


def execute():
    _ENGINE.execute()
