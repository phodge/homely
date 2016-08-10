# TODO: rename this file so that py.test finds it automatically
import os
import subprocess
import re

import pytest
from pytest import homelyroot, contents


HOMELY = ['python3',
          os.path.join(homelyroot, 'bin', 'homely'),
          '--no-interactive',
          '--verbose',
          # use fragile mode so that warnings will raise an exception instead
          '--fragile',
          ]


NEXT_ID = 1


class TestRepo(object):
    def __init__(self, tmpdir, name):
        import hashlib
        import datetime
        from homely._vcs.testhandler import MARKERFILE
        self._tmpdir = tmpdir
        self._name = name
        self.remotepath = os.path.join(tmpdir, name)
        self.url = 'homely.test.repo://%s' % self.remotepath
        os.mkdir(self.remotepath)
        global NEXT_ID
        with open(os.path.join(self.remotepath, MARKERFILE), 'w') as f:
            timestr = str(datetime.datetime.now())
            h = hashlib.sha1(timestr.encode('utf-8')).hexdigest()
            self.repoid = "%d-%s" % (NEXT_ID, h)
            f.write(self.repoid)
            NEXT_ID += 1

    def installedin(self, HOME):
        from homely._vcs.testhandler import Repo
        remote = Repo.frompath(self.remotepath)
        localdir = os.path.join(HOME, self._name)
        if os.path.exists(localdir):
            local = Repo.frompath(localdir)
            if local:
                return local.getrepoid() == remote.getrepoid()
        return False

    def getrepoid(self):
        from homely._vcs.testhandler import MARKERFILE
        with open(self.remotepath + '/' + MARKERFILE, 'r') as f:
            return f.read().strip()

    def suggestedlocal(self, HOME):
        return os.path.join(HOME, self._name)


