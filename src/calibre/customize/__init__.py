from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os, sys, zipfile

from calibre.constants import numeric_version
from calibre.ptempfile import PersistentTemporaryFile


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


    def search_sort_db(self, db, opts):

        db.search(opts.search_text)

        if opts.sort_by:
            # 2nd arg = ascending
            db.sort(opts.sort_by, True)

        return db.get_data_as_dict(ids=opts.ids)

    def get_output_fields(self, opts):
        # Return a list of requested fields, with opts.sort_by first
        all_fields = set(
                          ['author_sort','authors','comments','cover','formats',
                           'id','isbn','ondevice','pubdate','publisher','rating',
                           'series_index','series','size','tags','timestamp',
                           'title','uuid'])

        fields = all_fields
        if opts.fields != 'all':
            # Make a list from opts.fields
            requested_fields = set(opts.fields.split(','))
            fields = list(all_fields & requested_fields)
        else:
            fields = list(all_fields)

        if not opts.connected_device['is_device_connected'] and 'ondevice' in fields:
            fields.pop(int(fields.index('ondevice')))

        fields.sort()
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

    def load_actual_plugin(self, gui):
        '''
        This method should must the actual interface action plugin object.
        '''
        mod, cls = self.actual_plugin.split(':')
        return getattr(__import__(mod, fromlist=['1'], level=0), cls)(gui,
                self.site_customization)

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
        base = __import__(base, fromlist=[1])
        widget = getattr(base, wc)
        return widget(parent)

# }}}

