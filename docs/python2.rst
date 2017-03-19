.. _python2:

Python 2 Compatibility
======================

Please note that **homely** will suffer from the following limitations if you
install it with a python2 pip:

* Library functions that write or modify files (:any:`homely-files-lineinfile`, :any:`homely-files-blockinfile`) will always write files using unix ``\n`` line endings. Under python3, **homely** will use the first type of line ending encountered in a file and only use ``\n`` for new files or files with no existing linebreaks.
* Just in case it's not blindingly obvious, if you have installed **homely** under python2, you won't be able to use any python3 language or library features.
