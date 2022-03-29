from datetime import timedelta

import pytest
from freezegun import freeze_time

from homely._test import contents


@pytest.mark.parametrize('interval', ['2w', '14d', '336h', timedelta(days=14), timedelta(weeks=2)])
def test_homely_update_section_intervals(HOME, testrepo, interval):
    from homely._test import run_update_all

    contents(
        testrepo.remotepath + '/HOMELY.py',
        """
        import datetime  # needed for when we use raw timedelta instances as the interval
        from datetime import date
        from homely.general import section, writefile

        @section(interval={!r})
        def time_section():
            with writefile('~/last-update.txt') as f:
                f.write(str(date.today()))
        """.format(interval)
    )

    with freeze_time('2022-03-01'):
        run_update_all(
            # pull first so we get the new HOMELY.py script
            pullfirst=True,
        )
        assert contents(HOME + '/last-update.txt') == "2022-03-01"

    # run again one week later - there should be no change to the last-update
    # file
    with freeze_time('2022-03-08'):
        run_update_all()
        assert contents(HOME + '/last-update.txt') == "2022-03-01"

    # run again after the interval has elapsed
    with freeze_time('2022-03-15'):
        run_update_all()
        assert contents(HOME + '/last-update.txt') == "2022-03-15"

    # run again - no change again
    with freeze_time('2022-03-20'):
        run_update_all()
        assert contents(HOME + '/last-update.txt') == "2022-03-15"

    # run again - interval has elapsed so the new date is written
    with freeze_time('2022-03-30'):
        run_update_all()
        assert contents(HOME + '/last-update.txt') == "2022-03-30"
