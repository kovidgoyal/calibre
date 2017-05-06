.. _plugins:

API documentation for plugins
===============================

.. module:: calibre.customize
    :synopsis: Defines various abstract base classes that can be subclassed to create plugins.

Defines various abstract base classes that can be subclassed to create powerful plugins. The useful
classes are:

.. contents::
    :depth: 1
    :local:

.. _pluginsPlugin:

Plugin
-----------------

.. autoclass:: Plugin
   :members:
   :member-order: bysource

.. _pluginsFTPlugin:

FileTypePlugin
-----------------

.. autoclass:: FileTypePlugin
   :show-inheritance:
   :members:
   :member-order: bysource

.. _pluginsMetadataPlugin:


Metadata plugins
-------------------

.. autoclass:: MetadataReaderPlugin
   :show-inheritance:
   :members:
   :member-order: bysource


.. autoclass:: MetadataWriterPlugin
   :show-inheritance:
   :members:
   :member-order: bysource


Catalog plugins
----------------

.. autoclass:: CatalogPlugin
   :show-inheritance:
   :members:
   :member-order: bysource

.. _pluginsMetadataSource:

Metadata download plugins
--------------------------

.. module:: calibre.ebooks.metadata.sources.base

.. autoclass:: Source
   :show-inheritance:
   :members:
   :member-order: bysource

.. autoclass:: InternalMetadataCompareKeyGen

Conversion plugins
--------------------

.. module:: calibre.customize.conversion

.. autoclass:: InputFormatPlugin
   :show-inheritance:
   :members:
   :member-order: bysource

.. autoclass:: OutputFormatPlugin
   :show-inheritance:
   :members:
   :member-order: bysource

Device drivers
-----------------

.. module:: calibre.devices.interface

The base class for all device drivers is :class:`DevicePlugin`. However, if your device exposes itself as a USBMS drive to the operating system, you should use the USBMS class instead as it implements all the logic needed to support these kinds of devices.

.. autoclass:: DevicePlugin
   :show-inheritance:
   :members:
   :member-order: bysource

.. autoclass:: BookList
   :show-inheritance:
   :members:
   :member-order: bysource


USB Mass Storage based devices
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The base class for such devices is :class:`calibre.devices.usbms.driver.USBMS`. This class in turn inherits some of its functionality from its bases, documented below. A typical basic USBMS based driver looks like this:

.. code-block:: python

    from calibre.devices.usbms.driver import USBMS

    class PDNOVEL(USBMS):
        name = 'Pandigital Novel device interface'
        gui_name = 'PD Novel'
        description = _('Communicate with the Pandigital Novel')
        author = 'Kovid Goyal'
        supported_platforms = ['windows', 'linux', 'osx']
        FORMATS = ['epub', 'pdf']

        VENDOR_ID   = [0x18d1]
        PRODUCT_ID  = [0xb004]
        BCD         = [0x224]

        THUMBNAIL_HEIGHT = 144

        EBOOK_DIR_MAIN = 'eBooks'
        SUPPORTS_SUB_DIRS = False

        def upload_cover(self, path, filename, metadata):
            coverdata = getattr(metadata, 'thumbnail', None)
            if coverdata and coverdata[2]:
                with open('%s.jpg' % os.path.join(path, filename), 'wb') as coverfile:
                    coverfile.write(coverdata[2])

.. autoclass:: calibre.devices.usbms.device.Device
   :show-inheritance:
   :members:
   :member-order: bysource

.. autoclass:: calibre.devices.usbms.cli.CLI
   :members:
   :member-order: bysource

.. autoclass:: calibre.devices.usbms.driver.USBMS
   :show-inheritance:
   :members:
   :member-order: bysource

User Interface Actions
--------------------------

If you are adding your own plugin in a ZIP file, you should subclass both InterfaceActionBase and InterfaceAction. The :meth:`load_actual_plugin` method of your InterfaceActionBase subclass must return an instantiated object of your InterfaceBase subclass.


.. autoclass:: calibre.gui2.actions.InterfaceAction
   :show-inheritance:
   :members:
   :member-order: bysource

.. autoclass:: calibre.customize.InterfaceActionBase
   :show-inheritance:
   :members:
   :member-order: bysource


Preferences plugins
--------------------------

.. autoclass:: calibre.customize.PreferencesPlugin
   :show-inheritance:
   :members:
   :member-order: bysource

.. autoclass:: calibre.gui2.preferences.ConfigWidgetInterface
   :members:
   :member-order: bysource

.. autoclass:: calibre.gui2.preferences.ConfigWidgetBase
   :members:
   :member-order: bysource

Viewer plugins
----------------

.. autoclass:: calibre.customize.ViewerPlugin
   :show-inheritance:
   :members:
   :member-order: bysource


