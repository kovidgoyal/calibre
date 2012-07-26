.. include:: global.rst

.. _develop:

Setting up a |app| development environment
===========================================

|app| is completely open source, licensed under the `GNU GPL v3 <http://www.gnu.org/copyleft/gpl.html>`_.
This means that you are free to download and modify the program to your heart's content. In this section,
you will learn how to get a |app| development environment set up on the operating system of your choice.
|app| is written primarily in `Python <http://www.python.org>`_ with some C/C++ code for speed and system interfacing.
Note that |app| is not compatible with Python 3 and requires at least Python 2.7.

.. contents:: Contents
  :depth: 2
  :local:

Design philosophy
-------------------

|app| has its roots in the Unix world, which means that its design is highly modular.
The modules interact with each other via well defined interfaces. This makes adding new features and fixing
bugs in |app| very easy, resulting in a frenetic pace of development. Because of its roots, |app| has a
comprehensive command line interface for all its functions, documented in :ref:`cli`.

The modular design of |app| is expressed via ``Plugins``. There is a :ref:`tutorial <customize>` on writing |app| plugins.
For example, adding support for a new device to |app| typically involves writing less than a 100 lines of code in the form of
a device driver plugin. You can browse the
`built-in drivers <http://bazaar.launchpad.net/%7Ekovid/calibre/trunk/files/head%3A/src/calibre/devices/>`_. Similarly, adding support
for new conversion formats involves writing input/output format plugins. Another example of the modular design is the :ref:`recipe system <news>` for
fetching news. For more examples of plugins designed to add features to |app|, see the `plugin index <http://www.mobileread.com/forums/showthread.php?p=1362767#post1362767>`_.

Code layout
^^^^^^^^^^^^^^

All the |app| python code is in the ``calibre`` package. This package contains the following main sub-packages

    * devices - All the device drivers. Just look through some of the built-in drivers to get an idea for how they work.

      * For details, see: devices.interface which defines the interface supported by device drivers and devices.usbms which
        defines a generic driver that connects to a USBMS device. All USBMS based drivers in |app| inherit from it.

    * ebooks  - All the ebook conversion/metadata code. A good starting point is ``calibre.ebooks.conversion.cli`` which is the
      module powering the :command:`ebook-convert` command. The conversion process is controlled via conversion.plumber.
      The format independent code is all in ebooks.oeb and the format dependent code is in ebooks.format_name.

        * Metadata reading, writing, and downloading is all in ebooks.metadata
        * Conversion happens in a pipeline, for the structure of the pipeline,
          see :ref:`conversion-introduction`. The pipeline consists of an input
          plugin, various transforms and an output plugin. The code constructs
          and drives the pipeline is in plumber.py. The pipeline works on a
          representation of an ebook that is like an unzipped epub, with
          manifest, spine, toc, guide, html content, etc. The
          class that manages this representation is OEBBook in oeb/base.py. The
          various transformations that are applied to the book during
          conversions live in `oeb/transforms/*.py`. And the input and output
          plugins live in `conversion/plugins/*.py`.

    * library - The database back-end and the content server. See library.database2 for the interface to the |app| library. library.server is the |app| Content Server.
    * gui2 - The Graphical User Interface. GUI initialization happens in gui2.main and gui2.ui. The ebook-viewer is in gui2.viewer.

If you need help understanding the code, post in the `development forum <http://www.mobileread.com/forums/forumdisplay.php?f=240>`_
and you will most likely get help from one of |app|'s many developers.

Getting the code
------------------

|app| uses `Bazaar <http://bazaar-vcs.org/>`_, a distributed version control system. Bazaar is available on all the platforms |app| supports.
After installing Bazaar, you can get the |app| source code with the command::

    bzr branch lp:calibre

On Windows you will need the complete path name, that will be something like :file:`C:\\Program Files\\Bazaar\\bzr.exe`. To update a branch
to the latest code, use the command::

    bzr merge

The calibre repository is huge so the branch operation above takes along time (about an hour). If you want to get the code faster, the sourcecode for the latest release is always available as an
`archive <http://status.calibre-ebook.com/dist/src>`_.

