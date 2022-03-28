import os.path

from homely._test import contents, run_update_all


def test_files_writefile(HOME, testrepo):
    contents(
        testrepo.remotepath + '/HOMELY.py',
        """
        import json
        from homely.files import mkdir, writefile

        mkdir('~/somedir')
        with writefile('~/somedir/somefile.txt') as f:
            json.dump({'one': 1*1}, f)
        """
    )

    # pull first so we get the new HOMELY.py script
    run_update_all(pullfirst=True)
    assert contents(HOME + '/somedir/somefile.txt') == '{"one": 1}'


def test_files_writefile_cleans_up_or_not(testrepo, HOME):
    # create file A.txt already
    contents(HOME + '/A.txt', 'before-update')

    contents(
        testrepo.remotepath + '/HOMELY.py',
        """
        from homely.files import writefile

        with writefile('~/A.txt') as f1:
            f1.write('AAA\\n')
        with writefile('~/B.txt') as f2:
            f2.write('BBB\\n')
        with writefile('~/C.txt') as f3:
            f3.write('CCC\\n')
        """
    )

    # pull first so we get the new HOMELY.py script
    run_update_all(pullfirst=True, cancleanup=True)
    assert contents(HOME + '/A.txt') == 'AAA\n'
    assert contents(HOME + '/B.txt') == 'BBB\n'
    assert contents(HOME + '/C.txt') == 'CCC\n'

    # now remove the writes to A.txt and B.txt
    contents(
        testrepo.remotepath + '/HOMELY.py',
        """
        from homely.files import writefile

        with writefile('~/C.txt') as f3:
            f3.write('CCC FINAL\\n')
        """
    )
    run_update_all(pullfirst=True, cancleanup=True)

    # A.txt is *not* cleaned up because it wasn't created by homely
    assert contents(HOME + '/A.txt') == 'AAA\n'

    # B.txt *is* cleaned up because homely creatd it
    assert not os.path.exists(HOME + '/B.txt')

    # C.txt is modified to final state
    assert contents(HOME + '/C.txt') == 'CCC FINAL\n'
