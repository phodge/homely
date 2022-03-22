import functools
import os.path
import shutil
import sys
import tempfile

import pytest


@pytest.fixture(scope="function")
def HOME(tmpdir):
    old_home = os.environ['HOME']

    try:
        home = os.path.join(tmpdir, 'john')
        os.mkdir(home)
        # NOTE: homely._utils makes use of os.environ['HOME'], so we need to
        # destroy any homely modules that may have imported things based on this.
        # Essentially we blast away the entire module and reload it from scratch.
        for name in list(sys.modules.keys()):
            if name.startswith('homely.'):
                sys.modules.pop(name, None)
        os.environ['HOME'] = home
        yield home
    finally:
        os.environ['HOME'] = old_home


@pytest.fixture(scope="function")
def tmpdir(request):
    path = tempfile.mkdtemp()
    destructor = shutil.rmtree

    def destructor(path):
        print("rm -rf %s" % path)
        shutil.rmtree(path)
    request.addfinalizer(functools.partial(destructor, path))
    return os.path.realpath(path)


@pytest.fixture
def testrepo(HOME, tmpdir):
    from homely._test.system import TempRepo
    from homely._utils import saveconfig, RepoListConfig
    from homely._vcs import testhandler, Repo
    from homely._ui import addfromremote

    repo = TempRepo(tmpdir, 'cool-testrepo')

    handler: Repo = testhandler.Repo.frompath(repo.url)
    assert handler is not None
    localrepo, needpull = addfromremote(handler, None)

    with saveconfig(RepoListConfig()) as cfg:
        cfg.add_repo(localrepo)

    yield repo