Submitting your changes to be included
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you only plan to make a few small changes, you can make your changes and create a
"merge directive" which you can then attach to a ticket in the |app| bug tracker for consideration. To do
this, make your changes, then run::

    bzr commit -m "Comment describing your changes"
    bzr send -o my-changes

This will create a :file:`my-changes` file in the current directory,
simply attach that to a ticket on the |app| `bug tracker <https://bugs.launchpad.net/calibre>`_.

If you plan to do a lot of development on |app|, then the best method is to create a
`Launchpad <http://launchpad.net>`_ account. Once you have an account, you can use it to register
your bzr branch created by the `bzr branch` command above. First run the
following command to tell bzr about your launchpad account::

    bzr launchpad-login your_launchpad_username

Now, you have to setup SSH access to Launchpad. First create an SSH public/private keypair. Then upload
the public key to Launchpad by going to your Launchpad account page. Instructions for setting up the
private key in bzr are at http://bazaar-vcs.org/Bzr_and_SSH. Now you can upload your branch to the |app|
project in Launchpad by following the instructions at https://help.launchpad.net/Code/UploadingABranch.
Whenever you commit changes to your branch with the command::

    bzr commit -m "Comment describing your change"

Kovid can merge it directly from your branch into the main |app| source tree. You should also keep an eye on the |app|
`development forum <http://www.mobileread.com/forums/forumdisplay.php?f=240>`. Before making major changes, you should
discuss them in the forum or contact Kovid directly (his email address is all over the source code).

Windows development environment
---------------------------------

Install |app| normally, using the Windows installer. Then open a Command Prompt and change to
the previously checked out |app| code directory. For example::

    cd C:\Users\kovid\work\calibre

calibre is the directory that contains the src and resources sub-directories.

The next step is to set the environment variable ``CALIBRE_DEVELOP_FROM`` to the absolute path of the src directory.
So, following the example above, it would be ``C:\Users\kovid\work\calibre\src``. `Here is a short
guide <http://docs.python.org/using/windows.html#excursus-setting-environment-variables>`_ to setting environment
variables on Windows.

Once you have set the environment variable, open a new command prompt and check that it was correctly set by using
the command::

    echo %CALIBRE_DEVELOP_FROM%

Setting this environment variable means that |app| will now load all its Python code from the specified location.

That's it! You are now ready to start hacking on the |app| code. For example, open the file :file:`src\\calibre\\__init__.py`
in your favorite editor and add the line::

    print ("Hello, world!")

near the top of the file. Now run the command :command:`calibredb`. The very first line of output should be ``Hello, world!``.

OS X development environment
------------------------------

Install |app| normally using the provided .dmg. Then open a Terminal and change to
the previously checked out |app| code directory, for example::

    cd /Users/kovid/work/calibre

calibre is the directory that contains the src and resources sub-directories. Ensure you have installed the |app| commandline tools via :guilabel:`Preferences->Advanced->Miscellaneous` in the |app| GUI.

The next step is to create a bash script that will set the environment variable ``CALIBRE_DEVELOP_FROM`` to the absolute path of the src directory when running calibre in debug mode.

Create a plain text file:
    #!/bin/sh
    export CALIBRE_DEVELOP_FROM="/Users/kovid/work/calibre/src"
    calibre-debug -g

Save this file as ``/usr/bin/calibre-develop``, then set its permissions so that it can be run:
    chmod +x /usr/bin/calibre-develop

Once you have done this, type
    calibre-develop

You should see some diagnostic information in the Terminal window as calibre starts up, and you should see an asterisk after the version number in the GUI window, indicating that you are running from source.

That's it! You are now ready to start hacking on the |app| code. For example, open the file :file:`src/calibre/__init__.py`
in your favorite editor and add the line::

    print ("Hello, world!")

near the top of the file. Now run the command :command:`calibredb`. The very first line of output should be ``Hello, world!``.

Linux development environment
------------------------------

|app| is primarily developed on Linux. You have two choices in setting up the development environment. You can install the
|app| binary as normal and use that as a runtime environment to do your development. This approach is similar to that
used in Windows and OS X. Alternatively, you can install |app| from source. Instructions for setting up a development
environment from source are in the INSTALL file in the source tree. Here we will address using the binary at runtime, which is the
recommended method.

