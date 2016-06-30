========
 HOMELY
========

Single-command dotfile installation.


Installation
------------

To install **homely** on a new machine, use the following command::

    pip3 install git+https://github.com/toomuchphp/homely.git

Getting started
---------------

1. If you don't yet have a Dotfiles repo, create an empty repo now.
2. Run homely add https://your/public/repo.git


Keeping your repos up-to-date
-----------------------------

To update your dotfiles using the latest versions from online repos, run::

    homely update

If you would like your shell to remind you when it is time to update dotfiles, add one of the
following to your **~/.bashrc** (or equivalent)::

    homely updatecheck --daily
    homely updatecheck --weekly
    homely updatecheck --monthly
