# License: GPLv3 Copyright: 2008, Kovid Goyal kovid@kovidgoyal.net

"""
Manage application-wide preferences.
"""

import optparse
import os
from collections.abc import Iterable, Iterator
from copy import deepcopy
from types import TracebackType
from typing import TYPE_CHECKING, Any, NoReturn

from calibre.constants import CONFIG_DIR_MODE, __appname__, __author__, config_dir, get_version, iswindows
from calibre.utils.config_base import (  # ruff: ignore[unused-import]
    Config,
    ConfigInterface,
    ConfigProxy,
    Option,
    OptionSet,
    OptionValues,
    StringConfig,
    commit_data,
    from_json,
    json_dumps,
    json_loads,
    make_config_dir,
    plugin_dir,
    prefs,
    read_data,
    to_json,
    tweaks,
)
from calibre.utils.localization import _

if TYPE_CHECKING:
    from _typeshed import SupportsWrite

# optparse uses gettext.gettext instead of _ from builtins, so we
# monkey patch it.
setattr(optparse, '_', _)


def check_config_write_access() -> bool:
    return os.access(config_dir, os.W_OK) and os.access(config_dir, os.X_OK)


class CustomHelpFormatter(optparse.IndentedHelpFormatter):
    def format_usage(self, usage: str) -> str:
        from calibre.utils.terminal import colored

        parts = usage.split(' ')
        if parts:
            parts[0] = colored(parts[0], fg='yellow', bold=True)
        usage = ' '.join(parts)
        return colored(_('Usage'), fg='blue', bold=True) + ': ' + usage

    def format_heading(self, heading: str) -> str:
        from calibre.utils.terminal import colored

        return ' ' * self.current_indent + '{}:\n'.format(colored(heading, fg='blue', bold=True))

    def format_option(self, option: optparse.Option) -> str:
        import textwrap

        from calibre.utils.terminal import colored

        result = []
        opts = self.option_strings[option]
        opt_width = self.help_position - self.current_indent - 2
        if len(opts) > opt_width:
            opts = ' ' * self.current_indent + '{}\n'.format(colored(opts, fg='green'))
            indent_first = self.help_position
        else:  # start help on same line as opts
            opts = ' ' * self.current_indent + '%-*s  ' % (  # ruff: ignore[printf-string-formatting]
                opt_width + len(colored('', fg='green')),
                colored(opts, fg='green'),
            )
            indent_first = 0
        result.append(opts)
        if option.help:
            help_text = self.expand_default(option).split('\n')
            help_lines = []

            for line in help_text:
                help_lines.extend(textwrap.wrap(line, self.help_width))
            result.append(' ' * indent_first + f'{help_lines[0]}\n')
            result.extend(' ' * self.help_position + f'{line}\n' for line in help_lines[1:])
        elif opts[-1] != '\n':
            result.append('\n')
        return ''.join(result) + '\n'


