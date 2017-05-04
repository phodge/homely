Homely
======

:subtitle: Python-based dotfile management
:author: by Peter Hodge
:url: https://homely.readthedocs.io/
:github: https://github.com/phodge/homely/


DOTFILES
--------

::

    .ackrc
    .gitconfig
    .hgrc
    .tmux.conf
    .vim
    .vimrc


MY DOTFILES
-----------

A short history


MY DOTFILES - 2006-2008: VIMKIT
-------------------------------

* 128MB USB flash drive
* "vimkit-from-home" and "vimkit-from-work" folders
* ``sync.php``:

  * move "vimkit-from-home" sideways
  * ``cp -R`` new copy of "vimkit-from-home" onto flash drive
  * find files with newer timestamps, also copy them into "vimkit-from-work"

* *Abandoned Because:* Finite program-erase cycles


MY DOTFILES - 2008-2012: VIMKIT on BitBucket.org
------------------------------------------------

* Mercurial repo
* Hosted online
* *Abandoned Because:* only vim config


MY DOTFILES - 2012-2016: EXCALIBUR
----------------------------------

* Mercurial repo on bitbucket
* Included ``.bashrc.eaxmple``, ``.screenrc.example`` etc as well
* ``install.sh`` to download ack, vim plugins
* *Abandoned Because:* Too many manual steps


MY DOTFILES - 2016-PRESENT: USING HOMELY
----------------------------------------

* multiple git repos on github/bitbucket etc
* everything is scripted
* interactively select which things I want
* automatic cleanup


HOW DO YOU USE HOMELY
---------------------


1) INSTALL HOMELY
-----------------

::

    pip3 install homely --user


2) CREATE A GIT REPO
--------------------

::

    [peter@mac] /Users/peter/dotfiles [master]$ ls -a
    .              .git            .screenrc
    ..             .gitconfig      .tmux.conf
    .ackrc         .hgrc           .vimrc

* remember to commit at least one file!

    

3) ADD A HOMELY.py SCRIPT
-------------------------

::

    $ cat ~/dotfiles/HOMELY.py
    from homely.files import symlink
    symlink('.ackrc')
    symlink('.gitconfig')
    symlink('.hgrc')
    symlink('.screenrc')
    symlink('.tmux.conf')
    symlink('.vimrc')


4) TELL HOMELY ABOUT IT
-----------------------

::

    $ homely add ~/dotfiles
    [Thu Feb 23 06:51:09 2017] ::: Updating from ~/dotfiles [e5a89324]
    [Thu Feb 23 06:51:09 2017]     - Create symlink ~/.ackrc -> ~/dotfiles/.ackrc: Running ...
    [Thu Feb 23 06:51:09 2017]     - Create symlink ~/.gitconfig -> ~/dotfiles/.gitconfig: Running ...
    [Thu Feb 23 06:51:09 2017]     - Create symlink ~/.hgrc -> ~/dotfiles/.hgrc: Running ...
    [Thu Feb 23 06:51:09 2017]     - Create symlink ~/.screenrc -> ~/dotfiles/.screenrc: Running ...
    [Thu Feb 23 06:51:09 2017]     - Create symlink ~/.tmux.conf -> ~/dotfiles/.tmux.conf: Running ...
    [Thu Feb 23 06:51:09 2017]     - Create symlink ~/.vimrc -> ~/dotfiles/.vimrc: Running ...



5) UPDATE AS NECESSARY
----------------------

Add something to your ``HOMELY.py`` script::

    $ cat ~/dotfiles/HOMELY.py
    from homely.files import symlink
    [...]
    symlink('.gitignore')

Run ``homely update``::

    $ homely update
    [Thu Feb 23 06:51:09 2017] ::: Updating from ~/dotfiles [e5a89324]
    [Mon Feb 23 06:51:09 2017]     - Pulling changes for ~/dotfiles
    [Mon Feb 23 06:51:09 2017] !!!   Aborting - uncommitted changes
    [Thu Feb 23 06:51:09 2017]     - Create symlink ~/.gitignore -> ~/dotfiles/.gitignore: Running ...


SCRIPTING THINGS
----------------


DOWNLOADING FILES
-----------------

Download URL to target file::

    from homely.files import download
    url = ('https://raw.githubusercontent.com'
           '/git/git/master/contrib/completion/git-completion.bash')
    download(url, '~/src/git-completion.bash')

* Won't download again for 2 weeks (configurable)
* Automatic cleanup


LINE IN FILE
------------

Add a single line of text to a target file::

    from homely.files import lineinfile, WHERE_TOP
    lineinfile('.bashrc', 'source ~/src/git-completion.bash', WHERE_TOP)

