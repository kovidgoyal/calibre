from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os, shutil, traceback, functools, sys

from calibre.customize import (CatalogPlugin, FileTypePlugin, PluginNotFound,
                              MetadataReaderPlugin, MetadataWriterPlugin,
                              InterfaceActionBase as InterfaceAction,
                              PreferencesPlugin, platform, InvalidPlugin,
                              StoreBase as Store, ViewerPlugin)
from calibre.customize.conversion import InputFormatPlugin, OutputFormatPlugin
from calibre.customize.zipplugin import loader
from calibre.customize.profiles import InputProfile, OutputProfile
from calibre.customize.builtins import plugins as builtin_plugins
from calibre.devices.interface import DevicePlugin
from calibre.ebooks.metadata import MetaInformation
from calibre.utils.config import (make_config_dir, Config, ConfigProxy,
                                 plugin_dir, OptionParser)
from calibre.ebooks.epub.fix import ePubFixer
from calibre.ebooks.metadata.sources.base import Source
from calibre.constants import DEBUG

builtin_names = frozenset([p.name for p in builtin_plugins])

class NameConflict(ValueError):
    pass

def _config():
    c = Config('customize')
    c.add_opt('plugins', default={}, help=_('Installed plugins'))
    c.add_opt('filetype_mapping', default={}, help=_('Mapping for filetype plugins'))
    c.add_opt('plugin_customization', default={}, help=_('Local plugin customization'))
    c.add_opt('disabled_plugins', default=set([]), help=_('Disabled plugins'))
    c.add_opt('enabled_plugins', default=set([]), help=_('Enabled plugins'))

    return ConfigProxy(c)

config = _config()


def find_plugin(name):
    for plugin in _initialized_plugins:
        if plugin.name == name:
            return plugin


def load_plugin(path_to_zip_file): # {{{
    '''
    Load plugin from zip file or raise InvalidPlugin error

    :return: A :class:`Plugin` instance.
    '''
    return loader.load(path_to_zip_file)

# }}}

# Enable/disable plugins {{{

def disable_plugin(plugin_or_name):
    x = getattr(plugin_or_name, 'name', plugin_or_name)
    plugin = find_plugin(x)
    if not plugin.can_be_disabled:
        raise ValueError('Plugin %s cannot be disabled'%x)
    dp = config['disabled_plugins']
    dp.add(x)
    config['disabled_plugins'] = dp
    ep = config['enabled_plugins']
    if x in ep:
        ep.remove(x)
    config['enabled_plugins'] = ep

def enable_plugin(plugin_or_name):
    x = getattr(plugin_or_name, 'name', plugin_or_name)
    dp = config['disabled_plugins']
    if x in dp:
        dp.remove(x)
    config['disabled_plugins'] = dp
    ep = config['enabled_plugins']
    ep.add(x)
    config['enabled_plugins'] = ep

def restore_plugin_state_to_default(plugin_or_name):
    x = getattr(plugin_or_name, 'name', plugin_or_name)
    dp = config['disabled_plugins']
    if x in dp:
        dp.remove(x)
    config['disabled_plugins'] = dp
    ep = config['enabled_plugins']
    if x in ep:
        ep.remove(x)
    config['enabled_plugins'] = ep

default_disabled_plugins = set([
    'Overdrive', 'Douban Books', 'OZON.ru',
])

def is_disabled(plugin):
    if plugin.name in config['enabled_plugins']: return False
    return plugin.name in config['disabled_plugins'] or \
            plugin.name in default_disabled_plugins
# }}}

# File type plugins {{{

_on_import           = {}
_on_postimport       = {}
_on_preprocess       = {}
_on_postprocess      = {}

