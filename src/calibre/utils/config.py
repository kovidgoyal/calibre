from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Manage application-wide preferences.
'''
import os, cPickle, base64, datetime, json, plistlib
from copy import deepcopy
from optparse import OptionParser as _OptionParser
from optparse import IndentedHelpFormatter

from calibre.constants import (config_dir, CONFIG_DIR_MODE, __appname__,
        __version__, __author__, terminal_controller)
from calibre.utils.lock import ExclusiveFile
from calibre.utils.config_base import (make_config_dir, Option, OptionValues,
        OptionSet, ConfigInterface, Config, prefs, StringConfig, ConfigProxy,
        read_raw_tweaks, read_tweaks, write_tweaks, tweaks, plugin_dir)

if False:
    # Make pyflakes happy
    Config, ConfigProxy, Option, OptionValues, StringConfig
    OptionSet, ConfigInterface, read_tweaks, write_tweaks
    read_raw_tweaks, tweaks, plugin_dir, prefs

def check_config_write_access():
    return os.access(config_dir, os.W_OK) and os.access(config_dir, os.X_OK)

class CustomHelpFormatter(IndentedHelpFormatter):

    def format_usage(self, usage):
        tc = terminal_controller()
        return "%s%s%s: %s\n" % (tc.BLUE, _('Usage'), tc.NORMAL, usage)

    def format_heading(self, heading):
        tc = terminal_controller()
        return "%*s%s%s%s:\n" % (self.current_indent, tc.BLUE,
                                 "", heading, tc.NORMAL)

    def format_option(self, option):
        import textwrap
        tc = terminal_controller()

        result = []
        opts = self.option_strings[option]
        opt_width = self.help_position - self.current_indent - 2
        if len(opts) > opt_width:
            opts = "%*s%s\n" % (self.current_indent, "",
                                    tc.GREEN+opts+tc.NORMAL)
            indent_first = self.help_position
        else:                       # start help on same line as opts
            opts = "%*s%-*s  " % (self.current_indent, "", opt_width +
                    len(tc.GREEN + tc.NORMAL), tc.GREEN + opts + tc.NORMAL)
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
                 epilog=None,
                 gui_mode=False,
                 conflict_handler='resolve',
                 **kwds):
        import textwrap
        tc = terminal_controller()

        usage = textwrap.dedent(usage)
        if epilog is None:
            epilog = _('Created by ')+tc.RED+__author__+tc.NORMAL
        usage += '\n\n'+_('''Whenever you pass arguments to %prog that have spaces in them, '''
                 '''enclose the arguments in quotation marks.''')
        _OptionParser.__init__(self, usage=usage, version=version, epilog=epilog,
                               formatter=CustomHelpFormatter(),
                               conflict_handler=conflict_handler, **kwds)
        self.gui_mode = gui_mode
        for o, msg in {'-h':_('show this help message and exit'), '--version':
                _("show program's version number and exit")}.iteritems():
            opt = self.get_option(o)
            if opt is not None:
                opt.help = msg

    def error(self, msg):
        if self.gui_mode:
            raise Exception(msg)
        _OptionParser.error(self, msg)

    def merge(self, parser):
        '''
        Add options from parser to self. In case of conflicts, conflicting options from
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


class DynamicConfig(dict):
    '''
    A replacement for QSettings that supports dynamic config keys.
    Returns `None` if a config key is not found. Note that the config
    data is stored in a non human readable pickle file, so only use this
    class for preferences that you don't intend to have the users edit directly.
    '''
    def __init__(self, name='dynamic'):
        dict.__init__(self, {})
        self.name = name
        self.defaults = {}
        self.file_path = os.path.join(config_dir, name+'.pickle')
        self.refresh()

    def refresh(self):
        d = {}
        if os.path.exists(self.file_path):
            with ExclusiveFile(self.file_path) as f:
                raw = f.read()
                try:
                    d = cPickle.loads(raw) if raw.strip() else {}
                except SystemError:
                    pass
                except:
                    import traceback
                    print 'Failed to unpickle stored object:'
                    traceback.print_exc()
                    d = {}
        self.clear()
        self.update(d)

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults.get(key, None)

    def get(self, key, default=None):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults.get(key, default)

    def __setitem__(self, key, val):
        dict.__setitem__(self, key, val)
        self.commit()

    def set(self, key, val):
        self.__setitem__(key, val)

    def commit(self):
        if hasattr(self, 'file_path') and self.file_path:
            if not os.path.exists(self.file_path):
                make_config_dir()
            with ExclusiveFile(self.file_path) as f:
                raw = cPickle.dumps(self, -1)
                f.seek(0)
                f.truncate()
                f.write(raw)

