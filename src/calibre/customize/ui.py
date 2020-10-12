
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os, shutil, traceback, functools, sys
from collections import defaultdict
from itertools import chain

from calibre.customize import (CatalogPlugin, FileTypePlugin, PluginNotFound,
                              MetadataReaderPlugin, MetadataWriterPlugin,
                              InterfaceActionBase as InterfaceAction,
                              PreferencesPlugin, platform, InvalidPlugin,
                              StoreBase as Store, EditBookToolPlugin,
                              LibraryClosedPlugin)
from calibre.customize.conversion import InputFormatPlugin, OutputFormatPlugin
from calibre.customize.zipplugin import loader
from calibre.customize.profiles import InputProfile, OutputProfile
from calibre.customize.builtins import plugins as builtin_plugins
from calibre.devices.interface import DevicePlugin
from calibre.ebooks.metadata import MetaInformation
from calibre.utils.config import (make_config_dir, Config, ConfigProxy,
                                 plugin_dir, OptionParser)
from calibre.ebooks.metadata.sources.base import Source
from calibre.constants import DEBUG, numeric_version
from polyglot.builtins import iteritems, itervalues, unicode_type

builtin_names = frozenset(p.name for p in builtin_plugins)
BLACKLISTED_PLUGINS = frozenset({'Marvin XD', 'iOS reader applications'})


class NameConflict(ValueError):
    pass


def _config():
    c = Config('customize')
    c.add_opt('plugins', default={}, help=_('Installed plugins'))
    c.add_opt('filetype_mapping', default={}, help=_('Mapping for filetype plugins'))
    c.add_opt('plugin_customization', default={}, help=_('Local plugin customization'))
    c.add_opt('disabled_plugins', default=set(), help=_('Disabled plugins'))
    c.add_opt('enabled_plugins', default=set(), help=_('Enabled plugins'))

    return ConfigProxy(c)


config = _config()


def find_plugin(name):
    for plugin in _initialized_plugins:
        if plugin.name == name:
            return plugin


