Installing Packages from PIP
============================


Use **homely.pipinstall.pipinstall()** to install packages from pip. The
primary advantage of using this module is that homely can automatically remove
the package for you when you no longer want it.


homely.pipinstall
-----------------


`pipinstall(package, pips=[], *, trypips=[])`

* `package`: The name of the pip package to install
* `pips`: a list of `pip` executables to install the package with.
  You could use `['pip']` to use the OS's default pip.
  `['pip2.7', 'pip3.4']` would install the package using the `pip2.7` and
  `pip3.4` executables.
* `trypips=[]`: This is a supplementary list of `pip` executables that homely
  will use to install the package, but no exception will be raised if the
  `pip` executables aren't available.

Note that the `pip install ...` commands are run with the `--user` option so
that the packages are installed into your home directory.


Examples
--------


Install `ipython` package for python2::

    from homely.pipinstall import pipinstall
    pipinstall('ipython', ['pip2'])

Install `neovim` package for python3::

    from homely.pipinstall import pipinstall
    pipinstall('neovim', ['pip3'])

Install `ptpython` package using whichever pip executables are present.
Don't issue a warning if some pip executables aren't found::

    from homely.pipinstall import pipinstall
    pipinstall('ipython', trypips=['pip', 'pip2', 'pip3'])
