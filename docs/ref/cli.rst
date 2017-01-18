Command Line Interface
======================

.. _homely-add:

homely add
----------

Registers a git repository with **homely** so that it will run its
``HOMELY.py`` script on each invocation of `homely update`_. ``homely add``
also immediately executes a `homely update`_ so that the dotfiles are
installed straight away. If the git repository is hosted online, a local clone
will be created first.

``homely add [OPTIONS] REPO_PATH [DEST_PATH]``

``REPO_PATH``
    A path to a local git repository, or the URL for a git repository hosted
    online. If ``REPO_PATH`` is a URL, then it should be in a format accepted
    by `git clone <https://git-scm.com/docs/git-clone>`. If ``REPO_PATH`` is a
    URL, you may also specify ``DEST_PATH``.
``DEST_PATH``
    If ``REPO_PATH`` is a URL, then the local clone will be created at
    ``DEST_PATH``. If ``DEST_PATH`` is omitted then the path to the local clone
    will be automatically derived from ``REPO_PATH``.
``-a/--alwaysprompt``
    Always prompt the user to answer questions, even named questions that they
    have answered on previous runs. This is useful if you previously answered
    *No* to a question and would like to change your choice.
``-n/--neverprompt``
    Never prompt the user to answer questions. Questions asked using
    :any:`homely.ui.yesno() <homely-ui-yesno>` will be answered automatically
    using the user's previous answer or the `noprompt` value. This option
    should be used any time you are running without a TTY attached so that
    **homely** can A) avoid asking the user for input and B) exit with an error
    code if user input is unavoidable.
``-v/--verbose``
    Produce extra output.


Examples
^^^^^^^^

Add a dotfiles repo that has already been cloned to ``~/dotfiles``::

    $ homely add ~/dotfiles

Add a dotfiles repo that is hosted on github::

    $ homely add https://github.com/phodge/dotfiles.git


.. _homely-update:

homely update
-------------

Performs a ``git pull`` in each of the repositories registered with `homely
add`_, runs all of their ``HOMELY.py`` scripts, and then performs
:any:`automatic cleanup <automatic_cleanup>` as necessary.

``homely update [OPTIONS] [REPO ...]``

``REPO``
    This should be the path to a local dotfiles repository that has already
    been registered using `homely add`_. If you specify one or more ``REPO``\
    s, then only the ``HOMELY.py`` scripts from those repositories will be run,
    and :any:`automatic cleanup <automatic_cleanup>` will not be performed
    (automatic cleanup is only possible when **homely** has done an update of
    all repositories in one go). If you do not specify a ``REPO``, all
    repositories' ``HOMELY.py`` scripts will be run.
``-o/--only SECTION``
    ``homely update`` will only run the ``@section`` named ``SECTION``. You can use ``-o`` multiple times if you want to
    run multiple sections. If you have registered more than one repository then
    you must also specify a single ``REPO`` to look for sections in. Note that
    any code in the global scope of your ``HOMELY.py`` script (code not in a
    section) will also be executed. If you specify a ``SECTION``,
    :any:`automatic cleanup <automatic_cleanup>` will not be attempted.
``--nopull``
    **homely** will not use ``git pull`` to update the repositories, and will
    also skip any action that requires internet access. Note that this only
    applies to **homely**'s own modules such as :any:`homely.files.download()
    <homely-files-download>`.  If you run ``wget`` in a subprocess then
    ``--nopull`` will not prevent ``wget`` from accessing the internet.

    If you want your own code to respect the ``--nopull`` flag then check the
    return value of :any:`homely.ui.allowpull() <homely-ui-allowpull>` before
    doing anything that will try and access the internet.

``-a/--alwaysprompt``
    Always prompt the user to answer questions, even named questions that they
    have answered on previous runs.

``-n/--neverprompt``
    Never prompt the user to answer questions. Questions will be answered
    automatically using the user's previous answer or the `noprompt` value.
    Any calls to :any:`homely-install-installpkg`
    which want a TTY for user input will raise an error instead. (You can wrap
    these calls in a conditional check for :any:`homely-ui-allowinteractive` to
    avoid unnecessary errors).


The ``--nopull`` and ``--only`` options are useful when you are working on your
``HOMELY.py`` script - the ``--nopull`` option stops you from wasting time
checking the internet for the same updates on every run, and the ``--only``
option allows you to execute only the section you are working on.


Examples
^^^^^^^^

Tell **homely** to run all ``HOMELY.py`` scripts::

    $ homely update

Tell **homely** to run all ``HOMELY.py`` scripts and re-prompt you to answer every question::

    $ homely update -a


.. _homely-forget:

homely forget
-------------

Tells **homely** to forget about a dotfiles repository that was previously
added. You can then run `homely update`_ to have **homely** perform
:any:`automatic cleanup <automatic_cleanup>` of anything that was installed by
that dotfiles repo.

``homely forget REPO ...``

``REPO``
    This should be the path to a local dotfiles repository that has already
    been registered using `homely add`_. You may specify multiple REPOs to
    remove at once.

Examples
^^^^^^^^

Tell **homely** to forget about the dotfiles repo at ``~/work-dotfiles``, and
then use `homely update`_ to ensure that automatic cleanup happens::

    $ homely forget ~/work-dotfiles
    $ homley update