def reread_filetype_plugins():
    global _on_import
    global _on_postimport
    global _on_preprocess
    global _on_postprocess
    _on_import           = {}
    _on_postimport       = {}
    _on_preprocess       = {}
    _on_postprocess      = {}

    for plugin in _initialized_plugins:
        if isinstance(plugin, FileTypePlugin):
            for ft in plugin.file_types:
                if plugin.on_import:
                    if not _on_import.has_key(ft):
                        _on_import[ft] = []
                    _on_import[ft].append(plugin)
                if plugin.on_postimport:
                    if not _on_postimport.has_key(ft):
                        _on_postimport[ft] = []
                    _on_postimport[ft].append(plugin)
                if plugin.on_preprocess:
                    if not _on_preprocess.has_key(ft):
                        _on_preprocess[ft] = []
                    _on_preprocess[ft].append(plugin)
                if plugin.on_postprocess:
                    if not _on_postprocess.has_key(ft):
                        _on_postprocess[ft] = []
                    _on_postprocess[ft].append(plugin)


def _run_filetype_plugins(path_to_file, ft=None, occasion='preprocess'):
    occasion_plugins = {'import':_on_import, 'preprocess':_on_preprocess,
                'postprocess':_on_postprocess}[occasion]
    customization = config['plugin_customization']
    if ft is None:
        ft = os.path.splitext(path_to_file)[-1].lower().replace('.', '')
    nfp = path_to_file
    for plugin in occasion_plugins.get(ft, []):
        if is_disabled(plugin):
            continue
        plugin.site_customization = customization.get(plugin.name, '')
        with plugin:
            try:
                nfp = plugin.run(path_to_file)
                if not nfp:
                    nfp = path_to_file
            except:
                print 'Running file type plugin %s failed with traceback:'%plugin.name
                traceback.print_exc()
    x = lambda j : os.path.normpath(os.path.normcase(j))
    if occasion == 'postprocess' and x(nfp) != x(path_to_file):
        shutil.copyfile(nfp, path_to_file)
        nfp = path_to_file
    return nfp

run_plugins_on_import      = functools.partial(_run_filetype_plugins,
                                               occasion='import')
run_plugins_on_preprocess  = functools.partial(_run_filetype_plugins,
                                               occasion='preprocess')
run_plugins_on_postprocess = functools.partial(_run_filetype_plugins,
                                               occasion='postprocess')
                        
def postimport_plugins(id, format):
    from calibre.gui2.ui import get_gui
    db = get_gui().current_db
    customization = config['plugin_customization']
    format = format.lower()
    for plugin in _on_postimport.get(format, []):
        if is_disabled(plugin):
            continue
        plugin.site_customization = customization.get(plugin.name, '')
        with plugin:
            try:
                plugin.postimport(id, db)
            except:
                print 'Running file type plugin %s failed with traceback:'%plugin.name
                traceback.print_exc()
    
# }}}

# Plugin customization {{{
def customize_plugin(plugin, custom):
    d = config['plugin_customization']
    d[plugin.name] = custom.strip()
    config['plugin_customization'] = d

def plugin_customization(plugin):
    return config['plugin_customization'].get(plugin.name, '')

# }}}

# Input/Output profiles {{{
def input_profiles():
    for plugin in _initialized_plugins:
        if isinstance(plugin, InputProfile):
            yield plugin

def output_profiles():
    for plugin in _initialized_plugins:
        if isinstance(plugin, OutputProfile):
            yield plugin
# }}}

# Interface Actions # {{{

def interface_actions():
    customization = config['plugin_customization']
    for plugin in _initialized_plugins:
        if isinstance(plugin, InterfaceAction):
            if not is_disabled(plugin):
                plugin.site_customization = customization.get(plugin.name, '')
                yield plugin
# }}}

# Preferences Plugins # {{{

def preferences_plugins():
    customization = config['plugin_customization']
    for plugin in _initialized_plugins:
        if isinstance(plugin, PreferencesPlugin):
            if not is_disabled(plugin):
                plugin.site_customization = customization.get(plugin.name, '')
                yield plugin
# }}}

# Store Plugins # {{{

def store_plugins():
    customization = config['plugin_customization']
    for plugin in _initialized_plugins:
        if isinstance(plugin, Store):
            plugin.site_customization = customization.get(plugin.name, '')
            yield plugin

def available_store_plugins():
    for plugin in store_plugins():
        if not is_disabled(plugin):
            yield plugin

def stores():
    stores = set([])
    for plugin in store_plugins():
        stores.add(plugin.name)
    return stores

def available_stores():
    stores = set([])
    for plugin in available_store_plugins():
        stores.add(plugin.name)
    return stores

