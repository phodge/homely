# NOTE: this file is python3-only because of asyncio
import asyncio
import sys


def _runasync(stdoutfilter, stderrfilter, cmd, **kwargs):
    assert asyncio is not None

    async def _runandfilter(cmd, **kwargs):
        loop = asyncio.get_event_loop()

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

        transport, protocol = await loop.subprocess_exec(factory,
                                                         *cmd,
                                                         **kwargs)
        process = asyncio.subprocess.Process(transport, protocol, loop)

        # now wait for the process to complete
        out, err = await process.communicate()
        return process.returncode, out, err

    run_kwargs = {}
    if sys.version_info >= (3, 13):
        run_kwargs['loop_factory'] = asyncio.EventLoop

    return asyncio.run(
        _runandfilter(cmd, **kwargs),
        **run_kwargs,
    )
