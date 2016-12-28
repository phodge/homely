homely.files
============


homely.files.download()
-----------------------

**download()** will download a single file from a target URL.

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


homely.files.mkdir()
--------------------

**mkdir()** will create the nominated directory if it doesn't already exist.

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



homely.files.symlink()
----------------------

**symlink()** will create a symlink if it doesn't already exist.

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
