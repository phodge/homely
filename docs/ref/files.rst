homely.files
============


homely.files.blockinfile()
--------------------------

``blockinfile()`` will add a several line of text to a target file in a single block. The lines of text are surrounded by ``prefix`` and ``suffix`` lines so that the block can be maintained by **homely** over time.

``blockinfile(filename, contents, where=None, *, prefix=None, suffix=None)``

``filename``
    The name of the file to modify. If ``filename`` begins with a ``/`` it will be treated as an absolute path, otherwise it is assumed to be relative to ``$HOME``.  You can also use ``~`` and environment variables like ``$HOME`` directly in the filename string.
``contents``
    A sequence of strings representing the lines of text to add to the file. The individual lines must not contain ``\n`` or ``\r``.
``where``
    One of ``None``, ``homely.files.WHERE_TOP``, ``homely.files.WHERE_BOT`` or
    ``homely.files.WHERE_ANY``. If set to ``None`` the behaviour of
    ``homely.files.WHERE_ANY`` will be used.
``prefix=None``
    A string containing a line of text which is guaranteed to be unique in the file and can be used to determine where the block starts.
``suffix=None``
    A string containing a line of text which is guaranteed to be unique in the file and can be used to determine where the block ends.

If ``prefix=None`` or ``suffix=None`` then a prefix or suffix (respectively) will be generated for you automatically. The generated line will start with ``#`` since this represents a comment in most config file languages. If the target file is named ``.vimrc`` or ends in ``.vim``, the vim comment character ``"`` will be used instead.

``block()`` is idempotent and will also make sure there is only one occurrence of the ``prefix...suffix`` block in the file, at the location specified by ``where``:

``where=homely.files.WHERE_TOP``
    The block will be added or moved to the top of the file.
``where=homely.files.WHERE_BOT``
    The block will be added or moved to the bottom of the file.
``where=homely.files.WHERE_ANY`` or ``where=None``
    The block will be added to the bottom of the file, but if it is already present in the file it will be left wherever it is. If there are multiple occurrences of the block already in the file, the first will be kept and subsequent occurrences will be removed.


Examples
^^^^^^^^

You want to include `powerline` config in your ``.tmux.conf``, but the powerline config file is in different locations depending on the host operating system. You could find the location of the powerline module programmatically and then use blockinfile() to insert the config into your ``.tmux.conf`` using ``blockinfile()``::

    from os.path import dirname
    from homely.files import blockinfile, WHERE_TOP
    from homely.ui import system

    # use python to import powerline and find out where it is installed
    cmd = ['python', '-c', 'import powerline; print(powerline.__file__)']
    stdout = system(cmd, stdout=True)[1]
    powerline_pkg = dirname(stdout.strip().decode('utf-8'))
    lines = [
        'run-shell "powerline-daemon --replace -q"',
        'source "{}/bindings/tmux/powerline.conf"'.format(powerline_pkg),
    ])
    blockinfile('.tmux.conf', lines, WHERE_BOT)


Automatic Cleanup
^^^^^^^^^^^^^^^^^

If homely does modify a file using ``blockinfile()``, it will remember this fact so that it can [possibly] perform automatic cleanup in the future. Each time you run ``homely update`` homely will check to see if ``blockinfile()`` was called with the same prefix/suffix combination, and if it wasn't then the block will be removed from the file. This means that you don't need to remember to remove the lines you aren't using any more -- simply remove the call to ``blockinfile()`` and homely will clean it up for you.

**Note:** after cleaning up a ``blockinfile()`` section, **homely** will re-run all ``lineinfile()`` and ``blockinfile()`` functions that targetted that file. This ensures that when a block is removed from a file, it won't accidentally remove something that was still wanted by a ``lineinfile()``.
See :ref:`cleaning_modified_files` for more information about this feature.

.. _homely-files-download:

homely.files.download()
-----------------------

``download()`` will download a single file from a target URL.

``download(url, dest, expiry=None)``

``url``
    The URL of the file to be downloaded.
``dest``
    Path where the file should be downloaded to. If ``dest`` begins with a
    ``/`` it will be treated as an absolute path, otherwise it is assumed to be
    relative to ``$HOME``.  You can also use ``~`` and environment variables
    like ``$HOME`` directly in the path string.
``expiry``
    The file will be downloaded again when the local copy is ``<expiry>``
    seconds old. When ``expiry=0`` the file will be downloaded every time you
    run ``homely update``. When ``expiry=-1`` the file will never be downloaded
    again. When ``expiry=None`` it will default to ``60*60*24*14`` (2 weeks).


Examples
^^^^^^^^

Download git completion script for bash::

    from homely.files import download

    url = 'https://raw.githubusercontent.com/git/git/master/contrib/completion/git-completion.bash'
    download(url, '~/src/git-completion.bash')


Automatic Cleanup
^^^^^^^^^^^^^^^^^

If homely creates the file at ``dest``, it will remember this fact so that it can
[possibly] perform automatic cleanup in the future. Each time you run ``homely
update`` homely will check to see if ``download()`` was called with the same
``dest``, and if it wasn't then the file will be removed.
See :ref:`automatic_cleanup` for more information.


.. _homely-files-lineinfile:

homely.files.lineinfile()
-------------------------

``lineinfile()`` will add a single line of text to a target file.

``lineinfile(filename, contents, where=None)``

``filename``
    The name of the file to modify. If ``filename`` begins with a ``/`` it
    will be treated as an absolute path, otherwise it is assumed to be relative
    to ``$HOME``.  You can also use ``~`` and environment variables
    like ``$HOME`` directly in the filename string.
