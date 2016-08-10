import os
import subprocess
import re
import pytest

from pytest import homelyroot


HOMELY = ['python3',
            os.path.join(homelyroot, 'bin', 'homely'),
            '--no-interactive',
            '--verbose',
            # use fragile mode so that warnings will raise an exception instead
            '--fragile',
            ]


@pytest.fixture(scope="function")
def HOME(tmpdir):
    home = os.path.join(tmpdir, 'john')
    os.mkdir(home)
    return home


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


def getsystemfn(homedir):
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




def pytest_namespace():
    return dict(
        TestRepo=TestRepo,
        getsystemfn=getsystemfn,
        checkrepolist=checkrepolist,
        HOMELY=HOMELY,
    )
