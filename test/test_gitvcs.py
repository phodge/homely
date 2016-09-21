import re
import os
from subprocess import check_call

from pytest import contents


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
    https = 'https://github.com/johnsmith/example.git'

    tests = [
        'git@github.com:johnsmith/example.git',
        https,
    ]
    for repo_path in tests:
        repo = Repo.frompath(repo_path)
        assert repo.iscanonical == (repo_path == https)
        assert repo.isremote is True

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

    # FIXME: not sure why I have to close the main loop here when I didn't attach anything to it
    # ... :-(
    import asyncio
    asyncio.get_event_loop().close()
