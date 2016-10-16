import os
import re
import sys
from subprocess import Popen, STDOUT, TimeoutExpired
from contextlib import contextmanager

from pytest import homelyroot, withtmpdir


def HOMELY(command):
    return [
        'python3',
        os.path.join(homelyroot, 'bin', 'homely'),
        command,
        '--neverprompt',
        '--verbose',
    ]


NEXT_ID = 1


class TempRepo(object):
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


def _getfakeenv(homedir):
    env = os.environ.copy()
    env["HOME"] = homedir
    # FIXME: we have to manually add all paths to $PYTHONPATH because python in
    # the subprocess tries looking for packages in our custom $HOME and it
    # doesn't work.
    env["PYTHONPATH"] = ":".join(sys.path)
    return env


def getsystemfn(homedir):
    env = _getfakeenv(homedir)

    @withtmpdir
    def system(cmd, cwd=None, expecterror=False, tmpdir=None):
        returncode = '<NOT SPAWNED>'
        try:
            stdoutpath = tmpdir + '/stdout'
            with open(stdoutpath, 'w') as stdout:
                sub = Popen(cmd,
                            cwd=cwd,
                            env=env,
                            stdout=stdout,
                            stderr=STDOUT)
                try:
                    returncode = sub.wait(1)
                except TimeoutExpired:
                    returncode = '<KILLED>'
                    sub.kill()
                    raise Exception("Command did not finish quickly enough")

                if returncode == 0:
                    if expecterror:
                        raise Exception("Expected exit(%d) but got clean exit" % expecterror)
                elif expecterror:
                    assert type(expecterror) is int
                    assert returncode == expecterror, ("Expected exit(%d) but got exit(%d)"
                                                       % (expecterror, returncode))
                else:
                    raise Exception("Program did not exit cleanly")
        except Exception:
            if cwd is not None:
                print('$ cd %s' % cwd)
            print(returncode, '$', ' \\\n    '.join([
                ("'%s'" % arg.replace("'", "''")
                    if not re.match(r"[a-zA-Z0-9_\-.:/~$]", arg)
                    else arg)
                for arg in cmd
            ]))
            print(open(stdoutpath).read())
            raise

        return open(stdoutpath, 'r').read()

    return system


def getjobstartfn(homedir):
    env = _getfakeenv(homedir)

    @contextmanager
    @withtmpdir
    def jobstart(cmd, tmpdir, cwd=None):
        outpath = tmpdir + '/stdout'
        errpath = tmpdir + '/stderr'
        proc = None
        failed = False
        retval = '<NOT SPAWNED>'
        try:
            with open(outpath, 'w') as stdout, open(errpath, 'w') as stderr:
                proc = Popen(cmd,
                             cwd=cwd,
                             env=env,
                             stdout=stdout,
                             stderr=stderr,
                             )
                try:
                    yield proc
                except Exception:
                    # has the background job died?
                    retval = proc.poll()
                    if retval is None:
                        # just kill the background job silently
                        proc.kill()
                        failed = False
                    else:
                        failed = True
                    raise

                # send an interupt to the background process
                retval = proc.poll()
                if retval is None:
                    try:
                        # give the process up to 2 seconds to finish
                        retval = proc.wait(1)
                    except TimeoutExpired:
                        # kill the background process if it didn't finish
                        retval = '<KILLED>'
                        proc.kill()
                        failed = True
                        raise Exception("Job had to be killed")
                failed = retval != 0
        finally:
            if failed:
                print('retval: %r' % (retval, ))
                with open(outpath, 'r') as stdout:
                    print('STDOUT:')
                    print(stdout.read())
                with open(errpath, 'r') as stderr:
                    print('STDERR:')
                    print(stderr.read())

    return jobstart


def checkrepolist(HOME, systemfn, expected):
    # turn expected into a dict for easy lookup
    expected = {r.getrepoid(): r for r in expected}
    found = set()

    cmd = HOMELY('repolist') + ['--format=%(repoid)s|%(localpath)s']
    output = systemfn(cmd)
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
        TempRepo=TempRepo,
        getsystemfn=getsystemfn,
        getjobstartfn=getjobstartfn,
        checkrepolist=checkrepolist,
        HOMELY=HOMELY,
    )
