.. _automatic_cleanup:

Automatic Cleanup
=================

One of the key features provided by **homely** is automatic cleanup of things
you are no longer using. It does this by keeping a record of files it modified
and programs it installed each time it runs. Later on, when you run
:any:`homely-update` again and your ``HOMELY.py`` script is no longer asking to
change a particular file or install a particular program, **homely**
assumes that you no longer want that thing and it will try to undo the changes
to the file or uninstall the program.

Even though the automatic cleanup feature should just work how you expect it
to, it is still worthwhile reading through the examples below which will give
you a better idea what to expect in various scenarios.


Example 1: Cleaning Directories
-------------------------------

Let's assume you have a ``HOMELY.py`` script that creates several directories
like this::

    # ~/dotfiles/HOMELY.py
    from homely.files import mkdir
    mkdir('~/bin')
    mkdir('~/.vim')
    mkdir('~/.config')

When you run :any:`homely-update` **homely** will create all of those directories
(as long as they don't already exist) and it will remember which ones it
created. At some point in the future you might no longer want the ``.vim``
directory so you can just remove it or comment it out::

    # ~/dotfiles/HOMELY.py
    from homely.files import mkdir
    mkdir('~/bin')
    # I don't use this any more
    #mkdir('~/.vim')
    mkdir('~/.config')

Next time you run :any:`homely-update`, **homely** will get to the end of the
update process and notice that there was no call to ``mkdir("~/.vim")``. It
assumes this means you no longer want this directory so it will try to remove
the directory for you.

**homely** tries to be smart about the order it does cleanup. It can't remove a
directory that still contains files, so it will first perform cleanup of any
files inside that directory just in case this makes it possible to remove the
directory itself afterward.


Example 2: Cleaning Conditional Changes
---------------------------------------

Automatic cleanup also works well with conditional sections of code in your
``HOMELY.py`` script. For example, you might have a section of code that
creates your ``.isort.cfg`` file only when an ``isort`` executable is installed
on your system::

    from homely.files import symlink
    from homely.system import haveexecutable
    if haveexecutable('isort'):
        symlink('.isort.cfg')

If you run :any:`homely-update` with an ``isort`` executable in your ``$PATH``,
the ``.isort.cfg`` symlink will be created. If you uninstall ``isort`` and
re-run :any:`homely-update`, the call to ``symlink('.isort.cfg')`` will no
longer be run and **homely** will automatically remove the symlink for you.


Example 3: Multiple Repos
-------------------------

If you have multiple dotfiles repos, you may sometimes move code from one repo
to another. For example, let's say you had a ``personal-dotfiles`` repo and a
``work-dotfiles`` repo with these ``HOMELY.py`` scripts::

    # ~/personal-dotfiles/HOMELY.py
    from homely.files import symlink
    symlink('.vimrc')
    symlink('.gitconfig')
    symlink('.isort.cfg')

::

    # ~/work-dotfiles/HOMELY.py
    from homely.files import symlink
    symlink('.hgrc')

... and you decide that you want to make the ``isort.cfg`` part of your
``work-dotfiles`` repo. You might just move the ``symlink()`` line like this::

    # ~/personal-dotfiles/HOMELY.py
    from homely.files import symlink
    symlink('.vimrc')
    symlink('.gitconfig')

::

    # ~/work-dotfiles/HOMELY.py
    from homely.files import symlink
    symlink('.hgrc')
    symlink('.isort.cfg')

Next time you run :any:`homely-update`, **homely** *will not* attempt to
cleanup the ``.isort.cfg`` symlink because the the ``work-dotfiles/HOMELY.py``
script is still asking for the symlink to be created.


.. _cleaning_modified_files:

Example 4: Cleaning Modified Files
----------------------------------

Sometimes **homely** can't take total ownership of files for cleanup purposes.
For example, if you have a ``HOMELY.py`` script that modifies ``~/.bashrc`` using
:any:`homely.files.lineinfile() <homely-files-lineinfile>` like this::

    from homely.files import lineinfile
    lineinfile('~/.bashrc', 'PATH=$HOME/dotfiles/bin:$PATH')

If you comment out the call to ``lineinfile()`` and run :any:`homely-update`,
**homely** knows it can't just remove the whole ``~/.bashrc`` file. Instead, it
will try and "undo" the file changes -- it will look for the line of text added
by the call to ``lineinfile()`` and remove it if it is still present.

But what happens if you actually replaced the call to ``lineinfile()`` with a
call to ``blockinfile()`` that creates the same line?

::

    from homely.files import blockinfile
    #lineinfile('~/.bashrc', 'PATH=$HOME/dotfiles/bin:$PATH')
    lines = ['PATH=$HOME/dotfiles/bin:$PATH']
    blockinfile('~/.bashrc', lines, '# dotfiles begin', '# dotfiles end')

This scenario is also handled just fine because when **homely** cleans up a
file by undoing changes to it, *it will then re-run all of the other functions
that modified that file*. This is safe to do because all of the file
modification functions are idempotent.

In other words, when you run :any:`homely-update` after making the above
change, **homely** will:

#. Add 3 new lines to ``~/.bashrc`` when ``blockinfile()`` is called. This will
   result in the ``PATH=...`` temporarily appearing in ``~/.bashrc`` *twice*.
#. Note the fact that there was a call to ``blockinfile()`` where the target
   file was ``~/.bashrc``.
#. Run automatic cleanup of the ``lineinfile()`` call that no longer exists.
   This will cause *all* occurences of the ``PATH=...`` line to be removed from
   ``~/.bashrc`` -- even the line between ``# dotfiles begin`` and ``# dotfiles
   end`` will be removed.
#. Re-run the call to ``blockinfile()`` which will recreate the ``# dotfiles
   begin ... # dotfiles end`` block.


Limitations
-----------

* **homely** can only cleanup changes that were made using functions from its
  own modules. E.g., directories created using ``homely.files.mkdir()`` can be
  cleaned up, but not directories created using ``os.mkdir()``.
* **homely** can only perform cleanup when you perform an update of all repos
  using :any:`homely-update`.
* Sometimes things can't be cleaned up if they are still in use. E.g., if a
  directory created by ``homely.files.mkdir()`` isn't empty, then **homely**
  cannot remove it automatically. Check the documentation for each feature to
  find out if it has any additional limitations.
* If **homely** is prevented from performing cleanup (e.g. a directory can't be
  removed because isn't empty) it gives up and won't try and cleanup that thing
  again. This is to prevent :any:`homely-update` warning you every time about
  something that can't be cleaned up.