# }}}

# Metadata read/write {{{
_metadata_readers = {}
_metadata_writers = {}
def reread_metadata_plugins():
    global _metadata_readers
    global _metadata_writers
    _metadata_readers = {}
    for plugin in _initialized_plugins:
        if isinstance(plugin, MetadataReaderPlugin):
            for ft in plugin.file_types:
                if not _metadata_readers.has_key(ft):
                    _metadata_readers[ft] = []
                _metadata_readers[ft].append(plugin)
        elif isinstance(plugin, MetadataWriterPlugin):
            for ft in plugin.file_types:
                if not _metadata_writers.has_key(ft):
                    _metadata_writers[ft] = []
                _metadata_writers[ft].append(plugin)

def metadata_readers():
    ans = set([])
    for plugins in _metadata_readers.values():
        for plugin in plugins:
            ans.add(plugin)
    return ans

def metadata_writers():
    ans = set([])
    for plugins in _metadata_writers.values():
        for plugin in plugins:
            ans.add(plugin)
    return ans

class QuickMetadata(object):

    def __init__(self):
        self.quick = False

    def __enter__(self):
        self.quick = True

    def __exit__(self, *args):
        self.quick = False

quick_metadata = QuickMetadata()

class ApplyNullMetadata(object):

    def __init__(self):
        self.apply_null = False

    def __enter__(self):
        self.apply_null = True

    def __exit__(self, *args):
        self.apply_null = False

apply_null_metadata = ApplyNullMetadata()

def get_file_type_metadata(stream, ftype):
    mi = MetaInformation(None, None)

    ftype = ftype.lower().strip()
    if _metadata_readers.has_key(ftype):
        for plugin in _metadata_readers[ftype]:
            if not is_disabled(plugin):
                with plugin:
                    try:
                        plugin.quick = quick_metadata.quick
                        if hasattr(stream, 'seek'):
                            stream.seek(0)
                        mi = plugin.get_metadata(stream, ftype.lower().strip())
                        break
                    except:
                        traceback.print_exc()
                        continue
    return mi

def set_file_type_metadata(stream, mi, ftype):
    ftype = ftype.lower().strip()
    if _metadata_writers.has_key(ftype):
        for plugin in _metadata_writers[ftype]:
            if not is_disabled(plugin):
                with plugin:
                    try:
                        plugin.apply_null = apply_null_metadata.apply_null
                        plugin.set_metadata(stream, mi, ftype.lower().strip())
                        break
                    except:
                        print 'Failed to set metadata for', repr(getattr(mi, 'title', ''))
                        traceback.print_exc()

# }}}

# Add/remove plugins {{{

def add_plugin(path_to_zip_file):
    make_config_dir()
    plugin = load_plugin(path_to_zip_file)
    if plugin.name in builtin_names:
        raise NameConflict(
            'A builtin plugin with the name %r already exists' % plugin.name)
    plugin = initialize_plugin(plugin, path_to_zip_file)
    plugins = config['plugins']
    zfp = os.path.join(plugin_dir, plugin.name+'.zip')
    if os.path.exists(zfp):
        os.remove(zfp)
    shutil.copyfile(path_to_zip_file, zfp)
    plugins[plugin.name] = zfp
    config['plugins'] = plugins
    initialize_plugins()
    return plugin

def remove_plugin(plugin_or_name):
    name = getattr(plugin_or_name, 'name', plugin_or_name)
    plugins = config['plugins']
    removed = False
    if name in plugins:
        removed = True
        try:
            zfp = os.path.join(plugin_dir, name+'.zip')
            if os.path.exists(zfp):
                os.remove(zfp)
            zfp = plugins[name]
            if os.path.exists(zfp):
                os.remove(zfp)
        except:
            pass
        plugins.pop(name)
    config['plugins'] = plugins
    initialize_plugins()
    return removed

# }}}

# Input/Output format plugins {{{

def input_format_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, InputFormatPlugin):
            yield plugin

def plugin_for_input_format(fmt):
    customization = config['plugin_customization']
    for plugin in input_format_plugins():
        if fmt.lower() in plugin.file_types:
            plugin.site_customization = customization.get(plugin.name, None)
            return plugin

