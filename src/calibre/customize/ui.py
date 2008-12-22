from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import os, shutil, traceback, functools, sys

from calibre.customize import Plugin
from calibre.customize.filetype import Plugin as FileTypePlugin
from calibre.constants import __version__, iswindows, isosx
from calibre.utils.config import make_config_dir, Config, ConfigProxy, \
                                 plugin_dir, OptionParser


version = tuple([int(x) for x in __version__.split('.')])

platform = 'linux'
if iswindows:
    platform = 'windows'
if isosx:
    platform = 'osx'

from zipfile import ZipFile

def _config():
    c = Config('customize')
    c.add_opt('plugins', default={}, help=_('Installed plugins'))
    c.add_opt('filetype_mapping', default={}, help=_('Maping for filetype plugins'))
    c.add_opt('plugin_customization', default={}, help=_('Local plugin customization'))
    c.add_opt('disabled_plugins', default=set([]), help=_('Disabled plugins'))
    
    return ConfigProxy(c)

config = _config()


class InvalidPlugin(ValueError):
    pass

def load_plugin(path_to_zip_file):
    '''
    Load plugin from zip file or raise InvalidPlugin error
    
    :return: A :class:`Plugin` instance.
    '''
    print 'Loading plugin from', path_to_zip_file
    zf = ZipFile(path_to_zip_file)
    for name in zf.namelist():
        if name.lower().endswith('plugin.py'):
            locals = {}
            exec zf.read(name) in locals
            for x in locals.values():
                if isinstance(x, type) and issubclass(x, Plugin):
                    if x.minimum_calibre_version > version:
                        raise InvalidPlugin(_('%s needs calibre version at least %s')%
                                            (x.name, x.minimum_calibre_version))
                    if platform not in x.supported_platforms:
                        raise InvalidPlugin(_('%s is not supported on %s')%
                                            (x.name, platform))
                    
                    return x
    raise InvalidPlugin(_('No valid plugin found in ')+path_to_zip_file)

_initialized_plugins = []
_on_import           = {}
_on_preprocess       = {}
_on_postprocess      = {}



def reread_filetype_plugins():
    global _on_import
    global _on_preprocess
    global _on_postprocess
    _on_import           = {}
    _on_preprocess       = {}
    _on_postprocess      = {}

    for plugin in _initialized_plugins:
        if isinstance(plugin, FileTypePlugin):
            for ft in plugin.file_types:
                if plugin.on_import:
                    if not _on_import.has_key(ft):
                        _on_import[ft] = []
                    _on_import[ft].append(plugin)
                if plugin.on_preprocess:
                    if not _on_preprocess.has_key(ft):
                        _on_preprocess[ft] = []
                    _on_preprocess[ft].append(plugin)
                if plugin.on_postprocess:
                    if not _on_postprocess.has_key(ft):
                        _on_postprocess[ft] = []
                    _on_postprocess[ft].append(plugin)
                    
                
def _run_filetype_plugins(path_to_file, ft, occasion='preprocess'):
    occasion = {'import':_on_import, 'preprocess':_on_preprocess, 
                'postprocess':_on_postprocess}[occasion]
    customization = config['plugin_customization']
    nfp = path_to_file
    for plugin in occasion.get(ft, []):
        if is_disabled(plugin):
            continue
        sc = customization.get(plugin.name, '')
        try:
            nfp = plugin.run(path_to_file, sc)
        except:
            print 'Running file type plugin %s failed with traceback:'%plugin.name
            traceback.print_exc()
    return nfp

run_plugins_on_import      = functools.partial(_run_filetype_plugins, 
                                               occasion='import')
run_plugins_on_preprocess  = functools.partial(_run_filetype_plugins, 
                                               occasion='preprocess')
run_plugins_on_postprocess = functools.partial(_run_filetype_plugins, 
                                               occasion='postprocess')
                

def initialize_plugin(plugin, path_to_zip_file):
    print 'Initializing plugin', plugin.name
    try:
        plugin(path_to_zip_file)
    except Exception:
        tb = traceback.format_exc()
        raise InvalidPlugin((_('Initialization of plugin %s failed with traceback:')
                            %tb) + '\n'+tb)
    

def add_plugin(path_to_zip_file):
    make_config_dir()
    plugin = load_plugin(path_to_zip_file)
    initialize_plugin(plugin, path_to_zip_file)
    plugins = config['plugins']
    zfp = os.path.join(plugin_dir, 'name.zip')
    if os.path.exists(zfp):
        os.remove(zfp)
    shutil.copyfile(path_to_zip_file, zfp)
    plugins[plugin.name] = zfp
    config['plugins'] = plugins
    initialize_plugins()
    return plugin

def is_disabled(plugin):
    return plugin.name in config['disabled_plugins']

def find_plugin(name):
    for plugin in _initialized_plugins:
        if plugin.name == name:
            return plugin

def disable_plugin(plugin_or_name):
    x = getattr(plugin_or_name, 'name', plugin_or_name)
    dp = config['disabled_plugins']
    dp.add(x)
    config['disabled_plugins'] = dp

def enable_plugin(plugin_or_name):
    x = getattr(plugin_or_name, 'name', plugin_or_name)
    dp = config['disabled_plugins']
    if x in dp:
        dp.remove(x)
    config['disabled_plugins'] = dp

def initialize_plugins():
    global _initialized_plugins
    _initialized_plugins = []
    for zfp in config['plugins'].values():
        try:
            plugin = load_plugin(zfp)
            initialize_plugin(plugin, zfp)
            _initialized_plugins.append(plugin)
        except:
            print 'Failed to initialize plugin...'
            traceback.print_exc()
    _initialized_plugins.sort(cmp=lambda x,y:cmp(x.priority, y.priority), reverse=True)    
    reread_filetype_plugins()
    
initialize_plugins()

def option_parser():
    parser = OptionParser(usage=_('''\
    %prog options
    
    Customize calibre by loading external plugins.
    '''))
    parser.add_option('-a', '--add-plugin', default=None, 
                      help=_('Add a plugin by specifying the path to the zip file containing it.'))
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
    if opts.customize_plugin is not None:
        name, custom = opts.customize_plugin.split(',')
        plugin = find_plugin(name.strip())
        if plugin is None:
            print 'No plugin with the name %s exists'%name
            return 1
        config['plugin_customization'][plugin.name] = custom.strip()
    if opts.enable_plugin is not None:
        enable_plugin(opts.enable_plugin.strip())
    if opts.disable_plugin is not None:
        disable_plugin(opts.disable_plugin.strip())
    if opts.list_plugins:
        print 'Name\tVersion\tDisabled\tLocal Customization'
        for plugin in _initialized_plugins:
            print '%s\t%s\t%s\t%s'%(plugin.name, plugin.version, is_disabled(plugin), 
                                config['plugin_customization'].get(plugin.name))
            print '\t', plugin.customization_help()
        
    return 0
    
if __name__ == '__main__':
    sys.exit(main())