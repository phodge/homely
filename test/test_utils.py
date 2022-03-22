import os

import pytest


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


def test_time_interval_to_delta():
    from datetime import timedelta

    from homely._utils import _time_interval_to_delta

    # simple conversions
    assert _time_interval_to_delta('1h') == timedelta(hours=1)
    assert _time_interval_to_delta('27h') == timedelta(hours=27)
    assert _time_interval_to_delta('5d') == timedelta(days=5)
    assert _time_interval_to_delta('1125d') == timedelta(days=1125)
    assert _time_interval_to_delta('3w') == timedelta(weeks=3)
    assert _time_interval_to_delta('52w') == timedelta(weeks=52)

    # leading zeros are ignored
    assert _time_interval_to_delta('05d') == timedelta(days=5)

    # zero is technically valid
    assert _time_interval_to_delta('0d') == timedelta(seconds=0)

    # you can also pass a regular timedelta and get it back
    assert _time_interval_to_delta(timedelta(minutes=125)) == timedelta(minutes=125)

    def assert_invalid(invalid_value):
        with pytest.raises(ValueError, match="Invalid time interval"):
            _time_interval_to_delta(invalid_value)

    # negative values are invalid
    assert_invalid('-1h')
    # no number is not allowed
    assert_invalid('w')
    # no quantity is not allowed
    assert_invalid('5')
    # invalid type not allowed
    assert_invalid('5z')

    # ordinary integers are not allowed, but it raises a TypeError instead
    with pytest.raises(TypeError):
        _time_interval_to_delta(5)