def all_input_formats():
    formats = set([])
    for plugin in input_format_plugins():
        for format in plugin.file_types:
            formats.add(format)
    return formats

def available_input_formats():
    formats = set([])
    for plugin in input_format_plugins():
        if not is_disabled(plugin):
            for format in plugin.file_types:
                formats.add(format)
    formats.add('zip'), formats.add('rar')
    return formats


def output_format_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, OutputFormatPlugin):
            yield plugin

def plugin_for_output_format(fmt):
    customization = config['plugin_customization']
    for plugin in output_format_plugins():
        if fmt.lower() == plugin.file_type:
            plugin.site_customization = customization.get(plugin.name, None)
            return plugin

def available_output_formats():
    formats = set([])
    for plugin in output_format_plugins():
        if not is_disabled(plugin):
            formats.add(plugin.file_type)
    return formats

# }}}

# Catalog plugins {{{

def catalog_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, CatalogPlugin):
            yield plugin

def available_catalog_formats():
    formats = set([])
    for plugin in catalog_plugins():
        if not is_disabled(plugin):
            for format in plugin.file_types:
                formats.add(format)
    return formats

def plugin_for_catalog_format(fmt):
    for plugin in catalog_plugins():
        if fmt.lower() in plugin.file_types:
            return plugin

# }}}

# Device plugins {{{
def device_plugins(include_disabled=False):
    for plugin in _initialized_plugins:
        if isinstance(plugin, DevicePlugin):
            if include_disabled or not is_disabled(plugin):
                if platform in plugin.supported_platforms:
                    if getattr(plugin, 'plugin_needs_delayed_initialization',
                            False):
                        plugin.do_delayed_plugin_initialization()
                    yield plugin

def disabled_device_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, DevicePlugin):
            if is_disabled(plugin):
                if platform in plugin.supported_platforms:
                    yield plugin
# }}}

# epub fixers {{{
def epub_fixers():
    for plugin in _initialized_plugins:
        if isinstance(plugin, ePubFixer):
            if not is_disabled(plugin):
                if platform in plugin.supported_platforms:
                    yield plugin
# }}}

# Metadata sources2 {{{
def metadata_plugins(capabilities):
    capabilities = frozenset(capabilities)
    for plugin in all_metadata_plugins():
        if plugin.capabilities.intersection(capabilities) and \
                not is_disabled(plugin):
            yield plugin

def all_metadata_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, Source):
            yield plugin
# }}}

# Viewer plugins {{{
def all_viewer_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, ViewerPlugin):
            yield plugin
# }}}

# Initialize plugins {{{

_initialized_plugins = []

def initialize_plugin(plugin, path_to_zip_file):
    try:
        p = plugin(path_to_zip_file)
        p.initialize()
        return p
    except Exception:
        print 'Failed to initialize plugin:', plugin.name, plugin.version
        tb = traceback.format_exc()
        raise InvalidPlugin((_('Initialization of plugin %s failed with traceback:')
                            %tb) + '\n'+tb)

def has_external_plugins():
    'True if there are updateable (zip file based) plugins'
    return bool(config['plugins'])

def initialize_plugins(perf=False):
    global _initialized_plugins
    _initialized_plugins = []
    conflicts = [name for name in config['plugins'] if name in
            builtin_names]
    for p in conflicts:
        remove_plugin(p)
    external_plugins = config['plugins']
    ostdout, ostderr = sys.stdout, sys.stderr
    if perf:
        from collections import defaultdict
        import time
        times = defaultdict(lambda:0)
    for zfp in list(external_plugins) + builtin_plugins:
        try:
            if not isinstance(zfp, type):
                # We have a plugin name
                pname = zfp
                zfp = os.path.join(plugin_dir, zfp+'.zip')
                if not os.path.exists(zfp):
                    zfp = external_plugins[pname]
            try:
                plugin = load_plugin(zfp) if not isinstance(zfp, type) else zfp
            except PluginNotFound:
                continue
            if perf:
                st = time.time()
            plugin = initialize_plugin(plugin, None if isinstance(zfp, type) else zfp)
            if perf:
                times[plugin.name] = time.time() - st
            _initialized_plugins.append(plugin)
        except:
            print 'Failed to initialize plugin:', repr(zfp)
            if DEBUG:
                traceback.print_exc()
    # Prevent a custom plugin from overriding stdout/stderr as this breaks
    # ipython
    sys.stdout, sys.stderr = ostdout, ostderr
    if perf:
        for x in sorted(times, key=lambda x:times[x]):
            print ('%50s: %.3f'%(x, times[x]))
    _initialized_plugins.sort(cmp=lambda x,y:cmp(x.priority, y.priority), reverse=True)
    reread_filetype_plugins()
    reread_metadata_plugins()

