from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys, zipfile, importlib

from calibre.constants import numeric_version, iswindows, isosx
from calibre.ptempfile import PersistentTemporaryFile

platform = 'linux'
if iswindows:
    platform = 'windows'
elif isosx:
    platform = 'osx'


class PluginNotFound(ValueError):
    pass

class InvalidPlugin(ValueError):
    pass


class Plugin(object): # {{{
    '''
    A calibre plugin. Useful members include:

       * ``self.plugin_path``: Stores path to the zip file that contains
                               this plugin or None if it is a builtin
                               plugin
       * ``self.site_customization``: Stores a customization string entered
                                      by the user.

    Methods that should be overridden in sub classes:

       * :meth:`initialize`
       * :meth:`customization_help`

    Useful methods:

        * :meth:`temporary_file`

    '''
    #: List of platforms this plugin works on
    #: For example: ``['windows', 'osx', 'linux']``
    supported_platforms = []

    #: The name of this plugin. You must set it something other
    #: than Trivial Plugin for it to work.
    name           = 'Trivial Plugin'

    #: The version of this plugin as a 3-tuple (major, minor, revision)
    version        = (1, 0, 0)

    #: A short string describing what this plugin does
    description    = _('Does absolutely nothing')

    #: The author of this plugin
    author         = _('Unknown')

    #: When more than one plugin exists for a filetype,
    #: the plugins are run in order of decreasing priority
    #: i.e. plugins with higher priority will be run first.
    #: The highest possible priority is ``sys.maxint``.
    #: Default priority is 1.
    priority = 1

    #: The earliest version of calibre this plugin requires
    minimum_calibre_version = (0, 4, 118)

    #: If False, the user will not be able to disable this plugin. Use with
    #: care.
    can_be_disabled = True

    #: The type of this plugin. Used for categorizing plugins in the
    #: GUI
    type = _('Base')

    def __init__(self, plugin_path):
        self.plugin_path        = plugin_path
        self.site_customization = None

    def initialize(self):
        '''
        Called once when calibre plugins are initialized. Plugins are re-initialized
        every time a new plugin is added.

        Perform any plugin specific initialization here, such as extracting
        resources from the plugin zip file. The path to the zip file is
        available as ``self.plugin_path``.

        Note that ``self.site_customization`` is **not** available at this point.
        '''
        pass

    def config_widget(self):
        '''
        Implement this method and :meth:`save_settings` in your plugin to
        use a custom configuration dialog, rather then relying on the simple
        string based default customization.

        This method, if implemented, must return a QWidget. The widget can have
        an optional method validate() that takes no arguments and is called
        immediately after the user clicks OK. Changes are applied if and only
        if the method returns True.

        If for some reason you cannot perform the configuration at this time,
        return a tuple of two strings (message, details), these will be
        displayed as a warning dialog to the user and the process will be
        aborted.
        '''
        raise NotImplementedError()

    def save_settings(self, config_widget):
        '''
        Save the settings specified by the user with config_widget.

        :param config_widget: The widget returned by :meth:`config_widget`.

        '''
        raise NotImplementedError()

    def do_user_config(self, parent=None):
        '''
        This method shows a configuration dialog for this plugin. It returns
        True if the user clicks OK, False otherwise. The changes are
        automatically applied.
        '''
        from PyQt4.Qt import QDialog, QDialogButtonBox, QVBoxLayout, \
                QLabel, Qt, QLineEdit
        from calibre.gui2 import gprefs

        prefname = 'plugin config dialog:'+self.type + ':' + self.name
        geom = gprefs.get(prefname, None)

        config_dialog = QDialog(parent)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        v = QVBoxLayout(config_dialog)

        def size_dialog():
            if geom is None:
                config_dialog.resize(config_dialog.sizeHint())
            else:
                config_dialog.restoreGeometry(geom)

        button_box.accepted.connect(config_dialog.accept)
        button_box.rejected.connect(config_dialog.reject)
        config_dialog.setWindowTitle(_('Customize') + ' ' + self.name)
        try:
            config_widget = self.config_widget()
        except NotImplementedError:
            config_widget = None

        if isinstance(config_widget, tuple):
            from calibre.gui2 import warning_dialog
            warning_dialog(parent, _('Cannot configure'), config_widget[0],
                    det_msg=config_widget[1], show=True)
            return False

        if config_widget is not None:
            v.addWidget(config_widget)
            v.addWidget(button_box)
            size_dialog()
            config_dialog.exec_()

            if config_dialog.result() == QDialog.Accepted:
                if hasattr(config_widget, 'validate'):
                    if config_widget.validate():
                        self.save_settings(config_widget)
                else:
                    self.save_settings(config_widget)
        else:
            from calibre.customize.ui import plugin_customization, \
                customize_plugin
            help_text = self.customization_help(gui=True)
            help_text = QLabel(help_text, config_dialog)
            help_text.setWordWrap(True)
            help_text.setTextInteractionFlags(Qt.LinksAccessibleByMouse
                    | Qt.LinksAccessibleByKeyboard)
            help_text.setOpenExternalLinks(True)
            v.addWidget(help_text)
            sc = plugin_customization(self)
            if not sc:
                sc = ''
            sc = sc.strip()
            sc = QLineEdit(sc, config_dialog)
            v.addWidget(sc)
            v.addWidget(button_box)
            size_dialog()
            config_dialog.exec_()

            if config_dialog.result() == QDialog.Accepted:
                sc = unicode(sc.text()).strip()
                customize_plugin(self, sc)

        geom = bytearray(config_dialog.saveGeometry())
        gprefs[prefname] = geom

        return config_dialog.result()

    def load_resources(self, names):
        '''
        If this plugin comes in a ZIP file (user added plugin), this method
        will allow you to load resources from the ZIP file.

        For example to load an image::

            pixmap = QPixmap()
            pixmap.loadFromData(self.load_resources(['images/icon.png']).itervalues().next())
            icon = QIcon(pixmap)

        :param names: List of paths to resources in the zip file using / as separator

        :return: A dictionary of the form ``{name : file_contents}``. Any names
                 that were not found in the zip file will not be present in the
                 dictionary.

        '''
        if self.plugin_path is None:
            raise ValueError('This plugin was not loaded from a ZIP file')
        ans = {}
        with zipfile.ZipFile(self.plugin_path, 'r') as zf:
            for candidate in zf.namelist():
                if candidate in names:
                    ans[candidate] = zf.read(candidate)
        return ans


    def customization_help(self, gui=False):
        '''
        Return a string giving help on how to customize this plugin.
        By default raise a :class:`NotImplementedError`, which indicates that
        the plugin does not require customization.

        If you re-implement this method in your subclass, the user will
        be asked to enter a string as customization for this plugin.
        The customization string will be available as
        ``self.site_customization``.

        Site customization could be anything, for example, the path to
        a needed binary on the user's computer.

        :param gui: If True return HTML help, otherwise return plain text help.

        '''
        raise NotImplementedError

    def temporary_file(self, suffix):
        '''
        Return a file-like object that is a temporary file on the file system.
        This file will remain available even after being closed and will only
        be removed on interpreter shutdown. Use the ``name`` member of the
        returned object to access the full path to the created temporary file.

        :param suffix: The suffix that the temporary file will have.
        '''
        return PersistentTemporaryFile(suffix)

    def is_customizable(self):
        try:
            self.customization_help()
            return True
        except NotImplementedError:
            return False

    def __enter__(self, *args):
        if self.plugin_path is not None:
            from calibre.utils.zipfile import ZipFile
            zf = ZipFile(self.plugin_path)
            extensions = set([x.rpartition('.')[-1].lower() for x in
                zf.namelist()])
            zip_safe = True
            for ext in ('pyd', 'so', 'dll', 'dylib'):
                if ext in extensions:
                    zip_safe = False
            if zip_safe:
                sys.path.insert(0, self.plugin_path)
                self.sys_insertion_path = self.plugin_path
            else:
                from calibre.ptempfile import TemporaryDirectory
                self._sys_insertion_tdir = TemporaryDirectory('plugin_unzip')
                self.sys_insertion_path = self._sys_insertion_tdir.__enter__(*args)
                zf.extractall(self.sys_insertion_path)
                sys.path.insert(0, self.sys_insertion_path)
            zf.close()


    def __exit__(self, *args):
        ip, it = getattr(self, 'sys_insertion_path', None), getattr(self,
                '_sys_insertion_tdir', None)
        if ip in sys.path:
            sys.path.remove(ip)
        if hasattr(it, '__exit__'):
            it.__exit__(*args)

    def cli_main(self, args):
        '''
        This method is the main entry point for your plugins command line
        interface. It is called when the user does: calibre-debug
        '''
        raise NotImplementedError('The %s plugin has no command line interface'
                                  %self.name)

