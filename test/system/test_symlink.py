import os

from pytest import HOMELY, TempRepo, contents, getsystemfn


def test_symlink_paths(HOME, tmpdir, monkeypatch):
    from os import mkdir
    from homely._utils import RepoInfo
    from homely._vcs.testhandler import Repo

    nesteddest1 = HOME + '/nested/nested.txt'

    tr = TempRepo(tmpdir, 'dotfiles')
    repoflat = tr.remotepath + '/f-original.txt'
    reponested = tr.remotepath
    contents(repoflat, 'flat original')
    mkdir(tr.remotepath + '/afolder')
    contents(reponested + '/afolder/n-original.txt', 'nested original')

    remoterepo = Repo.frompath(tr.remotepath)
    # make a local copy of the repo for us to work with
    localpath = tr.suggestedlocal(HOME)
    remoterepo.clonetopath(localpath)
    localrepo = Repo.frompath(localpath)

    import homely._engine2
    homely._engine2.setrepoinfo(RepoInfo(localrepo, localrepo.getrepoid()))

    class FakeEngine(object):
        def expect(self, target, linkname):
            self.expected_target = target
            self.expected_linkname = linkname

        def run(self, helper):
            pass

    fake_engine = FakeEngine()

    class FakeSymlinkMaker(object):
        def __init__(self, target, linkname):
            assert target == fake_engine.expected_target
            assert linkname == fake_engine.expected_linkname

    import homely.files
    monkeypatch.setattr(homely.files, "getengine", lambda: fake_engine)
    monkeypatch.setattr(homely.files, "MakeSymlink", FakeSymlinkMaker)

    from homely.files import symlink

    def _verify(target, linkname):
        raise Exception("TODO: test that a symlink to target was made at linkname")  # noqa

    def flat_to_flat(arg1, arg2=None, targetname=None, env=None):
        if env is not None:
            restore = {}
            for key in env:
                if key in os.environ:
                    restore[key] = os.environ[key]
                os.environ[key] = env[key]
        if targetname is None:
            target = HOME + '/dotfiles/flat.txt'
        else:
            target = HOME + '/dotfiles/' + targetname
        fake_engine.expect(target, repoflat)
        symlink(arg1, arg2)

        # restore env
        if env is not None:
            for key in env:
                if key in restore:
                    os.environ[key] = restore[key]
                else:
                    os.environ.pop(key)

    def not_allowed(arg1, arg2=None):
        try:
            symlink(arg1, arg2)
        except ValueError:
            pass
        else:
            raise Exception("A ValueError was expected")

    def flat_to_nested(arg1, arg2=None):
        fake_engine.expect(target, reponested)
        symlink(arg1, arg2)

    def nested_to_flat(arg1, arg2=None):
        # TODO: test that a symlink from ~/afolder/nested.txt is made to
        # repo/flat.txt
        variants.append((arg1, arg2, nesteddest1, reponested))

    def nested_to_nested(arg1, arg2=None):
        # TODO: test that a symlink from ~/afolder/nested.txt is made to
        # repo/nested/nested.txt
        variants.append((arg1, arg2, nesteddest1, reponested))

    # test that all calls to symlink() is with these 1 or 2 positional
    # arguments are valid, and result in the correct target and linkname
    flat_to_flat('flat.txt')
    flat_to_flat('flat.txt', 'file.txt', destname='file.txt')
    flat_to_flat('flat.txt', '~/file.txt', destname='file.txt')
    flat_to_flat('flat.txt', '$HOME/file.txt', destname='file.txt')
    flat_to_flat('flat.txt', '$HOME/$MYTARGET',
                 env={"MYTARGET": "file.txt"}, destname="file.txt")
    flat_to_flat('./flat.txt')
    flat_to_flat('flat.txt', '~/')
    flat_to_flat('flat.txt', '$HOME/')

    # Test that none of these invocations are allowed. Why? Because the
    # automatic linkname would be the name of the target.
    not_allowed('~/flat.txt')
    not_allowed('$HOME/flat.txt', '~/')
    not_allowed('$HOME/flat.txt', '$HOME/')

    # test that these invocations work - even though they're asking for the
    # link to be created at a path which is already occupied by the $HOME dir,
    # this isn't checked at this point
    for badpath in ('~', '$HOME'):
        fake_engine.expect('zzzzzz/f-original.txt',
                           os.path.realpath(os.environ['HOME']))
        symlink('f-original.txt', badpath)

    #nested_to_home('~/flat.txt', 'afolder/nested.txt')
    #nested_to_home('$HOME/flat.txt', 'afolder/nested.txt')

    #nested_to_flat('flat.txt', 'afolder/nested.txt')

    #home_to_nested('repofolder/nested.txt')
    #home_to_nested('repofolder/nested.txt', '~/')
    #home_to_nested('repofolder/nested.txt', '$HOME/')
