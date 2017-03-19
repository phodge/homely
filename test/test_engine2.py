import os
import sys

import simplejson
from pytest import contents, gettmpfilepath


def test_engine_folder_cleanup(tmpdir):
    from homely._engine2 import Engine
    from homely.files import MakeDir

    # first thing ... test mkdir cleanup
    # a temporary file where the engine can store its config
    cfgpath = gettmpfilepath(tmpdir, '.json')

    d1 = os.path.join(tmpdir, 'dir1')
    d2 = os.path.join(tmpdir, 'dir2')
    d2a = os.path.join(d2, 'sub-a')
    d2a1 = os.path.join(d2a, 'supersub-1')
    d2a2 = os.path.join(d2a, 'supersub-2')

    # create the first directory
    e = Engine(cfgpath)
    e.run(MakeDir(d1))
    e.cleanup(e.RAISE)
    del e

    e = Engine(cfgpath)
    e.run(MakeDir(d1))
    e.run(MakeDir(d2))
    e.run(MakeDir(d2a))
    e.run(MakeDir(d2a1))
    e.run(MakeDir(d2a2))
    e.cleanup(e.RAISE)
    del e

    # all dirs should exist now
    check = [d1, d2, d2a, d2a1, d2a2]
    for d in check:
        assert os.path.exists(d)
    assert all(map(os.path.exists, check))

    # make a new engine and make ONLY d2a1 ... this should
    # be enough to keep everything but d1 and d2a2 alive
    e = Engine(cfgpath)
    e.run(MakeDir(d2a2))
    e.cleanup(e.POSTPONE)
    del e

    # all dirs should exist except for d1 and d2a1
    assert all(map(os.path.exists, [d2, d2a, d2a2]))
    assert not any(map(os.path.exists, [d1, d2a1]))

    # make a new engine, add nothing to it, this should be enough to blast away
    # all directories
    e = Engine(cfgpath)
    e.cleanup(e.RAISE)
    del e

    # all dirs are gone, EXCEPT FOR our original tmpdir, which our cleaners
    # were smart enough to leave behind
    assert not any(map(os.path.exists, [d1, d2, d2a, d2a1, d2a2]))
    assert os.path.exists(tmpdir)

    # FIXME: add a test to see what happens when we want to clean up a dir but
    # there's already files inside it ... we can add a test for BLASTAWAY mode
    # here I guess


def test_symlink_cleanup_interaction(tmpdir):
    from homely._engine2 import Engine
    from homely._errors import CleanupConflict
    from homely.files import MakeDir, MakeSymlink

    cfgpath = gettmpfilepath(tmpdir)

    d1 = os.path.join(tmpdir, 'dir1')
    l1 = os.path.join(tmpdir, 'link1')
    d1da = os.path.join(d1, 'dir-a')
    l1da = os.path.join(l1, 'dir-a')

    # basic symlink
    e = Engine(cfgpath)
    e.run(MakeDir(d1))
    e.run(MakeSymlink(d1, l1))
    e.cleanup(e.RAISE)
    del e

    # make sure they both exist, and the symlink has the correct target
    assert os.path.isdir(d1)
    assert os.path.islink(l1) and os.readlink(l1) == d1

    # mkdir() inside a symlink's target
    e = Engine(cfgpath)
    e.run(MakeDir(d1))
    e.run(MakeSymlink(d1, l1))
    e.run(MakeDir(l1da))
    e.cleanup(e.POSTPONE)
    del e

    # everything should exist, the symlink should have the correct target
    assert os.path.isdir(d1)
    assert os.path.islink(l1) and os.readlink(l1) == d1
    assert os.path.isdir(d1da) and os.path.isdir(l1da)

    # if we try and get rid of the symlink now, the cleaner will hang around
    # because it can't garbage collect the thing right now
    e = Engine(cfgpath)
    e.run(MakeDir(d1))
    e.run(MakeDir(l1da))
    try:
        e.cleanup(e.RAISE)
    except CleanupConflict as err:
        # conflict should be over the symlink's path
        assert err.conflictpath == l1
        # the path should still be needed by `l1da`
        assert err.pathwanter == l1da
    else:
        raise Exception("Expected a cleanup error!")  # noqa
    del e

    # clean everything up now
    e = Engine(cfgpath)
    e.cleanup(e.RAISE)
    del e
    assert not any(map(os.path.exists, [d1, d1da, l1]))
    os.unlink(cfgpath)

    # now we try the opposite - symlink to a directory and try to clean up the
    # directory
    e = Engine(cfgpath)
    e.run(MakeDir(d1))
    e.run(MakeSymlink(d1, l1))
    e.cleanup(e.RAISE)
    del e
    assert os.path.isdir(d1)
    assert os.path.islink(l1) and os.readlink(l1) == d1

    # the engine will happily clean up the directory, even though there is a
    # symlink pointing to it ... symlinks don't care whether the target exists
    # or not
    e = Engine(cfgpath)
    e.run(MakeSymlink(d1, l1))
    e.cleanup(e.RAISE)
    del e

    # clean up everything now
    e = Engine(cfgpath)
    e.cleanup(e.RAISE)
    assert not any(map(os.path.exists, [d1, d1da, l1]))
    os.unlink(cfgpath)


