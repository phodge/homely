========
 HOMELY
========

Single-command dotfile installation.


Installation
------------

To install **homely** on a new machine, use the following command::

    pip3 install git+https://github.com/phodge/homely.git

Getting started
---------------

1. If you don't yet have a Dotfiles repo, create an empty repo now.
2. Run homely add https://your/public/repo.git

TODO: these instructions are so incomplete


Keeping your repos up-to-date
-----------------------------

To manually fetch your latest dotfiles changes and install them locally, run::

    homely update

If you want something to put in a cronjob, try::

    homely autoupdate --daemon

If you want some visual feedback about what 'homely update' is doing, you might
want to use the powerline module.
