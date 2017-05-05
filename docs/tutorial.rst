.. _tutorial:

Beginner Tutorial
=================

This tutorial will walk you through setting up a git repository for your
dotfiles and creating a ``HOMELY.py`` script to automate their installation on
any of your computers.


1. Create an Online Repository
------------------------------

Since **homely** relies on a Version Control System to keep your dotfiles
syncronised across computers, the first step is to create a repository for your
dotfiles. If you already have a repository containing your dotfiles hosted
online, proceed to `2. Add a Repository`_.

If you are happy to publish your dotfiles publicly, you are may wish to host
wish to use one of the following VCS hosting providers:

GitHub
    `Create a Repository <https://help.github.com/articles/create-a-repo/>`_.
    Requires signing up for a free account.
BitBucket
    `Create a Repository <https://confluence.atlassian.com/bitbucket/create-and-clone-a-repository-800695642.html>`_.
    Requires signing up for a free account.


2. Add a Repository
-------------------

Once you have created your online repository, you will need to tell **homely**
to create a local clone of it. Use ``homely add <url>``, where ``<url>`` is the
same URL you would use to ``git clone`` the repository yourself.

**Note**: It is easier to get started cloning via HTTPS, but setting up SSH key
access can reduce the number of password prompts encountered.

**GitHub** (assuming a username of ``john.smith`` and a repository named ``dotfiles``)::

    # HTTPS
    $ homely add https://github.com/john.smith/dotfiles.git

    # SSH
    $ homely add git@github.com:phodge/dotfiles.git

**BitBucket** (assuming a username of ``john.smith`` and a repository named ``dotfiles``)::

    # HTTPS
    $ homely add https://john.smith@bitbucket.org/john.smith/dotfiles.git

    # SSH
    $ homely add git@bitbucket.org:john.smith/dotfiles.git

**homely** will create a local clone of your repository and put it in your home
directory. If you wish you may tell ``homely add`` where to create the local
clone by giving it a path as a 2nd parameter. If you don't provide an explicit
path, the repo's local path will be similar to what ``git clone`` would use.
(For the purposes of this tutorial, we will assume your dotfiles repo was
cloned to ``~/dotfiles``.). Check the CLI Reference for :any:`homely-add` for
more information.


3. Write and Run a HOMELY.py script
-----------------------------------

**homely** will look for a python script named ``HOMELY.py`` in your dotfiles
repo and execute it (import it) to install your config files locally. The
simplest things you can do in your ``HOMELY.py`` script is creating directories
and symlinks to things stored in the dotfiles repo.

For example, if you wanted to make sure that the ``~/.config/nvim`` and
``~/.config/pip`` directories are always created on all of your machines, you
could create a ``HOMELY.py`` script that looks like this::

    # ~/dotfiles/HOMELY.py
    # NOTE that we use homely's mkdir() not os.mkdir()
    from homely.files import mkdir
    # create ~/.config first - mkdir() is not recursive
    mkdir('~/.coonfig')
    mkdir('~/.coonfig/nvim')
    mkdir('~/.coonfig/pip')

Now you can use :any:`homely-update` to execute your ``HOMELY.py``::

    $ homely update

Now, assuming you already have a ``pip.conf`` and an ``init.vim`` in your
``~/.config`` directory, you might want to move these files into your dotfiles
repo and create symlinks to them on each machine.

First, move the real files into your dotfiles repo::

    $ mv ~/.config/nvim/init.vim ~/dotfiles/
    $ mv ~/.config/pip/pip.conf ~/dotfiles/

Now you can modify your ``HOMELY.py`` script to also install symlinks to those
files::

    # ~/dotfiles/HOMELY.py

    # NOTE that we use homely's mkdir() not os.mkdir()
    from homely.files import mkdir
    # create ~/.config first - mkdir() is not recursive
    mkdir('~/.coonfig')
    mkdir('~/.coonfig/nvim')
    mkdir('~/.coonfig/pip')

    # NOTE that we use homely's symlink() not os.symlink()
    from homely.files import symlink
    symlink('init.vim', '~/.coonfig/nvim')
    symlink('pip.conf', '~/.coonfig/pip')

**homely**'s functions are idempotent, so it is safe to run them again and
again. Run :any:`homely-update` again now to install your symlinks::

    $ homely update

Oh no! We misspelled ``~/.config`` everywhere! This is actually OK, because
**homely**'s :any:`automatic-cleanup` can remove all these unwanted
``~/.coonfig`` directories and symlinks for you, and all you need to do is
correct the typo and run :any:`homely-update` again. We can tidy up the code
while we're at it::

    # ~/dotfiles/HOMELY.py
    from homely.files import mkdir, symlink

    mkdir('~/.config')
    mkdir('~/.config/nvim')
    mkdir('~/.config/pip')

    symlink('init.vim', '~/.config/nvim/')
    symlink('pip.conf', '~/.config/pip/')

Now re-run update::

    $ homely update
So what exactly did :any:`homely-update` do here?

* First, :any:`homely-update` re-ran the corrected ``HOMELY.py`` script which
  created the symlinks in ``~/.config`` instead of ``~/.coonfig``.
* After finishing with the ``HOMELY.py`` script, :any:`homely-update` noticed
  that the calls to ``mkdir('~/.coonfig...')`` and ``symlink(..., '~/.coonfig...')``
  weren't executed, so it performed :any:`automatic-cleanup` of each of the
  things under ``~/.coonfig`` that it had created previously.

Automatic cleanup is one of the best features of **homely**. Generally speaking
it means you can just delete something from your ``HOMELY.py`` script and
:any:`homely-update` will make sure it gets removed anywhere it has already
been installed. There are some edge cases and limitations so there is a
:any:`dedicated page for how automatic cleanup works <automatic_cleanup>` which
you may wish to read after finishing the tutorials.

4. Installing Packages
----------------------

If you were writing a plain shell script to install your dotfiles, you might
also include a few calls to e.g. ``brew install`` to install your favourite
software packages. **homely** includes a dedicated function for this which
offers the following advantages:

* Automaticaly chooses between ``brew``, ``yum``, ``pacman`` or ``apt`` depending which on
  what's available on your operating system.
* Won't hang on a ``sudo`` password prompt when there's no TTY available.
* :any:`automatic_cleanup`!

You could get your ``HOMELY.py`` script to install
`ack <http://beyondgrep.com/>`_ and
`ag <http://geoff.greer.fm/ag/>`_ like this::

    #~/dotfiles/HOMELY.py
    [...snip...]

    from homely.install import installpkg
    # use the name "ack-grep" when installing using apt
    installpkg('ack', apt='ack-grep')
    # ag uses different names for yum, pacman and apt-get
    installpkg('ag', yum='the_silver_searcher', apt='silversearcher-ag', pacman = 'the_silver_searcher')

and then::

    $ homely update
    
Check the reference for :any:`homely-install-installpkg` for more information.

