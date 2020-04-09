.. _develop:

Setting up a calibre development environment
===========================================================

calibre is completely open source, licensed under the `GNU GPL v3 <https://www.gnu.org/licenses/gpl.html>`_.
This means that you are free to download and modify the program to your heart's content. In this section,
you will learn how to get a calibre development environment set up on the operating system of your choice.
calibre is written primarily in `Python <https://www.python.org>`_ with some C/C++ code for speed and system interfacing.
Note that calibre requires at least Python 3.8.

.. contents:: Contents
  :depth: 2
  :local:

Design philosophy
-------------------

calibre has its roots in the Unix world, which means that its design is highly modular.
The modules interact with each other via well defined interfaces. This makes adding new features and fixing
bugs in calibre very easy, resulting in a frenetic pace of development. Because of its roots, calibre has a
comprehensive command line interface for all its functions, documented in :doc:`generated/en/cli-index`.

The modular design of calibre is expressed via ``Plugins``. There is a :ref:`tutorial <customize>` on writing calibre plugins.
For example, adding support for a new device to calibre typically involves writing less than a 100 lines of code in the form of
a device driver plugin. You can browse the
`built-in drivers <https://github.com/kovidgoyal/calibre/tree/master/src/calibre/devices>`_. Similarly, adding support
for new conversion formats involves writing input/output format plugins. Another example of the modular design is the :ref:`recipe system <news>` for
fetching news. For more examples of plugins designed to add features to calibre, see the `Index of plugins <https://www.mobileread.com/forums/showthread.php?p=1362767#post1362767>`_.

.. _code_layout:

Code layout
^^^^^^^^^^^^^^

All the calibre python code is in the ``calibre`` package. This package contains the following main sub-packages

    * devices - All the device drivers. Just look through some of the built-in drivers to get an idea for how they work.

      * For details, see: ``devices.interface`` which defines the interface supported by device drivers and ``devices.usbms`` which
        defines a generic driver that connects to a USBMS device. All USBMS based drivers in calibre inherit from it.

    * e-books  - All the e-book conversion/metadata code. A good starting point is ``calibre.ebooks.conversion.cli`` which is the
      module powering the :command:`ebook-convert` command. The conversion process is controlled via ``conversion.plumber``.
      The format independent code is all in ``ebooks.oeb`` and the format dependent code is in ``ebooks.format_name``.

        * Metadata reading, writing, and downloading is all in ``ebooks.metadata``
        * Conversion happens in a pipeline, for the structure of the pipeline,
          see :ref:`conversion-introduction`. The pipeline consists of an input
          plugin, various transforms and an output plugin. The code that constructs
          and drives the pipeline is in :file:`plumber.py`. The pipeline works on a
          representation of an e-book that is like an unzipped epub, with
          manifest, spine, toc, guide, html content, etc. The
          class that manages this representation is OEBBook in ``ebooks.oeb.base``. The
          various transformations that are applied to the book during
          conversions live in :file:`oeb/transforms/*.py`. And the input and output
          plugins live in :file:`conversion/plugins/*.py`.
        * E-book editing happens using a different container object. It is
          documented in :ref:`polish_api`.

    * db - The database back-end. See :ref:`db_api` for the interface to the calibre library.

    * Content server: ``srv`` is the calibre Content server.

    * gui2 - The Graphical User Interface. GUI initialization happens in ``gui2.main`` and ``gui2.ui``. The e-book-viewer is in ``gui2.viewer``. The e-book editor is in ``gui2.tweak_book``.

If you want to locate the entry points for all the various calibre executables,
look at the ``entry_points`` structure in `linux.py
<https://github.com/kovidgoyal/calibre/blob/master/src/calibre/linux.py>`_.

If you need help understanding the code, post in the `development forum <https://www.mobileread.com/forums/forumdisplay.php?f=240>`_
and you will most likely get help from one of calibre's many developers.

Getting the code
------------------

You can get the calibre source code in two ways, using a version control system or
directly downloading a `tarball <https://calibre-ebook.com/dist/src>`_.

calibre uses `Git <https://www.git-scm.com/>`_, a distributed version control
system. Git is available on all the platforms calibre supports.  After
installing Git, you can get the calibre source code with the command::

    git clone git://github.com/kovidgoyal/calibre.git

On Windows you will need the complete path name, that will be something like :file:`C:\\Program Files\\Git\\git.exe`.

calibre is a very large project with a very long source control history, so the
above can take a while (10 mins to an hour depending on your internet speed).

If you want to get the code faster, the source code for the latest release is
always available as an `archive <https://calibre-ebook.com/dist/src>`_.

To update a branch to the latest code, use the command::

    git pull --no-edit

You can also browse the code at `GitHub <https://github.com/kovidgoyal/calibre>`_.

