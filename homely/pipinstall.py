import re
from distutils.version import StrictVersion

from homely._engine2 import Cleaner, Helper, getengine
from homely._errors import HelperError
from homely._utils import haveexecutable, run
from homely.system import execute

__all__ = ["pipinstall"]


def pipinstall(packagename, pips=None, trypips=[], scripts=None):
    """
    Install packages from pip.

    The primary advantage of using this function is that homely can
    automatically remove the package for you when you no longer want it.

    package:
      The name of the pip package to install

    pips:
      A list of `pip` executables to install the package with.

      `['pip2.7', 'pip3.4']` would install the package using both the `pip2.7`
      and `pip3.4` executables. The default is to use `['pip']` as long as you
      aren't using `trypips`.

    trypips:
      This is a supplementary list of `pip` executables that homely will use to
      install the package, but no exception will be raised if the `pip`
      executables aren't available.

    Note that the `pip install ...` commands are run with the `--user` option
    so that the packages are installed into your home directory.
    """
    # `scripts` is an alternate location for bin scripts. Useful for bad
    # platforms that put pip2/pip3 scripts in the same bin dir such that they
    # clobber each other.
    # FIXME: `scripts` still has the following issues
    # - useless if you're specifying multiple pips at once
    # - won't do the uninstall/reinstall dance to reinstall something that was
    #   installed with a different `scripts` path
    if scripts is None:
        scripts = {}
    if pips is None:
        pips = [] if len(trypips) else ['pip']
    engine = getengine()
    for pip in pips:
        helper = PIPInstall(packagename,
                            pip,
                            mustinstall=True,
                            scripts=scripts.get(pip))
        engine.run(helper)
    for pip in trypips:
        helper = PIPInstall(packagename,
                            pip,
                            mustinstall=False,
                            scripts=scripts.get(pip))
        engine.run(helper)


_known_pips = {}
# dict of pip executables and whether they need the --format arg
_needs_format_cache = {}


def _needs_format(pipcmd):
    """
    pip >= 9.0.0 needs a --format=freeze argument to avoid a DEPRECATION
    warning. This function returns True if the nominated pip executable
    is >= 9.0.0
    """
    try:
        return _needs_format_cache[pipcmd]
    except KeyError:
        pass

    # grab the version number
    output = run([pipcmd, '--version'], stdout=True)[1].decode('utf-8')
    m = re.match(r'^pip (\S+) from ', output)
    needs_format = StrictVersion(m.group(1)) >= '9.0.0'
    _needs_format_cache[pipcmd] = needs_format
    return needs_format


def _haspkg(pipcmd, name):
    cmd = [
        pipcmd,
        'list',
        '--disable-pip-version-check',
    ]
    if _needs_format(pipcmd):
        cmd.append('--format=freeze')
    output = execute(cmd, stdout=True)[1]
    find = '%s==' % name
    for line in output.decode('utf-8').split("\n"):
        if line.startswith(find):
            return True
    return False


class PIPInstall(Helper):
    _name = None
    _pip = None
    _pipcmd = None
    _mustinstall = True
    # TODO: get rid of this option
    _user = False

    def __init__(self, name, pip, mustinstall, scripts=None):
        super(PIPInstall, self).__init__()
        self._name = name
        self._mustinstall = mustinstall
        self._pip = pip
        self._scripts = scripts

        try:
            haveexec = _known_pips[pip]
        except KeyError:
            haveexec = haveexecutable(pip)
            _known_pips[pip] = haveexec

        if haveexec:
            self._pipcmd = pip

    def getcleaner(self):
        if self._pipcmd is not None:
            return PIPCleaner(self._name, self._pipcmd)

    def pathsownable(self):
        return {}

    def getclaims(self):
        yield "%s:%s" % (self._pipcmd, self._name)

    def isdone(self):
        if self._pipcmd is None:
            return not self._mustinstall
        return _haspkg(self._pipcmd, self._name)

    @property
    def description(self):
        return "%s install --user %s" % (self._pipcmd, self._name)

    def makechanges(self):
        if self._pipcmd is None:
            raise HelperError("%s executable not found" % self._pip)
        cmd = [
            self._pipcmd,
            'install',
            self._name,
            '--user',
            '--disable-pip-version-check',
        ]
        if self._scripts is not None:
            cmd.append('--install-option=--install-scripts=%s' % self._scripts)
        execute(cmd)
        factname = 'pipinstall:%s:%s' % (self._pipcmd, self._name)
        self._setfact(factname, True)

    def affectspath(self, path):
        return False


class PIPCleaner(Cleaner):
    def __init__(self, name, pipcmd):
        super(PIPCleaner, self).__init__()
        self._name = name
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
            '--yes',
        ]
        factname = 'pipinstall:%s:%s' % (self._pipcmd, self._name)
        try:
            execute(cmd)
        finally:
            self._clearfact(factname)
        return []

    def needsclaims(self):
        yield "%s:%s" % (self._pipcmd, self._name)

    def wantspath(self, path):
        return False
