#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, time, io, re
from zlib import decompressobj
from collections import OrderedDict
from threading import Thread

from calibre import prints
from calibre.constants import numeric_version, DEBUG
from calibre.gui2.store import StorePlugin
from calibre.utils.config import JSONConfig
from polyglot.urllib import urlencode
from polyglot.builtins import iteritems, itervalues, unicode_type


class VersionMismatch(ValueError):

    def __init__(self, ver):
        ValueError.__init__(self, 'calibre too old')
        self.ver = ver


def download_updates(ver_map={}, server='https://code.calibre-ebook.com'):
    from calibre.utils.https import get_https_resource_securely
    data = {k:unicode_type(v) for k, v in iteritems(ver_map)}
    data['ver'] = '1'
    url = '%s/stores?%s'%(server, urlencode(data))
    # We use a timeout here to ensure the non-daemonic update thread does not
    # cause calibre to hang indefinitely during shutdown
    raw = get_https_resource_securely(url, timeout=90.0)

    while raw:
        name, raw = raw.partition(b'\0')[0::2]
        name = name.decode('utf-8')
        d = decompressobj()
        src = d.decompress(raw)
        src = src.decode('utf-8').lstrip(u'\ufeff')
        # Python complains if there is a coding declaration in a unicode string
        src = re.sub(r'^#.*coding\s*[:=]\s*([-\w.]+)', '#', src, flags=re.MULTILINE)
        # Translate newlines to \n
        src = io.StringIO(src, newline=None).getvalue()
        yield name, src
        raw = d.unused_data


class Stores(OrderedDict):

    CHECK_INTERVAL = 24 * 60 * 60

    def builtins_loaded(self):
        self.last_check_time = 0
        self.version_map = {}
        self.cached_version_map = {}
        self.name_rmap = {}
        for key, val in iteritems(self):
            prefix, name = val.__module__.rpartition('.')[0::2]
            if prefix == 'calibre.gui2.store.stores' and name.endswith('_plugin'):
                module = sys.modules[val.__module__]
                sv = getattr(module, 'store_version', None)
                if sv is not None:
                    name = name.rpartition('_')[0]
                    self.version_map[name] = sv
                    self.name_rmap[name] = key
        self.cache_file = JSONConfig('store/plugin_cache')
        self.load_cache()

    def load_cache(self):
        # Load plugins from on disk cache
        remove = set()
        pat = re.compile(r'^store_version\s*=\s*(\d+)', re.M)
        for name, src in iteritems(self.cache_file):
            try:
                key = self.name_rmap[name]
            except KeyError:
                # Plugin has been disabled
                m = pat.search(src[:512])
                if m is not None:
                    try:
                        self.cached_version_map[name] = int(m.group(1))
                    except (TypeError, ValueError):
                        pass
                continue

            try:
                obj, ver = self.load_object(src, key)
            except VersionMismatch as e:
                self.cached_version_map[name] = e.ver
                continue
            except:
                import traceback
                prints('Failed to load cached store:', name)
                traceback.print_exc()
            else:
                if not self.replace_plugin(ver, name, obj, 'cached'):
                    # Builtin plugin is newer than cached
                    remove.add(name)

        if remove:
            with self.cache_file:
                for name in remove:
                    del self.cache_file[name]

    def check_for_updates(self):
        if hasattr(self, 'update_thread') and self.update_thread.is_alive():
            return
        if time.time() - self.last_check_time < self.CHECK_INTERVAL:
            return
        self.last_check_time = time.time()
        try:
            self.update_thread.start()
        except (RuntimeError, AttributeError):
            self.update_thread = Thread(target=self.do_update)
            self.update_thread.start()

    def join(self, timeout=None):
        hasattr(self, 'update_thread') and self.update_thread.join(timeout)

    def download_updates(self):
        ver_map = {name:max(ver, self.cached_version_map.get(name, -1))
            for name, ver in iteritems(self.version_map)}
        try:
            updates = download_updates(ver_map)
        except:
            import traceback
            traceback.print_exc()
        else:
            for name, code in updates:
                yield name, code

    def do_update(self):
        replacements = {}

        for name, src in self.download_updates():
            try:
                key = self.name_rmap[name]
            except KeyError:
                # Plugin has been disabled
                replacements[name] = src
                continue
            try:
                obj, ver = self.load_object(src, key)
            except VersionMismatch as e:
                self.cached_version_map[name] = e.ver
                replacements[name] = src
                continue
            except:
                import traceback
                prints('Failed to load downloaded store:', name)
                traceback.print_exc()
            else:
                if self.replace_plugin(ver, name, obj, 'downloaded'):
                    replacements[name] = src

        if replacements:
            with self.cache_file:
                for name, src in iteritems(replacements):
                    self.cache_file[name] = src

    def replace_plugin(self, ver, name, obj, source):
        if ver > self.version_map[name]:
            if DEBUG:
                prints('Loaded', source, 'store plugin for:',
                       self.name_rmap[name], 'at version:', ver)
            self[self.name_rmap[name]] = obj
            self.version_map[name] = ver
            return True
        return False

    def load_object(self, src, key):
        namespace = {}
        builtin = self[key]
        exec(src, namespace)
        ver = namespace['store_version']
        cls = None
        for x in itervalues(namespace):
            if (isinstance(x, type) and issubclass(x, StorePlugin) and x is not
                StorePlugin):
                cls = x
                break
        if cls is None:
            raise ValueError('No store plugin found')
        if cls.minimum_calibre_version > numeric_version:
            raise VersionMismatch(ver)
        return cls(builtin.gui, builtin.name, config=builtin.config,
                   base_plugin=builtin.base_plugin), ver


if __name__ == '__main__':
    st = time.time()
    count = 0
    for name, code in download_updates():
        count += 1
        print(name)
        print(code.encode('utf-8'))
        print('\n', '_'*80, '\n', sep='')
    print('Time to download all %d plugins: %.2f seconds'%(count, time.time() - st))
