# Publishing a New Release

First, ensure all tests are passing. If you have docker installed then you can run
`bin/all_tests_containerised.sh` to run the test suite on all supported python versions. If you
don't have docker, you should at least run `pytest test` to ensure the test suite passes on *your*
version of python.

Next, add a section to CHANGELOG.rst that looks like this:

    NEW
    ---

    * fixed something
    * fixed something else

Then, after you have committed the changelog changes, run the publish script:

    ./publish.py NEW_VERSION_NUMBER


After that is finished, you probably want to publish any changes to docs.
Checkout the `docs` branch, fast-forward it to the commit of the new tag, then
push that branch. readthedocs.io should hopefully publish an updated version of
the docs soon afterward.


# Manually Publishing Updated Docs

1. Make sure the `doc` branch is fast-forwarded to the same commit as master or the latest tag.
2. Log into https://readthedocs.io/
3. Navigate to "Builds"
4. Select "latest" in the dropdown at the top of the list, then click "Build Version"