# }}}

class FileTypePlugin(Plugin): # {{{
    '''
    A plugin that is associated with a particular set of file types.
    '''

    #: Set of file types for which this plugin should be run
    #: For example: ``set(['lit', 'mobi', 'prc'])``
    file_types     = set([])

    #: If True, this plugin is run when books are added
    #: to the database
    on_import      = False

    #: If True, this plugin is run after books are added
    #: to the database
    on_postimport  = False

    #: If True, this plugin is run just before a conversion
    on_preprocess  = False

    #: If True, this plugin is run after conversion
    #: on the final file produced by the conversion output plugin.
    on_postprocess = False

    type = _('File type')

    def run(self, path_to_ebook):
        '''
        Run the plugin. Must be implemented in subclasses.
        It should perform whatever modifications are required
        on the ebook and return the absolute path to the
        modified ebook. If no modifications are needed, it should
        return the path to the original ebook. If an error is encountered
        it should raise an Exception. The default implementation
        simply return the path to the original ebook.

        The modified ebook file should be created with the
        :meth:`temporary_file` method.

        :param path_to_ebook: Absolute path to the ebook.

        :return: Absolute path to the modified ebook.
        '''
        # Default implementation does nothing
        return path_to_ebook

    def postimport(self, book_id, book_format, db):
        '''
        Called post import, i.e., after the book file has been added to the database.

        :param book_id: Database id of the added book.
        :param book_format: The file type of the book that was added.
		:param db: Library database.
        '''
        pass # Default implementation does nothing