def test_lineinfile_usage(tmpdir):
    from homely._engine2 import Engine
    from homely.files import WHERE_END, WHERE_TOP, LineInFile

    cfgpath = gettmpfilepath(tmpdir, '.json')

    f1 = gettmpfilepath(tmpdir)
    # make sure the following types of input raise exceptions
    bad = [
        "",  # empty line
        "something\n",  # a string containing a newline
        "   \t",  # a line containing nothing but whitespace
    ]
    for b in bad:
        try:
            LineInFile(f1, b)
        except Exception:
            # we got an exception
            pass
        else:
            raise Exception("LineInFile should not accept input %s" % repr(b))

    # make sure LineInFile() doesn't override an existing line
    contents(f1, "AAA\nBBB\n")
    e = Engine(cfgpath)
    e.run(LineInFile(f1, "BBB"))
    assert contents(f1) == "AAA\nBBB\n"

    # make sure LineInFile() puts a new line at the end of the file by default
    e = Engine(cfgpath)
    e.run(LineInFile(f1, "CCC"))
    assert contents(f1) == "AAA\nBBB\nCCC\n"

    # make sure LineInFile() doesn't move a line unnecessarily
    e = Engine(cfgpath)
    e.run(LineInFile(f1, "BBB"))
    assert contents(f1) == "AAA\nBBB\nCCC\n"

    # make sure LineInFile() can move a line to the TOP of the file
    e = Engine(cfgpath)
    e.run(LineInFile(f1, "BBB", WHERE_TOP))
    assert contents(f1) == "BBB\nAAA\nCCC\n"

    # make sure LineInFile() can move a line to the END of the file
    e = Engine(cfgpath)
    e.run(LineInFile(f1, "BBB", WHERE_END))
    assert contents(f1) == "AAA\nCCC\nBBB\n"

    # make sure LineInFile() doesn't blow away empty lines
    # - adding to end of file
    contents(f1, "\n\n", strip=False)
    e = Engine(cfgpath)
    e.run(LineInFile(f1, "AAA"))
    assert contents(f1) == "\n\nAAA\n"
    # - adding to start of file
    contents(f1, "\n\n", strip=False)
    e = Engine(cfgpath)
    e.run(LineInFile(f1, "AAA", WHERE_TOP))
    assert contents(f1) == "AAA\n\n\n"
    # - when restoring the file
    e = Engine(cfgpath)
    e.cleanup(e.RAISE)
    del e
    assert contents(f1) == "\n\n"
    # - replacing something in the middle
    contents(f1, "\n\nAAA\n\n\n", strip=False)
    e = Engine(cfgpath)
    e.run(LineInFile(f1, "AAA"))
    assert contents(f1) == "\n\nAAA\n\n\n"

    # make sure LineInFile() respects existing line endings
    # NOTE: in python2 we always use Universal Newlines when reading the file,
    # which tricks us into using "\n" when writing the file
    if sys.version_info[0] > 2:
        # - windows
        contents(f1, "AAA\r\nBBB\r\n")
        e = Engine(cfgpath)
        e.run(LineInFile(f1, "CCC"))
        assert contents(f1) == "AAA\r\nBBB\r\nCCC\r\n"
        # - mac
        contents(f1, "AAA\rBBB\r")
        e = Engine(cfgpath)
        e.run(LineInFile(f1, "BBB", WHERE_TOP))
        assert contents(f1) == "BBB\rAAA\r"

    # make sure a file that starts empty is left empty after cleanup
    contents(f1, "")
    e = Engine(cfgpath)
    e.run(LineInFile(f1, "AAA"))
    assert contents(f1) == "AAA\n"
    e = Engine(cfgpath)
    e.cleanup(e.RAISE)
    assert contents(f1) == ""


