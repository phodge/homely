# Publishing a New Release

First, ensure all tests are passing. If you have docker installed then you can run
`bin/all_tests_containerised.sh` to run the test suite on all supported python versions. If you
don't have docker, you should at least run `pytest test` to ensure the test suite passes on *your*
version of python.

Next, add a section to CHANGELOG.rst that looks like this:

    Version $NEW_VERSION - $D $MMM $YYYY
    -------------------------------------

    * fixed something
    * fixed something else

Then, after you have committed the changelog changes, update the version number in these three files:

    vim homely/__init__.py
    vim pyproject.toml
    uv lock
    git add homely/__init__.py pyproject.toml uv.lock
    git commit -m "Bump version to $NEW_VERSION"


Push these changes in a new branch.
Open a PR for the branch.
After the branch is merged, add a tag on the merge commit and push the tag:

    git checkout master
    git pull
    git tag $NEW_VERSION
    git push --tags


# Manually Publishing Updated Docs

1. Make sure the `doc` branch is fast-forwarded to the same commit as master or the latest tag.
2. Log into https://readthedocs.io/
3. Navigate to "Builds"
4. Select "latest" in the dropdown at the top of the list, then click "Build Version"
