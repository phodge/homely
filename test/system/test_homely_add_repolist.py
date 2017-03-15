import os

from pytest import HOMELY, TempRepo, checkrepolist, contents, getsystemfn


def test_add_greenfield_repos(tmpdir, HOME):
    """
    Work or at least die with a helpful error message when ...
    """
    from homely._errors import ERR_NO_COMMITS, ERR_NOT_A_REPO, ERR_NO_SCRIPT

    system = getsystemfn(HOME)

    def _repolist():
        cmd = HOMELY('repolist') + ['--format', '%(localpath)s']
        return list(filter(None, system(cmd).strip().split("\n")))

    # Target dir is not a git repo
    notarepo = HOME + '/not_a_repo'
    os.mkdir(notarepo)
    contents(notarepo + '/HOMELY.py', "print('YES')\n")
    output = system(HOMELY('add') + [notarepo], expecterror=1)
    assert ERR_NOT_A_REPO in output
    del notarepo, output
    # this should have resulted in nothing being added to homely
    assert not len(_repolist())

    # Target dir doesn't have any commits
    nocommits = HOME + '/nocommits'
    os.mkdir(nocommits)
    contents(nocommits + '/HOMELY.py', "print('YES')\n")
    system(['git', 'init'], cwd=nocommits)
    assert os.path.exists(nocommits + '/.git')
    output = system(HOMELY('add') + [nocommits], expecterror=1)
    assert ERR_NO_COMMITS in output
    del nocommits, output
    # this should have resulted in nothing being added to homely
    assert not len(_repolist())

    # Target dir doesn't have a HOMELY.py script - when we add a repo that
    # doesn't have a HOMELY.py script we should raise an error and provide
    # instructions on how to write a HOMELY.py script (and not try to do the
    # homely update).
    noscript = HOME + '/noscript'
    os.mkdir(noscript)
    readme = noscript + '/README.md'
    contents(readme, "Hello world!\n")
    system(['git', 'init'], cwd=noscript)
    system(['git', 'config', 'user.name', "fred"], cwd=noscript)
    system(['git', 'config', 'user.email', "fred@example"], cwd=noscript)
    system(['git', 'add', 'README.md'], cwd=noscript)
    system(['git', 'commit', '-m', "Added readme"], cwd=noscript)
    output = system(HOMELY('add') + [noscript], expecterror=1)
    assert ERR_NO_SCRIPT in output
    # the repo should have added to homely
    assert [noscript] == _repolist()


def test_homely_add_repolist(tmpdir, HOME):
    system = getsystemfn(HOME)

    # make a fake repo - create a dir, a folder, and a symlink
    repo1 = TempRepo(tmpdir, 'repo1')
    homedir1 = os.path.join(HOME, 'dir1')
    homelink1 = os.path.join(HOME, 'link1')
    homedir1file = os.path.join(homelink1, 'file.txt')
    assert not os.path.exists(homedir1)
    assert not os.path.islink(homelink1)
    contents(repo1.remotepath + '/HOMELY.py',
             """
             from homely.files import lineinfile, mkdir, symlink
             mkdir('~/dir1')
             symlink('~/dir1', '~/link1')
             lineinfile('~/link1/file.txt', 'Hello World')
             """)

    # add the repo and ensure that everything was created as expected
    system(HOMELY('add') + [repo1.url])

    assert repo1.installedin(HOME)
    assert os.path.isdir(homedir1)
    assert os.path.islink(homelink1)
    assert os.readlink(homelink1) == os.path.realpath(homedir1)
    assert contents(homedir1file) == "Hello World\n"

    # make another repo that creates more things
    repo2 = TempRepo(tmpdir, 'repo2')
    repo2file = os.path.join(HOME, 'file2.txt')
    assert not os.path.exists(repo2file)
    contents(repo2.remotepath + '/HOMELY.py',
             """
             from homely.files import lineinfile
             lineinfile('~/file2.txt', 'Hey There')
             """)
    system(HOMELY('add') + [repo2.url])
    assert repo2.installedin(HOME)
    assert contents(repo2file, "Hey There\n")

    checkrepolist(HOME, system, [repo1, repo2])

    # a 3rd repo, but we're going to clone it into our home dir manually
    repo3 = TempRepo(tmpdir, 'repo3')
    contents(repo3.remotepath + '/HOMELY.py',
             """
             from homely.files import lineinfile
             lineinfile('~/r3.txt', 'From R3')
             """)
    # where would it go in the home dir?
    localrepo3 = os.path.join(HOME, 'repo3')
    # use a Repo instance to clone it into our home dir manually
    from homely._vcs.testhandler import Repo
    Repo.frompath(repo3.url).clonetopath(localrepo3)

    # test adding a repo from the local dir
    assert not os.path.exists(HOME + '/r3.txt')
    system(HOMELY('add') + [localrepo3])
    assert contents(HOME + '/r3.txt') == 'From R3\n'
    checkrepolist(HOME, system, [repo1, repo2, repo3])

    # test that you can't add the same repo again
    system(HOMELY('add') + [repo2.url])
    checkrepolist(HOME, system, [repo1, repo2, repo3])

    # test that adding a repo with something like 'homely add .' doesn't record
    # a stupid path like '.'
    repo4 = TempRepo(tmpdir, 'repo4')
    contents(repo4.remotepath + '/HOMELY.py',
             """
             from homely.files import lineinfile
             lineinfile('~/r4.txt', 'From R4')
             """)
    localrepo4 = os.path.join(HOME, 'repo4')
    # use a Repo instance to clone it into our home dir manually
    from homely._vcs.testhandler import Repo
    Repo.frompath(repo4.url).clonetopath(localrepo4)
    system(HOMELY('add') + ['.'], cwd=localrepo4)
    checkrepolist(HOME, system, [repo1, repo2, repo3, repo4])