def test_lineinfile_cleanup_interaction(tmpdir):
    from homely._engine2 import Engine
    from homely.files import MakeDir, LineInFile

    # a temporary file where the engine can store its config
    cfgpath = gettmpfilepath(tmpdir, '.json')
    f1 = os.path.join(tmpdir, 'f1.txt')
    d1 = os.path.join(tmpdir, 'f1.txt.dir')
    d1f1 = os.path.join(d1, 'f-1.txt')
    d2 = os.path.join(tmpdir, 'dir2')
    d2f1 = os.path.join(d2, 'f-1.txt')
    d3 = os.path.join(tmpdir, 'dir3')
    d3d1 = os.path.join(d3, 'sub-1')
    d3d2 = os.path.join(d3, 'sub-2')
    d3d1f1 = os.path.join(d3d1, 'somefile.txt')
    d3d2f1 = os.path.join(d3d2, 'somefile.txt')

    # make the dir and the file, make sure they both exist
    e = Engine(cfgpath)
    e.run(LineInFile(f1, "AAA"))
    e.run(MakeDir(d1))
    e.cleanup(e.RAISE)
    del e
    assert os.path.isdir(d1)
    assert contents(f1) == "AAA\n"

    # remake the engine without the dir, make sure the dir isn't kept around by
    # the file
    e = Engine(cfgpath)
    e.run(LineInFile(f1, "AAA"))
    e.cleanup(e.POSTPONE)
    del e
    assert not os.path.exists(d1)
    assert contents(f1) == "AAA\n"

    # make a new file in the directory, make sure they take ownership of the
    # directory
    e = Engine(cfgpath)
    e.run(MakeDir(d1))
    e.run(LineInFile(d1f1, "AAA"))
    e.run(LineInFile(d1f1, "BBB"))
    e.cleanup(e.POSTPONE)
    del e
    # the directory should still exist, the old file should not, and the new
    # file should contain both lines
    assert os.path.isdir(d1)
    assert not os.path.exists(f1)
    assert contents(d1f1) == "AAA\nBBB\n"

    # if we do the same thing again but without the MakeDir, we should get
    # exactly the same result
    e = Engine(cfgpath)
    e.run(LineInFile(d1f1, "AAA"))
    e.run(LineInFile(d1f1, "BBB"))
    e.cleanup(e.POSTPONE)
    del e
    # the directory should still exist, the old file should not, and the new
    # file should contain both lines
    assert os.path.isdir(d1)
    assert not os.path.exists(f1)
    assert contents(d1f1) == "AAA\nBBB\n"

    # the important thing to note is that the engine still knows that it needs
    # to clean up the directory later
    e = Engine(cfgpath)
    assert e.pathstoclean()[d1] == e.TYPE_FOLDER_ONLY
    del e

    # if we get rid of one of the LineInFile() items, the file and dir still
    # hang around
    e = Engine(cfgpath)
    e.run(LineInFile(d1f1, "AAA"))
    e.cleanup(e.POSTPONE)
    del e
    assert contents(d1f1) == "AAA\n"

    # now, when we get rid of the last LineInFile() items, everything will be
    # cleaned up
    e = Engine(cfgpath)
    e.cleanup(e.RAISE)
    del e
    assert not os.path.exists(d1)
    os.unlink(cfgpath)

    # if we make a dir ourselves, a LineInFile() will not clean it up
    assert not os.path.exists(d2)
    os.mkdir(d2)
    e = Engine(cfgpath)
    e.run(LineInFile(d2f1, "AAA"))
    del e
    assert contents(d2f1) == "AAA\n"
    e = Engine(cfgpath)
    e.cleanup(e.RAISE)
    del e
    assert os.path.isdir(d2) and not os.path.exists(d2f1)
    os.rmdir(d2)

    # if we make a file ourselves, LineInFile() will not try to clean it up
    assert not os.path.exists(f1)
    contents(f1, "")
    e = Engine(cfgpath)
    e.run(LineInFile(f1, "AAA"))
    del e
    assert contents(f1) == "AAA\n"
    e = Engine(cfgpath)
    e.cleanup(e.RAISE)
    del e
    assert contents(f1) == ""

    # if two LineInFile() items share a parent dir (even the parent dir's
    # parent, and so on), and that parent dir was made by a MakeDir(), then it
    # gets cleaned up eventually when both of the LineInFile() items go away
    # - create the folder structure
    assert not os.path.exists(d3)
    os.unlink(cfgpath)
    e = Engine(cfgpath)
    e.run(MakeDir(d3))
    e.run(MakeDir(d3d1))
    e.run(MakeDir(d3d2))
    e.cleanup(e.RAISE)
    del e
    assert all(map(os.path.isdir, [d3, d3d1, d3d2]))
    assert not any(map(os.path.exists, [d3d1f1, d3d2f1]))
    # - scrap the folder structure, but make files that depend on those folders
    e = Engine(cfgpath)
    e.run(LineInFile(d3d1f1, "AAA"))
    e.run(LineInFile(d3d2f1, "BBB"))
    e.cleanup(e.POSTPONE)
    del e
    assert contents(d3d1f1) == "AAA\n" and contents(d3d2f1) == "BBB\n"
    # - scrap the first file, and check that only things needed for the 2nd
    # file remain
    e = Engine(cfgpath)
    e.run(LineInFile(d3d2f1, "BBB"))
    e.cleanup(e.POSTPONE)
    del e
    assert not os.path.exists(d3d1)
    assert contents(d3d2f1) == "BBB\n"
    # - scrap the 2nd file and make sure everything else disappears
    e = Engine(cfgpath)
    e.cleanup(e.RAISE)
    del e
    assert not os.path.exists(d3)


