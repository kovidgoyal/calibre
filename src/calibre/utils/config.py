from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Manage application-wide preferences.
'''
import os, re, cPickle
from copy import deepcopy
from PyQt4.QtCore import QString
from calibre import iswindows, isosx, OptionParser, ExclusiveFile, LockError 
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
    config_dir = os.path.expanduser('~/.config/calibre')

if not os.path.exists(config_dir):
    os.makedirs(config_dir)
    
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
        