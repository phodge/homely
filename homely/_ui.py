import os
import sys
import subprocess
from importlib.machinery import SourceFileLoader

from homely._errors import RepoError, HelperError
from homely.utils import RepoInfo
import homely.engine


_ALLOWINTERACTIVE = True
_VERBOSE = False


def verbose(message):
    if _VERBOSE:
        sys.stdout.write("INFO: ")
        sys.stdout.write(message)
        sys.stdout.write("\n")


def heading(message):
    sys.stdout.write(message)
    sys.stdout.write("\n")
    sys.stdout.write("=" * len(message))
    sys.stdout.write("\n")


def warning(message):
    sys.stderr.write("WARNING: ")
    sys.stderr.write(message)
    sys.stderr.write("\n")


def run_update(info, pullfirst, allowinteractive, verbose=False):
    global _ALLOWINTERACTIVE, _VERBOSE
    _VERBOSE = verbose
    _ALLOWINTERACTIVE = allowinteractive
    assert isinstance(info, RepoInfo)
    heading("Updating from %s [%s]" % (info.localpath, info.shorthash))
    if pullfirst:
        # FIXME: warn if there are oustanding changes in the repo
        # FIXME: allow the user to configure whether they want to use 'git
        # pull' or some other command to update the repo
        sys.stdout.write("%s: Retrieving updates using git pull\n" %
                         info.localpath)
        cmd = ['git', 'pull']
        subprocess.check_call(cmd, cwd=info.localpath)
    else:
        # FIXME: notify the user if there are oustanding changes in the repo
        pass

    # make sure the HOMELY.py script exists
    pyscript = os.path.join(info.localpath, 'HOMELY.py')
    if not os.path.exists(pyscript):
        raise RepoError("%s does not exist" % pyscript)

    homely.engine.init(info)
    source = SourceFileLoader('__imported_by_homely', pyscript)
    try:
        source.load_module()
        homely.engine.execute()
    except HelperError as err:
        sys.stderr.write("ERROR: %s\n" % str(err))
        sys.exit(1)


def isinteractive():
    '''
    Returns True if the script is being run in a context where the user can
    provide input interactively. Otherwise, False is returned.
    '''
    return _ALLOWINTERACTIVE and sys.__stdin__.isatty() and sys.stderr.isatty()