dynamic = DynamicConfig()

class XMLConfig(dict):

    '''
    Similar to :class:`DynamicConfig`, except that it uses an XML storage
    backend instead of a pickle file.

    See `http://docs.python.org/dev/library/plistlib.html`_ for the supported
    data types.
    '''

    EXTENSION = '.plist'

    def __init__(self, rel_path_to_cf_file):
        dict.__init__(self)
        self.defaults = {}
        self.file_path = os.path.join(config_dir,
                *(rel_path_to_cf_file.split('/')))
        self.file_path = os.path.abspath(self.file_path)
        if not self.file_path.endswith(self.EXTENSION):
            self.file_path += self.EXTENSION

        self.refresh()

    def raw_to_object(self, raw):
        return plistlib.readPlistFromString(raw)

    def to_raw(self):
        return plistlib.writePlistToString(self)

    def refresh(self):
        d = {}
        if os.path.exists(self.file_path):
            with ExclusiveFile(self.file_path) as f:
                raw = f.read()
                try:
                    d = self.raw_to_object(raw) if raw.strip() else {}
                except SystemError:
                    pass
                except:
                    import traceback
                    traceback.print_exc()
                    d = {}
        self.clear()
        self.update(d)

    def __getitem__(self, key):
        try:
            ans = dict.__getitem__(self, key)
            if isinstance(ans, plistlib.Data):
                ans = ans.data
            return ans
        except KeyError:
            return self.defaults.get(key, None)

    def get(self, key, default=None):
        try:
            ans = dict.__getitem__(self, key)
            if isinstance(ans, plistlib.Data):
                ans = ans.data
            return ans
        except KeyError:
            return self.defaults.get(key, default)

    def __setitem__(self, key, val):
        if isinstance(val, (bytes, str)):
            val = plistlib.Data(val)
        dict.__setitem__(self, key, val)
        self.commit()

    def set(self, key, val):
        self.__setitem__(key, val)

    def __delitem__(self, key):
        if dict.has_key(self, key):
            dict.__delitem__(self, key)
            self.commit()

    def commit(self):
        if hasattr(self, 'file_path') and self.file_path:
            dpath = os.path.dirname(self.file_path)
            if not os.path.exists(dpath):
                os.makedirs(dpath, mode=CONFIG_DIR_MODE)
            with ExclusiveFile(self.file_path) as f:
                raw = self.to_raw()
                f.seek(0)
                f.truncate()
                f.write(raw)

def to_json(obj):
    if isinstance(obj, bytearray):
        return {'__class__': 'bytearray',
                '__value__': base64.standard_b64encode(bytes(obj))}
    if isinstance(obj, datetime.datetime):
        from calibre.utils.date import isoformat
        return {'__class__': 'datetime.datetime',
                '__value__': isoformat(obj, as_utc=True)}
    raise TypeError(repr(obj) + ' is not JSON serializable')

def from_json(obj):
    if '__class__' in obj:
        if obj['__class__'] == 'bytearray':
            return bytearray(base64.standard_b64decode(obj['__value__']))
        if obj['__class__'] == 'datetime.datetime':
            from calibre.utils.date import parse_date
            return parse_date(obj['__value__'], assume_utc=True)
    return obj

class JSONConfig(XMLConfig):

    EXTENSION = '.json'

    def raw_to_object(self, raw):
        return json.loads(raw.decode('utf-8'), object_hook=from_json)

    def to_raw(self):
        return json.dumps(self, indent=2, default=to_json)

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults[key]

    def get(self, key, default=None):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults.get(key, default)

    def __setitem__(self, key, val):
        dict.__setitem__(self, key, val)
        self.commit()





