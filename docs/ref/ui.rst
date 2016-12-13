homely.ui
=========


homely.ui.head()
----------------

Use **head("some text")** to display a nice heading in homely's output.
**head()** should be used as a context manager so that log output is indented
correctly::

    import os
    from os.path import join, isdir
    from homely.ui import head

    with head('Doing git fetches'):
        src = join(os.environ['HOME'], 'src')
        for entry in os.listdir(src):
            path = join(src, entry)
            if isdir(path):
                shell(['git', 'fetch', '-p'], cwd=path)


homely.ui.warn()
----------------

Use **warn("some text")** when you want to add an error message to homely's
output, but don't want to raise an exception which would bail out of the
`HOMELY.py` script completely. Note that calling **warn()** any time during
your `HOMELY.py` script will cause **homely update** and **homely add** to exit
with a non-zero error code when they are finished.

**Example**

Issue a warning when neovim is not installed::

    from homely.ui import warn
    from homely.system import haveexecutable

    if not haveexecutable('nvim'):
        warn("You haven't installed neovim or added it to your $PATH yet")


homely.ui.note()
----------------

Use **note("some text")** to display a message in the homely script output.

**Example**

Show a message before doing something::

    from homely.ui import note
    from homely.pipinstall import pipinstall


    for pkg in ('isort', 'flake8', 'ipython', 'jedi'):
        note("Running pip install of {}".format(pkg))
        pipinstall(pkg)


homely.ui.allowpull()
---------------------

Returns `False` if `homely` was invoked without the `--nopull` option. You can
use this function in your `HOMELY.py` script to make that your script doesn't
attempt to download or pull changes from online when the user has explicitly
told it not to.

**Example**

Run `git fetch` in a private repo except when `--nopull` is used::

    import os
    from homely.system import shell
    from homely.ui import allowpull

    repopath = os.environ['HOME'] + '/src/neovim.git'
    if allowpull():
        shell(['git', 'fetch', 'origin', '--tags'], cwd=repopath)


homely.ui.yesno()
-----------------

Use **yesno()** to ask the user a yes/no question. The user will be asked to
enter "Y" or "N" before proceeding.

*yesno(name, prompt, default=None, *, recommended=None, noprompt=None)*

* *name*: If you provide a *name*, the user's answer will be recorded and used
  as the return value on subsequent runs. If you want to prompt the user for
  the answer to a question that has been answered on a previous run, use the
  *--alwaysprompt* flag. If you pass *name=None* then the user will be prompted
  for an answer on each run. (If you are using *name=None* then you should also
  include a value for *noprompt*.)
* *prompt*: Text displayed to the user. You should phrase the sentence as a
  question and end it with a question mark.
* *default*: This value will be returned if the user hits enter without
  choosing "Y" or "N", unless a *name* was provided, in which case *default* is
  replaced by the user's previous choice. If *default=None* and no previous
  answer is available, the user will be forced to provide an answer.
* *recommended*: This option will be suggested to the user.
* *noprompt*: If homely was invoked with the *--neverprompt* flag, then this
  value will be returned instead of asking the user for an answer. You can use
  this argument for *yesno()* calls that have *name=None* so that homely knows
  what to do when the user can't be asked for an answer. If *noprompt* is
  omitted or *None*, and *yesno()* is called in a context that doesn't allow
  user input, a *homely.ui.InputError* will be raised.

To summarise - the return value will be:

1) If the question has a *name* and the user has answered this question
   previously, and the *--alwaysprompt* flag was not used, then the previous
   answer will be returned.

#) If there is no TTY attached or the *--neverprompt* flag was used:

   a. If a *name* was provided and the user answered this question on a
      previous run, then that answer will be returned.
   #. If *noprompt* has a value then that will be returned.
   #. A *homely.ui.InputError* will be raised

#) If the user provides a valid answer then that answer will be returned.

#) If the user hits enter without specifying "Y" or "N":

   a. If *name* is provided, then their previous answer will be returned.
   #. If *default* is not None, then it is returned.
   #. The user is forced to provide a valid answer and this answer will be returned.


**Examples**

Ask the user if they would like to install ipython, and remember their choice
for next time::

    from homely.ui import yesno
    from homely.pipinstall import pipinstall
    if yesno("install_ipython", "Install ipython?", True, recommended=True)
        pipinstall("ipython")


Ask the user if they would like to perform an interactive task like edit their
.bashrc::

    from homely.ui import yesno
    from homely.system import shell
    if yesno(None, "Edit .bashrc?", True, noprompt=False):
        shell(["vim", "~/.bashrc"], stdout="TTY")


homely.ui.allowinteractive()
----------------------------

Returns *True* if there is a TTY attached and the *--neverprompt* option was
not used.

In some circumstances no TTY is available (for example, autoupdate runs) and it
is not safe to start up an interactive program like vim from your HOMELY.py
script. You can use this function to check first.

**Examples**

Edit the user's .bashrc if there is a TTY attached::

    from homely.ui import allowinteractive
    from homely.system import shell
    if allowinteractive():
        shell(["vim", "~/.bashrc"], stdout="TTY")

