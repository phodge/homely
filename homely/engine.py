import os

from click import echo

from homely.utils import RepoError, RepoInfo, RepoScriptConfig


def heading(message):
    echo(message)
    echo("=" * len(message))
    echo("")


def run_update(info, pullfirst):
    assert isinstance(info, RepoInfo)
    heading("Updating from %s [%s]" % (info.localpath, info.shorthash))
    if pullfirst:
        # FIXME: warn if there are oustanding changes in the repo
        # FIXME: allow the user to configure whether they want to use 'git pull' or some other
        # command to update the repo
        echo("%s: Retrieving updates using git pull" % info.localpath)
        cmd = ['git', '-C', path, 'pull']
        subprocess.check_call(cmd)
    else:
        # FIXME: notify the user if there are oustanding changes in the repo
        pass

    # make sure the HOMELY.py script exists
    pyscript = os.path.join(info.localpath, 'HOMELY.py')
    if not os.path.exists(pyscript):
        raise RepoError("%s does not exist" % pyscript)

    global _ENGINE
    _ENGINE = Engine(info)
    from importlib.machinery import SourceFileLoader
    source = SourceFileLoader('__imported_by_homely', pyscript)
    module = source.load_module()
    _ENGINE.execute()


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
                if oldthing.isdone():
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
            if oldthing.isdone():
                oldthing.undochanges(prevchanges)
            cfg.writejson()


_ENGINE = None

def add(thing):
    _ENGINE.add(thing)
