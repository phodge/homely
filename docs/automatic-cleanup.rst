.. _automatic_cleanup:

Automatic Cleanup
=================

One of the key features provided by **homely** is automatic removal of things
you are no longer using. It does this by keeping a record of files it modified
and programs it installed each time it runs. Later on, when you run
``homely update`` again and your ``HOMELY.py`` script is no longer asking to
change that particular file, or install that particular program, **homely**
assumes that you no longer want that thing and it will try to undo the changes
to the file, or uninstall the program.

Limitations
-----------

* **homely** can only cleanup changes that were made using functions from its
  own modules. E.g., directories created using ``homely.files.mkdir()`` can be
  cleaned up, but not directories created using ``os.mkdir()``.
* **homely** can only perform cleanup when you perform an update of all repos
  using ``homely update``.
* Sometimes things can't be cleaned up if they are still in use. E.g., if a
  directory created by ``homely.files.mkdir()`` isn't empty, then **homely**
  cannot remove it automatically. Check the documentation for each feature to
  find out if it has any additional limitations.
* If **homely** is prevented from performing cleanup (e.g. a directory can't be
  removed because isn't empty) it gives up and won't try and cleanup that thing
  again. This is to prevent ``homely update`` warning you every time about
  something that can't be cleaned up.


Example 1: Cleaning Directories
-------------------------------

Let's assume you have a ``HOMELY.py`` script that creates several directories
like this::

    from homely.files import mkdir
    mkdir('~/bin')
    mkdir('~/.vim')
    mkdir('~/.config')

When you run ``homely update`` **homely** will create all of those directories
(as long as they don't already exist) and it will remember which ones it
created. At some point in the future you might no longer want the ``.vim``
directory, so you can just remove it or comment it out::

    from homely.files import mkdir
    mkdir('~/bin')
    # I don't use this any more
    #mkdir('~/.vim')
    mkdir('~/.config')

Next time you run ``homely update``, **homely** will get to the end of the
update process and notice that there was no call to ``mkdir("~/.vim")``. It
assumes this means you no longer want this directory, so it will try to remove
the directory for you.

**homely** tries to be smart about the order it does cleanup. It can't remove a
directory that still contains files, so it will first perform cleanup of any
files inside that directory just in case this makes it possible to remove the
directory itself at the end.

