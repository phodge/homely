homely.install
==============

.. _homely-install-installpkg:

homely.install.installpkg()
---------------------------

If you were writing a plain shell script to install your dotfiles, you might
also include a few calls to e.g. ``brew install ...`` to install your favourite
software packages. The ``installpkg()`` function can do this for you, and also
offers the following advantages:

* Automaticaly chooses between ``brew``, ``yum``, ``port``, ``pacman`` or ``apt``
  depending on what's available in your $PATH.
* Won't hang on a ``sudo`` password prompt when there's no TTY available.
* :any:`automatic_cleanup`!
  
``installpkg(name=None, *, apt=None, brew=None, yum=None, port=None, pacman=None)``

``name``
    The name of the package you want to install. If the package goes by
    different aliases in different package manager repos then you should use
    either A) the name of the main executable provided by the package, or B)
    the alias used by your favourite package manager.
``apt=None``
    The alias to use when install using ``apt-get install``. Defaults to ``name``.
    Use ``False`` to stop ``installpkg()`` trying to install with ``apt-get`` altogether.
``brew=None``
    The alias to use when install using ``brew install``. Defaults to ``name``.
    Use ``False`` to stop ``installpkg()`` trying to install with ``brew`` altogether.
``yum=None``
    The alias to use when install using ``yum install``. Defaults to ``name``.
    Use ``False`` to stop ``installpkg()`` trying to install with ``yum`` altogether.
``port=None``
    The alias to use when install using ``port install``. Defaults to ``name``.
    Use ``False`` to stop ``installpkg()`` trying to install with ``port`` altogether.
``pacman=None``
    The alias to use when install using ``pacman -S``. Defaults to ``name``.
    Use ``False`` to stop ``installpkg()`` trying to install with ``pacman`` altogether.

When the ``yum``, ``apt-get``, ``pacman`` or ``port`` package managers are being used, they
will be run as root using ``sudo``. This means the call to ``installpkg()``
will fail if you don't have ``sudo`` privileges, or when :any:`homely-update`
is run without a TTY or with the ``--neverprompt`` flag.

Note that ``installpkg()`` is lazy and doesn't actually check with the package
manager to see if a particular package is installed - it just checks to see if
an executable named ``name`` is in your ``$PATH``.

Examples
^^^^^^^^

Install `ack <http://beyondgrep.com/>`_ and `ag <http://geoff.greer.fm/ag/>`_::

    #~/dotfiles/HOMELY.py
    from homely.install import installpkg

    # use the name "ack-grep" when installing using apt
    installpkg('ack', apt='ack-grep')

    # ag has different names in yum, pacman and apt-get repos
    installpkg('ag', yum='the_silver_searcher', apt='silversearcher-ag', pacman='the_silver_searcher')


Automatic Cleanup
^^^^^^^^^^^^^^^^^

``installpkg()`` will only attempt automatic cleanup of a package if **homely**
installed the package originally. If you ``brew install ack`` and then add
``installpkg("ack")`` to your ``HOMELY.py`` script, **homely** won't install
``ack`` (since it's already installed) and therefore it will never
automatically remove it.

The automatic removal may fail if you run :any:`homely-update` in a context
where no TTY is available, but your operating system's package manager is e.g.
``yum`` and needs to be executed with ``sudo``. If the automatic removal fails,
**homely** won't attempt to remove the package again later.

Also note that the automatic removal *won't* remove other packages that were
installed as dependencies.