Install the |app| using the binary installer. Then open a terminal and change to the previously checked out |app| code directory, for example::

    cd /home/kovid/work/calibre

calibre is the directory that contains the src and resources sub-directories.

The next step is to set the environment variable ``CALIBRE_DEVELOP_FROM`` to the absolute path of the src directory.
So, following the example above, it would be ``/home/kovid/work/calibre/src``. How to set environment variables depends on
your Linux distribution and what shell you are using.

Once you have set the environment variable, open a new terminal and check that it was correctly set by using
the command::

    echo $CALIBRE_DEVELOP_FROM

Setting this environment variable means that |app| will now load all its Python code from the specified location.

That's it! You are now ready to start hacking on the |app| code. For example, open the file :file:`src/calibre/__init__.py`
in your favorite editor and add the line::

    print ("Hello, world!")

near the top of the file. Now run the command :command:`calibredb`. The very first line of output should be ``Hello, world!``.

Having separate "normal" and "development" |app| installs on the same computer
-------------------------------------------------------------------------------

The |app| source tree is very stable and rarely breaks, but if you feel the need to run from source on a separate
test library and run the released |app| version with your everyday library, you can achieve this easily using
.bat files or shell scripts to launch |app|. The example below shows how to do this on Windows using .bat files (the
instructions for other platforms are the same, just use a shell script instead of a .bat file)

To launch the release version of |app| with your everyday library:

calibre-normal.bat::

    calibre.exe "--with-library=C:\path\to\everyday\library folder"

calibre-dev.bat::

    set CALIBRE_DEVELOP_FROM=C:\path\to\calibre\checkout\src
    calibre.exe "--with-library=C:\path\to\test\library folder"


Debugging tips
----------------

Python is a
dynamically typed language with excellent facilities for introspection. Kovid wrote the core |app| code without once
using a debugger. There are many strategies to debug |app| code:

Using an interactive python interpreter
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can insert the following two lines of code to start an interactive python session at that point::

    from calibre import ipython
    ipython(locals())

When running from the command line, this will start an interactive Python interpreter with access to all
locally defined variables (variables in the local scope). The interactive prompt even has TAB completion
for object properties and you can use the various Python facilities for introspection, such as
:func:`dir`, :func:`type`, :func:`repr`, etc.

Using print statements
^^^^^^^^^^^^^^^^^^^^^^^

This is Kovid's favorite way to debug. Simply insert print statements at points of interest and run your program in the
terminal. For example, you can start the GUI from the terminal as::

    calibre-debug -g

Similarly, you can start the ebook-viewer as::

    calibre-debug -w /path/to/file/to/be/viewed

Using the debugger in PyDev
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is possible to get the debugger in PyDev working with the |app| development environment,
see the `forum thread <http://www.mobileread.com/forums/showthread.php?t=143208>`_.

Executing arbitrary scripts in the |app| python environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :command:`calibre-debug` command provides a couple of handy switches to execute your own
code, with access to the |app| modules::

    calibre-debug -c "some python code"

is great for testing a little snippet of code on the command line. It works in the same way as the -c switch to the python interpreter::

    calibre-debug -e myscript.py

can be used to execute your own Python script. It works in the same way as passing the script to the Python interpreter, except
that the calibre environment is fully initialized, so you can use all the calibre code in your script.


Using |app| in your projects
----------------------------------------

It is possible to directly use |app| functions/code in your Python project. Two ways exist to do this:

Binary install of |app|
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have a binary install of |app|, you can use the Python interpreter bundled with |app|, like this::

    calibre-debug -e /path/to/your/python/script.py

Source install on Linux
^^^^^^^^^^^^^^^^^^^^^^^^^^

In addition to using the above technique, if you do a source install on Linux,
you can also directly import |app|, as follows::

    import init_calibre
    import calibre

    print calibre.__version__

It is essential that you import the init_calibre module before any other |app| modules/packages as
it sets up the interpreter to run |app| code.

