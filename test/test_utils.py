import os


def test_paths(tmpdir, HOME):
    from homely._utils import isnecessarypath
    l1 = os.path.join(tmpdir, 'link1')
    d1 = os.path.join(tmpdir, 'dir1')
    d1s = os.path.join(d1, 'subdir')
    l1s = os.path.join(l1, 'subdir')

    os.mkdir(d1)
    os.mkdir(d1s)
    os.symlink(d1, l1)
    assert os.path.isdir(l1s)

    assert isnecessarypath(tmpdir, d1)
    assert isnecessarypath(tmpdir, l1)
    assert isnecessarypath(l1, l1s)
    assert isnecessarypath(d1, l1s)
    assert not isnecessarypath(d1, l1)


fixed = [
    'http://www.foo.com/foo.txt',
    'git+ssh://git.example.com/example/bar',
    'git+ssh://foo@example.com/example/bar',
    'homely.test.repo:///foo/something/bar',
]


def test_expansion_homepath(tmpdir):
    from homely._utils import _homepath2real

    # test how various paths expand out to the home dir
    os.environ["HOME"] = tmpdir

    dir1 = os.path.join(tmpdir, 'dir1')
    link1 = tmpdir + "/link1"

    os.mkdir(dir1)
    os.symlink(dir1, link1)

    assert _homepath2real('.vimrc') == tmpdir + '/.vimrc'
    assert _homepath2real('.vimrc') == tmpdir + '/.vimrc'
    assert _homepath2real('bin/ack') == tmpdir + '/bin/ack'
    assert _homepath2real('link1/foo.txt') == tmpdir + '/link1/foo.txt'
    assert _homepath2real('/etc/hosts') == '/etc/hosts'

    assert _homepath2real('~/.vimrc') == tmpdir + '/.vimrc'
    assert _homepath2real('$HOME/.vimrc') == tmpdir + '/.vimrc'
    assert _homepath2real('~/bin/ack') == tmpdir + '/bin/ack'

    # check that relative paths like '.' also work
    assert _homepath2real('..') == '..'
    assert _homepath2real('../foo') == '../foo'

    # these should all raise errors
    badpaths = ['.', 'bin/', '/etc/']
    for path in badpaths:
        try:
            _homepath2real(path)
        except Exception:
            pass
        else:
            raise Exception("Expected an error from %r!" % path)

    for path in fixed:
        assert _homepath2real(path) == path


def test_expansion_repopath(tmpdir):
    from homely._utils import _repopath2real
    os.environ["HOME"] = tmpdir

    rdir = os.path.join(tmpdir, 'repo.git')

    # construct a fake repo
    from homely._vcs.testhandler import Repo
    repo = Repo(rdir, False, False, None)
    assert _repopath2real('foo.txt', repo) == rdir + '/foo.txt'
    assert _repopath2real('a/b/c.txt', repo) == rdir + '/a/b/c.txt'
    assert _repopath2real('/tmp/foo.txt', repo) == os.path.realpath('/tmp/foo.txt')
    # if '~' is included in the path then it will always expand out to $HOME
    assert _repopath2real('~/bin/foo.txt', repo) == tmpdir + '/bin/foo.txt'
    assert _repopath2real('$HOME/bin/foo.txt', repo) == tmpdir + '/bin/foo.txt'
    for path in fixed:
        assert _repopath2real(path, repo) == path
