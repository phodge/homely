from homely._test import contents


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
