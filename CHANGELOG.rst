===========
 CHANGELOG
===========

Version 0.19.0 - 29 Mar 2022
----------------------------

* Made homely.file.writefile() officially available (added unit tests and docs).


Version 0.18.0 - 22 Mar 2022
----------------------------

* Add "interval" option for @section decorator
* Script for running all tests on all python versions via docker
* Started adding type signatures - Python2 is no longer supported


Version 0.17.2 - 22 Mar 2022
----------------------------

* Add "enabled" flag for @section() decorator


Version 0.17.1 - 21 Mar 2022
----------------------------

* Fix bug where ``homely update --quick`` was performing cleanup.


Version 0.17.0 - 21 Mar 2022
----------------------------

* Added --quick option for ``homely update``
* Fixed bug where you couldn't run ``homely update ~/dotfiles/`` with a trailing ``/``.


Version 0.16.0 - 25 Jul 2020
----------------------------

* Fix git repo address only recognizing GitHub URLs
* Switch from os.rename to shutil.move for /tmp management
* Ignore dotfiles associated with VSCode


Version 0.15.6 - 14 Jan 2019
----------------------------

* Fix string formatting bug in yesno()
* Stop using deprecated pytest_namespace() in tests


Version 0.15.5 - 02 Jan 2019
----------------------------

* Improvements for undocumented experimental InstallFromSource feature


Version 0.15.4 - 06 Dec 2018
----------------------------

* Better detection of git repos with no commits.
* Allow disabling installation of packages / compile from source using
  setallowinstall() (experimental feature).


Version 0.15.3 - 25 May 2018
----------------------------

* Allow overriding powerline unicode character using env var $HOMELY_POWERLINE_HOUSE


Version 0.15.2 - 11 May 2017
----------------------------

* Improvements for undocumented experimental InstallFromSource feature


Version 0.15.1 - 11 May 2017
----------------------------

* Bugfix for undocumented experimental InstallFromSource feature


Version 0.15.0 - 05 May 2017
----------------------------

* ``homely.system.execute()`` is now officially supported.


Version 0.14.0 - 14 Apr 2017
----------------------------

* Experimental ``scripts`` option for ``pipinstall()``


Version 0.13.1 - 25 Mar 2017
----------------------------

* Fixed `#22 <https://github.com/phodge/homely/issues/22>`: pipinstall cleanup tries to wait for user prompt


Version 0.13.0 - 25 Mar 2017
----------------------------

* Option to skip some package managers when using ``installpkg()`` (`#18 <https://github.com/phodge/homely/issues/18`)
* Fixed `#21 <https://github.com/phodge/homely/issues/21>`: Traceback when cleaning up installpkg()


Version 0.12.0 - 24 Mar 2017
----------------------------

* Runs on python2.7


Version 0.11.9 - 22 Feb 2017
----------------------------

* Improved error messages when git repo isn't quite right


Version 0.11.8 - 08 Feb 2017
----------------------------

* Terrible hack in ``homely.general`` to get my own dotfiles going again


Version 0.11.7 - 19 Jan 2017
----------------------------

* CLI: ``homely remove`` renamed to ``homely forget``. Also the ``--force`` and
  ``--update`` flags were removed.
* CLI: better docstrings
* ``homely.install.installpkg()`` now requires a ``name`` argument.


Version 0.11.6 - 29 Dec 2016
----------------------------

* Fixed ``homely.files.download()`` which was completely broken.


Version 0.11.5 - 29 Dec 2016
----------------------------

* ``homely.files.download()`` now respects ``expiry`` arg
* ``homely.pipinstall`` uses ``pip --format=legacy`` for newer versions of pip


Version 0.11.4 - 02 Nov 2016
----------------------------

* Fix binary downloads in `homely.general`


Version 0.11.3 - 02 Nov 2016
----------------------------

* Ensure `homely.install.installpkg` uses the correct package name for yum/apt etc


Version 0.11.2 - 02 Nov 2016
----------------------------

* Fix broken `yum ... --assume-yes` in homely.install


Version 0.11.1 - 02 Nov 2016
----------------------------

* Fix broken import in homely.install


Version 0.11.0 - 16 Oct 2016
----------------------------

* Refactor yesno() and interactivity mechanisms
* Refactor homely.install.InstallPackage


Version 0.10.0 - 04 Oct 2016
----------------------------

* Refactor pipinstall API
