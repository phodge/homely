import functools
import os.path
import shutil
import sys
import tempfile
from pathlib import Path
from textwrap import dedent
from typing import Iterator, Optional

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
    # XXX: this fixture needs the "HOME" fixture or it won't be able to
    # homely-add the repo
    from homely._test.system import TempRepo
    yield _get_test_repo(TempRepo(tmpdir, 'cool-testrepo'))


def _get_test_repo(repo) -> None:
    from homely._ui import addfromremote
    from homely._utils import RepoListConfig, saveconfig
    from homely._vcs import Repo, testhandler

    handler: Optional[Repo] = testhandler.Repo.frompath(repo.url)
    assert handler is not None
    localrepo, needpull = addfromremote(handler, None)

    with saveconfig(RepoListConfig()) as cfg:
        cfg.add_repo(localrepo)

    return repo


@pytest.fixture
def testrepo2(HOME, tmpdir):
    # XXX: this fixture needs the "HOME" fixture or it won't be able to
    # homely-add the repo
    from homely._test.system import TempRepo
    yield _get_test_repo(TempRepo(tmpdir, 'cool-testrepo-2'))


@pytest.fixture(autouse=True, scope='session')
def force_git_config() -> Iterator[None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        # force git commands to use a gitconfig that will:
        # A) provide a user.name/user.email for committing
        # B) allow the "file" protocol so that submodules can be cloned from
        #    filesystem paths instead of URLs
        # C) prevent anything in the host's user git config (like
        #    core.hooksPath) from slowing down or interfereing with tests.
        gitconfigpath = Path(tmpdir) / 'gitconfig'
        gitconfigpath.write_text(
            dedent(
                '''
                [protocol.file]
                    allow = always
                [user]
                    name = "John Smith"
                    email = "john@example.com"
                '''
            )
        )
        m = pytest.MonkeyPatch()
        try:
            # prevent reading any local git config during the tests
            m.setenv('GIT_CONFIG_GLOBAL', str(gitconfigpath))
            yield
        finally:
            m.undo()
