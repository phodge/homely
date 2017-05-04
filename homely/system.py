from functools import partial

from homely._ui import allowinteractive, note, shellquote, warn
from homely._utils import haveexecutable, run

__all__ = ["haveexecutable", "execute"]


def execute(cmd, stdout=None, stderr=None, expectexit=0, **kwargs):
    # Executes `cmd` in a subprocess. Raises a SystemError if the exit code
    # is different to `expecterror`.
    #
    # The stdout and stderr arguments for the most part work just like
    # homely._ui.run(), with the main difference being that when stdout=None or
    # stderr=None, these two streams will be filtered through the homely's
    # logging functions instead of being sent directly to the python process's
    # stdout/stderr. Also, the stderr argument will default to "STDOUT" so that
    # the timing of the two streams is recorded more accurately.
    #
    # If the process absolutely _must_ talk to a TTY, you can use stdout="TTY",
    # and a SystemError will be raised if homely is being run in
    # non-interactive mode. When using stdout="TTY", you should omit the stderr
    # argument.
    def outputhandler(data, isend, prefix):
        # FIXME: if we only get part of a stream, then we have a potential bug
        # where we only get part of a multi-byte utf-8 character.
        while len(data):
            pos = data.find(b"\n")
            if pos < 0:
                break
            # write out the line
            note(data[0:pos].decode('utf-8'), dash=prefix)
            data = data[pos+1:]

        if isend:
            if len(data):
                note(data.decode('utf-8'), dash=prefix)
        else:
            # return any remaining data so it can be included at the start of
            # the next run
            return data

    if stdout == "TTY":
        if not allowinteractive():
            raise SystemError("cmd wants interactive mode")

        assert stderr is None
        stdout = None
    else:
        if stdout is None:
            prefix = "1> " if stderr is False else "&> "
            stdout = partial(outputhandler, prefix=prefix)

        if stderr is None:
            if stdout in (False, True):
                stderr = partial(outputhandler, prefix="2> ")
            else:
                stderr = "STDOUT"

    outredir = ' 1> /dev/null' if stdout is False else ''
    if stderr is None:
        errredir = ' 2>&1'
    else:
        errredir = ' 2> /dev/null' if stderr is False else ''

    with note('{}$ {}{}{}'.format(kwargs.get('cwd', ''),
                                  ' '.join(map(shellquote, cmd)),
                                  outredir,
                                  errredir)):
        returncode, out, err = run(cmd, stdout=stdout, stderr=stderr, **kwargs)
        if type(expectexit) is int:
            exitok = returncode == expectexit
        else:
            exitok = returncode in expectexit
        if exitok:
            return returncode, out, err

        # still need to dump the stdout/stderr if they were captured
        if out is not None:
            outputhandler(out, True, '1> ')
        if err is not None:
            outputhandler(err, True, '1> ')
        message = "Unexpected exit code {}. Expected {}".format(
            returncode, expectexit)
        warn(message)
        raise SystemError(message)
