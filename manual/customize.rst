.. currentmodule:: calibre.customize.__init__

.. _customize:

Customizing calibre
==================================

calibre has a highly modular design. Various parts of it can be customized. You can learn how to create
*recipes* to add new sources of online content to calibre in the Section :ref:`news`. Here, you will learn,
first, how to use environment variables and *tweaks* to customize calibre's behavior,  and then how to
specify your own static resources like icons and templates to override the defaults and finally how to
use *plugins* to add functionality to calibre.

.. contents::
    :depth: 2
    :local:

.. toctree::
   :hidden:

   plugins

Environment variables
-----------------------

    * ``CALIBRE_CONFIG_DIRECTORY`` - sets the directory where configuration files are stored/read.
    * ``CALIBRE_TEMP_DIR`` - sets the temporary directory used by calibre
    * ``CALIBRE_CACHE_DIRECTORY`` - sets the directory calibre uses to cache persistent data between sessions
    * ``CALIBRE_OVERRIDE_DATABASE_PATH`` - allows you to specify the full path to metadata.db. Using this variable you can have metadata.db be in a location other than the library folder. Useful if your library folder is on a networked drive that does not support file locking.
    * ``CALIBRE_DEVELOP_FROM`` - Used to run from a calibre development environment. See :ref:`develop`.
    * ``CALIBRE_OVERRIDE_LANG`` - Used to force the language used by the interface (ISO 639 language code)
    * ``CALIBRE_TEST_TRANSLATION`` - Used to test a translation .po file (should be the path to the .po file)
    * ``CALIBRE_NO_NATIVE_FILEDIALOGS`` - Causes calibre to not use native file dialogs for selecting files/directories.
    * ``CALIBRE_NO_NATIVE_MENUBAR`` - Causes calibre to not create a native (global) menu on Ubuntu Unity and similar linux desktop environments. The menu is instead placed inside the window, as is traditional.
    * ``CALIBRE_USE_SYSTEM_THEME`` - By default, on Linux, calibre uses its own
      builtin Qt style. This is to avoid crashes and hangs caused by incompatibilities
      between the version of Qt calibre is built against and the system Qt. The
      downside is that calibre may not follow the system look and feel. If
      you set this environment variable on Linux, it will cause calibre to use
      the system theme -- beware of crashes and hangs.
    * ``CALIBRE_SHOW_DEPRECATION_WARNINGS`` - Causes calibre to print deprecation warnings to stdout. Useful for calibre developers.
    * ``CALIBRE_NO_DEFAULT_PROGRAMS`` - Prevent calibre from automatically registering the filetypes it is capable of handling with Windows.
    * ``CALIBRE_USE_DARK_PALETTE`` - Set it to ``1`` to have calibre use dark colors and ``0`` for normal colors (ignored on macOS).
      On Windows 10 in the absence of this variable, the Windows system preference for dark colors is used.
    * ``SYSFS_PATH`` - Use if sysfs is mounted somewhere other than /sys
    * ``http_proxy``, ``https_proxy`` - Used on Linux to specify an HTTP(S) proxy

See `How to set environment variables in Windows <https://www.computerhope.com/issues/ch000549.htm>`_. If you are on macOS
you can set environment variables by creating the :file:`~/Library/Preferences/calibre/macos-env.txt` and putting
the environment variables one per line in it, for example::

    CALIBRE_DEVELOP_FROM=$HOME/calibre-src/src
    CALIBRE_NO_NATIVE_FILEDIALOGS=1
    CALIBRE_CONFIG_DIRECTORY=~/.config/calibre


Tweaks
------------

Tweaks are small changes that you can specify to control various aspects of calibre's behavior. You can change them by going to Preferences->Advanced->Tweaks.
The default values for the tweaks are reproduced below

.. literalinclude:: ../resources/default_tweaks.py


Overriding icons, templates, et cetera
----------------------------------------

.. note::
    calibre has direct support for icon themes, there are several icon themes
    available for calibre, that you can use by going to :guilabel:`Preferences->Interface->Look & Feel->Change Icon theme`.
    The icon themes use the same mechanism as described below for overriding static resources.

calibre allows you to override the static resources, like icons, JavaScript and
templates for the metadata jacket, catalogs, etc. with customized versions that
you like.  All static resources are stored in the resources sub-folder of the
calibre install location. On Windows, this is usually :file:`C:\\Program Files\\Calibre2\\app\\resources`.
On macOS, :file:`/Applications/calibre.app/Contents/Resources/resources/`. On Linux, if
you are using the binary installer from the calibre website it will be
:file:`/opt/calibre/resources`. These paths can change depending on where you
choose to install calibre.

You should not change the files in this resources folder, as your changes will
get overwritten the next time you update calibre. Instead, go to
:guilabel:`Preferences->Advanced->Miscellaneous` and click
:guilabel:`Open calibre configuration directory`. In this configuration directory, create a
sub-folder called resources and place the files you want to override in it.
Place the files in the appropriate sub folders, for example place images in
:file:`resources/images`, etc. calibre will automatically use your custom file
in preference to the built-in one the next time it is started.

For example, if you wanted to change the icon for the :guilabel:`Remove books`
action, you would first look in the built-in resources folder and see that the
relevant file is :file:`resources/images/remove_books.png`. Assuming you have an
alternate icon in PNG format called :file:`my_remove_books.png` you would save it in
the configuration directory as :file:`resources/images/remove_books.png`. All the
icons used by the calibre user interface are in :file:`resources/images` and
its sub-folders.

Creating your own icon theme for calibre
-------------------------------------------------------------

If you have created a beautiful set of icons and wish to share them with other
calibre users via calibre's builtin icon theme support, you can easily package
up your icons into a theme. To do so, go to
:guilabel:`Preferences->Miscellaneous->Create icon theme`, select the folder
where you have put your icons (usually the :file:`resources/images` folder in
the calibre config directory, as described above). Then fill up the theme
metadata and click OK.  This will result in a ZIP file containing the theme
icons. You can upload that to the calibre forum at `Mobileread
<https://www.mobileread.com/forums/forumdisplay.php?f=166>`_ and then I will
make your theme available via calibre's builtin icon theme system.


Customizing calibre with plugins
--------------------------------

calibre has a very modular design. Almost all functionality in calibre comes in the form of plugins. Plugins are used for conversion, for downloading news (though these are called recipes), for various components of the user interface, to connect to different devices, to process files when adding them to calibre and so on. You can get a complete list of all the built-in plugins in calibre by going to :guilabel:`Preferences->Advanced->Plugins`.

You can write your own plugins to customize and extend the behavior of calibre. The plugin architecture in calibre is very simple, see the tutorial :ref:`pluginstutorial`.
