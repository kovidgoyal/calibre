#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import ctypes, ctypes.wintypes as types, struct, datetime, numbers

from calibre_extensions import winutil

try:
    import winreg
except ImportError:
    import _winreg as winreg


# Binding to C library {{{
advapi32 = ctypes.windll.advapi32
HKEY = types.HKEY
PHKEY = ctypes.POINTER(HKEY)
DWORD = types.DWORD
BYTE = types.BYTE
LONG = types.LONG
ULONG = types.ULONG
LPDWORD = ctypes.POINTER(DWORD)
LPBYTE = ctypes.POINTER(BYTE)
LPCWSTR = types.LPCWSTR
LPWSTR = types.LPWSTR
LPCVOID = types.LPCVOID

HKEY_CURRENT_USER  = HKCU = HKEY(ULONG(winreg.HKEY_CURRENT_USER).value)
HKEY_CLASSES_ROOT  = HKCR = HKEY(ULONG(winreg.HKEY_CLASSES_ROOT).value)
HKEY_LOCAL_MACHINE = HKLM = HKEY(ULONG(winreg.HKEY_LOCAL_MACHINE).value)
KEY_READ = winreg.KEY_READ
KEY_ALL_ACCESS = winreg.KEY_ALL_ACCESS
RRF_RT_ANY = 0x0000ffff
RRF_NOEXPAND = 0x10000000
RRF_ZEROONFAILURE = 0x20000000


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", DWORD), ("dwHighDateTime", DWORD)]


def default_errcheck(result, func, args):
    if result != getattr(winutil, 'ERROR_SUCCESS', 0):  # On shutdown winutil becomes None
        raise ctypes.WinError(result)
    return args


null = object()


class a:

    def __init__(self, name, typ, default=null, in_arg=True):
        self.typ = typ
        if default is null:
            self.spec = ((1 if in_arg else 2), name)
        else:
            self.spec = ((1 if in_arg else 2), name, default)


def cwrap(name, restype, *args, **kw):
    params = (restype,) + tuple(x.typ for x in args)
    paramflags = tuple(x.spec for x in args)
    func = ctypes.WINFUNCTYPE(*params)((name, kw.get('lib', advapi32)), paramflags)
    func.errcheck = kw.get('errcheck', default_errcheck)
    return func


RegOpenKey = cwrap(
    'RegOpenKeyExW', LONG, a('key', HKEY), a('sub_key', LPCWSTR), a('options', DWORD, 0), a('access', ULONG, KEY_READ), a('result', PHKEY, in_arg=False))
RegCreateKey = cwrap(
    'RegCreateKeyExW', LONG, a('key', HKEY), a('sub_key', LPCWSTR, ''), a('reserved', DWORD, 0), a('cls', LPWSTR, None), a('options', DWORD, 0),
    a('access', ULONG, KEY_ALL_ACCESS), a('security', ctypes.c_void_p, 0), a('result', PHKEY, in_arg=False), a('disposition', LPDWORD, in_arg=False))
RegCloseKey = cwrap('RegCloseKey', LONG, a('key', HKEY))


def enum_value_errcheck(result, func, args):
    if result == winutil.ERROR_SUCCESS:
        return args
    if result == winutil.ERROR_MORE_DATA:
        raise ValueError('buffer too small')
    if result == winutil.ERROR_NO_MORE_ITEMS:
        raise StopIteration()
    raise ctypes.WinError(result)


RegEnumValue = cwrap(
    'RegEnumValueW', LONG, a('key', HKEY), a('index', DWORD), a('value_name', LPWSTR), a('value_name_size', LPDWORD), a('reserved', LPDWORD),
    a('value_type', LPDWORD), a('data', LPBYTE), a('data_size', LPDWORD), errcheck=enum_value_errcheck)


def last_error_errcheck(result, func, args):
    if result == 0:
        raise ctypes.WinError()
    return args


ExpandEnvironmentStrings = cwrap(
    'ExpandEnvironmentStringsW', DWORD, a('src', LPCWSTR), a('dest', LPWSTR), a('size', DWORD), errcheck=last_error_errcheck, lib=ctypes.windll.kernel32)


