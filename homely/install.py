import os

from homely._errors import HelperError
from homely._engine2 import Helper, Cleaner, getengine, Engine
from homely._utils import haveexecutable, isnecessarypath
from homely._ui import note, allowinteractive, allowpull, system


def installpkg(name=None, wantcmd=None, **methods):
    for key in methods:
        assert key in InstallPackage.METHODS

    # FIXME: make sure the user specifies at least one way to install the thing
    getengine().run(InstallPackage(name, methods, wantcmd))


class InstallFromSource(Helper):
    _title = None
    _source_repo = None
    _clone_to = None
    _real_clone_to = None
    _branch = None
    _tag = None
    _compile = None

    def __init__(self, source_repo, clone_to):
        super(InstallFromSource, self).__init__()
        self._title = 'Install %s into %s' % (source_repo, clone_to)
        self._source_repo = source_repo
        self._clone_to = clone_to
        self._real_clone_to = os.path.expanduser(clone_to)
        self._symlinks = []

    def select_branch(self, branch_name):
        assert self._tag is None
        self._branch = branch_name

    def select_tag(self, tag_name):
        assert self._branch is None
        self._tag = tag_name

    def symlink(self, target, linkname):
        self._symlinks.append((os.path.join(self._real_clone_to, target),
                               os.path.expanduser(linkname)))

    def compile_cmd(self, commands):
        assert self._compile is None
        self._compile = list(commands)

    @property
    def description(self):
        return self._title

    def getcleaner(self):
        return

    def affectspath(self, path):
        return isnecessarypath(self._real_clone_to, path)

    def pathsownable(self):
        ret = {self._real_clone_to: Engine.TYPE_FOLDER_ONLY}
        for target, linkname in self._symlinks:
            ret[linkname] = Engine.TYPE_LINK
        return ret

    def getclaims(self):
        return []

    def isdone(self):
        if not os.path.exists(self._real_clone_to):
            return False

        # if a branch is requested, then we always need to check again ...
        if self._branch is not None:
            return False

        # has the correct branch or tag been checked out?
        assert self._tag is not None
        current = system(['git', 'tag', '--points-at', 'HEAD'],
                         cwd=self._real_clone_to,
                         stdout=True)[1]
        if self._tag not in map(str, current.splitlines()):
            return False

        # do the symlinks exist?
        for target, linkname in self._symlinks:
            if not os.path.islink(linkname):
                return False
            if os.readlink(linkname) != target:
                return False

        # it appears to be done ... yay
        return True

    def makechanges(self):
        assert self._source_repo is not None
        assert self._clone_to is not None
        if not os.path.exists(self._real_clone_to):
            note("Cloning %s" % self._source_repo)
            pull_needed = False
            system(['git', 'clone', self._source_repo, self._real_clone_to])
        else:
            pull_needed = True
            if not os.path.exists(os.path.join(self._real_clone_to, '.git')):
                raise HelperError("%s is not a git repo" % self._real_clone_to)

        # do we want a particular branch?
        if self._branch:
            system(['git', 'checkout', self._branch], cwd=self._real_clone_to)
            if pull_needed and allowpull():
                note("Updating %s from %s" %
                     (self._clone_to, self._source_repo))
                system(['git', 'pull'], cwd=self._real_clone_to)
        else:
            assert self._tag is not None
            if pull_needed and allowpull():
                note("Updating %s from %s" %
                     (self._clone_to, self._source_repo))
                system(['git', 'fetch', '--tags'], cwd=self._real_clone_to)
            system(['git', 'checkout', self._tag], cwd=self._real_clone_to)

        # run any compilation commands
        if self._compile is not None:
            # if we used a tag name, create a 'fact' to prevent us re-compiling
            # each time we run
            docompile = True
            factname = None
            if self._tag:
                factname = '{}:compilation:{}:{}'.format(
                    self.__class__.__name__,
                    'compilation',
                    self._real_clone_to,
                    self._tag)
                # check if we need to recompile
                if self._compile == self._getfact(factname, None):
                    note("Tag {} was compiled last time".format(self._tag))
                    docompile = False
                self._clearfact(factname)

            # FIXME: we probably need to delete all the symlink targets before
            # compiling, as this is our best way of determining that the
            # compilation has failed ...
            if docompile:
                for cmd in self._compile:
                    system(cmd, cwd=self._real_clone_to)

            if factname:
                self._setfact(factname, self._compile)

        # create new symlinks
        for source, dest in self._symlinks:
            with note("Ensure symlink exists: %s -> %s" % (source, dest)):
                if os.path.islink(dest):
                    target = os.readlink(dest)
                    if os.path.realpath(target) != os.path.realpath(source):
                        raise HelperError("Symlink %s is not pointing at %s" %
                                          (dest, source))
                    continue
                if os.path.exists(dest):
                    raise HelperError("%s already exists" % dest)
                os.symlink(source, dest)


