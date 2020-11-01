

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Manage application-wide preferences.
'''

import optparse
import os
from copy import deepcopy

from calibre.constants import (
    CONFIG_DIR_MODE, __appname__, __author__, config_dir, get_version, iswindows
)
from calibre.utils.config_base import (
    Config, ConfigInterface, ConfigProxy, Option, OptionSet, OptionValues,
    StringConfig, json_dumps, json_loads, make_config_dir, plugin_dir, prefs,
    tweaks, from_json, to_json
)
from calibre.utils.lock import ExclusiveFile
from polyglot.builtins import string_or_bytes, native_string_type


# optparse uses gettext.gettext instead of _ from builtins, so we
# monkey patch it.
optparse._ = _

if False:
    # Make pyflakes happy
    Config, ConfigProxy, Option, OptionValues, StringConfig, OptionSet,
    ConfigInterface, tweaks, plugin_dir, prefs, from_json, to_json


def check_config_write_access():
    return os.access(config_dir, os.W_OK) and os.access(config_dir, os.X_OK)


class CustomHelpFormatter(optparse.IndentedHelpFormatter):

    def format_usage(self, usage):
        from calibre.utils.terminal import colored
        parts = usage.split(' ')
        if parts:
            parts[0] = colored(parts[0], fg='yellow', bold=True)
        usage = ' '.join(parts)
        return colored(_('Usage'), fg='blue', bold=True) + ': ' + usage

    def format_heading(self, heading):
        from calibre.utils.terminal import colored
        return "%*s%s:\n" % (self.current_indent, '',
                                 colored(heading, fg='blue', bold=True))

    def format_option(self, option):
        import textwrap
        from calibre.utils.terminal import colored

        result = []
        opts = self.option_strings[option]
        opt_width = self.help_position - self.current_indent - 2
        if len(opts) > opt_width:
            opts = "%*s%s\n" % (self.current_indent, "",
                                    colored(opts, fg='green'))
            indent_first = self.help_position
        else:                       # start help on same line as opts
            opts = "%*s%-*s  " % (self.current_indent, "", opt_width +
                    len(colored('', fg='green')), colored(opts, fg='green'))
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


class OptionParser(optparse.OptionParser):

    def __init__(self,
                 usage='%prog [options] filename',
                 version=None,
                 epilog=None,
                 gui_mode=False,
                 conflict_handler='resolve',
                 **kwds):
        import textwrap
        from calibre.utils.terminal import colored

        usage = textwrap.dedent(usage)
        if epilog is None:
            epilog = _('Created by ')+colored(__author__, fg='cyan')
        usage += '\n\n'+_('''Whenever you pass arguments to %prog that have spaces in them, '''
                          '''enclose the arguments in quotation marks. For example: "{}"''').format(
                               "C:\\some path with spaces" if iswindows else '/some path/with spaces') +'\n'
        if version is None:
            version = '%%prog (%s %s)'%(__appname__, get_version())
        optparse.OptionParser.__init__(self, usage=usage, version=version, epilog=epilog,
                               formatter=CustomHelpFormatter(),
                               conflict_handler=conflict_handler, **kwds)
        self.gui_mode = gui_mode
        if False:
            # Translatable string from optparse
            _("Options")
            _("show this help message and exit")
            _("show program's version number and exit")

    def print_usage(self, file=None):
        from calibre.utils.terminal import ANSIStream
        s = ANSIStream(file)
        optparse.OptionParser.print_usage(self, file=s)

    def print_help(self, file=None):
        from calibre.utils.terminal import ANSIStream
        s = ANSIStream(file)
        optparse.OptionParser.print_help(self, file=s)

    def print_version(self, file=None):
        from calibre.utils.terminal import ANSIStream
        s = ANSIStream(file)
        optparse.OptionParser.print_version(self, file=s)

    def error(self, msg):
        if self.gui_mode:
            raise Exception(msg)
        optparse.OptionParser.error(self, msg)

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
            if native_string_type(opt).strip():
                yield opt
        for gr in self.option_groups:
            for opt in gr.option_list:
                if native_string_type(opt).strip():
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
            if dest not in upper.__dict__:
                continue
            opt = self.option_by_dest(dest)
            if lower.__dict__[dest] != opt.default and \
               upper.__dict__[dest] == opt.default:
                upper.__dict__[dest] = lower.__dict__[dest]

    def add_option_group(self, *args, **kwargs):
        if isinstance(args[0], string_or_bytes):
            args = list(args)
            args[0] = native_string_type(args[0])
        return optparse.OptionParser.add_option_group(self, *args, **kwargs)


class DynamicConfig(dict):
    '''
    A replacement for QSettings that supports dynamic config keys.
    Returns `None` if a config key is not found. Note that the config
    data is stored in a JSON file.
    '''

    def __init__(self, name='dynamic'):
        dict.__init__(self, {})
        self.name = name
        self.defaults = {}
        self.refresh()

    @property
    def file_path(self):
        return os.path.join(config_dir, self.name+'.pickle.json')

    def decouple(self, prefix):
        self.name = prefix + self.name
        self.refresh()

    def read_old_serialized_representation(self):
        from calibre.utils.shared_file import share_open
        from calibre.utils.serialize import pickle_loads
        path = self.file_path.rpartition('.')[0]
        try:
            with share_open(path, 'rb') as f:
                raw = f.read()
        except EnvironmentError:
            raw = b''
        try:
            d = pickle_loads(raw).copy()
        except Exception:
            d = {}
        return d

    def refresh(self, clear_current=True):
        d = {}
        migrate = False
        if clear_current:
            self.clear()
        if os.path.exists(self.file_path):
            with ExclusiveFile(self.file_path) as f:
                raw = f.read()
            if raw:
                try:
                    d = json_loads(raw)
                except Exception as err:
                    print('Failed to de-serialize JSON representation of stored dynamic data for {} with error: {}'.format(
                        self.name, err))
            else:
                d = self.read_old_serialized_representation()
                migrate = bool(d)
        else:
            d = self.read_old_serialized_representation()
            migrate = bool(d)
        if migrate and d:
            raw = json_dumps(d, ignore_unserializable=True)
            with ExclusiveFile(self.file_path) as f:
                f.seek(0), f.truncate()
                f.write(raw)

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
        if not getattr(self, 'name', None):
            return
        if not os.path.exists(self.file_path):
            make_config_dir()
        raw = json_dumps(self)
        with ExclusiveFile(self.file_path) as f:
            f.seek(0)
            f.truncate()
            f.write(raw)


dynamic = DynamicConfig()


class XMLConfig(dict):

    '''
    Similar to :class:`DynamicConfig`, except that it uses an XML storage
    backend instead of a pickle file.

    See `https://docs.python.org/library/plistlib.html`_ for the supported
    data types.
    '''

    EXTENSION = '.plist'

    def __init__(self, rel_path_to_cf_file, base_path=config_dir):
        dict.__init__(self)
        self.no_commit = False
        self.defaults = {}
        self.file_path = os.path.join(base_path,
                *(rel_path_to_cf_file.split('/')))
        self.file_path = os.path.abspath(self.file_path)
        if not self.file_path.endswith(self.EXTENSION):
            self.file_path += self.EXTENSION

        self.refresh()

    def mtime(self):
        try:
            return os.path.getmtime(self.file_path)
        except EnvironmentError:
            return 0

    def touch(self):
        try:
            os.utime(self.file_path, None)
        except EnvironmentError:
            pass

    def raw_to_object(self, raw):
        from polyglot.plistlib import loads
        return loads(raw)

    def to_raw(self):
        from polyglot.plistlib import dumps
        return dumps(self)

    def decouple(self, prefix):
        self.file_path = os.path.join(os.path.dirname(self.file_path), prefix + os.path.basename(self.file_path))
        self.refresh()

    def refresh(self, clear_current=True):
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
        if clear_current:
            self.clear()
        self.update(d)

    def has_key(self, key):
        return dict.__contains__(self, key)

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

    def __delitem__(self, key):
        try:
            dict.__delitem__(self, key)
        except KeyError:
            pass  # ignore missing keys
        else:
            self.commit()

    def commit(self):
        if self.no_commit:
            return
        if hasattr(self, 'file_path') and self.file_path:
            dpath = os.path.dirname(self.file_path)
            if not os.path.exists(dpath):
                os.makedirs(dpath, mode=CONFIG_DIR_MODE)
            with ExclusiveFile(self.file_path) as f:
                raw = self.to_raw()
                f.seek(0)
                f.truncate()
                f.write(raw)

    def __enter__(self):
        self.no_commit = True

    def __exit__(self, *args):
        self.no_commit = False
        self.commit()


class JSONConfig(XMLConfig):

    EXTENSION = '.json'

    def raw_to_object(self, raw):
        return json_loads(raw)

    def to_raw(self):
        return json_dumps(self)

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


class DevicePrefs:

    def __init__(self, global_prefs):
        self.global_prefs = global_prefs
        self.overrides = {}

    def set_overrides(self, **kwargs):
        self.overrides = kwargs.copy()

    def __getitem__(self, key):
        return self.overrides.get(key, self.global_prefs[key])


device_prefs = DevicePrefs(prefs)
