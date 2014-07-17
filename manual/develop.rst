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

.. _code_layout:

Code layout
^^^^^^^^^^^^^^

All the |app| python code is in the ``calibre`` package. This package contains the following main sub-packages

    * devices - All the device drivers. Just look through some of the built-in drivers to get an idea for how they work.

      * For details, see: ``devices.interface`` which defines the interface supported by device drivers and ``devices.usbms`` which
        defines a generic driver that connects to a USBMS device. All USBMS based drivers in |app| inherit from it.

    * ebooks  - All the ebook conversion/metadata code. A good starting point is ``calibre.ebooks.conversion.cli`` which is the
      module powering the :command:`ebook-convert` command. The conversion process is controlled via ``conversion.plumber``.
      The format independent code is all in ``ebooks.oeb`` and the format dependent code is in ``ebooks.format_name``.

        * Metadata reading, writing, and downloading is all in ``ebooks.metadata``
        * Conversion happens in a pipeline, for the structure of the pipeline,
          see :ref:`conversion-introduction`. The pipeline consists of an input
          plugin, various transforms and an output plugin. The code that constructs
          and drives the pipeline is in :file:`plumber.py`. The pipeline works on a
          representation of an ebook that is like an unzipped epub, with
          manifest, spine, toc, guide, html content, etc. The
          class that manages this representation is OEBBook in ``ebooks.oeb.base``. The
          various transformations that are applied to the book during
          conversions live in :file:`oeb/transforms/*.py`. And the input and output
          plugins live in :file:`conversion/plugins/*.py`.
        * Ebook editing happens using a different container object. It is
          documented in :ref:`polish_api`.

    * db - The database back-end. See :ref:`db_api` for the interface to the |app| library. 

    * content server: ``library.server`` is the |app| Content Server.

    * gui2 - The Graphical User Interface. GUI initialization happens in ``gui2.main`` and ``gui2.ui``. The ebook-viewer is in ``gui2.viewer``. The ebook editor is in ``gui2.tweak_book``.

If you want to locate the entry points for all the various |app| executables,
look at the ``entry_points`` structure in `linux.py
<https://github.com/kovidgoyal/calibre/blob/master/src/calibre/linux.py>`_.

If you need help understanding the code, post in the `development forum <http://www.mobileread.com/forums/forumdisplay.php?f=240>`_
and you will most likely get help from one of |app|'s many developers.

Getting the code
------------------

You can get the |app| source code in two ways, using a version control system or
directly downloading a `tarball <http://status.calibre-ebook.com/dist/src>`_.

|app| uses `Git <http://www.git-scm.com/>`_, a distributed version control
system. Git is available on all the platforms |app| supports.  After
installing Git, you can get the |app| source code with the command::

    git clone git://github.com/kovidgoyal/calibre.git

On Windows you will need the complete path name, that will be something like :file:`C:\\Program Files\\Git\\git.exe`. 

|app| is a very large project with a very long source control history, so the
above can take a while (10mins to an hour depending on your internet speed).

If you want to get the code faster, the sourcecode for the latest release is
always available as an `archive <http://status.calibre-ebook.com/dist/src>`_.

To update a branch to the latest code, use the command::

    git pull --no-edit

Submitting your changes to be included
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you only plan to make a few small changes, you can make your changes and
create a "merge directive" which you can then attach to a ticket in the |app|
`bug tracker <https://bugs.launchpad.net/calibre>`_. To do this, make your
changes, then run::

    git commit -am "Comment describing your changes"
    git format-patch origin/master --stdout > my-changes

This will create a :file:`my-changes` file in the current directory,
simply attach that to a ticket on the |app| `bug tracker <https://bugs.launchpad.net/calibre>`_.
Note that this will include *all* the commits you have made. If you only want
to send some commits, you have to change ``origin/master`` above. To send only
the last commit, use::

    git format-patch HEAD~1 --stdout > my-changes

To send the last *n* commits, replace *1* with *n*, for example, for the last 3
commits::

    git format-patch HEAD~3 --stdout > my-changes

Be careful to not include merges when using ``HEAD~n``.

If you plan to do a lot of development on |app|, then the best method is to create a
`GitHub <http://github.com>`_ account. Below is a basic guide to setting up
your own fork of calibre in a way that will allow you to submit pull requests
for inclusion into the main |app| repository:

  * Setup git on your machine as described in this article: `Setup Git <https://help.github.com/articles/set-up-git>`_
  * Setup ssh keys for authentication to GitHub, as described here: `Generating SSH keys <https://help.github.com/articles/generating-ssh-keys>`_
  * Go to https://github.com/kovidgoyal/calibre and click the :guilabel:`Fork` button.
  * In a Terminal do::

        git clone git@github.com:<username>/calibre.git

    Replace <username> above with your github username. That will get your fork checked out locally.
  * You can make changes and commit them whenever you like. When you are ready to have your work merged, do a::

        git push

    and go to ``https://github.com/<username>/calibre`` and click the :guilabel:`Pull Request` button to generate a pull request that can be merged.
  * You can update your local copy with code from the main repo at any time by doing::

        git pull upstream


You should also keep an eye on the |app| `development forum
<http://www.mobileread.com/forums/forumdisplay.php?f=240>`_. Before making
major changes, you should discuss them in the forum or contact Kovid directly
(his email address is all over the source code).

Windows development environment
---------------------------------

.. note:: You must also get the |app| source code separately as described above.

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

.. note:: You must also get the |app| source code separately as described above.