class InstallPackage(Helper):
    METHODS = ('brew', 'yum', 'port', 'apt')
    _ASROOT = ('yum', 'port', 'apt')
    _EXECUTABLES = {'apt': 'apt-get'}
    _INSTALL = {
        'apt': lambda name: ['apt-get', 'install', name,
                             '--quiet', '--assume-yes'],
        'yum': lambda name: ['yum', 'install', name, '--assumeyes'],
    }
    _UNINSTALL = {
        'apt': lambda name: ['apt-get', 'remove', name,
                             '--quiet', '--assume-yes'],
        'yum': lambda name: ['yum', 'erase', name, '--assumeyes'],
    }

    def __init__(self, name, methods, wantcmd):
        super(InstallPackage, self).__init__()
        self._name = name
        self._methods = methods
        self._wantcmd = name if wantcmd is None else wantcmd

    def getcleaner(self):
        return PackageCleaner(self._name, self._methods)

    def pathsownable(self):
        return {}

    def isdone(self):
        return haveexecutable(self._wantcmd)

    @property
    def description(self):
        how = [m for m in self.METHODS if self._methods.get(m, True)]
        return "Install package %s using %s" % (self._name, how)

    def getclaims(self):
        yield "package:%s" % self._name

    def affectspath(self, path):
        return False

    def makechanges(self):
        # try each method
        for method in self.METHODS:
            cmdname = self._EXECUTABLES.get(method, method)
            localname = self._methods.get(method, self._name)

            # see if the required executable is installed
            if not haveexecutable(cmdname):
                continue

            def getdefaultcmd(name):
                return [method, 'install', name]

            cmd = self._INSTALL.get(method, getdefaultcmd)(localname)
            if method in self._ASROOT:
                if not allowinteractive():
                    raise HelperError("Need to be able to escalate to root")
                cmd.insert(0, 'sudo')
            system(cmd)
            # record the fact that we installed this thing ourselves
            factname = 'InstalledPackage:%s:%s' % (method, localname)
            self._setfact(factname, True)
            return
        raise HelperError("No way to install %s" % self._name)


class PackageCleaner(Cleaner):
    def __init__(self, name, methods):
        super(PackageCleaner, self).__init__()
        self._name = name
        self._methods = methods

    def asdict(self):
        return dict(name=self._name, methods=self._methods)

    @classmethod
    def fromdict(class_, data):
        return class_(data["name"], data["methods"])

    def __eq__(self, other):
        return self._name == other._name and self._methods == other._methods

    @property
    def description(self):
        return "Remove package %s" % self._name

    def needsclaims(self):
        yield "package:%s" % self._name

    def isneeded(self):
        # look for any of the facts saying we installed these things
        for method in InstallPackage.METHODS:
            localname = self._methods.get(method, self._name)
            factname = 'InstalledPackage:%s:%s' % (method, localname)
            if self._getfact(factname, False):
                return True
        return False

    def makechanges(self):
        # look for any of the facts saying we installed these things
        for method in InstallPackage.METHODS:
            localname = self._methods.get(method, self._name)
            factname = 'InstalledPackage:%s:%s' % (method, localname)
            if not self._getfact(factname, False):
                continue

            def defaultuninstall(name):
                return [method, 'uninstall', name]

            cmd = self._UNINSTALL.get(method, defaultuninstall)(localname)
            if method in InstallPackage._ASROOT:
                if not allowinteractive():
                    raise HelperError("Need to be able to escalate to root")
                cmd.insert(0, 'sudo')
            try:
                system(cmd)
            finally:
                # always clear the fact
                self._clearfact(factname)
        raise HelperError("Didn't remove package %s" % self._name)

    def wantspath(self, path):
        return False
