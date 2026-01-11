import asyncio
import os
import sys
from typing import Any, Callable, Sequence


def _runasync(
    stdoutfilter: Callable[[bytes, bool], bytes] | None,
    stderrfilter: Callable[[bytes, bool], bytes] | None,
    cmd: Sequence[str | os.PathLike],
    **kwargs: Any,
) -> tuple[int | None, bytes, bytes]:
    assert asyncio is not None

    async def _runandfilter(
        cmd: Sequence[str | os.PathLike],
        **kwargs: Any,
    ) -> tuple[int | None, bytes, bytes]:
        loop = asyncio.get_event_loop()

        def factory() -> asyncio.subprocess.SubprocessStreamProtocol:
            return FilteringProtocol(
                asyncio.streams._DEFAULT_LIMIT,  # type: ignore
                loop,
            )

        class FilteringProtocol(asyncio.subprocess.SubprocessStreamProtocol):
            _stdout = b""
            _stderr = b""

            def pipe_data_received(self, fd: int, data: bytes | str) -> None:
                assert isinstance(data, bytes)
                if fd == 1:
                    if stdoutfilter:
                        self._stdout = stdoutfilter(self._stdout + data, False)
                    else:
                        assert self.stdout is not None
                        self.stdout.feed_data(data)
                elif fd == 2:
                    if stderrfilter:
                        self._stderr = stderrfilter(self._stderr + data, False)
                    else:
                        assert self.stderr is not None
                        self.stderr.feed_data(data)
                else:
                    raise Exception("Unexpected fd %r" % fd)

            def pipe_connection_lost(self, fd: int, exc: Exception | None) -> None:
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

    run_kwargs: dict[str, Any] = {}
    if sys.version_info >= (3, 13):
        run_kwargs['loop_factory'] = asyncio.EventLoop

    return asyncio.run(
        _runandfilter(cmd, **kwargs),
        **run_kwargs,
    )