* Will move line back to [where] on subsequent runs
* Automatic Cleanup


INSTALLING PACKAGES
-------------------

::

    from homely.install import installpkg

    installpkg('ack',
               apt='ack-grep')

    installpkg('ag',
               yum='the_silver_searcher',
               apt='silversearcher-ag')

* Automaticaly chooses between ``brew``, ``yum`` or ``apt`` depending which on
  what's available on your operating system.
* Won't hang on a ``sudo`` password prompt when there's no TTY available.
* Automatic Cleanup


PIP INSTALL
-----------

::

    from homely.pipinstall import pipinstall

    # pip install isort --user
    pipinstall('isort')

    # pip2 install flake8 --user; pip3 install flake8 --user
    pipinstall('flake8', ['pip2', 'pip3'])

    # if which pip2; then pip2 install py.test --user; fi
    pipinstall('py.test', trypips=['pip2'])


INVOKE SUBPROCESS
-----------------

Run shell commands when you need to::

    from homely.system import execute, haveexecutable
    if haveexecutable('brew'):
        execute(['brew', 'tap', 'universal-ctags/universal-ctags'])
        execute(['brew', 'install', '--HEAD', 'universal-ctags'])

Run interactively - won't hang if there's no TTY available::

    execute(["vim", "~/.bashrc"], stdout="TTY")

Run a command and capture stdout/stderr::

    retcode, stdout, stderr = execute([...], stdout=True, stderr=True)

Run a command that might have a non-zero exit code::

    retcode = execute([...], expectexit=[0,1])[0]


YESNO
-----
::

    from homely.ui import yesno

    if yesno("install_ipython", "Install ipython?", True, recommended=True)
        from homely.pipinstall import pipinstall
        pipinstall("ipython")

    if yesno(None, "Edit .bashrc?", True, noprompt=False):
        from homely.system import execute
        execute(["vim", "~/.bashrc"], stdout="TTY")


YESNO
-----

Default behaviour: use my answers from last time - only prompt me for new
questions::

    $ homely update


Ask me all the questions again so I can change my answers::

    $ homely update --alwaysprompt [ -a ]

Don't prompt me to answer questions - if a ``yesno()`` can't be avoided,
``exit(1)`` instead of waiting for input::

    $ homely update --neverprompt [ -n]

``--neverprompt`` is assumed when stdout/stderr are not a TTY.


SECTIONS
--------

Group related things in a `@section`-decorated function:

::

    from homely.ui import section

    @section
    def myutils():
        from homely.install import installpkg
        installpkg('ack')
        installpkg('ag')

Update using just that section:

::

    $ homely update -o myutils

* Traps exceptions and allows the rest of the script to continue (Coming Soon!)


AUTOMATIC CLEANUP
-----------------


AUTOMATIC CLEANUP
-----------------

1. Remove the thing you don't want

::

    [...]
    symlink('.hgrc')
    # I don't use this any more
    # symlink('.screenrc')
    symlink('.tmux.conf')
    [...]

2. Update

::

    $ homely update
    [Thu Feb 23 08:17:03 2017] ::: Updating from ~/dotfiles [e5380325]
    [Thu Feb 23 08:17:03 2017]     CLEANING UP 6 items ...
    [Thu Feb 23 08:17:03 2017]     Removing link ~/.screenrc

homely ...

* ... creates a symlink from [src] to [dst]
* ... remembers that it created a symlink from [src] to [dst]
* ... notices when the symlink is no longer asked for


LIMITATIONS
-----------

* bootstrapping requires pip
* not compatible with python2 (yet)
* cleanup of ``pipinstall()`` and ``installpkg()`` doesn't remove dependencies
  that were installed along the way
* not supported on Windows



HOW TO MIGRATE
--------------

Assuming you have a git repo with an ``install.sh`` already::

    # HOMELY.py
    from os.path import dirname
    from homely.system import execute
    execute(['install.sh'], stdout="TTY", cwd=dirname(__file__))


PROJECT TIMELINE
----------------

**Late 2016**: reach "beta" quality (stable code, useable features)

**Now**: share project with the community

**March**: collect feedback (tidy up APIs, fix bugs)

**April**: 1.0 release


THANK YOU FOR LISTENING
-----------------------

**Further Reading ...**

* Tutorial & Docs: https://homely.readthedocs.io/
* GitHub: https://github.com/phodge/homely/
* My Dotfiles: https://github.com/phodge/dotfiles/

**Get Involved**

* Use homely for your dotfiles repo!
* Submit feature requests & bug reports to https://github.com/phodge/homely/
* Email me if you get stuck: peter.hodge84@gmail.com