class OptionParser(optparse.OptionParser):
    def __init__(
        self,
        usage: str = '%prog [options] filename',
        version: str | None = None,
        epilog: str | None = None,
        gui_mode: bool = False,
        conflict_handler: str = 'resolve',
        **kwds: Any,  # ruff: ignore[any-type]
    ) -> None:
        import textwrap

        from calibre.utils.terminal import colored

        usage = textwrap.dedent(usage)
        if epilog is None:
            epilog = _('Created by ') + colored(__author__, fg='cyan')
        usage += (
            '\n\n'
            + _(
                '''Whenever you pass arguments to %prog that have spaces in them, '''
                '''enclose the arguments in quotation marks. For example: "{}"'''
            ).format('C:\\some path with spaces' if iswindows else '/some path/with spaces')
            + '\n'
        )
        if version is None:
            version = f'%prog ({__appname__} {get_version()})'
        optparse.OptionParser.__init__(
            self,
            usage=usage,
            version=version,
            epilog=epilog,
            formatter=CustomHelpFormatter(),
            conflict_handler=conflict_handler,
            **kwds,
        )
        self.gui_mode = gui_mode
        if False:
            # Translatable string from optparse
            _('Options')
            _('show this help message and exit')
            _("show program's version number and exit")

    def print_usage(self, file: SupportsWrite[str] | None = None) -> None:
        from calibre.utils.terminal import ANSIStream

        s = ANSIStream(file)  # ty: ignore[invalid-argument-type]
        optparse.OptionParser.print_usage(self, file=s)

    def print_help(self, file: SupportsWrite[str] | None = None) -> None:
        from calibre.utils.terminal import ANSIStream

        s = ANSIStream(file)  # ty: ignore[invalid-argument-type]
        optparse.OptionParser.print_help(self, file=s)

    def print_version(self, file: SupportsWrite[str] | None = None) -> None:
        from calibre.utils.terminal import ANSIStream

        s = ANSIStream(file)  # ty: ignore[invalid-argument-type]
        optparse.OptionParser.print_version(self, file=s)

    def error(self, msg: str) -> NoReturn:
        if self.gui_mode:
            raise Exception(msg)
        optparse.OptionParser.error(self, msg)

    def merge(self, parser: optparse.OptionParser) -> None:
        """
        Add options from parser to self. In case of conflicts, conflicting options from
        parser are skipped.
        """
        opts = list(parser.option_list)
        groups = list(parser.option_groups)

        def merge_options(options: Iterable[optparse.Option], container: optparse.OptionContainer) -> None:
            for opt in deepcopy(options):
                if not self.has_option(opt.get_opt_string()):
                    container.add_option(opt)

        merge_options(opts, self)

        for group in groups:
            g = self.add_option_group(group.title)
            merge_options(group.option_list, g)

    def subsume(self, group_name: str, msg: str = '') -> None:
        """
        Move all existing options into a subgroup named
        C{group_name} with description C{msg}.
        """
        opts = [opt for opt in self.options_iter() if opt.get_opt_string() not in ('--version', '--help')]
        self.option_groups = []
        subgroup = self.add_option_group(group_name, msg)
        for opt in opts:
            self.remove_option(opt.get_opt_string())
            subgroup.add_option(opt)

    def options_iter(self) -> Iterator[optparse.Option]:
        for opt in self.option_list:
            if str(opt).strip():
                yield opt
        for gr in self.option_groups:
            for opt in gr.option_list:
                if str(opt).strip():
                    yield opt

    def option_by_dest(self, dest: str) -> optparse.Option | None:
        for opt in self.options_iter():
            if opt.dest == dest:
                return opt

    def merge_options(self, lower: optparse.Values, upper: optparse.Values) -> None:
        """
        Merge options in lower and upper option lists into upper.
        Default values in upper are overridden by
        non default values in lower.
        """
        for dest in lower.__dict__.keys():
            if dest not in upper.__dict__:
                continue
            opt = self.option_by_dest(dest)
            if lower.__dict__[dest] != opt.default and upper.__dict__[dest] == opt.default:  # ty: ignore[unresolved-attribute]
                upper.__dict__[dest] = lower.__dict__[dest]

    def add_option_group(self, *args: Any, **kwargs: Any) -> optparse.OptionGroup:  # ruff: ignore[any-type]
        if isinstance(args[0], (str, bytes)):
            args = list(args)  # ty: ignore[invalid-assignment]
            args[0] = str(args[0])  # ty: ignore[invalid-assignment]
        return optparse.OptionParser.add_option_group(self, *args, **kwargs)


class DynamicConfig(dict):
    """
    A replacement for QSettings that supports dynamic config keys.
    Returns `None` if a config key is not found. Note that the config
    data is stored in a JSON file.
    """

    def __init__(self, name: str = 'dynamic') -> None:
        dict.__init__(self, {})
        self.name = name
        self.defaults: dict[str, Any] = {}
        self.refresh()

    @property
    def file_path(self) -> str:
        return os.path.join(config_dir, self.name + '.pickle.json')

    def decouple(self, prefix: str) -> None:
        self.name = prefix + self.name
        self.refresh()

    def read_old_serialized_representation(self) -> dict[str, Any]:
        from calibre.utils.serialize import pickle_loads
        from calibre.utils.shared_file import share_open

        path = self.file_path.rpartition('.')[0]
        try:
            with share_open(path, 'rb') as f:
                raw = f.read()
        except OSError:
            raw = b''
        try:
            d = pickle_loads(raw).copy()
        except Exception:
            d = {}
        return d

    def refresh(self, clear_current: bool = True) -> None:
        d = {}
        migrate = False
        if clear_current:
            self.clear()
        try:
            raw = read_data(self.file_path)
        except FileNotFoundError:
            d = self.read_old_serialized_representation()
            migrate = bool(d)
        else:
            if raw:
                try:
                    d = json_loads(raw)
                except Exception as err:
                    print(f'Failed to de-serialize JSON representation of stored dynamic data for {self.name} with error: {err}')
            else:
                d = self.read_old_serialized_representation()
                migrate = bool(d)
        if migrate and d:
            raw = json_dumps(d, ignore_unserializable=True)
            commit_data(self.file_path, raw)

        self.update(d)

    def __getitem__(self, key: str) -> Any:  # ruff: ignore[any-type]
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults.get(key, None)

    def get(self, key: object, default: Any = None) -> Any:  # ruff: ignore[any-type]
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults.get(key, default)

    def __setitem__(self, key: str, val: object) -> None:
        dict.__setitem__(self, key, val)
        self.commit()

    def set(self, key: str, val: object) -> None:
        self.__setitem__(key, val)

    def commit(self) -> None:
        if not getattr(self, 'name', None):
            return
        raw = json_dumps(self)
        commit_data(self.file_path, raw)


