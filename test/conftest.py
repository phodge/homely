import pytest

import functools
import os
import shutil
import tempfile


@pytest.fixture(scope="function")
def tmpdir(request):
    path = tempfile.mkdtemp()
    print('mkdir: %s' % path)
    destructor = shutil.rmtree

    def destructor(path):
        print("rm -rf %s" % path)
        shutil.rmtree(path)
    request.addfinalizer(functools.partial(destructor, path))
    return path


def contents(path, new_content=None):
    if new_content is not None:
        with open(path, 'w', newline="") as f:
            f.write(new_content)
    assert os.path.exists(path)
    with open(path, 'r', newline="") as f:
        return f.read()


NEXT_FILE = 1


def gettmpfilepath(tmpdir, suffix=".txt"):
    global NEXT_FILE
    tmppath = "%s/tmpfile-%03d%s" % (tmpdir, NEXT_FILE, suffix)
    NEXT_FILE += 1
    return tmppath


def pytest_namespace():
    return dict(
        contents=contents,
        gettmpfilepath=gettmpfilepath,
    )