# }}}

class MetadataReaderPlugin(Plugin): # {{{
    '''
    A plugin that implements reading metadata from a set of file types.
    '''
    #: Set of file types for which this plugin should be run
    #: For example: ``set(['lit', 'mobi', 'prc'])``
    file_types     = set([])

    supported_platforms = ['windows', 'osx', 'linux']
    version = numeric_version
    author  = 'Kovid Goyal'

    type = _('Metadata reader')

    def __init__(self, *args, **kwargs):
        Plugin.__init__(self, *args, **kwargs)
        self.quick = False

    def get_metadata(self, stream, type):
        '''
        Return metadata for the file represented by stream (a file like object
        that supports reading). Raise an exception when there is an error
        with the input data.
        :param type: The type of file. Guaranteed to be one of the entries
        in :attr:`file_types`.
        :return: A :class:`calibre.ebooks.metadata.book.Metadata` object
        '''
        return None
# }}}

class MetadataWriterPlugin(Plugin): # {{{
    '''
    A plugin that implements reading metadata from a set of file types.
    '''
    #: Set of file types for which this plugin should be run
    #: For example: ``set(['lit', 'mobi', 'prc'])``
    file_types     = set([])

    supported_platforms = ['windows', 'osx', 'linux']
    version = numeric_version
    author  = 'Kovid Goyal'

    type = _('Metadata writer')

    def __init__(self, *args, **kwargs):
        Plugin.__init__(self, *args, **kwargs)
        self.apply_null = False

    def set_metadata(self, stream, mi, type):
        '''
        Set metadata for the file represented by stream (a file like object
        that supports reading). Raise an exception when there is an error
        with the input data.
        :param type: The type of file. Guaranteed to be one of the entries
        in :attr:`file_types`.
        :param mi: A :class:`calibre.ebooks.metadata.book.Metadata` object
        '''
        pass

# }}}

