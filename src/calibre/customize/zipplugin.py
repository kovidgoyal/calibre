#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from future_builtins import map

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, zipfile, posixpath, importlib, threading, re, imp, sys
from collections import OrderedDict

from calibre.customize import (Plugin, numeric_version, platform,
        InvalidPlugin, PluginNotFound)

# PEP 302 based plugin loading mechanism, works around the bug in zipimport in
# python 2.x that prevents importing from zip files in locations whose paths
# have non ASCII characters


class PluginLoader(object):

    def __init__(self):
        self.loaded_plugins = {}
        self._lock = threading.RLock()
        self._identifier_pat = re.compile(r'[a-zA-Z][_0-9a-zA-Z]*')

    def _get_actual_fullname(self, fullname):
        parts = fullname.split('.')
        if parts[0] == 'calibre_plugins':
            if len(parts) == 1:
                return parts[0], None
            plugin_name = parts[1]
            with self._lock:
                names = self.loaded_plugins.get(plugin_name, None)[1]
                if names is None:
                    raise ImportError('No plugin named %r loaded'%plugin_name)
                fullname = '.'.join(parts[2:])
                if not fullname:
                    fullname = '__init__'
                if fullname in names:
                    return fullname, plugin_name
                if fullname+'.__init__' in names:
                    return fullname+'.__init__', plugin_name
        return None, None

    def find_module(self, fullname, path=None):
        fullname, plugin_name = self._get_actual_fullname(fullname)
        if fullname is None and plugin_name is None:
            return None
        return self

    def load_module(self, fullname):
        import_name, plugin_name = self._get_actual_fullname(fullname)
        if import_name is None and plugin_name is None:
            raise ImportError('No plugin named %r is loaded'%fullname)
        mod = sys.modules.setdefault(fullname, imp.new_module(fullname))
        mod.__file__ = "<calibre Plugin Loader>"
        mod.__loader__ = self

        if import_name.endswith('.__init__') or import_name in ('__init__',
                'calibre_plugins'):
            # We have a package
            mod.__path__ = []

        if plugin_name is not None:
            # We have some actual code to load
            with self._lock:
                zfp, names = self.loaded_plugins.get(plugin_name, (None, None))
            if names is None:
                raise ImportError('No plugin named %r loaded'%plugin_name)
            zinfo = names.get(import_name, None)
            if zinfo is None:
                raise ImportError('Plugin %r has no module named %r' %
                        (plugin_name, import_name))
            with zipfile.ZipFile(zfp) as zf:
                code = zf.read(zinfo)
            compiled = compile(code, 'import_name', 'exec', dont_inherit=True)
            exec compiled in mod.__dict__

        return mod


    def load(self, path_to_zip_file):
        if not os.access(path_to_zip_file, os.R_OK):
            raise PluginNotFound('Cannot access %r'%path_to_zip_file)

        with zipfile.ZipFile(path_to_zip_file) as zf:
            plugin_name = self._locate_code(zf, path_to_zip_file)

        try:
            ans = None
            m = importlib.import_module(
                    'calibre_plugins.%s'%plugin_name)
            for obj in m.__dict__.itervalues():
                if isinstance(obj, type) and issubclass(obj, Plugin) and \
                        obj.name != 'Trivial Plugin':
                    ans = obj
                    break
            if ans is None:
                raise InvalidPlugin('No plugin class found in %r:%r'%(
                    path_to_zip_file, plugin_name))

            if ans.minimum_calibre_version > numeric_version:
                raise InvalidPlugin(
                    'The plugin at %r needs a version of calibre >= %r' %
                    (path_to_zip_file, '.'.join(map(str,
                        ans.minimum_calibre_version))))

            if platform not in ans.supported_platforms:
                raise InvalidPlugin(
                    'The plugin at %r cannot be used on %s' %
                    (path_to_zip_file, platform))

            return ans
        except:
            with self._lock:
                del self.loaded_plugins[plugin_name]
            raise


    def _locate_code(self, zf, path_to_zip_file):
        names = [x if isinstance(x, unicode) else x.decode('utf-8') for x in
                zf.namelist()]
        names = [x[1:] if x[0] == '/' else x for x in names]

        plugin_name = None
        for name in names:
            name, ext = posixpath.splitext(name)
            if name.startswith('plugin-import-name-') and ext == '.txt':
                plugin_name = name.rpartition('-')[-1]

        if plugin_name is None:
            c = 0
            while True:
                c += 1
                plugin_name = 'dummy%d'%c
                if plugin_name not in self.loaded_plugins:
                    break
        else:
            if plugin_name in self.loaded_plugins:
                raise InvalidPlugin((
                    'The plugin in %r uses an import name %r that is already'
                    ' used by another plugin') % (path_to_zip_file, plugin_name))
            if self._identifier_pat.match(plugin_name) is None:
                raise InvalidPlugin((
                    'The plugin at %r uses an invalid import name: %r' %
                    (path_to_zip_file, plugin_name)))

        pynames = [x for x in names if x.endswith('.py')]

        candidates = [posixpath.dirname(x) for x in pynames if
                x.endswith('/__init__.py')]
        candidates.sort(key=lambda x: x.count('/'))
        valid_packages = set()

        for candidate in candidates:
            parts = candidate.split('/')
            parent = '.'.join(parts[:-1])
            if parent and parent not in valid_packages:
                continue
            valid_packages.add('.'.join(parts))

        names = OrderedDict()

        for candidate in pynames:
            parts = posixpath.splitext(candidate)[0].split('/')
            package = '.'.join(parts[:-1])
            if package and package not in valid_packages:
                continue
            name = '.'.join(parts)
            names[name] = zf.getinfo(candidate)

        # Legacy plugins
        if '__init__' not in names:
            for name in list(names.iterkeys()):
                if '.' not in name and name.endswith('plugin'):
                    names['__init__'] = names[name]
                    break

        if '__init__' not in names:
            raise InvalidPlugin(('The plugin in %r is invalid. It does not '
                    'contain a top-level __init__.py file')
                    % path_to_zip_file)

        with self._lock:
            self.loaded_plugins[plugin_name] = (path_to_zip_file, names)

        return plugin_name


loader = PluginLoader()
sys.meta_path.insert(0, loader)


