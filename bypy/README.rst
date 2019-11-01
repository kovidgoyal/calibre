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

To make the Windows and macOS builds it uses VirtualBox VMs. Instructions on
creating the VMs are in their respective sections below.

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

You need a VirtualBox virtual machine of macOS 10.14 (Mojave). Name the
VM using ``vm_name`` from :literal:`bypy/macos.conf`. To setup macOS inside the VM,
follow the steps:

* Turn on Remote Login under Network (SSHD)
* Create a user account named ``kovid`` and enable password-less login for SSH
  for that account (setup ``~/.ssh/authorized_keys``)
* Setup ssh into the VM from the host using the ``vm_name`` from above.
* Install the needed software mentioned in :literal:`bypy/macos.conf`.

To build the dependencies for calibre, run::

    ./setup.py build_dep macos

The output (after a very long time) will be in :literal:`bypy/b/macos`.
Now you can build the calibre ``.dmg`` with::

    ./setup.py osx --dont-sign --dont-notarize

The output will be in :literal:`dist`


Windows
-------------

You need a VirtualBox virtual machine of Windows 7 64bit. Name the
VM using ``vm_name`` from :literal:`bypy/windows.conf`. To setup windows inside the VM,
follow the steps:

* Install all the software mentioned in :literal:`bypy/windows.conf`

* Install cygwin, with the: vim, dos2unix, rsync, openssh, unzip, wget, make, zsh, patch, bash-completion, curl
  packages

* Edit ``/etc/passwd`` and replace all occurrences of ``/bin/bash`` with ``/bin/zsh`` (in
  a cygwin prompt)

* Setup a password for your windows user account

* Follow the steps here: http://pcsupport.about.com/od/windows7/ht/auto-logon-windows-7.htm to allow the
  machine to bootup without having to enter the password

* The following steps must all be run in an administrator cygwin shell, to
  enable SSH logins to the machine

* First clean out any existing cygwin ssh setup with::

    net stop sshd
    cygrunsrv -R sshd
    net user sshd /DELETE
    net user cyg_server /DELETE (delete any other cygwin users account you
    can list them with net user)
    rm -R /etc/ssh*
    mkpasswd -cl > /etc/passwd
    mkgroup --local > /etc/group

* Assign the necessary rights to the normal user account (administrator
  cygwin command prompt needed - editrights is available in ``\cygwin\bin``)::

    editrights.exe -a SeAssignPrimaryTokenPrivilege -u kovid
    editrights.exe -a SeCreateTokenPrivilege -u kovid
    editrights.exe -a SeTcbPrivilege -u kovid
    editrights.exe -a SeServiceLogonRight -u kovid

* Run::

    ssh-host-config
    And answer (yes) to all questions. If it asks do you want to use a
    different user name, specify the name of your user account and enter
    username and password

* Start sshd with::

    net start sshd

* See http://www.kgx.net.nz/2010/03/cygwin-sshd-and-windows-7/ for details


To build the dependencies for calibre, run::

    ./setup.py build_dep windows
    ./setup.py build_dep windows 32

The output (after a very long time) will be in :literal:`bypy/b/windows/[32|64]`.
Now you can build the calibre windows installers with::

    ./setup.py win --dont-sign

The output will be in :literal:`dist`
