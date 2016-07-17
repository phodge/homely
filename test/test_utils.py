import os

from homely._utils import isnecessarypath


def test_paths(tmpdir):
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