class CatalogPlugin(Plugin): # {{{
    '''
    A plugin that implements a catalog generator.
    '''

    resources_path = None

    #: Output file type for which this plugin should be run
    #: For example: 'epub' or 'xml'
    file_types = set([])

    type = _('Catalog generator')

    #: CLI parser options specific to this plugin, declared as namedtuple Option::
    #:
    #:  from collections import namedtuple
    #:  Option = namedtuple('Option', 'option, default, dest, help')
    #:  cli_options = [Option('--catalog-title',
    #:                       default = 'My Catalog',
    #:                       dest = 'catalog_title',
    #:                       help = (_('Title of generated catalog. \nDefault:') + " '" +
    #:                       '%default' + "'"))]
    #:  cli_options parsed in library.cli:catalog_option_parser()
    cli_options = []

    def _field_sorter(self, key):
        '''
        Custom fields sort after standard fields
        '''
        if key.startswith('#'):
            return '~%s' % key[1:]
        else:
            return key

    def search_sort_db(self, db, opts):

        db.search(opts.search_text)

        if opts.sort_by:
            # 2nd arg = ascending
            db.sort(opts.sort_by, True)
        return db.get_data_as_dict(ids=opts.ids)

    def get_output_fields(self, db, opts):
        # Return a list of requested fields, with opts.sort_by first
        all_std_fields = set(
                          ['author_sort','authors','comments','cover','formats',
                           'id','isbn','library_name','ondevice','pubdate','publisher',
                           'rating','series_index','series','size','tags','timestamp',
                           'title_sort','title','uuid','languages','identifiers'])
        all_custom_fields = set(db.custom_field_keys())
        for field in list(all_custom_fields):
            fm = db.field_metadata[field]
            if fm['datatype'] == 'series':
                all_custom_fields.add(field+'_index')
        all_fields = all_std_fields.union(all_custom_fields)

        if opts.fields != 'all':
            # Make a list from opts.fields
            requested_fields = set(opts.fields.split(','))

            # Validate requested_fields
            if requested_fields - all_fields:
                from calibre.library import current_library_name
                invalid_fields = sorted(list(requested_fields - all_fields))
                print("invalid --fields specified: %s" % ', '.join(invalid_fields))
                print("available fields in '%s': %s" %
                      (current_library_name(), ', '.join(sorted(list(all_fields)))))
                raise ValueError("unable to generate catalog with specified fields")

            fields = list(all_fields & requested_fields)
        else:
            fields = list(all_fields)

        if not opts.connected_device['is_device_connected'] and 'ondevice' in fields:
            fields.pop(int(fields.index('ondevice')))

        fields = sorted(fields, key=self._field_sorter)
        if opts.sort_by and opts.sort_by in fields:
            fields.insert(0,fields.pop(int(fields.index(opts.sort_by))))
        return fields

    def initialize(self):
        '''
        If plugin is not a built-in, copy the plugin's .ui and .py files from
        the zip file to $TMPDIR.
        Tab will be dynamically generated and added to the Catalog Options dialog in
        calibre.gui2.dialogs.catalog.py:Catalog
        '''
        from calibre.customize.builtins import plugins as builtin_plugins
        from calibre.customize.ui import config
        from calibre.ptempfile import PersistentTemporaryDirectory

        if not type(self) in builtin_plugins and \
           not self.name in config['disabled_plugins']:
            files_to_copy = ["%s.%s" % (self.name.lower(),ext) for ext in ["ui","py"]]
            resources = zipfile.ZipFile(self.plugin_path,'r')

            if self.resources_path is None:
                self.resources_path = PersistentTemporaryDirectory('_plugin_resources', prefix='')

            for file in files_to_copy:
                try:
                    resources.extract(file, self.resources_path)
                except:
                    print " customize:__init__.initialize(): %s not found in %s" % (file, os.path.basename(self.plugin_path))
                    continue
            resources.close()

    def run(self, path_to_output, opts, db, ids, notification=None):
        '''
        Run the plugin. Must be implemented in subclasses.
        It should generate the catalog in the format specified
        in file_types, returning the absolute path to the
        generated catalog file. If an error is encountered
        it should raise an Exception.

        The generated catalog file should be created with the
        :meth:`temporary_file` method.

        :param path_to_output: Absolute path to the generated catalog file.
        :param opts: A dictionary of keyword arguments
        :param db: A LibraryDatabase2 object
        '''
        # Default implementation does nothing
        raise NotImplementedError('CatalogPlugin.generate_catalog() default '
                'method, should be overridden in subclass')

# }}}

class InterfaceActionBase(Plugin): # {{{

    supported_platforms = ['windows', 'osx', 'linux']
    author         = 'Kovid Goyal'
    type = _('User Interface Action')
    can_be_disabled = False

    actual_plugin = None

    def __init__(self, *args, **kwargs):
        Plugin.__init__(self, *args, **kwargs)
        self.actual_plugin_ = None

    def load_actual_plugin(self, gui):
        '''
        This method must return the actual interface action plugin object.
        '''
        ac = self.actual_plugin_
        if ac is None:
            mod, cls = self.actual_plugin.split(':')
            ac = getattr(importlib.import_module(mod), cls)(gui,
                    self.site_customization)
            self.actual_plugin_ = ac
        return ac

