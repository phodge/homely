import os

from pytest import HOMELY, getsystemfn, getjobstartfn, TempRepo, contents, waitfor


def test_homely_updatestatus(HOME, tmpdir):
    from homely._utils import RUNFILE, FAILFILE, UpdateStatus, STATUSCODES

    system = getsystemfn(HOME)
    jobstart = getjobstartfn(HOME)

    exit_ok = STATUSCODES[UpdateStatus.OK]
    exit_never = STATUSCODES[UpdateStatus.NEVER]
    exit_paused = STATUSCODES[UpdateStatus.PAUSED]
    exit_failed = STATUSCODES[UpdateStatus.FAILED]
    exit_running = STATUSCODES[UpdateStatus.RUNNING]

    # create a special HOMELY.py script that we can control easily by putting magic files in the
    # right places
    spinfile = HOME + '/spin'
    diefile = HOME + '/diediedie'

    xdir1 = HOME + '/xdir1'
    assert not os.path.isdir(xdir1)

    # verify that homely updatestatus thinks we have never run an update
    system(HOMELY('updatestatus'), expecterror=exit_never)

    # pause autoupdate, and then check the status again
    system(HOMELY('autoupdate') + ['--pause'])
    system(HOMELY('updatestatus'), expecterror=exit_paused)

    # pausing again don't change anything
    system(HOMELY('autoupdate') + ['--pause'])
    system(HOMELY('updatestatus'), expecterror=exit_paused)

    # unpause takes us back to the previous status
    system(HOMELY('autoupdate') + ['--unpause'])
    system(HOMELY('updatestatus'), expecterror=exit_never)

    # add our special repo with our special file
    repo1 = TempRepo(tmpdir, 'repo1')
    contents(repo1.remotepath + '/HOMELY.py',
             """
             import os, time, sys
             from homely.general import mkdir
             while os.path.exists(%(spinfile)r):
                time.sleep(0.01)
             assert not os.path.exists(%(diefile)r), "Incredibly bad things in %(diefile)s"
             mkdir('~/xdir1')
             """ % locals())
    system(HOMELY('add') + [repo1.url])
    assert os.path.isdir(xdir1)

    # verify that homely updatestatus thinks we have run an update
    system(HOMELY('updatestatus'))

    # use the spinfile to make homely update sit in the background while we test some more things
    contents(spinfile, "spin!")
    with jobstart(HOMELY('update')) as job:
        for _ in waitfor('Appearance of RUNFILE %s' % RUNFILE):
            if os.path.exists(RUNFILE):
                break
        # verify that updatestatus says we are currently running
        system(HOMELY('updatestatus'), expecterror=exit_running)

        # remove the spinfile so the background job can finish
        os.unlink(spinfile)

    # verify that no update is currently running, and that the last run was successful
    system(HOMELY('updatestatus'))

    # now touch the errorfile and try a new update
    contents(diefile, "boom!")
    system(HOMELY('update'), expecterror=1)

    # updatestatus should tell us that the previous run failed
    system(HOMELY('updatestatus'), expecterror=exit_failed)

    # the error file should exist
    assert os.path.exists(FAILFILE)
    # grab the name of the OUTFILE
    outfile = system(HOMELY('autoupdate') + ['--outfile']).strip()
    # note that a plain 'homely update' won't create the outfile for us
    assert not os.path.exists(outfile)

    # try and kick off an autoupdate daemon ... it should fail miserably because the previous
    # update has already failed
    system(HOMELY('autoupdate') + ['--daemon'], expecterror=1)

    # use autoupdate --reset to allow automatic updates to resume
    system(HOMELY('autoupdate') + ['--clear'])
    system(HOMELY('updatestatus'), expecterror=exit_ok)

    # try and kick off an autoupdate daemon again ... it should fail miserably because the previous
    # update was too recent
    system(HOMELY('autoupdate') + ['--daemon'], expecterror=1)

    # remove the TIMEFILE so that homely thinks an update has never been run before
    from homely._utils import TIMEFILE
    os.unlink(TIMEFILE)

    try:
        # we use the spinfile to make sure the next autoupdate is going to stall
        contents(spinfile, "spin!")
        contents(diefile, "boom!")
        system(HOMELY('autoupdate') + ['--daemon'])

        # wait for the RUNFILE to appear
        for _ in waitfor('Appearance of RUNFILE'):
            if os.path.exists(RUNFILE):
                break

        # assert that our status is "running"
        system(HOMELY('updatestatus'), expecterror=exit_running)
    finally:
        # remove the spinfile so that the daemon can finish
        os.unlink(spinfile)

    # wait for the runfile to disappear
    for _ in waitfor('Disappearance of RUNFILE %s' % RUNFILE):
        if not os.path.exists(RUNFILE):
            break

    # the autoupdate should have failed because of the diefile
    system(HOMELY('updatestatus'), expecterror=exit_failed)
    with open(outfile) as f:
        assert 'Incredibly bad things' in f.read()

    # let's do this again, but without the diefile
    os.unlink(diefile)
    system(HOMELY('autoupdate') + ['--clear'])
    # we also need to manually remove the timefile
    os.unlink(TIMEFILE)
    try:
        contents(spinfile, "spin!")
        system(HOMELY('autoupdate') + ['--daemon'])
        for _ in waitfor('Appearance of RUNFILE'):
            if os.path.exists(RUNFILE):
                break
        system(HOMELY('updatestatus'), expecterror=exit_running)
    finally:
        os.unlink(spinfile)
    for _ in waitfor('Disappearance of RUNFILE %s' % RUNFILE):
        if not os.path.exists(RUNFILE):
            break

    # updatestatus should show that the update was successful
    system(HOMELY('updatestatus'), expecterror=exit_ok)
