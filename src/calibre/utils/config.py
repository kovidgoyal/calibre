from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Manage application-wide preferences.
'''
import os, re, cPickle, textwrap
from copy import deepcopy
from optparse import OptionParser as _OptionParser
from optparse import IndentedHelpFormatter
from PyQt4.QtCore import QString
from calibre.constants import terminal_controller, iswindows, isosx, \
                              __appname__, __version__, __author__
from calibre.utils.lock import LockError, ExclusiveFile 
from collections import defaultdict

if iswindows:
    from calibre import plugins
    config_dir = plugins['winutil'][0].special_folder_path(plugins['winutil'][0].CSIDL_APPDATA)
    if not os.access(config_dir, os.W_OK|os.X_OK):
        config_dir = os.path.expanduser('~')
    config_dir = os.path.join(config_dir, 'calibre')
elif isosx:
    config_dir = os.path.expanduser('~/Library/Preferences/calibre')
else:
    bdir = os.path.abspath(os.path.expanduser(os.environ.get('XDG_CONFIG_HOME', '~/.config')))
    config_dir = os.path.join(bdir, 'calibre')

if not os.path.exists(config_dir):
    os.makedirs(config_dir, mode=448) # 0700 == 448

class CustomHelpFormatter(IndentedHelpFormatter):
    
    def format_usage(self, usage):
        return _("%sUsage%s: %s\n") % (terminal_controller.BLUE, terminal_controller.NORMAL, usage)
    
    def format_heading(self, heading):
        return "%*s%s%s%s:\n" % (self.current_indent, terminal_controller.BLUE, 
                                 "", heading, terminal_controller.NORMAL)
        
    def format_option(self, option):
        result = []
        opts = self.option_strings[option]
        opt_width = self.help_position - self.current_indent - 2
        if len(opts) > opt_width:
            opts = "%*s%s\n" % (self.current_indent, "", 
                                    terminal_controller.GREEN+opts+terminal_controller.NORMAL)
            indent_first = self.help_position
        else:                       # start help on same line as opts
            opts = "%*s%-*s  " % (self.current_indent, "", opt_width + len(terminal_controller.GREEN + terminal_controller.NORMAL), 
                                  terminal_controller.GREEN + opts + terminal_controller.NORMAL)
            indent_first = 0
        result.append(opts)
        if option.help:
            help_text = self.expand_default(option).split('\n')
            help_lines = []
            
            for line in help_text:
                help_lines.extend(textwrap.wrap(line, self.help_width))
            result.append("%*s%s\n" % (indent_first, "", help_lines[0]))
            result.extend(["%*s%s\n" % (self.help_position, "", line)
                           for line in help_lines[1:]])
        elif opts[-1] != "\n":
            result.append("\n")
        return "".join(result)+'\n'


class OptionParser(_OptionParser):
    
    def __init__(self,
                 usage='%prog [options] filename',
                 version='%%prog (%s %s)'%(__appname__, __version__),
                 epilog=_('Created by ')+terminal_controller.RED+__author__+terminal_controller.NORMAL,
                 gui_mode=False,
                 conflict_handler='resolve',
                 **kwds):
        usage += '''\n\nWhenever you pass arguments to %prog that have spaces in them, '''\
                 '''enclose the arguments in quotation marks.'''
        _OptionParser.__init__(self, usage=usage, version=version, epilog=epilog, 
                               formatter=CustomHelpFormatter(), 
                               conflict_handler=conflict_handler, **kwds)
        self.gui_mode = gui_mode
        
    def error(self, msg):
        if self.gui_mode:
            raise Exception(msg)
        _OptionParser.error(self, msg)
        
    def merge(self, parser):
        '''
        Add options from parser to self. In case of conflicts, confilicting options from
        parser are skipped.
        '''
        opts   = list(parser.option_list)
        groups = list(parser.option_groups)
        
        def merge_options(options, container):
            for opt in deepcopy(options):
                if not self.has_option(opt.get_opt_string()):
                    container.add_option(opt)
                
        merge_options(opts, self)
        
        for group in groups:
            g = self.add_option_group(group.title)
            merge_options(group.option_list, g)
        
    def subsume(self, group_name, msg=''):
        '''
        Move all existing options into a subgroup named
        C{group_name} with description C{msg}.
        '''
        opts = [opt for opt in self.options_iter() if opt.get_opt_string() not in ('--version', '--help')]
        self.option_groups = []
        subgroup = self.add_option_group(group_name, msg)
        for opt in opts:
            self.remove_option(opt.get_opt_string())
            subgroup.add_option(opt)
        
    def options_iter(self):
        for opt in self.option_list:
            if str(opt).strip():
                yield opt
        for gr in self.option_groups:
            for opt in gr.option_list:
                if str(opt).strip():
                    yield opt
                
    def option_by_dest(self, dest):
        for opt in self.options_iter():
            if opt.dest == dest:
                return opt
    
    def merge_options(self, lower, upper):
        '''
        Merge options in lower and upper option lists into upper.
        Default values in upper are overridden by
        non default values in lower.
        '''
        for dest in lower.__dict__.keys():
            if not upper.__dict__.has_key(dest):
                continue
            opt = self.option_by_dest(dest)
            if lower.__dict__[dest] != opt.default and \
               upper.__dict__[dest] == opt.default:
                upper.__dict__[dest] = lower.__dict__[dest]
        


class Option(object):
    
    def __init__(self, name, switches=[], help='', type=None, choices=None, 
                 check=None, group=None, default=None, action=None, metavar=None):
        if choices:
            type = 'choice'
        
        self.name     = name
        self.switches = switches
        self.help     = help.replace('%default', repr(default)) if help else None
        self.type     = type
        self.choices  = choices
        self.check    = check
        self.group    = group
        self.default  = default
        self.action   = action
        self.metavar  = metavar
        
    def __eq__(self, other):
        return self.name == getattr(other, 'name', None)
        
class OptionValues(object):
    
    def copy(self):
        return deepcopy(self)

class OptionSet(object):
    
    OVERRIDE_PAT = re.compile(r'#{3,100} Override Options #{15}(.*?)#{3,100} End Override #{3,100}', 
                              re.DOTALL|re.IGNORECASE)
    
    def __init__(self, description=''):
        self.description = description
        self.preferences = []
        self.group_list  = []
        self.groups      = {}
        self.set_buffer  = {}
    
    def has_option(self, name_or_option_object):
        if name_or_option_object in self.preferences:
            return True
        for p in self.preferences:
            if p.name == name_or_option_object:
                return True
        return False
    
    def add_group(self, name, description=''):
        if name in self.group_list:
            raise ValueError('A group by the name %s already exists in this set'%name)
        self.groups[name] = description
        self.group_list.append(name)
        
    def add_opt(self, name, switches=[], help=None, type=None, choices=None, 
                 group=None, default=None, action=None, metavar=None):
        '''
        Add an option to this section.
        
        :param name:       The name of this option. Must be a valid Python identifier.
                           Must also be unique in this OptionSet and all its subsets. 
        :param switches:   List of command line switches for this option 
                           (as supplied to :module:`optparse`). If empty, this
                           option will not be added to the command line parser.
        :param help:       Help text.
        :param type:       Type checking of option values. Supported types are:
                           `None, 'choice', 'complex', 'float', 'int', 'long', 'string'`.
        :param choices:    List of strings or `None`.
        :param group:      Group this option belongs to. You must previously 
                           have created this group with a call to :method:`add_group`.
        :param default:    The default value for this option.
        :param action:     The action to pass to optparse. Supported values are:
                           `None, 'count'`. For choices and boolean options,
                           action is automatically set correctly.
        '''
        pref = Option(name, switches=switches, help=help, type=type, choices=choices, 
                 group=group, default=default, action=action, metavar=None)
        if group is not None and group not in self.groups.keys():
            raise ValueError('Group %s has not been added to this section'%group)
        if pref in self.preferences:
            raise ValueError('An option with the name %s already exists in this set.'%name)
        self.preferences.append(pref)
        
    def option_parser(self, user_defaults=None, usage='', gui_mode=False):
        parser = OptionParser(usage, gui_mode=gui_mode)
        groups = defaultdict(lambda : parser)
        for group, desc in self.groups.items():
            groups[group] = parser.add_group(group, desc)
        
        for pref in self.preferences:
            if not pref.switches:
                continue
            g = groups[pref.group]
            action = pref.action
            if action is None:
                action = 'store'
                if pref.default is True or pref.default is False:
                    action = 'store_' + ('false' if pref.default else 'true')
            args = dict(
                        dest=pref.name,
                        help=pref.help,
                        metavar=pref.metavar,
                        type=pref.type,
                        choices=pref.choices,
                        default=getattr(user_defaults, pref.name, pref.default),
                        action=action,
                        )
            g.add_option(*pref.switches, **args)
            
            
        return parser
    
    def get_override_section(self, src):
        match = self.OVERRIDE_PAT.search(src)
        if match:
            return match.group()
        return ''
    
    def parse_string(self, src):
        options = {'cPickle':cPickle}
        if src is not None:
            exec src in options
        opts = OptionValues()
        for pref in self.preferences:
            setattr(opts, pref.name, options.get(pref.name, pref.default))
            
        return opts
    
    def render_group(self, name, desc, opts):
        prefs = [pref for pref in self.preferences if pref.group == name]
        lines = ['### Begin group: %s'%(name if name else 'DEFAULT')]
        if desc:
            lines += map(lambda x: '# '+x for x in desc.split('\n'))
        lines.append(' ')
        for pref in prefs:
            lines.append('# '+pref.name.replace('_', ' '))
            if pref.help:
                lines += map(lambda x: '# ' + x, pref.help.split('\n'))
            lines.append('%s = %s'%(pref.name, 
                            self.serialize_opt(getattr(opts, pref.name, pref.default))))
            lines.append(' ')
        return '\n'.join(lines)
        
    def serialize_opt(self, val):
        if val is val is True or val is False or val is None or \
           isinstance(val, (int, float, long, basestring)):
            return repr(val)
        if isinstance(val, QString):
            return repr(unicode(val))
        pickle = cPickle.dumps(val, -1)
        return 'cPickle.loads(%s)'%repr(pickle)
    
    def serialize(self, opts):
        src = '# %s\n\n'%(self.description.replace('\n', '\n# '))
        groups = [self.render_group(name, self.groups.get(name, ''), opts) \
                                        for name in [None] + self.group_list]
        return src + '\n\n'.join(groups)
    
class Config(object):
    
    def __init__(self, basename, description=''):
        self.config_file_path = os.path.join(config_dir, basename+'.py')
        self.option_set       = OptionSet(description=description)
        self.add_opt          = self.option_set.add_opt
        self.add_group        = self.option_set.add_group
        
    def option_parser(self, usage='', gui_mode=False):
        return self.option_set.option_parser(user_defaults=self.parse(), 
                                             usage=usage, gui_mode=gui_mode)
        
    def parse(self):
        try:
            with ExclusiveFile(self.config_file_path) as f:
                src = f.read()
        except LockError:
            raise IOError('Could not lock config file: %s'%self.config_file_path)
        return self.option_set.parse_string(src)
    
    def as_string(self):
        if not os.path.exists(self.config_file_path):
            return ''
        try:
            with ExclusiveFile(self.config_file_path) as f:
                return f.read()
        except LockError:
            raise IOError('Could not lock config file: %s'%self.config_file_path)
    
    def set(self, name, val):
        if not self.option_set.has_option(name):
            raise ValueError('The option %s is not defined.'%name)
        try:
            with ExclusiveFile(self.config_file_path) as f:
                src = f.read()
                opts = self.option_set.parse_string(src)
                setattr(opts, name, val)
                footer = self.option_set.get_override_section(src)
                src = self.option_set.serialize(opts)+ '\n\n' + footer + '\n'
                f.seek(0)
                f.truncate()
                f.write(src)
        except LockError:
            raise IOError('Could not lock config file: %s'%self.config_file_path)
            
class StringConfig(object):
    
    def __init__(self, src, description=''):
        self.src = src
        self.option_set       = OptionSet(description=description)
        self.add_opt          = self.option_set.add_opt
        self.option_parser    = self.option_set.option_parser
        
    def option_parser(self, usage='', gui_mode=False):
        return self.option_set.option_parser(user_defaults=self.parse(), 
                                             usage=usage, gui_mode=gui_mode)
    
    def parse(self):
        return self.option_set.parse_string(self.src)
    
    def set(self, name, val):
        if not self.option_set.has_option(name):
            raise ValueError('The option %s is not defined.'%name)
        opts = self.option_set.parse_string(self.src)
        setattr(opts, name, val)
        footer = self.option_set.get_override_section(self.src)
        self.src = self.option_set.serialize(opts)+ '\n\n' + footer + '\n'

class ConfigProxy(object):
    '''
    A Proxy to minimize file reads for widely used config settings
    '''
    
    def __init__(self, config):
        self.__config = config
        self.__opts   = None 
        
    def refresh(self):
        self.__opts = self.__config.parse()
    
    def __getitem__(self, key):
        return self.get(key)
    
    def __setitem__(self, key, val):
        return self.set(key, val)
    
    def get(self, key):
        if self.__opts is None:
            self.refresh()
        return getattr(self.__opts, key)
        
    def set(self, key, val):
        if self.__opts is None:
            self.refresh()
        setattr(self.__opts, key, val)
        return self.__config.set(key, val) 

class DynamicConfig(dict):
    '''
    A replacement for QSettings that supports dynamic config keys.
    Returns `None` if a config key is not found. Note that the config
    data is stored in a non human readable pickle file, so only use this
    class for preferences that you don't intend to have the users edit directly.
    '''
    def __init__(self, name='dynamic'):
        self.name = name
        self.file_path = os.path.join(config_dir, name+'.pickle')
        with ExclusiveFile(self.file_path) as f:
            raw = f.read()
            d = cPickle.loads(raw) if raw.strip() else {}
        dict.__init__(self, d)
        
    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return None
        
    def __setitem__(self, key, val):
        dict.__setitem__(self, key, val)
        self.commit()
        
    def set(self, key, val):
        self.__setitem__(key, val)
    
    def commit(self):
        if hasattr(self, 'file_path') and self.file_path:
            with ExclusiveFile(self.file_path) as f:
                raw = cPickle.dumps(self, -1)
                f.seek(0)
                f.truncate()
                f.write(raw)
            
dynamic = DynamicConfig()    

def _prefs():
    c = Config('global', 'calibre wide preferences')
    c.add_opt('database_path', 
              default=os.path.expanduser('~/library1.db'),
              help=_('Path to the database in which books are stored'))
    c.add_opt('filename_pattern', default=ur'(?P<title>.+) - (?P<author>[^_]+)',
              help=_('Pattern to guess metadata from filenames'))
    c.add_opt('isbndb_com_key', default='', 
              help=_('Access key for isbndb.com'))
    c.add_opt('network_timeout', default=5,
              help=_('Default timeout for network operations (seconds)'))
    c.add_opt('library_path', default=None,
              help=_('Path to directory in which your library of books is stored'))
    
    c.add_opt('migrated', default=False, help='For Internal use. Don\'t modify.')
    return c

prefs = ConfigProxy(_prefs())

def migrate():
    p = prefs
    if p.get('migrated'):
        return

    from PyQt4.QtCore import QSettings, QVariant
    class Settings(QSettings):
    
        def __init__(self, name='calibre2'):
            QSettings.__init__(self, QSettings.IniFormat, QSettings.UserScope,
                               'kovidgoyal.net', name)
            
        def get(self, key, default=None):
            try:
                key = str(key)
                if not self.contains(key):
                    return default
                val = str(self.value(key, QVariant()).toByteArray())
                if not val:
                    return None
                return cPickle.loads(val)
            except:
                return default
        
    s, migrated = Settings(), set([])
    all_keys = set(map(unicode, s.allKeys()))
    from calibre.gui2 import config, dynamic
    def _migrate(key, safe=None, from_qvariant=None, p=config):
        try:
            if key not in all_keys:
                return
            if safe is None:
                safe = re.sub(r'[^0-9a-zA-Z]', '_', key)
            val = s.get(key)
            if from_qvariant is not None:
                val = getattr(s.value(key), from_qvariant)()
            p.set(safe, val)
        except:
            pass
        finally:
            migrated.add(key)
        
    
    _migrate('database path',    p=prefs)
    _migrate('filename pattern', p=prefs)
    _migrate('network timeout', p=prefs)
    _migrate('isbndb.com key',   p=prefs)
    
    _migrate('frequently used directories')
    _migrate('send to device by default')
    _migrate('save to disk single format')
    _migrate('confirm delete')
    _migrate('show text in toolbar')
    _migrate('new version notification')
    _migrate('use roman numerals for series number')
    _migrate('cover flow queue length')
    _migrate('LRF conversion defaults')
    _migrate('LRF ebook viewer options')
    
    for key in all_keys - migrated:
        if key.endswith(': un') or key.endswith(': pw'):
            _migrate(key, p=dynamic)
    p.set('migrated', True)
        
    
if __name__ == '__main__':
    import subprocess
    from PyQt4.Qt import QByteArray
    c = Config('test', 'test config')
    
    c.add_opt('one', ['-1', '--one'], help="This is option #1")
    c.set('one', u'345')
    
    c.add_opt('two', help="This is option #2")
    c.set('two', 345)
    
    c.add_opt('three', help="This is option #3")
    c.set('three', QString(u'aflatoon'))
    
    c.add_opt('four', help="This is option #4")
    c.set('four', QByteArray('binary aflatoon'))
    
    subprocess.call(['pygmentize', os.path.expanduser('~/.config/calibre/test.py')])
    
    opts = c.parse()
    for i in ('one', 'two', 'three', 'four'):
        print i, repr(getattr(opts, i))
        