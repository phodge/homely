import os.path
import sys
from io import StringIO

import pytest

from homely._test import contents


@pytest.fixture
def captured_stderr():
    from homely._ui import setstreams

    stream = StringIO()

    setstreams(sys.stdout, stream)

    yield stream

    setstreams(sys.stdout, sys.stderr)


def test_homely_general_include_executes_target_scripts(HOME, testrepo):
    from homely._test import run_update_all

    contents(
        testrepo.remotepath + '/HOMELY.py',
        """
        from homely.general import include
        include("test1/HOMELY.py")
        include("test2/HOMELY.py")
        """
    )

    contents(
        testrepo.remotepath + '/test1/HOMELY.py',
        """
        from homely.files import writefile
        with writefile("~/file1.txt") as f: f.write("I.\\n")
        """,
        mkdir=True,
    )

    contents(
        testrepo.remotepath + '/test2/HOMELY.py',
        """
        from homely.files import writefile
        with writefile("~/file2.txt") as f: f.write("II.\\n")
        """,
        mkdir=True,
    )

    run_update_all(
        # pull first so we get the new HOMELY.py script
        pullfirst=True,
    )

    assert contents(HOME + '/file1.txt') == "I.\n"
    assert contents(HOME + '/file2.txt') == "II.\n"


def test_homely_general_include_returns_target_modules(HOME, testrepo):
    from homely._test import run_update_all

    contents(
        testrepo.remotepath + '/HOMELY.py',
        """
        from homely.general import include

        mod1 = include("mod1/HOMELY.py")
        abc = include("a/b/c/HOMELY.py")

        assert mod1.THE_NUMBER == "Five"
        abc.do_something()
        """
    )

    contents(
        testrepo.remotepath + '/mod1/HOMELY.py',
        """
        THE_NUMBER = 'Five'
        """,
        mkdir=True,
    )

    contents(
        testrepo.remotepath + '/a/b/c/HOMELY.py',
        """
        from homely.files import writefile
        def do_something():
            with writefile("~/abc.txt") as f:
                f.write("Now I know my ABC's\\n")
        """,
        mkdir=True,
    )

    run_update_all(
        # pull first so we get the new HOMELY.py script
        pullfirst=True,
    )

    assert contents(HOME + '/abc.txt') == "Now I know my ABC's\n"


def test_homely_general_include_can_import_parent_module(HOME, testrepo):
    from homely._test import run_update_all

    contents(
        testrepo.remotepath + '/HOMELY.py',
        """
        from homely.general import include
        THE_WORD = "bonza"
        include("subdir/HOMELY.py")
        """
    )

    contents(
        testrepo.remotepath + '/subdir/HOMELY.py',
        """
        from homely.files import writefile
        import HOMELY
        with writefile('~/the_word.txt') as f: f.write(HOMELY.THE_WORD)
        """,
        mkdir=True,
    )

    run_update_all(
        # pull first so we get the new HOMELY.py script
        pullfirst=True,
    )

    assert contents(HOME + '/the_word.txt') == "bonza"


def test_homely_general_include_is_always_relative_to_repo_root(HOME, testrepo):
    """
    This test also ensures the main "HOMELY" import is always the root module
    """
    from homely._test import run_update_all

    contents(
        testrepo.remotepath + '/HOMELY.py',
        """
        from homely.general import include
        THE_WORD = 'flamingo'
        include("a/HOMELY.py")
        """
    )

    contents(
        testrepo.remotepath + '/a/HOMELY.py',
        """
        THE_WORD = 'flamingo'
        from homely.general import include
        include("a/b/HOMELY.py")
        """,
        mkdir=True,
    )

    contents(
        testrepo.remotepath + '/a/b/HOMELY.py',
        """
        from homely.general import include
        include("a/b/c/HOMELY.py")
        """,
        mkdir=True,
    )

    contents(
        testrepo.remotepath + '/a/b/c/HOMELY.py',
        """
        from homely.files import writefile
        import HOMELY
        with writefile('~/the_word.txt') as f: f.write(HOMELY.THE_WORD)
        """,
        mkdir=True,
    )

    run_update_all(
        # pull first so we get the new HOMELY.py script
        pullfirst=True,
    )

    assert contents(HOME + '/the_word.txt') == "flamingo"


def test_homely_general_include_works_with_multiple_repos(HOME, testrepo, testrepo2):
    """
    Tests three facets of include() when there are multiple dotfiles repos:
    - the script from the correct dotfiles repo is executed
    - the "HOMELY" import inside the included script is the root module for that repo
    - the module returned by include() is the correct module
    """
    from homely._test import run_update_all

    contents(
        testrepo.remotepath + '/HOMELY.py',
        """
        from homely.general import include
        THE_TEXT = 'The Phantom Mentace'
        a = include("a/HOMELY.py")
        assert a.THE_NUMBER == "One"
        """
    )

    contents(
        testrepo.remotepath + '/a/HOMELY.py',
        """
        from homely.files import writefile
        import HOMELY
        with writefile('~/text1.txt') as f: f.write(HOMELY.THE_TEXT)
        THE_NUMBER = "One"
        """,
        mkdir=True,
    )

    contents(
        testrepo2.remotepath + '/HOMELY.py',
        """
        from homely.general import include
        THE_TEXT = 'The Clone Wars'
        a = include("a/HOMELY.py")
        assert a.THE_NUMBER == "Two"
        """
    )

    contents(
        testrepo2.remotepath + '/a/HOMELY.py',
        """
        from homely.files import writefile
        import HOMELY
        with writefile('~/text2.txt') as f: f.write(HOMELY.THE_TEXT)
        THE_NUMBER = "Two"
        """,
        mkdir=True,
    )

    run_update_all(
        # pull first so we get the new HOMELY.py script
        pullfirst=True,
    )

    assert contents(HOME + '/text1.txt') == 'The Phantom Mentace'
    assert contents(HOME + '/text2.txt') == 'The Clone Wars'


def test_homely_general_include_relative_includes_do_not_work(HOME, testrepo, captured_stderr):
    """
    Tests three facets of include() when there are multiple dotfiles repos:
    - the script from the correct dotfiles repo is executed
    - the "HOMELY" import inside the included script is the root module for that repo
    - the module returned by include() is the correct module
    """
    from homely._test import run_update_all

    contents(
        testrepo.remotepath + '/HOMELY.py',
        """
        from homely.general import include
        include("a/HOMELY.py")
        """
    )

    contents(
        testrepo.remotepath + '/a/HOMELY.py',
        """
        from homely.general import include
        from homely.files import writefile
        try:
            include("b/HOMELY.py")
        except ImportError:
            with writefile('~/failed.txt') as f: f.write('the include failed')
        """,
        mkdir=True,
    )

    contents(
        testrepo.remotepath + '/a/b/HOMELY.py',
        """
        from homely.files import writefile
        with writefile('~/file1.txt') as f: f.write("Hello world\\n")
        """,
        mkdir=True,
    )

    # the include() will fail and issue a warn(), so run_update_all() will raise an exception
    with pytest.raises(AssertionError, match=r"run_update\(\) encountered errors or warnings"):
        run_update_all(
            # pull first so we get the new HOMELY.py script
            pullfirst=True,
        )

    # file1.txt is not created because the include did not work
    assert not os.path.exists(HOME + '/file1.txt')

    # the 'failed.txt' is not created because include() does not raise an exception
    assert not os.path.exists(HOME + '/failed.txt')

    # there is an ERR in stderr
    captured_stderr.seek(0)
    stderr = captured_stderr.read()
    assert '] ERR   b/HOMELY.py not found at ' in stderr
