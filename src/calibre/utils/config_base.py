#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re, cPickle, traceback
from functools import partial
from collections import defaultdict
from copy import deepcopy

from calibre.utils.lock import LockError, ExclusiveFile
from calibre.constants import config_dir, CONFIG_DIR_MODE

plugin_dir = os.path.join(config_dir, 'plugins')

def make_config_dir():
    if not os.path.exists(plugin_dir):
        os.makedirs(plugin_dir, mode=CONFIG_DIR_MODE)

class Option(object):

    def __init__(self, name, switches=[], help='', type=None, choices=None,
                 check=None, group=None, default=None, action=None, metavar=None):
        if choices:
            type = 'choice'

        self.name     = name
        self.switches = switches
        self.help     = help.replace('%default', repr(default)) if help else None
        self.type     = type
        if self.type is None and action is None and choices is None:
            if isinstance(default, float):
                self.type = 'float'
            elif isinstance(default, int) and not isinstance(default, bool):
                self.type = 'int'

        self.choices  = choices
        self.check    = check
        self.group    = group
        self.default  = default
        self.action   = action
        self.metavar  = metavar

    def __eq__(self, other):
        return self.name == getattr(other, 'name', other)

    def __repr__(self):
        return 'Option: '+self.name

    def __str__(self):
        return repr(self)

class OptionValues(object):

    def copy(self):
        return deepcopy(self)

class OptionSet(object):

    OVERRIDE_PAT = re.compile(r'#{3,100} Override Options #{15}(.*?)#{3,100} End Override #{3,100}',
                              re.DOTALL|re.IGNORECASE)

    def __init__(self, description=''):
        self.description = description
        self.defaults = {}
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

    def get_option(self, name_or_option_object):
        idx = self.preferences.index(name_or_option_object)
        if idx > -1:
            return self.preferences[idx]
        for p in self.preferences:
            if p.name == name_or_option_object:
                return p

    def add_group(self, name, description=''):
        if name in self.group_list:
            raise ValueError('A group by the name %s already exists in this set'%name)
        self.groups[name] = description
        self.group_list.append(name)
        return partial(self.add_opt, group=name)

    def update(self, other):
        for name in other.groups.keys():
            self.groups[name] = other.groups[name]
            if name not in self.group_list:
                self.group_list.append(name)
        for pref in other.preferences:
            if pref in self.preferences:
                self.preferences.remove(pref)
            self.preferences.append(pref)

    def smart_update(self, opts1, opts2):
        '''
        Updates the preference values in opts1 using only the non-default preference values in opts2.
        '''
        for pref in self.preferences:
            new = getattr(opts2, pref.name, pref.default)
            if new != pref.default:
                setattr(opts1, pref.name, new)

    def remove_opt(self, name):
        if name in self.preferences:
            self.preferences.remove(name)


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
                           `None, 'choice', 'complex', 'float', 'int', 'string'`.
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
        self.defaults[name] = default

    def option_parser(self, user_defaults=None, usage='', gui_mode=False):
        from calibre.utils.config import OptionParser
        parser = OptionParser(usage, gui_mode=gui_mode)
        groups = defaultdict(lambda : parser)
        for group, desc in self.groups.items():
            groups[group] = parser.add_option_group(group.upper(), desc)

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
            try:
                if not isinstance(src, unicode):
                    src = src.decode('utf-8')
                exec src in options
            except:
                print 'Failed to parse options string:'
                print repr(src)
                traceback.print_exc()
        opts = OptionValues()
        for pref in self.preferences:
            val = options.get(pref.name, pref.default)
            formatter = __builtins__.get(pref.type, None)
            if callable(formatter):
                val = formatter(val)
            setattr(opts, pref.name, val)

        return opts

    def render_group(self, name, desc, opts):
        prefs = [pref for pref in self.preferences if pref.group == name]
        lines = ['### Begin group: %s'%(name if name else 'DEFAULT')]
        if desc:
            lines += map(lambda x: '# '+x, desc.split('\n'))
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
        if val.__class__.__name__ == 'QString':
            return repr(unicode(val))
        pickle = cPickle.dumps(val, -1)
        return 'cPickle.loads(%s)'%repr(pickle)

    def serialize(self, opts):
        src = '# %s\n\n'%(self.description.replace('\n', '\n# '))
        groups = [self.render_group(name, self.groups.get(name, ''), opts) \
                                        for name in [None] + self.group_list]
        return src + '\n\n'.join(groups)

class ConfigInterface(object):

    def __init__(self, description):
        self.option_set       = OptionSet(description=description)
        self.add_opt          = self.option_set.add_opt
        self.add_group        = self.option_set.add_group
        self.remove_opt       = self.remove = self.option_set.remove_opt
        self.parse_string     = self.option_set.parse_string
        self.get_option       = self.option_set.get_option
        self.preferences      = self.option_set.preferences

    def update(self, other):
        self.option_set.update(other.option_set)

    def option_parser(self, usage='', gui_mode=False):
        return self.option_set.option_parser(user_defaults=self.parse(),
                                             usage=usage, gui_mode=gui_mode)

    def smart_update(self, opts1, opts2):
        self.option_set.smart_update(opts1, opts2)