def _getsystemfn(homedir):
    env = os.environ.copy()
    env["HOME"] = homedir

    def system(cmd, cwd=None, capture=False, expecterror=False):
        try:
            output = subprocess.check_output(cmd,
                                             cwd=cwd,
                                             env=env,
                                             stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as err:
            if not expecterror:
                print('$', ' \\\n    '.join([
                    ("'%s'" % arg.replace("'", "''")
                     if not re.match(r"[a-zA-Z0-9_\-.:/~$]", arg)
                     else arg)
                    for arg in cmd
                ]))
                print(err.output.decode('utf-8'))
                raise
        else:
            if capture:
                assert not expecterror
                return output.decode('utf-8')
            if expecterror:
                print('$', ' \\\n    '.join([
                    ("'%s'" % arg.replace("'", "''")
                     if not re.match(r"[a-zA-Z0-9_\-.:/~$]", arg)
                     else arg)
                    for arg in cmd
                ]))
                print(output.decode('utf-8'))
                raise Exception("Expected this command to fail")

    return system


def checkrepolist(HOME, systemfn, expected):
    # turn expected into a dict for easy lookup
    expected = {r.getrepoid(): r for r in expected}
    found = set()

    cmd = HOMELY + [
        'repolist',
        '--format=%(repoid)s|%(localpath)s',
    ]
    output = systemfn(cmd, capture=True)
    for line in output.split("\n"):
        if line:
            id_, local = line.split('|')
            assert id_ not in found
            repo = expected[id_]
            assert local == repo.suggestedlocal(HOME)
            #assert remote == repo.url
            found.add(id_)

    for id_ in expected:
        if id_ not in found:
            raise Exception("homely repolist is missing repo %s: %s" % (
                id_, expected[id_].url))


@pytest.fixture(scope="function")
def HOME(tmpdir):
    home = os.path.join(tmpdir, 'john')
    os.mkdir(home)
    return home


def test_homely_update_check(tmpdir):
    raise Exception("TODO: test all aspects of 'homely updatecheck'")  # noqa


def test_homely_add_repolist(tmpdir, HOME):
    system = _getsystemfn(HOME)

    # make a fake repo - create a dir, a folder, and a symlink
    repo1 = TestRepo(tmpdir, 'repo1')
    homedir1 = os.path.join(HOME, 'dir1')
    homelink1 = os.path.join(HOME, 'link1')
    homedir1file = os.path.join(homelink1, 'file.txt')
    assert not os.path.exists(homedir1)
    assert not os.path.islink(homelink1)
    contents(repo1.remotepath + '/HOMELY.py',
             """
             from homely.general import mkdir, symlink, lineinfile
             mkdir('~/dir1')
             symlink('~/dir1', '~/link1')
             lineinfile('~/link1/file.txt', 'Hello World')
             """)

    # add the repo and ensure that everything was created as expected
    system(HOMELY + ['add', repo1.url])

    assert repo1.installedin(HOME)
    assert os.path.isdir(homedir1)
    assert os.path.islink(homelink1)
    assert os.readlink(homelink1) == os.path.realpath(homedir1)
    assert contents(homedir1file) == "Hello World\n"

    # make another repo that creates more things
    repo2 = TestRepo(tmpdir, 'repo2')
    repo2file = os.path.join(HOME, 'file2.txt')
    assert not os.path.exists(repo2file)
    contents(repo2.remotepath + '/HOMELY.py',
             """
             from homely.general import lineinfile
             lineinfile('~/file2.txt', 'Hey There')
             """)
    system(HOMELY + ['add', repo2.url])
    assert repo2.installedin(HOME)
    assert contents(repo2file, "Hey There\n")

    checkrepolist(HOME, system, [repo1, repo2])

    # a 3rd repo, but we're going to clone it into our home dir manually
    repo3 = TestRepo(tmpdir, 'repo3')
    contents(repo3.remotepath + '/HOMELY.py',
             """
             from homely.general import lineinfile
             lineinfile('~/r3.txt', 'From R3')
             """)
    # where would it go in the home dir?
    localrepo3 = os.path.join(HOME, 'repo3')
    # use a Repo instance to clone it into our home dir manually
    from homely._vcs.testhandler import Repo
    Repo.frompath(repo3.url).clonetopath(localrepo3)

    # test adding a repo from the local dir
    assert not os.path.exists(HOME + '/r3.txt')
    system(HOMELY + ['add', localrepo3])
    assert contents(HOME + '/r3.txt') == 'From R3\n'
    checkrepolist(HOME, system, [repo1, repo2, repo3])

    # test that you can't add the same repo again
    system(HOMELY + ['add', repo2.url])
    checkrepolist(HOME, system, [repo1, repo2, repo3])


def test_homely_remove(tmpdir, HOME):
    system = _getsystemfn(HOME)

    def _addfake(name, createfile):
        # create a fake repo and add it
        tr = TestRepo(tmpdir, name)
        tf = os.path.join(HOME, createfile)
        contents(tr.remotepath + '/HOMELY.py',
                 """
                 from homely.general import lineinfile
                 lineinfile('~/%s', 'Hello from %s')
                 """ % (createfile, name))
        assert not os.path.exists(tf)
        system(HOMELY + ['add', tr.url])
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
    system(HOMELY + ['remove', r1.repoid], expecterror=True)
    checkrepolist(HOME, system, [r1, r2, r3])

    # Check that the repo can be removed without --force once it has
    # disappeared from local disk. Note that because we use --update here, the
    # file will be removed from disk
    import shutil
    shutil.rmtree(os.path.join(HOME, 'repo1'))
    print(system(HOMELY + ['remove', r1.repoid, '--update'], capture=True))
    checkrepolist(HOME, system, [r2, r3])
    assert not os.path.exists(HOME + '/file1.txt')
    assert contents(HOME + '/file2.txt', "Hello from repo2\n")
    assert contents(HOME + '/file3.txt', "Hello from repo3\n")

    # Test removing multiple repos, but using local path this time
    # Note that because we don't use --update, the created files will still be
    # sitting around on disk
    system(HOMELY + ['remove', '~/repo2', '~/repo3', '--force'])
    checkrepolist(HOME, system, [])
    assert not os.path.exists(HOME + '/repo1')
    # repo2 and repo3 are stilling going to hang around on disk
    assert os.path.exists(HOME + '/repo2')
    assert os.path.exists(HOME + '/repo3')
    assert not os.path.exists(HOME + '/file1.txt')
    assert contents(HOME + '/file2.txt', "Hello from repo2\n")
    assert contents(HOME + '/file3.txt', "Hello from repo3\n")


def test_homely_update(HOME, tmpdir):
    system = _getsystemfn(HOME)

    def _addfake(name, createfile):
        # create a fake repo and add it
        tr = TestRepo(tmpdir, name)
        tf = os.path.join(HOME, createfile)
        contents(tr.remotepath + '/HOMELY.py',
                 """
                 from homely.general import lineinfile
                 lineinfile('~/%s', 'Hello from %s')
                 """ % (createfile, name))
        assert not os.path.exists(tf)
        system(HOMELY + ['add', tr.url])
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
    print(system(HOMELY + ['update'], capture=True))
    assert contents(HOME + '/file1.txt') == "AAA\n"
    assert contents(HOME + '/file2.txt') == "AAA\n"
    assert contents(HOME + '/file3.txt') == "AAA\n"

    # modify all the repos again
    contents(r1.remotepath + '/HOMELY.py', template % ('~/file1.txt', 'BBB'))
    contents(r2.remotepath + '/HOMELY.py', template % ('~/file2.txt', 'BBB'))
    contents(r3.remotepath + '/HOMELY.py', template % ('~/file3.txt', 'BBB'))
    # run an update again, but only do it with the 2nd repo
    system(HOMELY + ['update', '~/repo2'])
    # 1st and 3rd repos haven't been rerun
    assert contents(HOME + '/file1.txt') == "AAA\n"
    assert contents(HOME + '/file3.txt') == "AAA\n"
    # NOTE that the cleanup of the 2nd repo doesn't happen when we're doing a
    # single repo
    assert contents(HOME + '/file2.txt') == "AAA\nBBB\n"

    # run an update, but specify all repos - this should be enough to trigger
    # the cleanup
    system(HOMELY + ['update', '~/repo1', '~/repo3', '~/repo2'])
    assert contents(HOME + '/file1.txt') == "BBB\n"
    assert contents(HOME + '/file2.txt') == "BBB\n"
    assert contents(HOME + '/file3.txt') == "BBB\n"

    # modify the repos again, but run update with --nopull so that we don't get
    # any changes
    contents(r1.remotepath + '/HOMELY.py', template % ('~/file1.txt', 'CCC'))
    contents(r2.remotepath + '/HOMELY.py', template % ('~/file2.txt', 'CCC'))
    contents(r3.remotepath + '/HOMELY.py', template % ('~/file3.txt', 'CCC'))
    system(HOMELY + ['update', '~/repo1', '--nopull'])
    assert contents(HOME + '/file1.txt') == "BBB\n"
    assert contents(HOME + '/file2.txt') == "BBB\n"
    assert contents(HOME + '/file3.txt') == "BBB\n"
    system(HOMELY + ['update', '--nopull'])
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
    system(HOMELY + ['update', '~/repo1', '-o', 'partE'])
    assert contents(HOME + '/file1.txt') == "BBB\nEEE\nHHH\n"
    os.unlink(HOME + '/file1.txt')
    system(HOMELY + ['update', '~/repo1', '-o', 'partF', '-o', 'partG'])
    assert contents(HOME + '/file1.txt') == "FFF\nGGG\nHHH\n"
    system(HOMELY + ['update', '~/repo1', '-o', 'partF', '-o', 'partG'])
    assert contents(HOME + '/file1.txt') == "FFF\nGGG\nHHH\n"

    # ensure that --only isn't allowed with multiple repos
    system(HOMELY + ['update', '~/repo1', '~/repo2', '-o', 'something'],
           expecterror=True)

    # test that cleanup stuff doesn't happen when --only is used
    system(HOMELY + ['remove', '~/repo2', '~/repo3', '--force'])
    assert os.path.exists(HOME + '/file2.txt')
    assert os.path.exists(HOME + '/file3.txt')
    # note that this test also proves that you can use --only without naming a
    # repo as long as you only have one repo
    system(HOMELY + ['update', '-o', 'partE'])
    assert contents(HOME + '/file1.txt') == "FFF\nGGG\nHHH\nEEE\n"
    # these files are still hanging around because we keep using --only
    assert os.path.exists(HOME + '/file2.txt')
    assert os.path.exists(HOME + '/file3.txt')

    # finally do an update without --only, and file1 and file2 will be cleaned
    # up
    system(HOMELY + ['update'])
    assert not os.path.exists(HOME + '/file2.txt')
    assert not os.path.exists(HOME + '/file3.txt')
