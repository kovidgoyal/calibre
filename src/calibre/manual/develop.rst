.. include:: global.rst

.. _develop:

Setting up a |app| development environment
===========================================

|app| is completely open source, licensed under the `GNU GPL v3 <http://www.gnu.org/copyleft/gpl.html>`_.
This means that you are free to download and modify the program to your hearts content. In this section, 
you will learn how to get a |app| development environment setup on the operating system of your choice. 
|app| is written primarily in `Python <http://www.python.org>`_ with some C/C++ code for speed and system interfacing. 
Note that |app| is not compatible with Python 3 and requires at least Python 2.6.

.. contents:: Contents
  :depth: 2
  :local:

Design philosophy
-------------------

|app| has its roots in the Unix world, which means that it's design is highly modular.
The modules interact with each other via well defined interfaces. This makes adding new features and fixing
bugs in |app| very easy, resulting in a frenetic pace of development. Because of its roots, |app| has a 
comprehensive command line interface for all its functions, documented in :ref:`cli`.

The modular design of |app| is expressed via ``Plugins``. There is a :ref:`tutorial <customize>` on writing |app| plugins.
For example, adding support for a new device to |app| typically involves writing less than a 100 lines of code in the form of
a device driver plugin. You can browse the 
`built-in drivers <http://bazaar.launchpad.net/%7Ekovid/calibre/trunk/files/head%3A/src/calibre/devices/>`_. Similarly, adding support 
for new conversion formats involves writing input/output format plugins. Another example of the modular design is the :ref:`recipe system <news>` for 
fetching news. 

Code layout
^^^^^^^^^^^^^^

All the |app| python code is in the ``calibre`` package. This package contains the following main sub-packages

    * devices - All the device drivers. Just look through some of the built-in drivers to get an idea for how they work.
    * ebooks  - All the ebook conversion code. A good starting point is ``calibre.ebooks.conversion.cli`` which is the
      module powering the :command:`ebook-convert` command.
    * library - The database backed and the content server. 
    * gui2 - The Graphical User Interface. 

Getting the code
------------------

|app| uses `Bazaar <http://bazaar-vcs.org/>`_ a distributed version control system. Bazaar is available on all the platforms |app| supports.
After installing Bazaar, you can get the calibre source code with the command::

    bzr branch lp:calibre

On Windows you will need the complete path name, that will be something like :file:`C:\\Program Files\\Bazaar\\bzr.exe`. To update a branch
to the latest code, use the command::

    bzr merge

Submitting your changes to be included
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you only plan to only make a few small changes, you can make your changes and create a
"merge directive" which you can then attach to a ticket in the |app| bug tracker for consideration. To do
this, make your changes, then run::

    bzr commit -m "Comment describing your changes"
    bzr send -o my-changes

This will create a :file:`my-changes` file in the current directory,
simply attach that to a ticket on the |app| `bug tracker <http://bugs.calibre-ebook.com/newticket>`_.

If you plan to do a lot of development on |app|, then the best method is to create a 
`Launchpad <http://launchpad.net>`_ account. Once you have the account, you can use it to register
your bzr branch created by the `bzr branch` command above with the |app| project. First run the
following command to tell bzr about your launchpad account::

    bzr launchpad-login your_launchpad_username

Now, you have to setup SSH access to Launchpad. First create an SSH public/private keypair. Then upload 
the public key to Launchpad by going to your Launchpad account page. Instructions for setting up the 
private key in bzr are at http://bazaar-vcs.org/Bzr_and_SSH. Now you can upload your branch to the |app|
project in Launchapd by following the instructions at https://help.launchpad.net/Code/UploadingABranch.
Now whenever you commit changes to your branch with the command::

    bzr commit -m "Comment describing your change"

I can merge it directly from you branch into the main |app| source tree. You should also subscribe to the |app|
developers mailing list `calibre-devs <https://launchpad.net/~calibre-devs>`_. Before making major changes, you should
discuss them on the mailing list or the #calibre IRC channel on Freenode to ensure that the changes will be accepted once you're done. 

Windows development environment
---------------------------------

Install |app| normally, using the windows installer. Then, open a Command Prompt and change to
the previously checked out calibre code directory, for example::

    cd C:\Users\kovid\work\calibre

calibre is the directory that contains the src and resources sub directories. 

The next step is to set the environment variable ``CALIBRE_DEVELOP_FROM`` to the absolute path to the src directory.
So, following the example above, it would be ``C:\Users\kovid\work\calibre\src``. A short
`guide <http://docs.python.org/using/windows.html#excursus-setting-environment-variables>`_ to setting environment
variables on windows. 

Once you have set the environment variable, open a new Command Prompt and check that it was correctly set by using
the command::

    echo %CALIBRE_DEVELOP_FROM%

Setting this environment variable means that |app| will now load all its Python code from the specified location.

That's it! You are now ready to start hacking on the |app| code. For example, open the file :file:`src\\calibre\\__init__.py`
in your favorite editor and add the line::
    
    print "Hello, world!"

near the top of the file. Now run the command :command:`calibredb`. The very first line of output should be ``Hello, world!``.

OS X development environment
------------------------------

Install |app| normally, using the provided .dmg. Then, open a Terminal and change to
the previously checked out calibre code directory, for example::

    cd /Users/kovid/work/calibre

calibre is the directory that contains the src and resources sub directories. Ensure you have installed the |app| commandline tools via Preferences->Advanced in the |app| GUI.

The next step is to set the environment variable ``CALIBRE_DEVELOP_FROM`` to the absolute path to the src directory.
So, following the example above, it would be ``/Users/kovid/work/calibre/src``. Apple 
`documentation <http://developer.apple.com/mac/library/documentation/MacOSX/Conceptual/BPRuntimeConfig/Articles/EnvironmentVars.html#//apple_ref/doc/uid/20002093-BCIJIJBH>`_
on how to set environment variables. 

Once you have set the environment variable, open a new Terminal and check that it was correctly set by using
the command::

    echo $CALIBRE_DEVELOP_FROM

Setting this environment variable means that |app| will now load all its Python code from the specified location.

That's it! You are now ready to start hacking on the |app| code. For example, open the file :file:`src/calibre/__init__.py`
in your favorite editor and add the line::
    
    print "Hello, world!"

near the top of the file. Now run the command :command:`calibredb`. The very first line of output should be ``Hello, world!``.

Linux development environment
------------------------------

|app| is primarily developed on linux. You have two choices in setting up the development environment. You can install the
|app| binary as normal and use that as a runtime environment to do your development. This approach is similar to that
used in windows and linux. Alternatively, you can install |app| from source. Instructions for setting up a development
environment from source are in the INSTALL file in the source tree. Here we will address using the binary a runtime.

Install the |app| using the binary installer. The opena  terminal and change to the previously checked out |app| code directory, for example::

    cd /home/kovid/work/calibre

calibre is the directory that contains the src and resources sub directories. 

The next step is to set the environment variable ``CALIBRE_DEVELOP_FROM`` to the absolute path to the src directory.
So, following the example above, it would be ``/home/kovid/work/calibre/src``. How to set environment variables depends on
your linux distribution and what shell you are using. 

Once you have set the environment variable, open a new terminal and check that it was correctly set by using
the command::

    echo $CALIBRE_DEVELOP_FROM

Setting this environment variable means that |app| will now load all its Python code from the specified location.

That's it! You are now ready to start hacking on the |app| code. For example, open the file :file:`src/calibre/__init__.py`
in your favorite editor and add the line::
    
    print "Hello, world!"

near the top of the file. Now run the command :command:`calibredb`. The very first line of output should be ``Hello, world!``.