def expand_environment_strings(src):
    buf = ctypes.create_unicode_buffer(32 * 1024)
    ExpandEnvironmentStrings(src, buf, len(buf))
    return buf.value


def convert_to_registry_data(value, has_expansions=False):
    if value is None:
        return None, winreg.REG_NONE, 0
    if isinstance(value, (str, bytes)):
        buf = ctypes.create_unicode_buffer(value)
        return buf, (winreg.REG_EXPAND_SZ if has_expansions else winreg.REG_SZ), len(buf) * 2
    if isinstance(value, (list, tuple)):
        buf = ctypes.create_unicode_buffer('\0'.join(map(str, value)) + '\0\0')
        return buf, winreg.REG_MULTI_SZ, len(buf) * 2
    if isinstance(value, numbers.Integral):
        try:
            raw, dtype = struct.pack('L', value), winreg.REG_DWORD
        except struct.error:
            raw = struct.pack('Q', value), winutil.REG_QWORD
        buf = ctypes.create_string_buffer(raw)
        return buf, dtype, len(buf)
    if isinstance(value, bytes):
        buf = ctypes.create_string_buffer(value)
        return buf, winreg.REG_BINARY, len(buf)
    raise ValueError('Unknown data type: %r' % value)


def convert_registry_data(raw, size, dtype):
    if dtype == winreg.REG_NONE:
        return None
    if dtype == winreg.REG_BINARY:
        return ctypes.string_at(raw, size)
    if dtype in (winreg.REG_SZ, winreg.REG_EXPAND_SZ, winreg.REG_MULTI_SZ):
        ans = ctypes.wstring_at(raw, size // 2).rstrip('\0')
        if dtype == winreg.REG_MULTI_SZ:
            ans = tuple(ans.split('\0'))
        elif dtype == winreg.REG_EXPAND_SZ:
            ans = expand_environment_strings(ans)
        return ans
    if dtype == winreg.REG_DWORD:
        if size == 0:
            return 0
        return ctypes.cast(raw, LPDWORD).contents.value
    if dtype == winutil.REG_QWORD:
        if size == 0:
            return 0
        return ctypes.cast(raw, ctypes.POINTER(ctypes.c_uint64)).contents.value
    raise ValueError('Unsupported data type: %r' % dtype)


try:
    RegSetKeyValue = cwrap(
        'RegSetKeyValueW', LONG, a('key', HKEY), a('sub_key', LPCWSTR, None), a('name', LPCWSTR, None),
        a('dtype', DWORD, winreg.REG_SZ), a('data', LPCVOID, None), a('size', DWORD))
except Exception:
    raise RuntimeError('calibre requires Windows Vista or newer to run, the last version of calibre'
                       ' that could run on Windows XP is version 1.48, available from: http://download.calibre-ebook.com/')


def delete_value_errcheck(result, func, args):
    if result == winutil.ERROR_FILE_NOT_FOUND:
        return args
    if result != 0:
        raise ctypes.WinError(result)
    return args


RegDeleteKeyValue = cwrap(
    'RegDeleteKeyValueW', LONG, a('key', HKEY), a('sub_key', LPCWSTR, None), a('name', LPCWSTR, None), errcheck=delete_value_errcheck)
RegDeleteTree = cwrap(
    'RegDeleteTreeW', LONG, a('key', HKEY), a('sub_key', LPCWSTR, None), errcheck=delete_value_errcheck)
RegEnumKeyEx = cwrap(
    'RegEnumKeyExW', LONG, a('key', HKEY), a('index', DWORD), a('name', LPWSTR), a('name_size', LPDWORD), a('reserved', LPDWORD, None),
    a('cls', LPWSTR, None), a('cls_size', LPDWORD, None), a('last_write_time', ctypes.POINTER(FILETIME), in_arg=False),
    errcheck=enum_value_errcheck)


def get_value_errcheck(result, func, args):
    if result == winutil.ERROR_SUCCESS:
        return args
    if result == winutil.ERROR_MORE_DATA:
        raise ValueError('buffer too small')
    if result == winutil.ERROR_FILE_NOT_FOUND:
        raise KeyError('No such value found')
    raise ctypes.WinError(result)


RegGetValue = cwrap(
    'RegGetValueW', LONG, a('key', HKEY), a('sub_key', LPCWSTR, None), a('value_name', LPCWSTR, None), a('flags', DWORD, RRF_RT_ANY),
    a('data_type', LPDWORD, 0), a('data', ctypes.c_void_p, 0), a('size', LPDWORD, 0), errcheck=get_value_errcheck
)
RegLoadMUIString = cwrap(
    'RegLoadMUIStringW', LONG, a('key', HKEY), a('value_name', LPCWSTR, None), a('data', LPWSTR, None), a('buf_size', DWORD, 0),
    a('size', LPDWORD, 0), a('flags', DWORD, 0), a('directory', LPCWSTR, None), errcheck=get_value_errcheck
)


def filetime_to_datettime(ft):
    timestamp = ft.dwHighDateTime
    timestamp <<= 32
    timestamp |= ft.dwLowDateTime
    return datetime.datetime(1601, 1, 1, 0, 0, 0) + datetime.timedelta(microseconds=timestamp/10)

# }}}


class Key:

    def __init__(self, create_at=None, open_at=None, root=HKEY_CURRENT_USER, open_mode=KEY_READ):
        root = getattr(root, 'hkey', root)
        self.was_created = False
        if create_at is not None:
            self.hkey, self.was_created = RegCreateKey(root, create_at)
        elif open_at is not None:
            self.hkey = RegOpenKey(root, open_at, 0, open_mode)
        else:
            self.hkey = HKEY()

    def get(self, value_name=None, default=None, sub_key=None):
        data_buf = ctypes.create_string_buffer(1024)
        len_data_buf = DWORD(len(data_buf))
        data_type = DWORD(0)
        while True:
            len_data_buf.value = len(data_buf)
            try:
                RegGetValue(self.hkey, sub_key, value_name, RRF_RT_ANY | RRF_NOEXPAND | RRF_ZEROONFAILURE,
                            ctypes.byref(data_type), data_buf, len_data_buf)
                break
            except ValueError:
                data_buf = ctypes.create_string_buffer(2 * len(data_buf))
            except KeyError:
                return default
        return convert_registry_data(data_buf, len_data_buf.value, data_type.value)

    def get_mui_string(self, value_name=None, default=None, directory=None, fallback=True):
        data_buf = ctypes.create_unicode_buffer(1024)
        len_data_buf = DWORD(len(data_buf))
        size = DWORD(0)
        while True:
            len_data_buf.value = len(data_buf)
            try:
                RegLoadMUIString(self.hkey, value_name, data_buf, 2 * len(data_buf), ctypes.byref(size), 0, directory)
                break
            except ValueError:
                data_buf = ctypes.create_unicode_buffer(max(2 * len(data_buf), size.value // 2))
            except KeyError:
                return default
            except OSError as err:
                if fallback and err.winerror in (winutil.ERROR_BAD_COMMAND, winutil.ERROR_INVALID_DATA):
                    return self.get(value_name=value_name, default=default)
                raise
        return data_buf.value

    def iterkeynames(self, get_last_write_times=False):
        ' Iterate over the names of all keys in this key '
        name_buf = ctypes.create_unicode_buffer(1024)
        lname_buf = DWORD(len(name_buf))
        i = 0
        while True:
            lname_buf.value = len(name_buf)
            try:
                file_time = RegEnumKeyEx(self.hkey, i, name_buf, ctypes.byref(lname_buf))
            except ValueError:
                raise RuntimeError('Enumerating keys failed with buffer too small, which should never happen')
            except StopIteration:
                break
            if get_last_write_times:
                yield name_buf.value[:lname_buf.value], filetime_to_datettime(file_time)
            else:
                yield name_buf.value[:lname_buf.value]
            i += 1

    def delete_value(self, name=None, sub_key=None):
        ' Delete the named value from this key. If name is None the default value is deleted. If name does not exist, not error is reported. '
        RegDeleteKeyValue(self.hkey, sub_key, name)

    def delete_tree(self, sub_key=None):
        ''' Delete this all children of this key. Note that a key is not
        actually deleted till the last handle to it is closed. Also if you
        specify a sub_key, then the sub-key is deleted completely. If sub_key
        does not exist, no error is reported.'''
        RegDeleteTree(self.hkey, sub_key)

    def set(self, name=None, value=None, sub_key=None, has_expansions=False):
        ''' Set a value for this key (with optional sub-key). If name is None,
        the Default value is set. value can be an integer, a string, bytes or a list
        of strings. If you want to use expansions, set has_expansions=True. '''
        value, dtype, size = convert_to_registry_data(value, has_expansions=has_expansions)
        RegSetKeyValue(self.hkey, sub_key, name, dtype, value, size)

    def set_default_value(self, sub_key=None, value=None, has_expansions=False):
        self.set(sub_key=sub_key, value=value, has_expansions=has_expansions)

    def sub_key(self, path, allow_create=True, open_mode=KEY_READ):
        ' Create (or open) a sub-key at the specified relative path. When opening instead of creating, use open_mode '
        if allow_create:
            return Key(create_at=path, root=self.hkey)
        return Key(open_at=path, root=self.hkey)

    def itervalues(self, get_data=False, sub_key=None):
        '''Iterate over all values in this key (or optionally the specified
        sub-key. If get_data is True also return the data for every value,
        otherwise, just the name.'''
        key = self.hkey
        if sub_key is not None:
            try:
                key = RegOpenKey(key, sub_key)
            except OSError:
                return
        try:
            name_buf = ctypes.create_unicode_buffer(16385)
            lname_buf = DWORD(len(name_buf))
            if get_data:
                data_buf = (BYTE * 1024)()
                ldata_buf = DWORD(len(data_buf))
                vtype = DWORD(0)
            i = 0
            while True:
                lname_buf.value = len(name_buf)
                if get_data:
                    ldata_buf.value = len(data_buf)
                    try:
                        RegEnumValue(
                            key, i, name_buf, ctypes.byref(lname_buf), None, ctypes.byref(vtype), data_buf, ctypes.byref(ldata_buf))
                    except ValueError:
                        data_buf = (BYTE * ldata_buf.value)()
                        continue
                    except StopIteration:
                        break
                    data = convert_registry_data(data_buf, ldata_buf.value, vtype.value)
                    yield name_buf.value[:lname_buf.value], data
                else:
                    try:
                        RegEnumValue(
                            key, i, name_buf, ctypes.byref(lname_buf), None, None, None, None)
                    except StopIteration:
                        break
                    yield name_buf.value[:lname_buf.value]

                i += 1
        finally:
            if sub_key is not None:
                RegCloseKey(key)
    values = itervalues

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __nonzero__(self):
        return bool(self.hkey)

    def close(self):
        if not getattr(self, 'hkey', None):
            return
        if RegCloseKey is None or HKEY is None:
            return  # globals become None during exit
        RegCloseKey(self.hkey)
        self.hkey = HKEY()

    def __del__(self):
        self.close()


if __name__ == '__main__':
    from pprint import pprint
    k = Key(open_at=r'Software\RegisteredApplications', root=HKLM)
    pprint(tuple(k.values(get_data=True)))
    k = Key(r'Software\calibre\winregtest')
    k.set('Moose.Cat.1')
    k.set('unicode test', 'fällen粗楷体简a\U0001f471')
    k.set('none test')
    k.set_default_value(r'other\key', '%PATH%', has_expansions=True)
    pprint(tuple(k.values(get_data=True)))
    pprint(k.get('unicode test'))
    k.set_default_value(r'delete\me\please', 'xxx')
    pprint(tuple(k.iterkeynames(get_last_write_times=True)))
    k.delete_tree('delete')
    pprint(tuple(k.iterkeynames(get_last_write_times=True)))
