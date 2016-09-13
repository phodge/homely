import os

from pytest import getsystemfn, TempRepo, contents, HOMELY, checkrepolist


def test_homely_remove(tmpdir, HOME):
    system = getsystemfn(HOME)

    def _addfake(name, createfile):
        # create a fake repo and add it
        tr = TempRepo(tmpdir, name)
        tf = os.path.join(HOME, createfile)
        contents(tr.remotepath + '/HOMELY.py',
                 """
                 from homely.general import lineinfile
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

    # check that trying to remove a repo that still exists locally doesn't work
    system(HOMELY('remove') + [r1.repoid], expecterror=1)
    checkrepolist(HOME, system, [r1, r2, r3])

    # Check that the repo can be removed without --force once it has
    # disappeared from local disk. Note that because we use --update here, the
    # file will be removed from disk
    import shutil
    shutil.rmtree(os.path.join(HOME, 'repo1'))
    system(HOMELY('remove') + [r1.repoid, '--update'])
    checkrepolist(HOME, system, [r2, r3])
    assert not os.path.exists(HOME + '/file1.txt')
    assert contents(HOME + '/file2.txt', "Hello from repo2\n")
    assert contents(HOME + '/file3.txt', "Hello from repo3\n")

    # Test removing multiple repos, but using local path this time
    # Note that because we don't use --update, the created files will still be
    # sitting around on disk
    system(HOMELY('remove') + ['~/repo2', '~/repo3', '--force'])
    checkrepolist(HOME, system, [])
    assert not os.path.exists(HOME + '/repo1')
    # repo2 and repo3 are stilling going to hang around on disk
    assert os.path.exists(HOME + '/repo2')
    assert os.path.exists(HOME + '/repo3')
    assert not os.path.exists(HOME + '/file1.txt')
    assert contents(HOME + '/file2.txt', "Hello from repo2\n")
    assert contents(HOME + '/file3.txt', "Hello from repo3\n")
