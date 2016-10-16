import time
from datetime import datetime
from subprocess import Popen, STDOUT

from homely._utils import OUTFILE, getstatus, UpdateStatus


_defaultcolors = {
    UpdateStatus.PAUSED: "information:priority",
    UpdateStatus.RUNNING: "critical:success",
    UpdateStatus.FAILED: "warning:regular",
    UpdateStatus.NOCONN: "critical:failure",
    UpdateStatus.DIRTY: "critical:failure",
    UpdateStatus.NEVER: "warning:regular",
    UpdateStatus.OK: "information:regular",
}


_house = "\U0001F3E0"

_defaulttxt = {
    UpdateStatus.PAUSED: _house + "  ||",
    UpdateStatus.RUNNING: _house + '  {time} {section}',
    UpdateStatus.FAILED: _house + '  {time}',
    UpdateStatus.NOCONN: _house + "  {time} N/C",
    UpdateStatus.DIRTY: _house + "  {time} [dirty]",
    UpdateStatus.NEVER: _house + '  [READY]',
    UpdateStatus.OK: _house + '  {time}',
}


SUB = None


def shortstatus(pl,
                colors={},
                fmt={},
                autoupdate=None,
                interval=60*60*20,
                reattach_to_user_namespace=False):
    status, timestamp, section = getstatus()

    doupdate = False
    if autoupdate:
        # if an autoupdate is necessary, start it running in the background
        if status == UpdateStatus.NEVER:
            doupdate = True
        elif (status == UpdateStatus.OK
              and (time.time() - timestamp) > interval):
            doupdate = True

    global SUB

    if doupdate:
        # NOTE: make use of reattach-to-user-namespace from homebrew if it is
        # present
        cmd = []
        if reattach_to_user_namespace:
            cmd.append('reattach-to-user-namespace')
        cmd.extend([
            'homely',
            'update',
            '--neverprompt'
        ])
        SUB = Popen(cmd, stdout=open(OUTFILE, 'a'), stderr=STDOUT)

    if SUB is not None and SUB.poll() is not None:
        SUB = None

    color = colors.get(status) or _defaultcolors[status]
    txt = fmt.get(status) or _defaulttxt[status]

    if timestamp is not None:
        time_ = datetime.fromtimestamp(timestamp).strftime('%H:%M')
    else:
        time_ = ""

    info = {
        'contents': txt.format(section=section, time=time_),
        'highlight_groups': [color],
    }
    return [info]
