.. include:: global.rst

.. currentmodule:: calibre.customize.__init__

.. _customize:

Customizing |app|
==================================

|app| has a highly modular design. Various parts of it can be customized. You can learn how to create
*recipes* to add new sources of online content to |app| in the Section :ref:`news`. Here, you will learn,
first, how to use environment variables and *tweaks* to customize |app|'s behavior,  and then how to
specify your own static resources like icons and templates to override the defaults and finally how to 
use *plugins* to add functionality to |app|.

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
    * ``CALIBRE_OVERRIDE_DATABASE_PATH`` - allows you to specify the full path to metadata.db. Using this variable you can have metadata.db be in a location other than the library folder. Useful if your library folder is on a networked drive that does not support file locking.
    * ``CALIBRE_DEVELOP_FROM`` - Used to run from a calibre development environment. See :ref:`develop`.
    * ``CALIBRE_OVERRIDE_LANG`` - Used to force the language used by the interface (ISO 639 language code)
    * ``SYSFS_PATH`` - Use if sysfs is mounted somewhere other than /sys
    * ``http_proxy`` - Used on linux to specify an HTTP proxy

Tweaks
------------

Tweaks are small changes that you can specify to control various aspects of |app|'s behavior. You can change them by going to Preferences->Advanced->Tweaks.
The default values for the tweaks are reproduced below

.. literalinclude:: ../../../resources/default_tweaks.py


Overriding icons, templates, et cetera
----------------------------------------

|app| allows you to override the static resources, like icons, templates, javascript, etc. with customized versions that you like.
All static resources are stored in the resources sub-folder of the calibre install location. On Windows, this is usually
:file:`C:/Program Files/Calibre2/resources`. On OS X, :file:`/Applications/calibre.app/Contents/Resources/resources/`. On linux, if you are using the binary installer
from the calibre website it will be :file:`/opt/calibre/resources`. These paths can change depending on where you choose to install |app|. 

You should not change the files in this resources folder, as your changes will get overwritten the next time you update |app|. Instead, go to
:guilabel:`Preferences->Advanced->Miscellaneous` and click :guilabel:`Open calibre configuration directory`. In this configuration directory, create a sub-folder called resources and place the files you want to override in it. Place the files in the appropriate sub folders, for example place images in :file:`resources/images`, etc. 
|app| will automatically use your custom file in preference to the built-in one the next time it is started.

For example, if you wanted to change the icon for the :guilabel:`Remove books` action, you would first look in the built-in resources folder and see that the relevant file is
:file:`resources/images/trash.png`. Assuming you have an alternate icon in PNG format called :file:`mytrash.png` you would save it in the configuration directory as :file:`resources/images/trash.png`. All the icons used by the calibre user interface are in :file:`resources/images` and its sub-folders.

Customizing |app| with plugins
--------------------------------

|app| has a very modular design. Almost all functionality in |app| comes in the form of plugins. Plugins are used for conversion, for downloading news (though these are called recipes), for various components of the user interface, to connect to different devices, to process files when adding them to |app| and so on. You can get a complete list of all the built-in plugins in |app| by going to :guilabel:`Preferences->Plugins`.

You can write your own plugins to customize and extend the behavior of |app|. The plugin architecture in |app| is very simple, see the tutorial :ref:`pluginstutorial`.