initialize_plugins()

def initialized_plugins():
    for plugin in _initialized_plugins:
        yield plugin

# }}}

# CLI {{{

def build_plugin(path):
    from calibre import prints
    from calibre.ptempfile import PersistentTemporaryFile
    from calibre.utils.zipfile import ZipFile, ZIP_STORED
    path = type(u'')(path)
    names = frozenset(os.listdir(path))
    if u'__init__.py' not in names:
        prints(path, ' is not a valid plugin')
        raise SystemExit(1)
    t = PersistentTemporaryFile(u'.zip')
    with ZipFile(t, u'w', ZIP_STORED) as zf:
        zf.add_dir(path)
    t.close()
    plugin = add_plugin(t.name)
    os.remove(t.name)
    prints(u'Plugin updated:', plugin.name, plugin.version)

def option_parser():
    parser = OptionParser(usage=_('''\
    %prog options

    Customize calibre by loading external plugins.
    '''))
    parser.add_option('-a', '--add-plugin', default=None,
                      help=_('Add a plugin by specifying the path to the zip file containing it.'))
    parser.add_option('-b', '--build-plugin', default=None,
            help=_('For plugin developers: Path to the directory where you are'
                ' developing the plugin. This command will automatically zip '
                'up the plugin and update it in calibre.'))
    parser.add_option('-r', '--remove-plugin', default=None,
                      help=_('Remove a custom plugin by name. Has no effect on builtin plugins'))
    parser.add_option('--customize-plugin', default=None,
                      help=_('Customize plugin. Specify name of plugin and customization string separated by a comma.'))
    parser.add_option('-l', '--list-plugins', default=False, action='store_true',
                      help=_('List all installed plugins'))
    parser.add_option('--enable-plugin', default=None,
                      help=_('Enable the named plugin'))
    parser.add_option('--disable-plugin', default=None,
                      help=_('Disable the named plugin'))
    return parser

def main(args=sys.argv):
    parser = option_parser()
    if len(args) < 2:
        parser.print_help()
        return 1
    opts, args = parser.parse_args(args)
    if opts.add_plugin is not None:
        plugin = add_plugin(opts.add_plugin)
        print 'Plugin added:', plugin.name, plugin.version
    if opts.build_plugin is not None:
        build_plugin(opts.build_plugin)
    if opts.remove_plugin is not None:
        if remove_plugin(opts.remove_plugin):
            print 'Plugin removed'
        else:
            print 'No custom plugin named', opts.remove_plugin
    if opts.customize_plugin is not None:
        name, custom = opts.customize_plugin.split(',')
        plugin = find_plugin(name.strip())
        if plugin is None:
            print 'No plugin with the name %s exists'%name
            return 1
        customize_plugin(plugin, custom)
    if opts.enable_plugin is not None:
        enable_plugin(opts.enable_plugin.strip())
    if opts.disable_plugin is not None:
        disable_plugin(opts.disable_plugin.strip())
    if opts.list_plugins:
        fmt = '%-15s%-20s%-15s%-15s%s'
        print fmt%tuple(('Type|Name|Version|Disabled|Site Customization'.split('|')))
        print
        for plugin in initialized_plugins():
            print fmt%(
                                plugin.type, plugin.name,
                                plugin.version, is_disabled(plugin),
                                plugin_customization(plugin)
                                )
            print '\t', plugin.description
            if plugin.is_customizable():
                print '\t', plugin.customization_help()
            print

    return 0

if __name__ == '__main__':
    sys.exit(main())
# }}}