Install |app| normally using the provided .dmg. Then open a Terminal and change to
the previously checked out |app| code directory, for example::

    cd /Users/kovid/work/calibre

calibre is the directory that contains the src and resources sub-directories. Ensure you have installed the |app| commandline tools via :guilabel:`Preferences->Advanced->Miscellaneous` in the |app| GUI.

The next step is to create a bash script that will set the environment variable ``CALIBRE_DEVELOP_FROM`` to the absolute path of the src directory when running calibre in debug mode.

Create a plain text file::

    #!/bin/sh
    export CALIBRE_DEVELOP_FROM="/Users/kovid/work/calibre/src"
    calibre-debug -g

Save this file as ``/usr/bin/calibre-develop``, then set its permissions so that it can be executed::

    chmod +x /usr/bin/calibre-develop

Once you have done this, run::

    calibre-develop

You should see some diagnostic information in the Terminal window as calibre
starts up, and you should see an asterisk after the version number in the GUI
window, indicating that you are running from source.

Linux development environment
------------------------------

.. note:: You must also get the |app| source code separately as described above.

|app| is primarily developed on Linux. You have two choices in setting up the development environment. You can install the
|app| binary as normal and use that as a runtime environment to do your development. This approach is similar to that
used in Windows and OS X. Alternatively, you can install |app| from source. Instructions for setting up a development
environment from source are in the INSTALL file in the source tree. Here we will address using the binary at runtime, which is the
recommended method.

Install |app| using the binary installer. Then open a terminal and change to the previously checked out |app| code directory, for example::

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

Using print statements
^^^^^^^^^^^^^^^^^^^^^^^

This is Kovid's favorite way to debug. Simply insert print statements at points of interest and run your program in the
terminal. For example, you can start the GUI from the terminal as::

    calibre-debug -g

Similarly, you can start the ebook-viewer as::

    calibre-debug -w /path/to/file/to/be/viewed

The ebook-editor can be started as::

    calibre-debug -t /path/to/be/edited

Using an interactive python interpreter
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can insert the following two lines of code to start an interactive python session at that point::

    from calibre import ipython
    ipython(locals())

When running from the command line, this will start an interactive Python interpreter with access to all
locally defined variables (variables in the local scope). The interactive prompt even has TAB completion
for object properties and you can use the various Python facilities for introspection, such as
:func:`dir`, :func:`type`, :func:`repr`, etc.

Using the python debugger as a remote debugger
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can use the builtin python debugger (pdb) as a remote debugger from the
command line. First, start the remote debugger at the point in the calibre code
you are interested in, like this::

    from calibre.rpdb import set_trace
    set_trace()

Then run calibre, either as normal, or using one of the calibre-debug commands
described in the previous section. Once the above point in the code is reached,
calibre will freeze, waiting for the debugger to connect.

Now open a terminal or command prompt and use the following command to start
the debugging session::

    calibre-debug -c "from calibre.rpdb import cli; cli()"

You can read about how to use the python debugger in the `python stdlib docs
for the pdb module <https://docs.python.org/2/library/pdb.html#debugger-commands>`_.

.. note::
    By default, the remote debugger will try to connect on port 4444. You can
    change it, by passing the port parameter to both the set_trace() and the
    cli() functions above, like this: ``set_trace(port=1234)`` and
    ``cli(port=1234)``.

.. note:: 
    The python debugger cannot handle multiple threads, so you have to
    call set_trace once per thread, each time with a different port number.

Using the debugger in your favorite python IDE
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is possible to use the builtin debugger in your favorite python IDE, if it
supports remote debugging. The first step is to add the |app| src checkout to
the ``PYTHONPATH`` in your IDE. In other words, the directory you set as
``CALIBRE_DEVELOP_FROM`` above, must also be in the ``PYTHONPATH`` of your IDE.

Then place the IDE's remote debugger module into the :file:`src` subdirectory
of the |app| source code checkout. Add whatever code is needed to launch the
remote debugger to |app| at the point of interest, for example in the main
function. Then run |app| as normal. Your IDE should now be able to connect to
the remote debugger running inside |app|.

Executing arbitrary scripts in the |app| python environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :command:`calibre-debug` command provides a couple of handy switches to execute your own
code, with access to the |app| modules::

    calibre-debug -c "some python code"

is great for testing a little snippet of code on the command line. It works in the same way as the -c switch to the python interpreter::

    calibre-debug myscript.py

can be used to execute your own Python script. It works in the same way as passing the script to the Python interpreter, except
that the calibre environment is fully initialized, so you can use all the calibre code in your script. To use command line arguments with your script, use the form::

    calibre-debug myscript.py -- --option1 arg1

The ``--`` causes all subsequent arguments to be passed to your script.


Using |app| in your projects
----------------------------------------

It is possible to directly use |app| functions/code in your Python project. Two ways exist to do this:

Binary install of |app|
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have a binary install of |app|, you can use the Python interpreter bundled with |app|, like this::

    calibre-debug /path/to/your/python/script.py -- arguments to your script

Source install on Linux
^^^^^^^^^^^^^^^^^^^^^^^^^^

In addition to using the above technique, if you do a source install on Linux,
you can also directly import |app|, as follows::

    import init_calibre
    import calibre

    print calibre.__version__

It is essential that you import the init_calibre module before any other |app| modules/packages as
it sets up the interpreter to run |app| code.

API documentation for various parts of |app|
------------------------------------------------

.. toctree::
    :maxdepth: 1

    news_recipe
    plugins
    db_api
    polish