Submitting your changes to be included
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you only plan to make a few small changes, you can make your changes and
create a "merge directive" which you can then attach to a ticket in the calibre
`bug tracker <https://bugs.launchpad.net/calibre>`_. To do this, make your
changes, then run::

    git commit -am "Comment describing your changes"
    git format-patch origin/master --stdout > my-changes

This will create a :file:`my-changes` file in the current directory,
simply attach that to a ticket on the calibre `bug tracker <https://bugs.launchpad.net/calibre>`_.
Note that this will include *all* the commits you have made. If you only want
to send some commits, you have to change ``origin/master`` above. To send only
the last commit, use::

    git format-patch HEAD~1 --stdout > my-changes

To send the last *n* commits, replace *1* with *n*, for example, for the last 3
commits::

    git format-patch HEAD~3 --stdout > my-changes

Be careful to not include merges when using ``HEAD~n``.

If you plan to do a lot of development on calibre, then the best method is to create a
`GitHub <https://github.com>`__ account. Below is a basic guide to setting up
your own fork of calibre in a way that will allow you to submit pull requests
for inclusion into the main calibre repository:

  * Setup git on your machine as described in this article: `Setup Git <https://help.github.com/articles/set-up-git>`_
  * Setup ssh keys for authentication to GitHub, as described here: `Generating SSH keys <https://help.github.com/articles/generating-ssh-keys>`_
  * Go to https://github.com/kovidgoyal/calibre and click the :guilabel:`Fork` button.
  * In a Terminal do::

        git clone git@github.com:<username>/calibre.git
        git remote add upstream https://github.com/kovidgoyal/calibre.git

    Replace <username> above with your GitHub username. That will get your fork checked out locally.
  * You can make changes and commit them whenever you like. When you are ready to have your work merged, do a::

        git push

    and go to ``https://github.com/<username>/calibre`` and click the :guilabel:`Pull Request` button to generate a pull request that can be merged.
  * You can update your local copy with code from the main repo at any time by doing::

        git pull upstream


You should also keep an eye on the calibre `development forum
<https://www.mobileread.com/forums/forumdisplay.php?f=240>`_. Before making
major changes, you should discuss them in the forum or contact Kovid directly
(his email address is all over the source code).

Windows development environment
---------------------------------

.. note:: You must also get the calibre source code separately as described above.

Install calibre normally, using the Windows installer. Then open a Command Prompt and change to
the previously checked out calibre code directory. For example::

    cd C:\Users\kovid\work\calibre

calibre is the directory that contains the src and resources sub-directories.

The next step is to set the environment variable ``CALIBRE_DEVELOP_FROM`` to the absolute path of the src directory.
So, following the example above, it would be ``C:\Users\kovid\work\calibre\src``. `Here is a short
guide <https://docs.python.org/using/windows.html#excursus-setting-environment-variables>`_ to setting environment
variables on Windows.

Once you have set the environment variable, open a new command prompt and check that it was correctly set by using
the command::

    echo %CALIBRE_DEVELOP_FROM%

Setting this environment variable means that calibre will now load all its Python code from the specified location.

That's it! You are now ready to start hacking on the calibre code. For example, open the file :file:`src\\calibre\\__init__.py`
in your favorite editor and add the line::

    print ("Hello, world!")

near the top of the file. Now run the command :command:`calibredb`. The very first line of output should be ``Hello, world!``.

You can also setup a calibre development environment inside the free Microsoft
Visual Studio, if you like, following the instructions `here <https://www.mobileread.com/forums/showthread.php?t=251201>`_.

macOS development environment
------------------------------

.. note:: You must also get the calibre source code separately as described above.

Install calibre normally using the provided .dmg. Then open a Terminal and change to
the previously checked out calibre code directory, for example::

    cd /Users/kovid/work/calibre

calibre is the directory that contains the src and resources sub-directories.
The calibre command line tools are found inside the calibre app bundle, in
:file:`/Applications/calibre.app/Contents/MacOS`
you should add this directory to your PATH environment variable, if you want to
run the command line tools easily.

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

.. note:: You must also get the calibre source code separately as described above.

calibre is primarily developed on Linux. You have two choices in setting up the development environment. You can install the
calibre binary as normal and use that as a runtime environment to do your development. This approach is similar to that
used in Windows and macOS. Alternatively, you can install calibre from source. Instructions for setting up a development
environment from source are in the INSTALL file in the source tree. Here we will address using the binary as a runtime, which is the
recommended method.

Install calibre using the binary installer. Then open a terminal and change to the previously checked out calibre code directory, for example::

    cd /home/kovid/work/calibre

calibre is the directory that contains the src and resources sub-directories.

The next step is to set the environment variable ``CALIBRE_DEVELOP_FROM`` to the absolute path of the src directory.
So, following the example above, it would be ``/home/kovid/work/calibre/src``. How to set environment variables depends on
your Linux distribution and what shell you are using.

Once you have set the environment variable, open a new terminal and check that it was correctly set by using
the command::

    echo $CALIBRE_DEVELOP_FROM