``contents``
    The line of text to add to the file. ``contents`` must not contain ``\n`` or ``\r``.
``where``
    One of ``None``, ``homely.files.WHERE_TOP``, ``homely.files.WHERE_BOT`` or
    ``homely.files.WHERE_ANY``. If set to ``None`` the behaviour of
    ``homely.files.WHERE_ANY`` will be used.

``lineinfile()`` is idempotent and will also make sure there is only one
occurrence of the line contents in the file, at the location specified by
``where``:

``where=homely.files.WHERE_TOP``
    The line will be added or moved to the top of the file.
``where=homely.files.WHERE_BOT``
    The line will be added or moved to the bottom of the file.
``where=homely.files.WHERE_ANY`` or ``where=None``
    The line will be added to the bottom of the file, but if it is already
    present in the file it will be left wherever it is. If there are multiple
    occurrences of the line already in the file, the first will be kept and
    subsequent occurrences will be removed.


Examples
^^^^^^^^

Use ``lineinfile()`` to add a line to the end of your ``.bashrc``::

    from homely.files import lineinfile, WHERE_BOT
    lineinfile('.bashrc', 'PATH=$HOME/dotfiles/bin:$PATH', WHERE_BOT)

Use ``lineinfile()`` to add a line to the top of your ``~/.vimrc`` which
sources a shared vimrc inside your dotfiles repo::

    from homely.files import lineinfile, WHERE_TOP
    lineinfile('~/.vimrc', 'source $HOME/dotfiles/vimrc.vim', WHERE_TOP)


Automatic Cleanup
^^^^^^^^^^^^^^^^^

If homely does modify a file using ``lineinfile()``, it will remember this fact
so that it can [possibly] perform automatic cleanup in the future. Each time
you run ``homely update`` homely will check to see if ``lineinfile()`` was
called with the same arguments, and if it wasn't then the line will be removed
from the file. This means that you don't need to remember to remove the lines
you aren't using any more -- simply remove the call to ``lineinfile()`` and
homely will clean it up for you.

**Note:** after cleaning up line added by a ``lineinfile()`` that is no longer present, **homely** will re-run all ``lineinfile()`` and ``blockinfile()`` functions that targetted that file. This ensures that when a line is removed from a file, it won't accidentally remove something that was still wanted by another ``lineinfile()`` or ``blockinfile()``.  See :ref:`cleaning_modified_files` for more information about this feature.


homely.files.mkdir()
--------------------

``mkdir()`` will create the nominated directory if it doesn't already exist.

``mkdir(path)``

``path``
    The path to be created. If ``path`` begins with a ``/`` it will be treated
    as an absolute path, otherwise it is assumed to be relative to ``$HOME``.
    You can also use ``~`` and environment variables like ``$HOME`` directly in
    the path string.

Examples
^^^^^^^^

Different ways to create ``~/bin`` directory::

    from homely.files import mkdir

    # absolute path
    mkdir('/home/peter/bin')

    # path implicitly relative to $HOME
    mkdir('bin')

    # "~" expansion works
    mkdir('~/bin')

    # Environment variables are also expanded
    mkdir('$HOME/bin')


Automatic Cleanup
^^^^^^^^^^^^^^^^^

If homely does create the directory, it will remember this fact so that it can
[possibly] perform automatic cleanup in the future. Each time you run
``homely update`` homely will check to see if ``mkdir()`` was called, and if it
wasn't then the directory will be removed. This means that you don't need to
remember to delete directories you aren't using any more - simply remove the
call to ``mkdir()`` and homely will clean it up for you. Note that the
directory *won't* be cleaned up if it is still in use.
See :ref:`automatic_cleanup` for more information.


homely.files.symlink()
----------------------

``symlink()`` will create a symlink if it doesn't already exist.

``symlnk(target, linkname=None)``

``target``
    The file or directory to symlink to. Typically this will be the name of a
    file in your dotfiles repo. If ``target`` begins with a ``/`` it
    will be treated as an absolute path, otherwise it is assumed to be relative
    to the current dotfiles repo. You can also use ``~`` and environment
    variables like ``$HOME`` directly in the target string.
``linkname``
    Where to create the symlink. If this parameter is omitted, it will default
    to ``$HOME+basename(target)``. E.g., if ``target`` was ``'.bashrc'``, then
    ``linkname`` would default to ``'~/.bashrc'``. If ``linkname`` begins with
    a ``/`` it will be treated as an absolute path, otherwise it is assumed to
    be relative to ``$HOME``. You can also use ``~`` and environment variables
    like ``$HOME`` directly in the target string.


Examples
^^^^^^^^

Create a symlink to ``~/.bashrc`` to ``[dotfiles]/shell/.bashrc``::

    from homely.files import symlink

    # absolute linkname
    symlink('shell/.bashrc', '/home/peter/.bashrc')

    # linkname implicitly relative to $HOME
    symlink('shell/.bashrc', '.bashrc')

    # automatic linkname=$HOME+basename(target)
    symlink('shell/.bashrc')


Automatic Cleanup
^^^^^^^^^^^^^^^^^

If homely creates the symlink, it will remember this fact so that it can
[possibly] perform automatic cleanup in the future. Each time you run
``homely update`` homely will check to see if ``symlink()`` was called with the
same target/linkname, and if it wasn't then the symlink will be removed. This
means that you don't need to remember to delete symlinks you aren't using any
more - simply remove the call to ``symlink()`` and homely will clean it up for
you.  Note that the symlink *won't* be cleaned up if it has been modified by
something other than homely, or replaced with a regular file or directory.
See :ref:`automatic_cleanup` for more information.
