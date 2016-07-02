import contextlib
import os
import subprocess

import simplejson

from homely._errors import JsonError, RepoError

CONFIG_DIR = os.path.join(os.environ.get('HOME'), '.homely')
REPO_CONFIG_PATH = os.path.join(CONFIG_DIR, 'repos.json')


def _resolve(path):
    return os.path.realpath(os.path.expanduser(path))


class GitHubURL(object):
    @classmethod
    def loadfromurl(class_, url):
        import re
        m = re.match('^(https://|git@)github\.com[/:]([^/]+)/([^/]+)', url)
        if not m:
            return
        _, user, name = m.groups()
        scheme = 'https' if url.startswith('https://') else 'ssh'
        if name.endswith('.git'):
            name = name[0:-4]
        return class_(user, name, scheme)

    def __init__(self, user, name, scheme):
        self._user = user
        self._name = name

    def getname(self):
        return self._name

    def ashttps(self):
        return 'https://github.com/%s/%s.git' % (self._user, self._name)

    def asssh(self):
        return 'git@github.com:%s/%s.git' % (self._user, self._name)


class JsonConfig(object):
    jsonpath = None
    jsondata = None

    def __init__(self):
        try:
            with open(self.jsonpath, 'r') as f:
                data = f.read()
                if not len(data):
                    raise FileNotFoundError(None)
                self.jsondata = simplejson.loads(data)
                self.checkjson()
        except FileNotFoundError as err:
            self.jsondata = self.defaultjson()
        except simplejson.JSONDecodeError:
            raise JsonError("%s does not contain valid JSON" % self.jsonpath)

    def checkjson(self):
        """
        Child classes should override this method to check if self.jsondata is
        sane.
        """
        raise Exception("This method needs to be overridden")

    def defaultjson(self):
        """
        Child classes should override this method to return the default json
        object for when the config file doesn't exist yet.
        """
        raise Exception("This method needs to be overridden")

    def writejson(self):
        # make dirs needed for config file
        os.makedirs(os.path.dirname(self.jsonpath), mode=0o755, exist_ok=True)
        # write the config file now
        with open(self.jsonpath, 'w') as f:
            f.write(simplejson.dumps(self.jsondata, indent=' ' * 4))


class RepoListConfig(JsonConfig):
    jsonpath = REPO_CONFIG_PATH
    jsondata = None

    def __init__(self):
        super(RepoListConfig, self).__init__()

        # fix any paths that have changed
        modified = False
        for entry in self.jsondata:
            resolved = _resolve(entry['localpath'])
            if resolved != entry['localpath']:
                entry['localpath'] = resolved
                modified = True
        if modified:
            self.writejson()

    def defaultjson(self):
        return []

    def checkjson(self):
        assert isinstance(self.jsondata, list)
        for entry in self.jsondata:
            assert 'commithash' in entry
            assert 'localpath' in entry

    def add_repo(self, info):
        assert isinstance(info, RepoInfo)
        commithash = info.commithash
        modified = False
        for repo in self.jsondata:
            if repo["commithash"] == commithash:
                # change the local path in the config
                repo["localpath"] = _resolve(info.localpath)
                if info.githuburl is not None:
                    repo["githuburl"] = info.githuburl.ashttps()
                modified = True
                break
        if not modified:
            self.jsondata.append(info.asdict())

    def remove_repo(self, commithash):
        newdata = []
        for repo in self.jsondata:
            if repo["commithash"] != commithash:
                newdata.append(repo)
        self.jsondata = newdata

    def find_repo(self, hash_or_path):
        for repo in self.jsondata:
            match = False
            if hash_or_path == repo["commithash"]:
                match = True
            elif _resolve(hash_or_path) == _resolve(repo["localpath"]):
                match = True
            if match:
                return RepoInfo.fromdict(repo)

    def find_by_ghurl(self, ghurl):
        assert isinstance(ghurl, GitHubURL)
        httpsurl = ghurl.ashttps()
        for repo in self.jsondata:
            if httpsurl == repo.get("githuburl"):
                return RepoInfo.fromdict(repo)

    def find_all(self):
        for repo in self.jsondata:
            yield RepoInfo.fromdict(repo)


