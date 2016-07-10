import os
import functools
import pytest
import shutil
import tempfile

from homely._changes import ChangeManager, WHERE_TOP


@pytest.fixture(scope="function")
def tmpdir(request):
    global NEXT_FILE
    path = tempfile.mkdtemp()
    request.addfinalizer(functools.partial(shutil.rmtree, path))
    return path


NEXT_FILE = 1


def gettmpfilepath(tmpdir):
    global NEXT_FILE
    tmppath = "%s/tmpfile-%03d.txt" % (tmpdir, NEXT_FILE)
    NEXT_FILE += 1
    return tmppath


def contents(path, new_content=None):
    if new_content is not None:
        with open(path, 'w') as f:
            f.write(new_content)
    assert os.path.exists(path)
    with open(path, 'r') as f:
        return f.read()


def test_add_remove_line(tmpdir):
    tmppath = gettmpfilepath(tmpdir)

    # file changes will be recorded here
    cfgpath = gettmpfilepath(tmpdir)

    # write out a file with beginning content
    contents(tmppath, "AAA\nBBB\nCCC\n")
    cm = ChangeManager(cfgpath)

    # add a new line to the file and check that it's still ok
    cm.lineinfile(tmppath, contents="DDD")
    cm.lineinfile(tmppath, contents="DDD")
    cm.lineinfile(tmppath, contents="DDD")
    assert contents(tmppath) == "AAA\nBBB\nCCC\nDDD\n"

    del cm

    # load up a new change manager with the old path, and do the same action
    oldcfg = contents(cfgpath)
    cm2 = ChangeManager(cfgpath)
    cm2.lineinfile(tmppath, contents="DDD")
    assert contents(tmppath) == "AAA\nBBB\nCCC\nDDD\n"

    # garbage collect the 2nd change manager ... the DDD line shouldn't be
    # collected because we added it a 2nd time
    cm2.cleanup()
    assert contents(tmppath) == "AAA\nBBB\nCCC\nDDD\n"

    # the list of file changes should be identical
    assert contents(cfgpath) == oldcfg

    del cm2

    # rearrange the contents of the file
    assert contents(tmppath) == "AAA\nBBB\nCCC\nDDD\n"
    assert contents(tmppath, "AAA\nDDD\nCCC\nBBB\n")

    # create a new change manager and allow it to restore the old file contents
    cm3 = ChangeManager(cfgpath)
    cm3.cleanup()

    # ensure the file contents are as expected
    assert contents(tmppath) == "AAA\nCCC\nBBB\n"


def test_add_remove_block(tmpdir):
    tmppath = gettmpfilepath(tmpdir)

    # changes will be recorded here:
    cfgpath = gettmpfilepath(tmpdir)

    # write out a file with beginning content
    contents(tmppath, "AAA\nBBB\n")
    cm = ChangeManager(cfgpath)

    # add a new block to the file and check that it's still ok
    pre = '#START1'
    post = '#END1'
    add = ['DDD', 'EEE']
    newblock = "%s\n%s\n%s\n" % (pre, "\n".join(add), post)
    cm.blockinfile(tmppath, pre, post, add)
    cm.blockinfile(tmppath, pre, post, add)
    cm.blockinfile(tmppath, pre, post, add)
    assert contents(tmppath) == "AAA\nBBB\n%s" % newblock

    del cm

    # append some new content to the file
    with open(tmppath, 'a') as fp:
        fp.write("ZZZ\n")

    # load up a new change manager with the old path, and do the same action,
    # but move the block at the start of the file
    cm2 = ChangeManager(cfgpath)
    cm2.blockinfile(tmppath, pre, post, add, where=WHERE_TOP)
    assert contents(tmppath) == "%sAAA\nBBB\nZZZ\n" % newblock

    # garbage collect the 2nd change manager ... the new block shouldn't be
    # collected because we added it to the top this time
    cm2.cleanup()
    assert contents(tmppath) == "%sAAA\nBBB\nZZZ\n" % newblock

    del cm2

    # create a new change manager and allow it to restore the old file contents
    cm3 = ChangeManager(cfgpath)
    cm3.cleanup()

    # ensure the file contents are as expected
    assert contents(tmppath) == "AAA\nBBB\nZZZ\n"
