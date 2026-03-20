import os
import re
from pathlib import Path
from subprocess import check_call

from homely._test import contents

GIT = [
    'git',
    '-c',
    'user.name=John Smith',
    '-c',
    'user.email=john@example.com',
]


def makegitrepo(tmpdir, name):
    path = os.path.join(tmpdir, name)

    def system(cmd):
        check_call(cmd, cwd=path)

    os.mkdir(path)
    system(GIT + ['init'])
    readme = os.path.join(path, 'README.md')
    contents(readme, "Hello\n")
    system(GIT + ['add', 'README.md'])
    system(GIT + ['commit', '-m', 'Added readme'])
    return path


def test_git(tmpdir):
    # test loading handler from url
    from homely._vcs.git import Repo

    # check that frompath() works on folders also
    assert Repo.frompath(tmpdir) is None

    mygit = os.path.join(tmpdir, 'therepo')
    os.mkdir(mygit)
    os.mkdir(mygit + '/.git')
    repo = Repo.frompath(mygit)
    assert repo is not None
    assert repo.repo_path == mygit
    assert repo.iscanonical is False
    assert repo.isremote is False
    assert repo.pulldesc == 'git pull'

    # test repo.clonetopath() and repo.isdirty()
    fake1path = makegitrepo(tmpdir, 'fake1')
    fake1repo = Repo.frompath(fake1path)
    assert fake1repo.suggestedlocal == 'fake1'
    assert re.match(r'^[0-9a-f]{40}$', fake1repo.getrepoid())
    assert re.match(r'^[0-9a-f]{8}$', fake1repo.shortid(fake1repo.getrepoid()))
    assert not fake1repo.isdirty()
    with open(os.path.join(fake1path, 'file.txt'), 'w'):
        pass
    assert not fake1repo.isdirty()
    check_call(GIT + ['add', 'file.txt'], cwd=fake1path)
    assert fake1repo.isdirty()

    clone1path = os.path.join(tmpdir, 'clone1')
    fake1repo.clonetopath(clone1path)
    clone1repo = Repo.frompath(clone1path)
    assert clone1repo.getrepoid() == fake1repo.getrepoid()

    # test repo.pullchanges() by making a change in the original fake
    assert not os.path.exists(os.path.join(clone1path, 'file.txt'))
    check_call(GIT + ['commit', '-m', 'Added file'], cwd=fake1path)
    clone1repo.pullchanges()
    assert os.path.exists(os.path.join(clone1path, 'file.txt'))


def test_clonetopath_recurses_submodules(tmpdir, monkeypatch):
    """
    Ensure that clonetopath() uses --recurse-submodules so that submodules are
    initialised and checked out in the clone.
    """
    from homely._vcs.git import Repo

    # allow local file:// cloning for submodules in this test
    monkeypatch.setenv('GIT_CONFIG_COUNT', '1')
    monkeypatch.setenv('GIT_CONFIG_KEY_0', 'protocol.file.allow')
    monkeypatch.setenv('GIT_CONFIG_VALUE_0', 'always')

    # create a repo that will be used as a submodule
    subpath = makegitrepo(tmpdir, 'subrepo')

    # create a parent repo that adds subrepo as a submodule
    parentpath = makegitrepo(tmpdir, 'parent')
    check_call(
        GIT + ['submodule', 'add', subpath, 'libs/the_submodule'],
        cwd=parentpath,
    )
    check_call(GIT + ['commit', '-m', 'Added submodule'], cwd=parentpath)

    # clone via Repo.clonetopath()
    parentrepo = Repo.frompath(parentpath)
    clonepath = os.path.join(tmpdir, 'clone')
    parentrepo.clonetopath(clonepath)

    # the submodule should already be initialised and checked out
    sub_readme = Path(clonepath) / 'libs/the_submodule' / 'README.md'
    assert sub_readme.exists()


def test_repo_object_recognises_git_repos():
    from homely._vcs.git import Repo

    repo1 = Repo.frompath('https://github.com/johnsmith/example.git')
    assert repo1.iscanonical is True
    assert repo1.isremote is True
    assert repo1.suggestedlocal == 'example'
    assert repo1._canonical == 'https://github.com/johnsmith/example.git'

    repo2 = Repo.frompath('git@github.com:johnsmith/example.git')
    assert repo2.iscanonical is False
    assert repo2.isremote is True
    assert repo1.suggestedlocal == 'example'
    assert repo2._canonical == 'https://github.com/johnsmith/example.git'
