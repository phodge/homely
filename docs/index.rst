.. homely documentation master file, created by
   sphinx-quickstart on Wed Oct  5 20:11:11 2016.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Homely - Dotfile Management
===========================


Hello and welcome to the **homely** project. If you're reading this page it's
probably because you've realised you need a good way to keep your
every-growing collection of configuration files (usually referred to as
"dotfiles") syncronised across multiple computers, either real or virtual.

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
#. **Homely** makes a reasonable attempt at cleaning up things you don't use any
   more. Removed ``symlink(".screenrc")`` from your repo? **Homely** will notice
   that it's not being asked for any more and remove the ``.screenrc`` symlink on
   any computer where it was previously installed.

