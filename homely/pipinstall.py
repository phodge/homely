from subprocess import check_output, check_call

from homely._engine2 import Helper, Cleaner, getengine
from homely._utils import haveexecutable
from homely._ui import isinteractive


def pipinstall(packagename, which, user=True):
    engine = getengine()
    for version in which:
        assert version in (2, 3)
        helper = PIPInstall(packagename, version, user)
        engine.run(helper)


_known_pips = set()


def _haspkg(pipcmd, name):
    output = check_output([pipcmd, 'list', '--disable-pip-version-check'])
    find = '%s ' % name
    for line in output.decode('utf-8').split("\n"):
        if line.startswith(find):
            return True
    return False


class PIPInstall(Helper):
    _name = None
    _version = None
    _user = False

    def __init__(self, name, version, user):
        super(PIPInstall, self).__init__()
        self._name = name
        self._version = version
        self._user = user
        self._pipcmd = {2: "pip2", 3: "pip3"}[version]

        if self._pipcmd not in _known_pips:
            if not haveexecutable(self._pipcmd):
                # FIXME: what type of helpful error should we be raising here?
                raise Exception("%s executable not found" % self._pipcmd)
            _known_pips.add(self._pipcmd)

    def getcleaner(self):
        return PIPCleaner(self._name, self._pipcmd)

    def pathsownable(self):
        return {}

    def getclaims(self):
        yield "%s:%s" % (self._pipcmd, self._name)

    def isdone(self):
        return _haspkg(self._pipcmd, self._name)

    @property
    def description(self):
        user = ' --user' if self._user else ''
        return "%s install %s%s" % (self._pipcmd, self._name, user)

    def makechanges(self):
        cmd = [
            self._pipcmd,
            'install',
            self._name,
            '--disable-pip-version-check',
        ]
        if self._user:
            cmd.append('--user')
        check_call(cmd)
        factname = 'pipinstall:%s:%s' % (self._pipcmd, self._name)
        self._setfact(factname, True)

    def affectspath(self, path):
        return False


class PIPCleaner(Cleaner):
    def __init__(self, name, pipcmd):
        super(PIPCleaner, self).__init__()
        self._name = name
        assert pipcmd in ('pip2', 'pip3')
        self._pipcmd = pipcmd

    def asdict(self):
        return dict(name=self._name, pipcmd=self._pipcmd)

    @classmethod
    def fromdict(class_, data):
        return class_(data["name"], data["pipcmd"])

    def __eq__(self, other):
        return self._name == other._name and self._pipcmd == other._pipcmd

    def isneeded(self):
        factname = 'pipinstall:%s:%s' % (self._pipcmd, self._name)
        hasfact = self._getfact(factname, False)
        return hasfact and _haspkg(self._pipcmd, self._name)

    @property
    def description(self):
        return "%s uninstall %s" % (self._pipcmd, self._name)

    def makechanges(self):
        cmd = [
            self._pipcmd,
            'uninstall',
            self._name,
            '--disable-pip-version-check',
        ]
        if not isinteractive():
            cmd.append('--yes')
        factname = 'pipinstall:%s:%s' % (self._pipcmd, self._name)
        try:
            check_call(cmd)
        finally:
            self._clearfact(factname)
        return []

    def needsclaims(self):
        yield "%s:%s" % (self._pipcmd, self._name)

    def wantspath(self, path):
        return False
