homely.system
=============

.. _homely-system-execute:

homely.system.execute()
-----------------------

``execute()`` runs an external program in a subprocess in much the same way as
python's subprocess module does, but the API is better suited towards the sorts
of things you will probably do in a ``HOMELY.py`` script. When possible, the
program's output is filtered through **homely**'s logging functions so that the
output is more readable amongst the other output from homely.

Note: if your python version doesn't have ``asyncio``, output from the command will not be printed until the program has exited.

``execute(cmd, stdout=None, stderr=None, expectexit=0, **kwargs)``

``stdout``
    There are four possible values for ``stdout``:

    ``stdout=None``
        Stdout from the subprocess will be filtered through homely's logging
        functions so that the output is more readable in the context of
        everything else that's printed to screen by homely. The subprocess will
        not have access to a TTY for user input. This is the default.
    ``stdout=False``
        Stdout from the subprocess will be discarded.
    ``stdout=True``
        Stdout from the subprocess will be included in the return value.
    ``stdout="TTY"``
        The subprocess's stdout will be connected directly to the **homely**
        process's TTY to allow the user to interact with the subprocess. An
        exception will be raised if ``execute()`` was invoked in a context
        where there is no TTY available.
        (You can use :any:`homely-ui-allowinteractive` to determine if ``stdout="TTY"`` will be successful or not.)

        If you have used ``stdout="TTY"``, then you must omit the ``stderr``
        argument, or use ``stderr=None``.

``stderr``
    There are four possible values for ``stderr``:

    ``stderr=None``
        Stderr from the subprocess will be filtered through homely's logging functions so that the output is more readable in the context of everything else that's printed to screen by homely.

        NOTE: If you used ``stdout="TTY"`` then you must omit ``stderr`` or use ``stderr=None``, and the subprocess's stderr stream will be connected to the parent process' TTY.
    ``stderr=False``
        Same as for ``stdout=False`` - the subprocess' stderr will be discarded.
    ``stderr=True``
        Same as for ``stdout=True`` - the subprocess' stderr will be included in the return value.
    ``stderr="STDOUT"``
        The subprocess' stderr stream will be merged with its stdout stream.

``expectexit=0``
    If the subprocess' exit code is not equal to ``expectexit``, an exception
    will be raised. You can also use a sequence (``expectexit=[0, 1, ...]``) if
    there are multiple exit codes that signify success.

``**kwargs``
    ``kwargs`` are passed directly into `subprocess.Popen() <https://docs.python.org/3/library/subprocess.html>`_, or `loop.subprocess_exec() <https://docs.python.org/3/library/asyncio-subprocess.html#asyncio.AbstractEventLoop.subprocess_exec>`_ when asyncio is used to spawn the subprocess.

The return value will be a tuple of (``exitcode``, ``stdout``, ``stderr``).
The ``stdout`` and ``stderr`` components will contain the entire contents of the process's stdout/stderr streams, but only when you use use ``stdout=True`` or ``stderr=True``, respectively.


Examples
^^^^^^^^

Universal ctags is a great tool, but not available by default in homebrew. This
example installs it by running the necessary brew commands::

    from homely.system import execute
    # install universal-ctags with homebrew
    if haveexecutable('brew'):
        execute(['brew', 'tap', 'universal-ctags/universal-ctags'])
        execute(['brew', 'install', '--HEAD', 'universal-ctags'])

When homebrew isn't installed, we can run the necessary shell commands to
compile from source::

    import os
    from homely.system import execute, haveexecutable
    from homely.files import mkdir, symlink

    # install universal-ctags from source
    if not haveexecutable('brew'):
        url = 'https://github.com/universal-ctags/ctags'
        checkout = '{}/src/universal-ctags.git'.format(os.environ['HOME']')
        branch = 'master'

        mkdir('~/src')
        if not os.path.exists(checkout):
            # clone the repo if we don't have a copy yet
            execute(['git', 'clone', 'url', checkout])
            execute(['git', 'checkout', 'master'], cwd=checkout)
        else:
            # pull the branch we want if we already have a clone
            execute(['git', 'checkout', branch], cwd=checkout)
            execute(['git', 'pull'], cwd=checkout)

        # update to latest master branch
        execute(['./autogen.sh'], cwd=checkout)
        execute(['./configure'], cwd=checkout)
        execute(['make'], cwd=checkout)

        # create a symlink to the compiled binary and put it in ~/bin
        mkdir('~/bin')
        symlink('{}/ctags'.format(checkout), '~/bin/ctags')


Automatic Cleanup
^^^^^^^^^^^^^^^^^

Automatic Cleanup is not available for this feature.


.. _homely-system-haveexecutable:

homely.system.haveexecutable()
------------------------------

``haveexecutable()`` will return ``True`` or ``False`` depending on whether or not a particular executable is available in your ``$PATH``.

``haveexecutable(name)``

``name``
    The name of the executable you want to check for.

Examples
^^^^^^^^

This code will clone a copy of the `crecord <https://bitbucket.org/edgimar/crecord>`_ mercurial extension in ``~/src/crecord``, but only when the mercurial executable (``hg``) is present::

    import os
    from homely.system import haveexecutable, execute

    if haveexecutable('hg'):
        src = os.environ["HOME"] + '/src'
        mkdir(src)
        localpath = src + '/crecord'
        url = 'https://bitbucket.org/edgimar/crecord'
        if os.path.exists(localpath):
            execute(['hg', 'pull'], cwd=localpath)
        else:
            execute(['hg', 'clone', url, localpath])