# }}}

class PreferencesPlugin(Plugin): # {{{

    '''
    A plugin representing a widget displayed in the Preferences dialog.

    This plugin has only one important method :meth:`create_widget`. The
    various fields of the plugin control how it is categorized in the UI.
    '''

    supported_platforms = ['windows', 'osx', 'linux']
    author         = 'Kovid Goyal'
    type = _('Preferences')
    can_be_disabled = False

    #: Import path to module that contains a class named ConfigWidget
    #: which implements the ConfigWidgetInterface. Used by
    #: :meth:`create_widget`.
    config_widget = None

    #: Where in the list of categories the :attr:`category` of this plugin should be.
    category_order = 100

    #: Where in the list of names in a category, the :attr:`gui_name` of this
    #: plugin should be
    name_order = 100

    #: The category this plugin should be in
    category = None

    #: The category name displayed to the user for this plugin
    gui_category = None

    #: The name displayed to the user for this plugin
    gui_name = None

    #: The icon for this plugin, should be an absolute path
    icon = None

    #: The description used for tooltips and the like
    description = None

    def create_widget(self, parent=None):
        '''
        Create and return the actual Qt widget used for setting this group of
        preferences. The widget must implement the
        :class:`calibre.gui2.preferences.ConfigWidgetInterface`.

        The default implementation uses :attr:`config_widget` to instantiate
        the widget.
        '''
        base, _, wc = self.config_widget.partition(':')
        if not wc:
            wc = 'ConfigWidget'
        base = importlib.import_module(base)
        widget = getattr(base, wc)
        return widget(parent)

# }}}

class StoreBase(Plugin): # {{{

    supported_platforms = ['windows', 'osx', 'linux']
    author         = 'John Schember'
    type = _('Store')
    # Information about the store. Should be in the primary language
    # of the store. This should not be translatable when set by
    # a subclass.
    description = _('An ebook store.')
    minimum_calibre_version = (0, 8, 0)
    version        = (1, 0, 1)

    actual_plugin = None

    # Does the store only distribute ebooks without DRM.
    drm_free_only = False
    # This is the 2 letter country code for the corporate
    # headquarters of the store.
    headquarters = ''
    # All formats the store distributes ebooks in.
    formats = []
    # Is this store on an affiliate program?
    affiliate = False

    def load_actual_plugin(self, gui):
        '''
        This method must return the actual interface action plugin object.
        '''
        mod, cls = self.actual_plugin.split(':')
        self.actual_plugin_object  = getattr(importlib.import_module(mod), cls)(gui, self.name)
        return self.actual_plugin_object

    def customization_help(self, gui=False):
        if getattr(self, 'actual_plugin_object', None) is not None:
            return self.actual_plugin_object.customization_help(gui)
        raise NotImplementedError()

    def config_widget(self):
        if getattr(self, 'actual_plugin_object', None) is not None:
            return self.actual_plugin_object.config_widget()
        raise NotImplementedError()

    def save_settings(self, config_widget):
        if getattr(self, 'actual_plugin_object', None) is not None:
            return self.actual_plugin_object.save_settings(config_widget)
        raise NotImplementedError()

# }}}

class ViewerPlugin(Plugin): # {{{

    '''
    These plugins are used to add functionality to the calibre viewer.
    '''

    def load_fonts(self):
        '''
        This method is called once at viewer starup. It should load any fonts
        it wants to make available. For example::

            def load_fonts():
                from PyQt4.Qt import QFontDatabase
                font_data = get_resources(['myfont1.ttf', 'myfont2.ttf'])
                for raw in font_data.itervalues():
                    QFontDatabase.addApplicationFontFromData(raw)
        '''
        pass

    def load_javascript(self, evaljs):
        '''
        This method is called every time a new HTML document is loaded in the
        viewer. Use it to load javascript libraries into the viewer. For
        example::

            def load_javascript(self, evaljs):
                js = get_resources('myjavascript.js')
                evaljs(js)
        '''
        pass

    def run_javascript(self, evaljs):
        '''
        This method is called every time a document has finished loading. Use
        it in the same way as load_javascript().
        '''
        pass

# }}}

