import os
from datetime import datetime, timedelta

from homely._engine2 import getengine, getrepoinfo
from homely._ui import entersection, head, note, warn
# allow importing from outside
from homely._utils import haveexecutable  # noqa
from homely._utils import _loadmodule, _repopath2real, _time_interval_to_delta
# TODO: remove these deprecated aliases which I'm still using in my homely
# repos. Note that the cleaners will need some sort of special handling in
# cleanerfromdict() if ever we want to remove these imports
from homely.files import (WHERE_ANY, WHERE_BOT, WHERE_END, WHERE_TOP,  # noqa
                          CleanBlockInFile, CleanLineInFile, WriteFile,
                          blockinfile, download, lineinfile, mkdir, symlink,
                          writefile)


def run(updatehelper):
    getengine().run(updatehelper)


_include_num = 0


def include(pyscript):
    path = _repopath2real(pyscript, getrepoinfo().localrepo)
    if not os.path.exists(path):
        warn("{} not found at {}".format(pyscript, path))
        return

    global _include_num
    _include_num += 1

    name = '__imported_by_homely_{}'.format(_include_num)
    try:
        with entersection("/" + pyscript):
            _loadmodule(name, path)
    except Exception:
        import traceback
        warn("Error while including {}: {}".format(pyscript,
                                                   traceback.format_exc()))


def section(func=None, quick=False, enabled=True, interval=None):
    delta = None
    if interval:
        delta = _time_interval_to_delta(interval)

    def _decorator(func):
        return _execute_section(
            func,
            is_quick=quick,
            is_enabled=enabled,
            interval=delta,
        )

    if func:
        return _decorator(func)
    else:
        return _decorator


def _execute_section(func, is_quick, is_enabled, interval: timedelta = None) -> None:
    name = func.__name__
    engine = getengine()

    if not is_enabled:
        note("Skipping @section {}() due to enabled=False".format(name))
        return

    if engine.quickmode and not is_quick:
        note("Skipping @section {}() due to --quick flag".format(name))
        return

    if interval:
        timeformat = '%Y-%m-%d %H:%M:%S'
        repoinfo = getrepoinfo()
        assert repoinfo is not None
        last_run_fact_name = 'section_last_run:{}:{}'.format(repoinfo.repoid, name)
        lastrun = None
        try:
            lastrun = engine._getfact(last_run_fact_name)
        except KeyError:
            pass
        if lastrun:
            # XXX: type-ignore on this because it doesn't exist in python3.6
            lastruntime: datetime = datetime.strptime(lastrun, timeformat)  # type: ignore

            nextrun = lastruntime + interval
            if datetime.now() < nextrun:
                note("Skipping @section {}(), not due again until {}".format(name, nextrun))
                return

    try:
        with entersection(":" + name + "()"):
            if engine.pushsection(name):
                head("Executing @section {}()".format(name))
                func()
                if interval:
                    engine._setfact(last_run_fact_name, datetime.now().strftime(timeformat))
            else:
                note("Skipping @section {}() due to -o/--only flag".format(name))
    finally:
        engine.popsection(name)