Setting this environment variable means that calibre will now load all its Python code from the specified location.

That's it! You are now ready to start hacking on the calibre code. For example, open the file :file:`src/calibre/__init__.py`
in your favorite editor and add the line::

    print ("Hello, world!")

near the top of the file. Now run the command :command:`calibredb`. The very first line of output should be ``Hello, world!``.

Having separate "normal" and "development" calibre installs on the same computer
-----------------------------------------------------------------------------------------------------------------

The calibre source tree is very stable and rarely breaks, but if you feel the need to run from source on a separate
test library and run the released calibre version with your everyday library, you can achieve this easily using
.bat files or shell scripts to launch calibre. The example below shows how to do this on Windows using .bat files (the
instructions for other platforms are the same, just use a shell script instead of a .bat file)

To launch the release version of calibre with your everyday library:

calibre-normal.bat::

    calibre.exe "--with-library=C:\path\to\everyday\library folder"

calibre-dev.bat::

    set CALIBRE_DEVELOP_FROM=C:\path\to\calibre\checkout\src
    calibre.exe "--with-library=C:\path\to\test\library folder"


Debugging tips
----------------

Python is a
dynamically typed language with excellent facilities for introspection. Kovid wrote the core calibre code without once
using a debugger. There are many strategies to debug calibre code:

Using print statements
^^^^^^^^^^^^^^^^^^^^^^^

This is Kovid's favorite way to debug. Simply insert print statements at points of interest and run your program in the
terminal. For example, you can start the GUI from the terminal as::

    calibre-debug -g

Similarly, you can start the e-book-viewer as::

    calibre-debug -w /path/to/file/to/be/viewed

The e-book-editor can be started as::

    calibre-debug -t /path/to/be/edited

Using an interactive Python interpreter
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can insert the following two lines of code to start an interactive Python session at that point::

    from calibre import ipython
    ipython(locals())

When running from the command line, this will start an interactive Python interpreter with access to all
locally defined variables (variables in the local scope). The interactive prompt even has TAB completion
for object properties and you can use the various Python facilities for introspection, such as
:func:`dir`, :func:`type`, :func:`repr`, etc.

Using the Python debugger as a remote debugger
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can use the builtin Python debugger (pdb) as a remote debugger from the
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

You can read about how to use the Python debugger in the `Python stdlib docs
for the pdb module <https://docs.python.org/library/pdb.html#debugger-commands>`_.

.. note::
    By default, the remote debugger will try to connect on port 4444. You can
    change it, by passing the port parameter to both the set_trace() and the
    cli() functions above, like this: ``set_trace(port=1234)`` and
    ``cli(port=1234)``.

.. note::
    The Python debugger cannot handle multiple threads, so you have to
    call set_trace once per thread, each time with a different port number.

Using the debugger in your favorite Python IDE
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is possible to use the builtin debugger in your favorite Python IDE, if it
supports remote debugging. The first step is to add the calibre src checkout to
the ``PYTHONPATH`` in your IDE. In other words, the directory you set as
``CALIBRE_DEVELOP_FROM`` above, must also be in the ``PYTHONPATH`` of your IDE.

Then place the IDE's remote debugger module into the :file:`src` subdirectory
of the calibre source code checkout. Add whatever code is needed to launch the
remote debugger to calibre at the point of interest, for example in the main
function. Then run calibre as normal. Your IDE should now be able to connect to
the remote debugger running inside calibre.

Executing arbitrary scripts in the calibre Python environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :command:`calibre-debug` command provides a couple of handy switches to execute your own
code, with access to the calibre modules::

    calibre-debug -c "some Python code"

is great for testing a little snippet of code on the command line. It works in the same way as the -c switch to the Python interpreter::

    calibre-debug myscript.py

can be used to execute your own Python script. It works in the same way as passing the script to the Python interpreter, except
that the calibre environment is fully initialized, so you can use all the calibre code in your script. To use command line arguments with your script, use the form::

    calibre-debug myscript.py -- --option1 arg1

The ``--`` causes all subsequent arguments to be passed to your script.


Using calibre in your projects
----------------------------------------

It is possible to directly use calibre functions/code in your Python project. Two ways exist to do this:

Binary install of calibre
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you have a binary install of calibre, you can use the Python interpreter bundled with calibre, like this::

    calibre-debug /path/to/your/python/script.py -- arguments to your script

Source install on Linux
^^^^^^^^^^^^^^^^^^^^^^^^^^

In addition to using the above technique, if you do a source install on Linux,
you can also directly import calibre, as follows::

    import init_calibre
    import calibre

    print calibre.__version__

It is essential that you import the init_calibre module before any other calibre modules/packages as
it sets up the interpreter to run calibre code.

API documentation for various parts of calibre
------------------------------------------------

.. toctree::
    :maxdepth: 1

    news_recipe
    plugins
    db_api
    polish
