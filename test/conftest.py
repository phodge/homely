import functools
import os.path
import shutil
import sys
import tempfile

import pytest


@pytest.fixture(scope="function")
def HOME(tmpdir):
    home = os.path.join(tmpdir, 'john')
    os.mkdir(home)
    # NOTE: homely._utils makes use of os.environ['HOME'], so we need to
    # destroy any homely modules that may have imported things based on this.
    # Essentially we blast away the entire module and reload it from scratch.
    for name in list(sys.modules.keys()):
        if name.startswith('homely.'):
            sys.modules.pop(name, None)
    os.environ['HOME'] = home
    return home


@pytest.fixture(scope="function")
def tmpdir(request):
    path = tempfile.mkdtemp()
    destructor = shutil.rmtree

    def destructor(path):
        print("rm -rf %s" % path)
        shutil.rmtree(path)
    request.addfinalizer(functools.partial(destructor, path))
    return os.path.realpath(path)
