# Publishing a New Release

Add a section to CHANGELOG.rst that looks like this:

    NEW
    ---

    * fixed something
    * fixed something else

Then, after you have committed the changelog changes, run the publish script:

    ./publish.py NEW_VERSION_NUMBER