class RepoScriptConfig(JsonConfig):
    jsondata = None

    def __init__(self, info):
        self.jsonpath = os.path.join(CONFIG_DIR,
                                     'repos',
                                     info.commithash + '.json')
        super(RepoScriptConfig, self).__init__()

    @staticmethod
    def remove(info):
        assert isinstance(info, RepoInfo)
        os.unlink(os.path.join(CONFIG_DIR, 'repos', info.commithash + '.json'))

    def defaultjson(self):
        return {
            # a list of things that were installed on the last run
            "prevthings": [],
            "prevchanges": {},
            "questions": {},
        }

    def checkjson(self):
        pass

    def getthings(self):
        import homely.general
        import homely.install
        modules = [homely.general, homely.install]
        for thing in self.jsondata['prevthings']:
            class_ = thing["class"]
            identifiers = thing["identifiers"]
            for module in modules:
                if hasattr(module, class_):
                    yield getattr(module, class_).fromidentifiers(identifiers)
                    break
            else:
                raise Exception("No modules own %s" % class_)

    def clearthings(self):
        self.jsondata["prevthings"] = []
        return self.jsondata["prevchanges"]

    @staticmethod
    def _asdict(thing):
        return {"class": thing.__class__.__name__,
                "identifiers": thing.identifiers}

    def addthing(self, thing):
        self.jsondata["prevthings"].append(self._asdict(thing))
        self.jsondata["prevchanges"].setdefault(thing.uniqueid, {})

    def removething(self, thing):
        thingdict = self._asdict(thing)
        prevthings = [t for t in self.jsondata["prevthings"] if t != thingdict]
        assert (len(self.jsondata["prevthings"]) - len(prevthings)) == 1
        del self.jsondata["prevchanges"][thing.uniqueid]

    def setchanges(self, uniqueid, changes):
        self.jsondata["prevchanges"][uniqueid] = changes

    def getprevchanges(self, uniqueid):
        return self.jsondata["prevchanges"].get(uniqueid, {})

    def getquestionanswer(self, name):
        return self.jsondata["questions"].get(name, None)

    def setquestionanswer(self, name, value):
        self.jsondata["questions"][name] = value


@contextlib.contextmanager
def saveconfig(cfg):
    assert isinstance(cfg, JsonConfig)
    yield cfg
    cfg.writejson()


class RepoInfo(object):
    localpath = None
    commithash = None
    githuburl = None

    def __init__(self, path, commithash=None, githuburl=None):
        path = _resolve(path)

        # make sure the path is valid
        if not os.path.exists(path):
            raise RepoError("%s does not exist" % path)
        if not os.path.exists(os.path.join(path, '.git')):
            raise RepoError("%s is not a valid git repo" % path)
        self.localpath = path
        if commithash is None:
            # ask git for the commit hash
            self.commithash = self.getfirsthash(path)
        else:
            self.commithash = commithash
        if githuburl is not None:
            assert isinstance(githuburl, GitHubURL)
        self.githuburl = githuburl

    @classmethod
    def fromdict(class_, data):
        ret = class_(data["localpath"], data.get("commithash"))
        githuburl = data.get("githuburl")
        if githuburl is not None:
            ret.githuburl = GitHubURL.loadfromurl(githuburl)
            assert ret.githuburl is not None
        return ret

    def asdict(self):
        ret = {"localpath": self.localpath}
        if self.commithash is not None:
            ret["commithash"] = self.commithash
        if self.githuburl is not None:
            ret["githuburl"] = self.githuburl.ashttps()
        return ret

    @staticmethod
    def getfirsthash(localpath):
        cmd = ['git', 'rev-list', '--max-parents=0', 'HEAD']
        return (subprocess.check_output(cmd, cwd=localpath)
                .rstrip()
                .decode('utf-8'))

    @property
    def shorthash(self):
        return self.commithash[0:8]


@contextlib.contextmanager
def filereplacer(filepath):
    """
    This context manager yields two file pointers:

    orig:
        a file descriptor as if you had used open(filepath)
    tmp:
        a file descriptor as if you had used open(tempfile.mkstemp(), 'w')

    Note that upon successful exiting of the context manager, the file
    nominated by filepath will be replaced by the temp file. This will be done
    using file renames, so it is as close to atomic as we can get it.

    If the context block raises an exception, the original file is not changed,
    and the temp file is deleted.
    """
    import shutil
    # create the tmp dir if it doesn't exist yet
    tmpdir = os.path.join(CONFIG_DIR, 'tmp')
    os.makedirs(tmpdir, mode=0o700, exist_ok=True)
    tmpname = os.path.join(tmpdir, os.path.basename(filepath))
    try:
        if os.path.exists(filepath):
            shutil.copy2(filepath, tmpname)
        with open(tmpname, 'w') as tmp:
            try:
                with open(filepath, 'r') as orig:
                    yield tmp, orig
            except FileNotFoundError:
                yield tmp, None
    except:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmpname)
        raise
    with contextlib.suppress(FileNotFoundError):
        os.unlink(filepath)
    os.rename(tmpname, filepath)
