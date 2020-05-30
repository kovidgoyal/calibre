Build the calibre installers, including all dependencies from scratch
=======================================================================

This folder contains code to automate the process of building calibre,
including all its dependencies, from scratch, for all platforms that calibre
supports.

In general builds proceed in two steps, first build all the dependencies, then
build the calibre installer itself.

Requirements
---------------

Building *must* run on a Linux computer.

First create some empty top level directory and run the following commands::

    git clone https://github.com/kovidgoyal/bypy.git
    git clone https://github.com/kovidgoyal/calibre.git
    cd calibre
    ./setup.py bootstrap

To make the Windows and macOS builds it uses QEMU VMs. Instructions on
creating the VMs are in the bypy repo under :file:`virtual_machine/README.rst`.
Required software for the VMs are listed in :file:`bypy/windows.conf` and
:file:`bypy/macos.conf`.

Linux
-------

To build the 64bit and 32bit dependencies for calibre, run::

    ./setup.py build_dep linux
    ./setup.py build_dep linux 32

The output (after a very long time) will be in :literal:`bypy/b/linux/[32|64]`

Now you can build the calibre Linux tarballs with::

    ./setup.py linux

The output will be in :literal:`dist`


macOS
--------------

Name the QEMU VM using ``vm_name`` from :literal:`bypy/macos.conf`.
Make sure all software mentioned in :file:`bypy/macos.conf` is installed.
To build the dependencies for calibre, run::

    ./setup.py build_dep macos

The output (after a very long time) will be in :literal:`bypy/b/macos`.
Now you can build the calibre ``.dmg`` with::

    ./setup.py osx --dont-sign --dont-notarize

The output will be in :literal:`dist`


Windows
-------------

Name the QEMU VM using ``vm_name`` from :file:`bypy/windows.conf`.
Make sure all software mentioned in :file:`bypy/windows.conf` is installed.

To build the dependencies for calibre, run::

    ./setup.py build_dep windows
    ./setup.py build_dep windows 32

The output (after a very long time) will be in :literal:`bypy/b/windows/[32|64]`.
Now you can build the calibre windows installers with::

    ./setup.py win --dont-sign

The output will be in :literal:`dist`
