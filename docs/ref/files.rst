homely.files
============


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
``homely update``
homely will check to see if ``mkdir()`` was called, and if it wasn't then the
directory will be removed. This means that you don't need to remember to delete
directories you aren't using any more - simply remove the call to ``mkdir()``
and homely will clean it up for you. Note that the directory *won't* be cleaned
up if it is still in use.