def test_blockinfile_lineinfile_cleanup_interaction(tmpdir):
    '''
    Test that when a LineInFile is cleaned up, any other LineInFile() or
    BlockInFile() that affected the same file, needs a chance to re-check
    whether it is still valid. If *any* of the remaining Helpers needs to be
    reapplied, then they *all* need to be reapplied.
    '''
    from homely._engine2 import Engine
    from homely.files import LineInFile, BlockInFile

    cfgpath = gettmpfilepath(tmpdir, '.json')
    f1 = gettmpfilepath(tmpdir, '.txt')

    def bif(filename, lines):
        # shorthand constructor for BlockInFile()
        return BlockInFile(filename, lines, None, "PRE", "POST")

    # check that a LineInFile followed by a BlockInFile that both try to add
    # the same line will result in the file containing both things, even if
    # you rerun it many times
    for i in range(3):
        e = Engine(cfgpath)
        e.run(LineInFile(f1, "AAA"))
        e.run(bif(f1, ["AAA"]))
        e.cleanup(e.RAISE)
        del e
        assert contents(f1) == "AAA\nPRE\nAAA\nPOST\n"

    # check that a BlockInFile followed by a LineInFile that adds the same line
    # will result in the LineInFile not having any effect, even if you rerun it
    # many times
    os.unlink(f1)
    for i in range(3):
        e = Engine(cfgpath)
        e.run(bif(f1, ["AAA"]))
        e.run(LineInFile(f1, "AAA"))
        e.cleanup(e.RAISE)
        del e
        assert contents(f1) == "PRE\nAAA\nPOST\n"

    # check that removing the LineInFile doesn't destroy the contents added by
    # BlockInFile
    e = Engine(cfgpath)
    e.run(bif(f1, ["AAA"]))
    e.cleanup(e.RAISE)
    del e
    assert contents(f1) == "PRE\nAAA\nPOST\n"

    # put both things back in ...
    e = Engine(cfgpath)
    e.run(bif(f1, ["AAA"]))
    e.run(LineInFile(f1, "AAA"))
    e.cleanup(e.RAISE)
    del e
    assert contents(f1) == "PRE\nAAA\nPOST\n"

    # test that the LineInFile keeps itself there after removing the
    # BlockInFile
    e = Engine(cfgpath)
    e.run(LineInFile(f1, "AAA"))
    e.cleanup(e.RAISE)
    del e
    assert contents(f1) == "AAA\n"


