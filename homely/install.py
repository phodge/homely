import os
import time

from homely._engine2 import Cleaner, Engine, Helper, getengine
from homely._errors import HelperError
from homely._ui import allowinteractive, allowpull, note
from homely._utils import haveexecutable, isnecessarypath
from homely.system import execute


def installpkg(name, wantcmd=None, **methods):
    for key in methods:
        assert key in _METHODS

    # FIXME: make sure the user specifies at least one way to install the thing
    getengine().run(InstallPackage(name, methods, wantcmd))


_ALLOW_INSTALL = True


def setallowinstall(allow_install):
    """
    Configure whether installpkg() InstallPackage() are actually allowed to
    install anything.

    If installing isn't allowed, installpkg() and InstallPackage() will raise
    an error instead of installing the package. This is useful in work
    environment where your local sysadmin wants additional packages managed
    externally by a tool like salt.

    NOTE: This also controls whether InstallFromSource() is allowed to perform
    commands starting with "sudo" - the assumption here is that if
    InstallFromSource() can't run commands as root, it can't install anything.
    Compiling from source and symlinking to ~/bin will still work fine.
    """
    global _ALLOW_INSTALL
    _ALLOW_INSTALL = bool(allow_install)


class InstallFromSource(Helper):
    _title = None
    _source_repo = None
    _clone_to = None
    _real_clone_to = None
    _branch = None
    _tag = None
    _compile = None

    # FIXME: we need a better way to specify whether or not a TTY is needed
    _needs_tty = False

    def __init__(self, source_repo, clone_to):
        super(InstallFromSource, self).__init__()
        self._title = 'Install %s into %s' % (source_repo, clone_to)
        self._source_repo = source_repo
        self._clone_to = clone_to
        self._real_clone_to = os.path.expanduser(clone_to)
        self._symlinks = []

    def select_branch(self, branch_name, expiry=None):
        # possible values of expiry:
        # 0:     always pull and compile
        # -1:    never pull or compile again
        # <int>: pull and compile again after <int> seconds
        if expiry is None:
            expiry = 60 * 60 * 24 * 14
        assert self._tag is None
        assert type(expiry) is int and expiry >= -1
        self._branch = branch_name
        self._expiry = expiry
        self._branchfact = '{}:compile-branch:{}:{}'.format(
            self.__class__.__name__,
            self._real_clone_to,
            branch_name)

    def select_tag(self, tag_name):
        assert self._branch is None
        self._tag = tag_name
        self._expiry = None

    def symlink(self, target, linkname):
        self._symlinks.append((os.path.join(self._real_clone_to, target),
                               os.path.expanduser(linkname)))

    def compile_cmd(self, commands):
        assert self._compile is None
        self._compile = list(commands)
        for cmd in self._compile:
            if cmd[0] == "sudo":
                self._needs_tty = True

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

        if self._tag:
            # has the correct branch or tag been checked out?
            current = execute(['git', 'tag', '--points-at', 'HEAD'],
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
            execute(['git', 'clone', self._source_repo, self._real_clone_to])
        else:
            pull_needed = True
            if not os.path.exists(os.path.join(self._real_clone_to, '.git')):
                raise HelperError("%s is not a git repo" % self._real_clone_to)

        # do we want a particular branch?
        if self._branch:
            execute(['git', 'checkout', self._branch], cwd=self._real_clone_to)
            if pull_needed and allowpull():
                note("Updating %s from %s" %
                     (self._clone_to, self._source_repo))
                execute(['git', 'pull'], cwd=self._real_clone_to)

            # check the branch fact to see if we need to compile again
            factname = self._branchfact
        else:
            assert self._tag is not None
            if pull_needed and allowpull():
                note("Updating %s from %s" %
                     (self._clone_to, self._source_repo))
                execute(['git', 'fetch', '--tags'], cwd=self._real_clone_to)
            execute(['git', 'checkout', self._tag], cwd=self._real_clone_to)

            # if we used a tag name, create a 'fact' to prevent us re-compiling
            # each time we run
            factname = '{}:compile-tag:{}:{}'.format(
                self.__class__.__name__,
                self._real_clone_to,
                self._tag)

        docompile = False
        if self._compile:
            last_compile, prev_cmds = self._getfact(factname, (0, None))
            what = ("Branch {}".format(self._branch) if self._branch
                    else "Tag {}".format(self._tag))
            if last_compile == 0:
                note("{} has never been compiled".format(what))
                docompile = True
            elif (self._expiry is not None
                  and ((last_compile + self._expiry) < time.time())):
                note("{} is due to be compiled again".format(what))
                docompile = True
            elif prev_cmds != self._compile:
                note("{} needs to be compiled again with new commands"
                     .format(what))
                docompile = True

        # run any compilation commands
        if docompile:
            # FIXME: we probably need to delete all the symlink targets before
            # compiling, as this is our best way of determining that the
            # compilation has failed ...
            stdout = "TTY" if self._needs_tty else None
            for cmd in self._compile:
                if cmd[0] == "sudo" and not _ALLOW_INSTALL:
                    raise HelperError(
                        "%s is not allowed to run commands as root"
                        ", as per setallowinstall()")
                execute(cmd, cwd=self._real_clone_to, stdout=stdout)

            self._setfact(factname, (time.time(), self._compile))

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


_METHODS = ('brew', 'yum', 'apt', 'port')
_ASROOT = ('yum', 'port', 'apt')
_INSTALL = {
    'apt': lambda name: ['apt-get', 'install', name, '--quiet',
                         '--assume-yes'],
    'yum': lambda name: ['yum', 'install', name, '--assumeyes'],
}
_UNINSTALL = {
    'apt': lambda name: ['apt-get', 'remove', name, '--quiet', '--assume-yes'],
    'yum': lambda name: ['yum', 'erase', name, '--assumeyes'],
}


class InstallPackage(Helper):
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
        how = [m for m in _METHODS if self._methods.get(m, True)]
        return "Install package %s using %s" % (self._name, how)

    def getclaims(self):
        yield "package:%s" % self._name

    def affectspath(self, path):
        return False

    def makechanges(self):
        # try each method
        for method in _METHODS:
            localname = self._methods.get(method, self._name)

            if localname is False:
                continue

            def getdefaultcmd(name):
                return [method, 'install', name]

            cmd = _INSTALL.get(method, getdefaultcmd)(localname)

            # see if the required executable is installed
            if not haveexecutable(cmd[0]):
                continue

            if not _ALLOW_INSTALL:
                raise HelperError(
                    "InstallPackage() is not allowed to install packages"
                    ", as per setallowinstall()")

            if method in _ASROOT:
                if not allowinteractive():
                    raise HelperError("Need to be able to escalate to root")
                cmd.insert(0, 'sudo')
            execute(cmd)
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
        for method in _METHODS:
            localname = self._methods.get(method, self._name)
            factname = 'InstalledPackage:%s:%s' % (method, localname)
            if self._getfact(factname, False):
                return True
        return False

    def makechanges(self):
        # look for any of the facts saying we installed these things
        for method in _METHODS:
            localname = self._methods.get(method, self._name)
            factname = 'InstalledPackage:%s:%s' % (method, localname)
            if not self._getfact(factname, False):
                continue

            def defaultuninstall(name):
                return [method, 'uninstall', name]

            cmd = _UNINSTALL.get(method, defaultuninstall)(localname)
            if method in _ASROOT:
                if not allowinteractive():
                    raise HelperError("Need to be able to escalate to root")
                cmd.insert(0, 'sudo')
            try:
                execute(cmd)
            finally:
                # always clear the fact
                self._clearfact(factname)
        raise HelperError("Didn't remove package %s" % self._name)

    def wantspath(self, path):
        return False
