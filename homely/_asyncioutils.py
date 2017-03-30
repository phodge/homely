# NOTE: this file is python3-only because of asyncio and yield from syntax
# asyncio
import asyncio


def _runasync(stdoutfilter, stderrfilter, cmd, **kwargs):
    assert asyncio is not None

    @asyncio.coroutine
    def _runandfilter(loop, cmd, **kwargs):
        def factory():
            return FilteringProtocol(asyncio.streams._DEFAULT_LIMIT, loop)

        class FilteringProtocol(asyncio.subprocess.SubprocessStreamProtocol):
            _stdout = b""
            _stderr = b""

            def pipe_data_received(self, fd, data):
                if fd == 1:
                    if stdoutfilter:
                        self._stdout = stdoutfilter(self._stdout + data, False)
                    else:
                        self.stdout.feed_data(data)
                elif fd == 2:
                    if stderrfilter:
                        self._stderr = stderrfilter(self._stderr + data, False)
                    else:
                        self.stderr.feed_data(data)
                else:
                    raise Exception("Unexpected fd %r" % fd)

            def pipe_connection_lost(self, fd, exc):
                if fd == 1:
                    if stdoutfilter and self._stdout:
                        stdoutfilter(self._stdout, True)
                elif fd == 2:
                    if stderrfilter and self._stderr:
                        stderrfilter(self._stderr, True)
                return super().pipe_connection_lost(fd, exc)

        transport, protocol = yield from loop.subprocess_exec(factory,
                                                              *cmd,
                                                              **kwargs)
        process = asyncio.subprocess.Process(transport, protocol, loop)

        # now wait for the process to complete
        out, err = yield from process.communicate()
        return process.returncode, out, err

    _exception = None

    def handleexception(loop, context):
        nonlocal _exception
        if _exception is None:
            _exception = context["exception"]

    # FIXME: probably shouldn't be using the main loop here
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(handleexception)
    result = loop.run_until_complete(_runandfilter(loop, cmd, **kwargs))
    if _exception:
        raise _exception
    return result