def test_cleanup_everything(tmpdir):
    '''
    test that recreating the engine, running nothing on it, then calling
    cleanup() will remove all of things that might be lying around
    '''
    from homely._engine2 import Engine
    from homely.files import MakeDir, MakeSymlink, LineInFile

    cfgpath = gettmpfilepath(tmpdir, '.json')
    d1 = gettmpfilepath(tmpdir, '.d')
    d1f1 = os.path.join(d1, 'sub-file.txt')
    l1 = gettmpfilepath(tmpdir, '.lnk')

    e = Engine(cfgpath)
    e.run(MakeDir(d1))
    e.run(MakeSymlink(d1, l1))
    e.run(LineInFile(d1f1, "AAA"))
    e.cleanup(e.RAISE)
    del e

    assert os.path.isdir(d1)
    assert contents(d1f1, "AAA\n")
    assert os.path.islink(l1) and os.readlink(l1) == d1

    # if we recreate the engine with nothing on it, it should clean everything
    # up
    e = Engine(cfgpath)
    e.cleanup(e.RAISE)

    assert not os.path.exists(d1)
    assert not os.path.islink(l1)


def test_partial_run_cleanup(tmpdir):
    from homely._engine2 import Engine
    from homely.files import MakeDir

    cfgpath = gettmpfilepath(tmpdir, '.json')
    d1 = os.path.join(tmpdir, 'dir1')
    d2 = os.path.join(tmpdir, 'dir2')

    # simulate adding our first repo which just creates d1
    e = Engine(cfgpath)
    e.run(MakeDir(d1))
    e.cleanup(e.RAISE)
    del e
    assert os.path.isdir(d1) and not os.path.isdir(d2)

    # simulate adding a 2nd repo that would just created 2 ... this shouldn't
    # trigger a cleanup though
    e = Engine(cfgpath)
    e.run(MakeDir(d2))
    del e
    assert os.path.isdir(d1) and os.path.isdir(d2)

    # pretend that the first repo is removed, and do a full update
    e = Engine(cfgpath)
    e.run(MakeDir(d2))
    e.cleanup(e.RAISE)
    assert not os.path.isdir(d1) and os.path.isdir(d2)


def test_writefile_usage(tmpdir):
    from homely._engine2 import Engine
    from homely.files import LineInFile
    from homely.general import WriteFile, writefile

    cfgpath = gettmpfilepath(tmpdir, '.json')

    # the file we'll be playing with
    f1 = os.path.join(tmpdir, 'f1.txt')
    f2 = os.path.join(tmpdir, 'f2.txt')
    f3 = os.path.join(tmpdir, 'f3.json')

    # use LineInFile to put stuff in the file
    e = Engine(cfgpath)
    e.run(LineInFile(f1, 'AAA'))
    e.run(LineInFile(f1, 'BBB'))
    del e
    assert contents(f1) == "AAA\nBBB\n"

    # now use WriteFile() to give it new contents
    e = Engine(cfgpath)
    e.run(WriteFile(f1, "BBB\nCCC\n"))
    assert contents(f1) == "BBB\nCCC\n"
    e.cleanup(e.RAISE)
    del e
    # make sure the cleanup didn't blow anything away
    assert contents(f1) == "BBB\nCCC\n"

    # make sure the file is removed on cleanup
    e = Engine(cfgpath)
    e.cleanup(e.RAISE)
    del e
    assert not os.path.exists(f1)

    contents(f2, "Already here!\n")
    assert os.path.exists(f2)
    e = Engine(cfgpath)
    e.run(WriteFile(f2, "AAA\nBBB\n", canoverwrite=True))
    e.cleanup(e.RAISE)
    del e
    assert contents(f2) == "AAA\nBBB\n"

    # running a LineInFile() won't clean up what's already there
    e = Engine(cfgpath)
    e.run(LineInFile(f2, "CCC"))
    e.cleanup(e.RAISE)
    del e
    assert contents(f2) == "AAA\nBBB\nCCC\n"

    # note that removing the LineInFile() doesn't clean up the file because we
    # no longer know whether the user put their config in there
    e = Engine(cfgpath)
    e.cleanup(e.RAISE)
    del e
    assert not os.path.exists(f1)
    assert os.path.exists(f2)

    # now test the context manager
    import homely._engine2
    e = Engine(cfgpath)
    homely._engine2._ENGINE = e
    data = {"z": [3, 4, 5, True], "y": "Hello world", "x": None}
    with writefile(f3) as f:
        if sys.version_info[0] < 3:
            f.write(simplejson.dumps(data, ensure_ascii=False))
        else:
            f.write(simplejson.dumps(data))
    e.cleanup(e.RAISE)
    del e
    assert os.path.exists(f3)
    with open(f3, 'r') as f:
        assert simplejson.loads(f.read()) == data

    # prove that the WriteFile() disappearing results in the file being removed
    e = Engine(cfgpath)
    e.cleanup(e.RAISE)
    del e
    assert not os.path.exists(f3)
