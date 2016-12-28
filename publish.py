#!/usr/bin/env python3
import sys
import glob
from subprocess import check_call, check_output
from datetime import date


def fail(message):
    sys.stderr.write(message)
    sys.stderr.write("\n")
    sys.exit(1)


def updatechangelog(tag):
    changelog = 'CHANGELOG.rst'

    with open(changelog) as f:
        for line in f:
            if line == 'NEW\n':
                break
        else:
            fail("Heading 'NEW' doesn't appear in {}".format(
                changelog))

    # create the new heading - include the current date
    heading = "Version {} - {}".format(tag, date.today().strftime("%d %b %Y"))
    lines = '-' * len(heading)
    cmd = ['vim', '-u', 'NONE', changelog,
           '+%s/^NEW$/{}\r{}/'.format(heading, lines),
           '+wq',
           ]
    check_call(cmd)
    check_call(['git', 'commit', changelog,
                '-m', 'Update heading in changelog'])


def main():
    tag = sys.argv[1]
    if not len(tag):
        fail("USAGE: {} TAG".format(sys.argv[0]))

    # make sure there is nothing in git status that could get in the way
    output = check_output(['git', 'st', '-s'])
    if len(output):
        fail("ERROR: A clean checkout is required")

    updatechangelog(tag)

    # create the new tag
    check_call(['git', 'tag', tag, '-m', 'Tagged {}'.format(tag)])
    # build
    check_call(['python3', 'setup.py', 'sdist', 'bdist_wheel'])
    # upload
    files = ['dist/homely-{}.tar.gz'.format(tag)]
    files.extend(glob.glob('dist/homely-{}-py*.whl'.format(tag)))
    check_call(['twine', 'upload'] + files)
    print("New version published - don't forget to 'git push --tags'")


if __name__ == '__main__':
    main()
