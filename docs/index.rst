.. homely documentation master file, created by
   sphinx-quickstart on Wed Oct  5 20:11:11 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Homely - Dotfile Management
===========================

One of the joys of being a software developer is meticulously customising the
various tools you use such that you maximise their utility and potential for
your own personal needs.  These customisations are typically stored in files
with names that begin with a dot ("."), so developers have creatively named
them "Dotfiles".

One of the great frustrations as a software developer is jumping onto a
different computer and having none of your customisations available.  Many
developers have taken to storing their Dotfiles in a git repository so that
changes can be shared across computers easily, and then added shell scripts to
automate their installation.  However, the lack of programming features
available in shell scripts soon becomes a dreadful burden as you continue to
add more and more customisations to your shell script.

**homely** is a small tool which allows you to take a repository full of
Dotfiles and script their installation using a real programming language
(Python).  It provides a small library containing the sorts of functions you
need to programmatically write Dotfiles and install software packages, and a
simple CLI tool to make running your installation script easy.

If you want to use **homely** to manage your dotfiles, you will need to be
able to:

1. Commit your dotfiles to one or more git repos which are hosted online
   (publically or privately is fine).
#. Write a small python script which tells **homely** how to install each of
   your dotfiles.

For example, you might put all of your dotfiles into a git repo that looks like
this::

    [peter@yourpc] /Users/peter/dotfiles [master]$ ls -a
    .              .git            .screenrc
    ..             .gitconfig      .tmux.conf
    .ackrc         .hgrc           .vimrc
    .bashrc        .isort.cfg


Then, you could write a small ``HOMELY.py`` script to symlink each of these files into
your home directory::

    $ cat ~/dotfiles/HOMELY.py
    from homely.files import symlink
    symlink('.ackrc')
    symlink('.bashrc')
    symlink('.git')
    symlink('.gitconfig')
    symlink('.hgrc')
    symlink('.isort.cfg')
    symlink('.screenrc')
    symlink('.tmux.conf')
    symlink('.vimrc')

**Important!** If you _only_ want to use symlinks and shell scripts to install
your dotfiles on each computer, then there are other mature projects that are
better suited for this. You can find a list of them at
https://dotfiles.github.io/. The reasons for using **homely** over other
dotfile managers are:

1. You want the full power of the python programming language at your disposal
   so that you aren't limited to just the features of your Dotfile Manager or
   things that can be done in a shell script.
#. **homely** makes a reasonable attempt at cleaning up things you don't use any
   more. Removed ``symlink(".screenrc")`` from your repo? **homely** will notice
   that it's not being asked for any more and remove the ``.screenrc`` symlink on
   any computer where it was previously installed.

If you would like to learn more, check out the :ref:`tutorial` or the :ref:`installation_guide`.