dynamic = DynamicConfig()


class XMLConfig(dict):
    """
    Similar to :class:`DynamicConfig`, except that it uses an XML storage
    backend instead of a pickle file.

    See `https://docs.python.org/library/plistlib.html`_ for the supported
    data types.
    """

    EXTENSION = '.plist'

    def __init__(self, rel_path_to_cf_file: str, base_path: str = config_dir, permissions: int = 0o666) -> None:
        dict.__init__(self)
        self.file_permissions = permissions
        self.no_commit = False
        self.defaults: dict[str, Any] = {}
        self.file_path = os.path.join(base_path, *(rel_path_to_cf_file.split('/')))
        self.file_path = os.path.abspath(self.file_path)
        if not self.file_path.endswith(self.EXTENSION):
            self.file_path += self.EXTENSION

        self.refresh()

    def mtime(self) -> float:
        try:
            return os.path.getmtime(self.file_path)
        except OSError:
            return 0

    def touch(self) -> None:
        try:
            os.utime(self.file_path, None)
        except OSError:
            pass

    def raw_to_object(self, raw: bytes) -> Any:  # ruff: ignore[any-type]
        from plistlib import loads

        return loads(raw)

    def to_raw(self) -> bytes:
        from plistlib import dumps

        return dumps(self)

    def decouple(self, prefix: str) -> None:
        self.file_path = os.path.join(os.path.dirname(self.file_path), prefix + os.path.basename(self.file_path))
        self.refresh()

    def refresh(self, clear_current: bool = True) -> None:
        d = {}
        try:
            raw = read_data(self.file_path)
        except FileNotFoundError:
            pass
        else:
            try:
                d = self.raw_to_object(raw) if raw.strip() else {}
            except SystemError:
                pass
            except Exception:
                import traceback

                traceback.print_exc()
                d = {}
        if clear_current:
            self.clear()
        self.update(d)

    def has_key(self, key: str) -> bool:
        return dict.__contains__(self, key)

    def __getitem__(self, key: str) -> Any:  # ruff: ignore[any-type]
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults.get(key, None)

    def get(self, key: object, default: Any = None) -> Any:  # ruff: ignore[any-type]
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults.get(key, default)

    def __setitem__(self, key: str, val: object) -> None:
        dict.__setitem__(self, key, val)
        self.commit()

    def set(self, key: str, val: object) -> None:
        self.__setitem__(key, val)

    def __delitem__(self, key: str) -> None:
        try:
            dict.__delitem__(self, key)
        except KeyError:
            pass  # ignore missing keys
        else:
            self.commit()

    def commit(self) -> None:
        if self.no_commit:
            return
        if path := getattr(self, 'file_path', None):
            os.makedirs(os.path.dirname(path), exist_ok=True, mode=CONFIG_DIR_MODE)
            commit_data(path, self.to_raw(), self.file_permissions)

    def __enter__(self) -> None:
        self.no_commit = True

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> bool | None:
        self.no_commit = False
        self.commit()


class JSONConfig(XMLConfig):
    EXTENSION = '.json'

    def raw_to_object(self, raw: bytes) -> Any:  # ruff: ignore[any-type]
        return json_loads(raw)

    def to_raw(self) -> bytes:
        return json_dumps(self)

    def __getitem__(self, key: str) -> Any:  # ruff: ignore[any-type]
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults[key]

    def get(self, key: object, default: Any = None) -> Any:  # ruff: ignore[any-type]
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return self.defaults.get(key, default)

    def __setitem__(self, key: str, val: object) -> None:
        dict.__setitem__(self, key, val)
        self.commit()


class DevicePrefs:
    def __init__(self, global_prefs: ConfigProxy) -> None:
        self.global_prefs = global_prefs
        self.overrides: dict[str, Any] = {}

    def set_overrides(self, **kwargs: object) -> None:
        self.overrides = kwargs.copy()

    def __getitem__(self, key: str) -> Any:  # ruff: ignore[any-type]
        return self.overrides.get(key, self.global_prefs[key])


device_prefs = DevicePrefs(prefs)
