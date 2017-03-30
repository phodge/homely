import os

from pytest import HOMELY, TempRepo, checkrepolist, contents, getsystemfn


def test_homely_remove(tmpdir, HOME):
    system = getsystemfn(HOME)

    def _addfake(name, createfile):
        # create a fake repo and add it
        tr = TempRepo(tmpdir, name)
        tf = os.path.join(HOME, createfile)
        contents(tr.remotepath + '/HOMELY.py',
                 """
                 from homely.files import lineinfile
                 lineinfile('~/%s', 'Hello from %s')
                 """ % (createfile, name))
        assert not os.path.exists(tf)
        system(HOMELY('add') + [tr.url])
        assert contents(tf) == "Hello from %s\n" % name
        return tr

    r1 = _addfake('repo1', 'file1.txt')
    r2 = _addfake('repo2', 'file2.txt')
    r3 = _addfake('repo3', 'file3.txt')

    # check that all the repos are there
    checkrepolist(HOME, system, [r1, r2, r3])
    assert contents(HOME + '/file1.txt', "Hello from repo1\n")
    assert contents(HOME + '/file2.txt', "Hello from repo2\n")
    assert contents(HOME + '/file3.txt', "Hello from repo3\n")

    # Check that the repo can be removed.
    system(HOMELY('forget') + [r1.repoid])
    checkrepolist(HOME, system, [r2, r3])
    assert contents(HOME + '/file1.txt', "Hello from repo1\n")
    assert contents(HOME + '/file2.txt', "Hello from repo2\n")
    assert contents(HOME + '/file3.txt', "Hello from repo3\n")

    # now run an update to make repo1's files go away
    system(HOMELY('update'))
    assert not os.path.exists(HOME + '/file1.txt')
    assert contents(HOME + '/file2.txt', "Hello from repo2\n")
    assert contents(HOME + '/file3.txt', "Hello from repo3\n")

    # Test removing multiple repos, but using local path this time
    # Note that because we don't use --update, the created files will still be
    # sitting around on disk
    system(HOMELY('forget') + ['~/repo2', '~/repo3'])
    checkrepolist(HOME, system, [])
    # repo2 and repo3 are stilling going to hang around on disk
    assert os.path.exists(HOME + '/repo2')
    assert os.path.exists(HOME + '/repo3')
    assert not os.path.exists(HOME + '/file1.txt')
    assert contents(HOME + '/file2.txt', "Hello from repo2\n")
    assert contents(HOME + '/file3.txt', "Hello from repo3\n")
