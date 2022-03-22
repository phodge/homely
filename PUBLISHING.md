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
