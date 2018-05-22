calibre supports installation from source, only on Linux. If you want to create
installers for Windows or macOS, instructions can be found at
https://github.com/kovidgoyal/build-calibre

Note that you *do not* need to install from source to hack on the calibre
source code. To get started with calibre development, use a normal calibre
install and follow the instructions at
https://manual.calibre-ebook.com/develop.html

On Linux, there are two kinds of installation from source possible. Note that
both kinds require lots of dependencies as well as a full development
environment (compilers, headers files, etc.)

All installation related functions are accessed by the command::

    python2 setup.py

For details on what functions are available, see::

    python2 setup.py -h

Or for help on any individual functions, see::

    python2 setup.py <function> -h

Note that many of these functions are only useful for creating official release
compilations.

Prerequisites
=============

In order to install calibre, you will need:

  - The system dependencies listed at the bottom of
    https://calibre-ebook.com/download_linux

  - Either the raw source code available from git, or the release source code
    available at https://download.calibre-ebook.com (preferred). There is a big
    difference between the two, as the raw sources do not include several
    precompiled resources, for example localizations and Mathjax support.

    For anyone familiar with autotools builds, this is somewhat similar to the
    difference between configure.ac in git and the dist tarball after
    autoreconf is run. i.e. users are generally expected to use the latter.

Build
=====

In order to bootstrap the raw git sources to a release-ready state, run the
command::

    python2 setup.py bootstrap

In order to compile the C/C++ extensions etc. for a release-ready tarball
(these functions are already included by the bootstrap function), run the
commands::

    python2 setup.py build
    python2 setup.py gui

Install
==========

The first type of install will actually "install" calibre to your computer by
putting its files into the system in the following locations:

  - Binaries (actually python wrapper scripts) in <prefix>/bin
  - Python and C modules in <prefix>/lib/calibre
  - Resources like icons, etc. in <prefix>/share/calibre

This type of install can be run by the command::

    sudo python2 setup.py install

<prefix> is normally the installation prefix of python, usually /usr.  It can
be controlled by the --prefix option.

For distro packagers, DESTDIR support is implemented via the --staging-root
option, usually ${DESTDIR}/usr.

Develop
=============

This type of install is designed to let you run calibre from your home
directory, making it easy to hack on it.

It will only install binaries into /usr/bin, but all the actual code and
resource files will be read from the calibre source tree in your home directory
(or wherever you choose to put it).

This type of install can be run with the command::

    sudo python2 setup.py develop