class Config(ConfigInterface):
    '''
    A file based configuration.
    '''

    def __init__(self, basename, description=''):
        ConfigInterface.__init__(self, description)
        self.config_file_path = os.path.join(config_dir, basename+'.py')


    def parse(self):
        src = ''
        if os.path.exists(self.config_file_path):
            try:
                with ExclusiveFile(self.config_file_path) as f:
                    try:
                        src = f.read().decode('utf-8')
                    except ValueError:
                        print "Failed to parse", self.config_file_path
                        traceback.print_exc()
            except LockError:
                raise IOError('Could not lock config file: %s'%self.config_file_path)
        return self.option_set.parse_string(src)

    def as_string(self):
        if not os.path.exists(self.config_file_path):
            return ''
        try:
            with ExclusiveFile(self.config_file_path) as f:
                return f.read().decode('utf-8')
        except LockError:
            raise IOError('Could not lock config file: %s'%self.config_file_path)

    def set(self, name, val):
        if not self.option_set.has_option(name):
            raise ValueError('The option %s is not defined.'%name)
        try:
            if not os.path.exists(config_dir):
                make_config_dir()
            with ExclusiveFile(self.config_file_path) as f:
                src = f.read()
                opts = self.option_set.parse_string(src)
                setattr(opts, name, val)
                footer = self.option_set.get_override_section(src)
                src = self.option_set.serialize(opts)+ '\n\n' + footer + '\n'
                f.seek(0)
                f.truncate()
                if isinstance(src, unicode):
                    src = src.encode('utf-8')
                f.write(src)
        except LockError:
            raise IOError('Could not lock config file: %s'%self.config_file_path)

class StringConfig(ConfigInterface):
    '''
    A string based configuration
    '''

    def __init__(self, src, description=''):
        ConfigInterface.__init__(self, description)
        self.src = src

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

    @property
    def defaults(self):
        return self.__config.option_set.defaults

    def refresh(self):
        self.__opts = self.__config.parse()

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, val):
        return self.set(key, val)

    def __delitem__(self, key):
        self.set(key, self.defaults[key])

    def get(self, key):
        if self.__opts is None:
            self.refresh()
        return getattr(self.__opts, key)

    def set(self, key, val):
        if self.__opts is None:
            self.refresh()
        setattr(self.__opts, key, val)
        return self.__config.set(key, val)

    def help(self, key):
        return self.__config.get_option(key).help



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
    c.add_opt('language', default=None,
              help=_('The language in which to display the user interface'))
    c.add_opt('output_format', default='EPUB',
              help=_('The default output format for ebook conversions.'))
    c.add_opt('input_format_order', default=['EPUB', 'MOBI', 'LIT', 'PRC',
        'FB2', 'HTML', 'HTM', 'XHTM', 'SHTML', 'XHTML', 'ZIP', 'ODT', 'RTF', 'PDF',
        'TXT'],
              help=_('Ordered list of formats to prefer for input.'))
    c.add_opt('read_file_metadata', default=True,
              help=_('Read metadata from files'))
    c.add_opt('worker_process_priority', default='normal',
              help=_('The priority of worker processes. A higher priority '
                  'means they run faster and consume more resources. '
                  'Most tasks like conversion/news download/adding books/etc. '
                  'are affected by this setting.'))
    c.add_opt('swap_author_names', default=False,
            help=_('Swap author first and last names when reading metadata'))
    c.add_opt('add_formats_to_existing', default=False,
            help=_('Add new formats to existing book records'))
    c.add_opt('installation_uuid', default=None, help='Installation UUID')
    c.add_opt('new_book_tags', default=[], help=_('Tags to apply to books added to the library'))

    # these are here instead of the gui preferences because calibredb and
    # calibre server can execute searches
    c.add_opt('saved_searches', default={}, help=_('List of named saved searches'))
    c.add_opt('user_categories', default={}, help=_('User-created tag browser categories'))
    c.add_opt('manage_device_metadata', default='manual',
        help=_('How and when calibre updates metadata on the device.'))
    c.add_opt('limit_search_columns', default=False,
            help=_('When searching for text without using lookup '
            'prefixes, as for example, Red instead of title:Red, '
            'limit the columns searched to those named below.'))
    c.add_opt('limit_search_columns_to',
            default=['title', 'authors', 'tags', 'series', 'publisher'],
            help=_('Choose columns to be searched when not using prefixes, '
                'as for example, when searching for Red instead of '
                'title:Red. Enter a list of search/lookup names '
                'separated by commas. Only takes effect if you set the option '
                'to limit search columns above.'))

    c.add_opt('migrated', default=False, help='For Internal use. Don\'t modify.')
    return c

prefs = ConfigProxy(_prefs())
if prefs['installation_uuid'] is None:
    import uuid
    prefs['installation_uuid'] = str(uuid.uuid4())

# Read tweaks
def read_raw_tweaks():
    make_config_dir()
    default_tweaks = P('default_tweaks.py', data=True,
            allow_user_override=False)
    tweaks_file = os.path.join(config_dir, 'tweaks.py')
    if not os.path.exists(tweaks_file):
        with open(tweaks_file, 'wb') as f:
            f.write(default_tweaks)
    with open(tweaks_file, 'rb') as f:
        return default_tweaks, f.read()

def read_tweaks():
    default_tweaks, tweaks = read_raw_tweaks()
    l, g = {}, {}
    try:
        exec tweaks in g, l
    except:
        import traceback
        print 'Failed to load custom tweaks file'
        traceback.print_exc()
    dl, dg = {}, {}
    exec default_tweaks in dg, dl
    dl.update(l)
    return dl

def write_tweaks(raw):
    make_config_dir()
    tweaks_file = os.path.join(config_dir, 'tweaks.py')
    with open(tweaks_file, 'wb') as f:
        f.write(raw)


tweaks = read_tweaks()


