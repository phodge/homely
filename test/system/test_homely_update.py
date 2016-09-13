import os

from pytest import getsystemfn, TempRepo, contents, HOMELY


def test_symlink_recreate(HOME, tmpdir):
    system = getsystemfn(HOME)

    def _addfake(name, createfile):
        # create a fake repo and add it
        tr = TempRepo(tmpdir, name)
        tf = os.path.join(tr.remotepath, createfile)
        with open(tf, 'w') as f:
            f.write('hello world')
        contents(tr.remotepath + '/HOMELY.py',
                 """
                 from homely.general import symlink
                 symlink('%s', '~/%s')
                 """ % (createfile, createfile))
        system(HOMELY('add') + [tr.url])
        local = '%s/%s' % (tr.suggestedlocal(HOME), createfile)
        assert os.readlink('%s/%s' % (HOME, createfile)) == local

    # add a fake repo
    _addfake('repo1', 'file1.txt')

    # try doing a homely update
    system(HOMELY('update'))


def test_homely_update(HOME, tmpdir):
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

    template = ("""
                from homely.general import lineinfile
                lineinfile(%r, %r)
                """)

    # add some fake repos
    r1 = _addfake('repo1', 'file1.txt')
    r2 = _addfake('repo2', 'file2.txt')
    r3 = _addfake('repo3', 'file3.txt')

    # update the repos slightly, run an update, ensure all changes have gone
    # through (including cleanup of old content)
    contents(r1.remotepath + '/HOMELY.py', template % ('~/file1.txt', 'AAA'))
    contents(r2.remotepath + '/HOMELY.py', template % ('~/file2.txt', 'AAA'))
    contents(r3.remotepath + '/HOMELY.py', template % ('~/file3.txt', 'AAA'))
    system(HOMELY('update'))
    assert contents(HOME + '/file1.txt') == "AAA\n"
    assert contents(HOME + '/file2.txt') == "AAA\n"
    assert contents(HOME + '/file3.txt') == "AAA\n"

    # modify all the repos again
    contents(r1.remotepath + '/HOMELY.py', template % ('~/file1.txt', 'BBB'))
    contents(r2.remotepath + '/HOMELY.py', template % ('~/file2.txt', 'BBB'))
    contents(r3.remotepath + '/HOMELY.py', template % ('~/file3.txt', 'BBB'))
    # run an update again, but only do it with the 2nd repo
    system(HOMELY('update') + ['~/repo2'])
    # 1st and 3rd repos haven't been rerun
    assert contents(HOME + '/file1.txt') == "AAA\n"
    assert contents(HOME + '/file3.txt') == "AAA\n"
    # NOTE that the cleanup of the 2nd repo doesn't happen when we're doing a
    # single repo
    assert contents(HOME + '/file2.txt') == "AAA\nBBB\n"

    # run an update, but specify all repos - this should be enough to trigger
    # the cleanup
    system(HOMELY('update') + ['~/repo1', '~/repo3', '~/repo2'])
    assert contents(HOME + '/file1.txt') == "BBB\n"
    assert contents(HOME + '/file2.txt') == "BBB\n"
    assert contents(HOME + '/file3.txt') == "BBB\n"

    # modify the repos again, but run update with --nopull so that we don't get
    # any changes
    contents(r1.remotepath + '/HOMELY.py', template % ('~/file1.txt', 'CCC'))
    contents(r2.remotepath + '/HOMELY.py', template % ('~/file2.txt', 'CCC'))
    contents(r3.remotepath + '/HOMELY.py', template % ('~/file3.txt', 'CCC'))
    system(HOMELY('update') + ['~/repo1', '--nopull'])
    assert contents(HOME + '/file1.txt') == "BBB\n"
    assert contents(HOME + '/file2.txt') == "BBB\n"
    assert contents(HOME + '/file3.txt') == "BBB\n"
    system(HOMELY('update') + ['--nopull'])
    assert contents(HOME + '/file1.txt') == "BBB\n"
    assert contents(HOME + '/file2.txt') == "BBB\n"
    assert contents(HOME + '/file3.txt') == "BBB\n"

    # split r1 into multiple sections and just do one of them
    contents(r1.remotepath + '/HOMELY.py',
             """
             from homely.general import lineinfile, section
             @section
             def partE():
                lineinfile('~/file1.txt', 'EEE')
             @section
             def partF():
                lineinfile('~/file1.txt', 'FFF')
             @section
             def partG():
                lineinfile('~/file1.txt', 'GGG')
             lineinfile('~/file1.txt', 'HHH')
             """)
    system(HOMELY('update') + ['~/repo1', '-o', 'partE'])
    assert contents(HOME + '/file1.txt') == "BBB\nEEE\nHHH\n"
    os.unlink(HOME + '/file1.txt')
    system(HOMELY('update') + ['~/repo1', '-o', 'partF', '-o', 'partG'])
    assert contents(HOME + '/file1.txt') == "FFF\nGGG\nHHH\n"
    system(HOMELY('update') + ['~/repo1', '-o', 'partF', '-o', 'partG'])
    assert contents(HOME + '/file1.txt') == "FFF\nGGG\nHHH\n"

    # ensure that --only isn't allowed with multiple repos
    system(HOMELY('update') + ['~/repo1', '~/repo2', '-o', 'something'], expecterror=1)

    # test that cleanup stuff doesn't happen when --only is used
    system(HOMELY('remove') + ['~/repo2', '~/repo3', '--force'])
    assert os.path.exists(HOME + '/file2.txt')
    assert os.path.exists(HOME + '/file3.txt')
    # note that this test also proves that you can use --only without naming a
    # repo as long as you only have one repo
    system(HOMELY('update') + ['-o', 'partE'])
    assert contents(HOME + '/file1.txt') == "FFF\nGGG\nHHH\nEEE\n"
    # these files are still hanging around because we keep using --only
    assert os.path.exists(HOME + '/file2.txt')
    assert os.path.exists(HOME + '/file3.txt')

    # finally do an update without --only, and file1 and file2 will be cleaned
    # up
    system(HOMELY('update'))
    assert not os.path.exists(HOME + '/file2.txt')
    assert not os.path.exists(HOME + '/file3.txt')