def load_plugin(path_to_zip_file):  # {{{
    '''
    Load plugin from ZIP file or raise InvalidPlugin error

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


default_disabled_plugins = {
    'Overdrive', 'Douban Books', 'OZON.ru', 'Edelweiss', 'Google Images', 'Big Book Search',
}


def is_disabled(plugin):
    if plugin.name in config['enabled_plugins']:
        return False
    return plugin.name in config['disabled_plugins'] or \
            plugin.name in default_disabled_plugins
# }}}

# File type plugins {{{


_on_import           = {}
_on_postimport       = {}
_on_preprocess       = {}
_on_postprocess      = {}
_on_postadd          = []


def reread_filetype_plugins():
    global _on_import, _on_postimport, _on_preprocess, _on_postprocess, _on_postadd
    _on_import           = defaultdict(list)
    _on_postimport       = defaultdict(list)
    _on_preprocess       = defaultdict(list)
    _on_postprocess      = defaultdict(list)
    _on_postadd          = []

    for plugin in _initialized_plugins:
        if isinstance(plugin, FileTypePlugin):
            for ft in plugin.file_types:
                if plugin.on_import:
                    _on_import[ft].append(plugin)
                if plugin.on_postimport:
                    _on_postimport[ft].append(plugin)
                    _on_postadd.append(plugin)
                if plugin.on_preprocess:
                    _on_preprocess[ft].append(plugin)
                if plugin.on_postprocess:
                    _on_postprocess[ft].append(plugin)


def plugins_for_ft(ft, occasion):
    op = {
        'import':_on_import, 'preprocess':_on_preprocess, 'postprocess':_on_postprocess, 'postimport':_on_postimport,
    }[occasion]
    for p in chain(op.get(ft, ()), op.get('*', ())):
        if not is_disabled(p):
            yield p


def _run_filetype_plugins(path_to_file, ft=None, occasion='preprocess'):
    customization = config['plugin_customization']
    if ft is None:
        ft = os.path.splitext(path_to_file)[-1].lower().replace('.', '')
    nfp = path_to_file
    for plugin in plugins_for_ft(ft, occasion):
        plugin.site_customization = customization.get(plugin.name, '')
        oo, oe = sys.stdout, sys.stderr  # Some file type plugins out there override the output streams with buggy implementations
        with plugin:
            try:
                plugin.original_path_to_file = path_to_file
            except Exception:
                pass
            try:
                nfp = plugin.run(nfp) or nfp
            except:
                print('Running file type plugin %s failed with traceback:'%plugin.name, file=oe)
                traceback.print_exc(file=oe)
        sys.stdout, sys.stderr = oo, oe
    x = lambda j: os.path.normpath(os.path.normcase(j))
    if occasion == 'postprocess' and x(nfp) != x(path_to_file):
        shutil.copyfile(nfp, path_to_file)
        nfp = path_to_file
    return nfp


run_plugins_on_import      = functools.partial(_run_filetype_plugins, occasion='import')
run_plugins_on_preprocess  = functools.partial(_run_filetype_plugins, occasion='preprocess')
run_plugins_on_postprocess = functools.partial(_run_filetype_plugins, occasion='postprocess')


def run_plugins_on_postimport(db, book_id, fmt):
    customization = config['plugin_customization']
    fmt = fmt.lower()
    for plugin in plugins_for_ft(fmt, 'postimport'):
        plugin.site_customization = customization.get(plugin.name, '')
        with plugin:
            try:
                plugin.postimport(book_id, fmt, db)
            except:
                print('Running file type plugin %s failed with traceback:'%
                       plugin.name)
                traceback.print_exc()


def run_plugins_on_postadd(db, book_id, fmt_map):
    customization = config['plugin_customization']
    for plugin in _on_postadd:
        if is_disabled(plugin):
            continue
        plugin.site_customization = customization.get(plugin.name, '')
        with plugin:
            try:
                plugin.postadd(book_id, fmt_map, db)
            except Exception:
                print('Running file type plugin %s failed with traceback:'%
                       plugin.name)
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

# Library Closed Plugins # {{{


def available_library_closed_plugins():
    customization = config['plugin_customization']
    for plugin in _initialized_plugins:
        if isinstance(plugin, LibraryClosedPlugin):
            if not is_disabled(plugin):
                plugin.site_customization = customization.get(plugin.name, '')
                yield plugin


def has_library_closed_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, LibraryClosedPlugin):
            if not is_disabled(plugin):
                return True
    return False
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
    stores = set()
    for plugin in store_plugins():
        stores.add(plugin.name)
    return stores


def available_stores():
    stores = set()
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
    _metadata_readers = defaultdict(list)
    _metadata_writers = defaultdict(list)
    for plugin in _initialized_plugins:
        if isinstance(plugin, MetadataReaderPlugin):
            for ft in plugin.file_types:
                _metadata_readers[ft].append(plugin)
        elif isinstance(plugin, MetadataWriterPlugin):
            for ft in plugin.file_types:
                _metadata_writers[ft].append(plugin)

    # Ensure custom metadata plugins are used in preference to builtin
    # ones for a given filetype
    def key(plugin):
        return (1 if plugin.plugin_path is None else 0), plugin.name

    for group in (_metadata_readers, _metadata_writers):
        for plugins in itervalues(group):
            if len(plugins) > 1:
                plugins.sort(key=key)


def metadata_readers():
    ans = set()
    for plugins in _metadata_readers.values():
        for plugin in plugins:
            ans.add(plugin)
    return ans


def metadata_writers():
    ans = set()
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


class ForceIdentifiers(object):

    def __init__(self):
        self.force_identifiers = False

    def __enter__(self):
        self.force_identifiers = True

    def __exit__(self, *args):
        self.force_identifiers = False


force_identifiers = ForceIdentifiers()


def get_file_type_metadata(stream, ftype):
    mi = MetaInformation(None, None)

    ftype = ftype.lower().strip()
    if ftype in _metadata_readers:
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


def set_file_type_metadata(stream, mi, ftype, report_error=None):
    ftype = ftype.lower().strip()
    if ftype in _metadata_writers:
        customization = config['plugin_customization']
        for plugin in _metadata_writers[ftype]:
            if not is_disabled(plugin):
                with plugin:
                    try:
                        plugin.apply_null = apply_null_metadata.apply_null
                        plugin.force_identifiers = force_identifiers.force_identifiers
                        plugin.site_customization = customization.get(plugin.name, '')
                        plugin.set_metadata(stream, mi, ftype.lower().strip())
                        break
                    except:
                        if report_error is None:
                            from calibre import prints
                            prints('Failed to set metadata for the', ftype.upper(), 'format of:', getattr(mi, 'title', ''), file=sys.stderr)
                            traceback.print_exc()
                        else:
                            report_error(mi, ftype, traceback.format_exc())


def can_set_metadata(ftype):
    ftype = ftype.lower().strip()
    for plugin in _metadata_writers.get(ftype, ()):
        if not is_disabled(plugin):
            return True
    return False

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
    formats = set()
    for plugin in input_format_plugins():
        for format in plugin.file_types:
            formats.add(format)
    return formats


def available_input_formats():
    formats = set()
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
    formats = set()
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
    formats = set()
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


def patch_metadata_plugins(possibly_updated_plugins):
    patches = {}
    for i, plugin in enumerate(_initialized_plugins):
        if isinstance(plugin, Source) and plugin.name in builtin_names:
            pup = possibly_updated_plugins.get(plugin.name)
            if pup is not None:
                if pup.version > plugin.version and pup.minimum_calibre_version <= numeric_version:
                    patches[i] = pup(None)
                    # Metadata source plugins dont use initialize() but that
                    # might change in the future, so be safe.
                    patches[i].initialize()
    for i, pup in iteritems(patches):
        _initialized_plugins[i] = pup
# }}}

# Editor plugins {{{


def all_edit_book_tool_plugins():
    for plugin in _initialized_plugins:
        if isinstance(plugin, EditBookToolPlugin):
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
        print('Failed to initialize plugin:', plugin.name, plugin.version)
        tb = traceback.format_exc()
        raise InvalidPlugin((_('Initialization of plugin %s failed with traceback:')
                            %tb) + '\n'+tb)


def has_external_plugins():
    'True if there are updateable (ZIP file based) plugins'
    return bool(config['plugins'])


def initialize_plugins(perf=False):
    global _initialized_plugins
    _initialized_plugins = []
    conflicts = [name for name in config['plugins'] if name in
            builtin_names]
    for p in conflicts:
        remove_plugin(p)
    external_plugins = config['plugins'].copy()
    for name in BLACKLISTED_PLUGINS:
        external_plugins.pop(name, None)
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
            print('Failed to initialize plugin:', repr(zfp))
            if DEBUG:
                traceback.print_exc()
    # Prevent a custom plugin from overriding stdout/stderr as this breaks
    # ipython
    sys.stdout, sys.stderr = ostdout, ostderr
    if perf:
        for x in sorted(times, key=lambda x: times[x]):
            print('%50s: %.3f'%(x, times[x]))
    _initialized_plugins.sort(key=lambda x: x.priority, reverse=True)
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
    path = unicode_type(path)
    names = frozenset(os.listdir(path))
    if '__init__.py' not in names:
        prints(path, ' is not a valid plugin')
        raise SystemExit(1)
    t = PersistentTemporaryFile(u'.zip')
    with ZipFile(t, 'w', ZIP_STORED) as zf:
        zf.add_dir(path, simple_filter=lambda x:x in {'.git', '.bzr', '.svn', '.hg'})
    t.close()
    plugin = add_plugin(t.name)
    os.remove(t.name)
    prints('Plugin updated:', plugin.name, plugin.version)


def option_parser():
    parser = OptionParser(usage=_('''\
    %prog options

    Customize calibre by loading external plugins.
    '''))
    parser.add_option('-a', '--add-plugin', default=None,
                      help=_('Add a plugin by specifying the path to the ZIP file containing it.'))
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
        print('Plugin added:', plugin.name, plugin.version)
    if opts.build_plugin is not None:
        build_plugin(opts.build_plugin)
    if opts.remove_plugin is not None:
        if remove_plugin(opts.remove_plugin):
            print('Plugin removed')
        else:
            print('No custom plugin named', opts.remove_plugin)
    if opts.customize_plugin is not None:
        name, custom = opts.customize_plugin.split(',')
        plugin = find_plugin(name.strip())
        if plugin is None:
            print('No plugin with the name %s exists'%name)
            return 1
        customize_plugin(plugin, custom)
    if opts.enable_plugin is not None:
        enable_plugin(opts.enable_plugin.strip())
    if opts.disable_plugin is not None:
        disable_plugin(opts.disable_plugin.strip())
    if opts.list_plugins:
        type_len = name_len = 0
        for plugin in initialized_plugins():
            type_len, name_len = max(type_len, len(plugin.type)), max(name_len, len(plugin.name))
        fmt = '%-{}s%-{}s%-15s%-15s%s'.format(type_len+1, name_len+1)
        print(fmt%tuple(('Type|Name|Version|Disabled|Site Customization'.split('|'))))
        print()
        for plugin in initialized_plugins():
            print(fmt%(
                                plugin.type, plugin.name,
                                plugin.version, is_disabled(plugin),
                                plugin_customization(plugin)
                                ))
            print('\t', plugin.description)
            if plugin.is_customizable():
                try:
                    print('\t', plugin.customization_help())
                except NotImplementedError:
                    pass
            print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
# }}}
