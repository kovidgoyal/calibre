.. include:: global.rst

.. _plugins:

API Documentation for plugins
===============================

.. module:: calibre.customize.__init__
    :synopsis: Defines various abstract base classes that can be subclassed to create plugins.

Defines various abstract base classes that can be subclassed to create powerful plugins. The useful
classes are:

.. contents::
    :depth: 1
    :local:

.. _pluginsPlugin:

Plugin
-----------------

.. class:: Plugin

    Abstract base class that contains a number of members and methods to create your plugin. All
    plugins must inherit from this class or a subclass of it.

    The members and methods are:

.. automember:: Plugin.name

.. automember:: Plugin.author

.. automember:: Plugin.description

.. automember:: Plugin.version

.. automember:: Plugin.supported_platforms

.. automember:: Plugin.priority

.. automember:: Plugin.minimum_calibre_version

.. automember:: Plugin.can_be_disabled

.. automethod:: Plugin.initialize

.. automethod:: Plugin.customization_help

.. automethod:: Plugin.temporary_file

.. _pluginsFTPlugin:

FileTypePlugin
-----------------

.. class:: Plugin

    Abstract base class that contains a number of members and methods to create your file type plugin. All file type
    plugins must inherit from this class or a subclass of it.

    The members and methods are:

.. automember:: FileTypePlugin.file_types

.. automember:: FileTypePlugin.on_import

.. automember:: FileTypePlugin.on_preprocess

.. automember:: FileTypePlugin.on_postprocess

.. automethod:: FileTypePlugin.run

.. _pluginsMetadataPlugin:

Metadata plugins
-------------------

.. class:: MetadataReaderPlugin

    Abstract base class that contains a number of members and methods to create your metadata reader plugin. All metadata
    reader plugins must inherit from this class or a subclass of it.

    The members and methods are:

.. automember:: MetadataReaderPlugin.file_types

.. automethod:: MetadataReaderPlugin.get_metadata


.. class:: MetadataWriterPlugin

    Abstract base class that contains a number of members and methods to create your metadata writer plugin. All metadata
    writer plugins must inherit from this class or a subclass of it.

    The members and methods are:

.. automember:: MetadataWriterPlugin.file_types

.. automethod:: MetadataWriterPlugin.set_metadata
