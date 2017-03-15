import functools
import os
import shutil
import sys
import tempfile
import time

import pytest

from homely._utils import opentext


def withtmpdir(func):
    """Decorator for <func> that generates an extra kwarg tmpdir="/path" which
    is a randomly-generated temp dir. A new temp dir is generated on each call
    to <func>, and the temp dirs are automatically cleaned up when <func> ends.

    Note: this decorator needs to go inside any contextlib.contextmanager
    decorator
    """
    def stdwrapper(*args, **kwargs):
        tmpdir = None
        try:
            tmpdir = tempfile.mkdtemp()
            return func(*args, tmpdir=tmpdir, **kwargs)
        finally:
            if tmpdir and os.path.exists(tmpdir):
                shutil.rmtree(tmpdir)

    def genwrapper(*args, **kwargs):
        tmpdir = None
        try:
            tmpdir = tempfile.mkdtemp()
            for item in func(*args, tmpdir=tmpdir, **kwargs):
                yield item
        finally:
            if tmpdir and os.path.exists(tmpdir):
                shutil.rmtree(tmpdir)
    import inspect
    wrapper = genwrapper if inspect.isgeneratorfunction(func) else stdwrapper
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper


@pytest.fixture(scope="function")
def tmpdir(request):
    path = tempfile.mkdtemp()
    destructor = shutil.rmtree

    def destructor(path):
        print("rm -rf %s" % path)
        shutil.rmtree(path)
    request.addfinalizer(functools.partial(destructor, path))
    return os.path.realpath(path)


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


def contents(path, new_content=None, strip=True):
    if new_content is not None:
        # if new_content was a triple-quoted python string, try and strip off
        # the indent
        if strip and new_content.startswith('\n'):
            indent = len(new_content) - len(new_content[1:].lstrip(' ')) - 1
            stripped = []
            for line in new_content[1:].split('\n'):
                assert line.startswith(' ' * indent)
                stripped.append(line[indent:])
            assert stripped[-1] == ''
            new_content = '\n'.join(stripped)

        with opentext(path, 'w') as f:
            f.write(new_content)
    assert os.path.exists(path)
    with opentext(path, 'r') as f:
        return f.read()


NEXT_FILE = 1


def gettmpfilepath(tmpdir, suffix=".txt"):
    global NEXT_FILE
    try:
        return os.path.join(tmpdir, "tmpfile-%03d%s" % (NEXT_FILE, suffix))
    finally:
        NEXT_FILE += 1


def waitfor(desc, maxtime=1, interval=0.05):
    """
    wait up to maxtime
    """
    yield
    start = time.time()
    while True:
        time.sleep(interval)
        yield
        if time.time() > (start + maxtime):
            raise Exception("Waited too long for: %s" % desc)


def pytest_namespace():
    # path to the bin dir
    return dict(
        contents=contents,
        gettmpfilepath=gettmpfilepath,
        waitfor=waitfor,
        withtmpdir=withtmpdir,
    )
