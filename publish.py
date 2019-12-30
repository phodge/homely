#!/usr/bin/env python3
import glob
import os
import shutil
import sys
from datetime import date
from subprocess import check_call, check_output


def fail(message):
    sys.stderr.write(message)
    sys.stderr.write("\n")
    sys.exit(1)


def updatechangelog(new_tag, latest_tag):
    # what should the heading at top of changelog be?
    new_heading = "Version {} - {}".format(
        new_tag, date.today().strftime("%d %b %Y"))

    changelog_old = 'CHANGELOG.rst'
    changelog_new = changelog_old + '.new'

    heading_replaced = False
    replace_next_lines = False

    with open(changelog_old) as f_old, open(changelog_new, 'w') as f_new:
        for line in f_old:
            if line == 'NEW\n':
                # instead of copying this line, replace it with the new heading
                f_new.write(new_heading)
                f_new.write('\n')
                heading_replaced = True
                replace_next_lines = True
                continue

            if replace_next_lines:
                replace_next_lines = False
                f_new.write('-' * len(new_heading))
                f_new.write('\n')

                if line == '\n':
                    # a blank line should be re-inserted
                    f_new.write('\n')
                if not line.startswith('---'):
                    # Don't re-insert the dashed line (it will have incorrect
                    # length). Anything else is unexpected.
                    fail('"NEW" heading not followed by blank line or "---"')

                continue

            # otherwise, just copy the line to the new file
            f_new.write(line)

    # if we didn't replace the NEW heading, we should add it
    if not heading_replaced:
        with open(changelog_old) as f_old, open(changelog_new, 'w') as f_new:
            heading_added = False
            seen_title = False
            for line in f_old:
                f_new.write(line)
                if heading_added:
                    pass
                elif line.strip() == 'CHANGELOG':
                    seen_title = True
                elif seen_title and line.startswith('==='):
                    # add the new heading here
                    f_new.write('\n\n')
                    f_new.write(new_heading)
                    f_new.write('\n')
                    f_new.write('-' * len(new_heading))
                    f_new.write('\n\n')
                    f_new.write('* DOCUMENT CHANGES HERE\n')
                    heading_added = True

        if not heading_added:
            fail('"NEW" heading not present and was not added automatically')

    # have a go at editing the file directly
    splitcmds = [
        # start a new buffer
        '+new',
        # give it a name
        '+silent file === Changes since {} ==='.format(latest_tag),
        # paste git log output
        '+silent read !git log --oneline {}..'.format(latest_tag),
        # delete blank line at top
        '+normal! ggdd',
        # modify buffer settings so that vim doesn't ask to save this buffer
        '+setlocal buftype=nofile',
        # jump back to original window
        '+wincmd w',
    ]
    check_call(['vim', changelog_new] + splitcmds)

    # move file sideways and commit it
    shutil.move(changelog_new, changelog_old)
    check_call(['git', 'commit', changelog_old, '-m', 'Update changelog'])


def main():
    tag = sys.argv[1]
    if not len(tag):
        fail("USAGE: {} TAG".format(sys.argv[0]))

    # get the latest tag name
    revlist = check_output(['git', 'rev-list', '--tags', '--max-count=1'])
    branches = filter(None, revlist.decode('utf-8').split('\n'))
    cmd = ['git', 'describe', '--tags'] + list(branches)
    latest_tag = check_output(cmd).strip().decode('utf-8')

    # make sure there is nothing in git status that could get in the way
    output = check_output(['git', 'st', '-s'])
    if len(output):
        fail("ERROR: A clean checkout is required")

    updatechangelog(tag, latest_tag)

    # create the new tag
    check_call(['git', 'tag', tag, '-m', 'Tagged {}'.format(tag)])
    # build
    check_call(['python3', 'setup.py', 'sdist'])
    check_call(['python3', 'setup.py', 'bdist_wheel', '--universal'])
    # upload
    files = ['dist/homely-{}.tar.gz'.format(tag)]
    files.extend(glob.glob('dist/homely-{}-py*.whl'.format(tag)))

    repository = 'https://upload.pypi.org/legacy/'

    check_call(['twine', 'upload', '--repository-url', repository] + files)
    print("NEW VERSION PUBLISHED!")
    check_call(['git', 'push'])
    check_call(['git', 'push', '--tags'])


if __name__ == '__main__':
    main()
