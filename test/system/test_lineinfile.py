from pytest import HOMELY, TempRepo, contents, getsystemfn


def test_lineinfile_knows_about_ownership(HOME, tmpdir):
    system = getsystemfn(HOME)

    # put the 'AAA' line into my file1.txt
    f1 = HOME + '/file1.txt'
    contents(f1, 'AAA\n')

    # create a fake repo and add it
    tr = TempRepo(tmpdir, 'dotfiles')
    contents(tr.remotepath + '/HOMELY.py',
             """
             from homely.general import lineinfile
             lineinfile('file1.txt', 'AAA')
             lineinfile('file1.txt', 'BBB')
             """)
    system(HOMELY('add') + [tr.url])

    # check that my file1.txt now has both lines
    assert contents(f1) == "AAA\nBBB\n"

    # now remove the repo and do a full update to trigger cleanup
    system(HOMELY('forget') + [tr.url])
    system(HOMELY('update'))

    # run homely update a few more times to confuse it
    system(HOMELY('update'))
    system(HOMELY('update'))

    # check that only the 'BBB' line was removed
    assert contents(f1) == "AAA\n"
