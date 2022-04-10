homely.general
==============


.. _homely-general-include:

homely.general.include()
------------------------

``include()`` makes it easy to split your *HOMELY.py* script into multiple files if it is getting too big to be in a single file.

``include(filename)``

``filename``
    The relative path to another ``HOMELY.py`` script in your dotfiles repo.

``include()`` is imperative and will immediately start executing the target script. It is therefore
more likely that you will want to add a collection of ``include(...)`` calls at the *end* of your
main ``HOMELY.py`` script, after core dependencies have been installed.

When ``include()`` finishes executing the target file it returns the associated python module,
making it possible to access symbols from the included file.

Also, inside the included file you can also import symbols from the root ``HOMELY.py`` script by
importing from the special module named ``"HOMELY"``.


Example 1: Moving code into an include()
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You have a command that sets the keyboard repeat rate for MacOS, and you want to move it out of your
main ``HOMELY.py`` script and into ``mac/HOMELY.py``. But you also want to set a boolean variable
to indicate whether or not the command was executed.::

    # ~/dotfiles/HOMELY.py
    from homely.general import include

    mac = include('mac/HOMELY.py')

    if mac.KEY_REPEAT_RATE_IS_SET:
        print("Key repeat rate has been set automatically")
    else:
        print("You need to set key repeat rate manually in system preferences")

and then in ``mac/HOMELY.py``...::

    # ~/dotfiles/mac/HOMELY.py
    import platform
    from homely.system import execute

    KEY_REPEAT_RATE_IS_SET = False

    if platform.system() == "Darwin":
        execute(['defaults', 'write', 'NSGlobalDomain', 'KeyRepeat', '-float', '1.0'])
        KEY_REPEAT_RATE_IS_SET = True


Example 2: Importing from your root HOMELY.py
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Taking the code from the example above, you might want to put the logic for detecting MacOS into
your root ``HOMELY.py`` script and then import that boolean into ``mac/HOMELY.py``:::

    # ~/dotfiles/HOMELY.py
    import platform
    from homely.general import include

    [... snip non-mac things ...]

    IS_MACOS = platform.system() == "Darwin"

    include('mac/HOMELY.py')

and then in ``mac/HOMELY.py``...::

    # ~/dotfiles/mac/HOMELY.py
    from homely.system import execute
    import HOMELY

    if HOMELY.IS_MACOS:
        execute(['defaults', 'write', 'NSGlobalDomain', 'KeyRepeat', '-float', '1.0'])
