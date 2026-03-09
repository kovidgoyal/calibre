#!/usr/bin/env python
__license__ = 'GPL v3'
__copyright__ = '2024, Kovid Goyal <kovid at kovidgoyal.net>'

import importlib.util
import os
import threading
import traceback

from calibre import prints
from calibre.ebooks.metadata.sources.base import Source


def get_script_sources_dir():
    '''Return the directory where user metadata source scripts are stored.'''
    from calibre.utils.config import config_dir
    return os.path.join(config_dir, 'metadata_sources')


class ScriptSource(Source):
    '''Wrapper that adapts a simple Python script into a full calibre Source plugin.

    A minimal user script looks like::

        name = 'My Custom Source'
        version = (1, 0, 0)
        description = 'My custom metadata source'
        capabilities = frozenset({'identify'})
        touched_fields = frozenset({'title', 'authors', 'comments'})

        def identify(title=None, authors=None, identifiers=None, timeout=30):
            from calibre.ebooks.metadata.book.base import Metadata
            results = []
            # ... fetch metadata ...
            return results
    '''

    name = 'Script Source'
    version = (1, 0, 0)
    description = _('A script-based metadata source')
    capabilities = frozenset()
    touched_fields = frozenset()
    has_html_comments = False
    can_get_multiple_covers = False

    def __init__(self, script_path):
        self._script_path = script_path
        self._module = None
        self._load_error = None
        self._load_script()

        if self._module is not None:
            m = self._module
            self.name = getattr(m, 'name', os.path.splitext(os.path.basename(script_path))[0])
            self.version = getattr(m, 'version', (1, 0, 0))
            self.description = getattr(m, 'description', _('Script source from %s') % os.path.basename(script_path))
            self.capabilities = frozenset(getattr(m, 'capabilities', set()))
            self.touched_fields = frozenset(getattr(m, 'touched_fields', set()))
            self.has_html_comments = getattr(m, 'has_html_comments', False)
            self.can_get_multiple_covers = getattr(m, 'can_get_multiple_covers', False)

        # Set up the minimal state that Source/Plugin normally provides,
        # without calling Plugin.__init__ which requires the plugin ZIP system
        self.plugin_path = None
        self.site_customization = None
        self.running_a_test = False
        self._isbn_to_identifier_cache = {}
        self._identifier_to_cover_url_cache = {}
        self.cache_lock = threading.RLock()
        self._config_obj = None
        self._browser = None

    def _load_script(self):
        try:
            mod_name = f'calibre_script_source_{os.path.splitext(os.path.basename(self._script_path))[0]}'
            spec = importlib.util.spec_from_file_location(mod_name, self._script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            self._module = module
        except Exception:
            self._load_error = traceback.format_exc()
            prints(f'Failed to load script source from {self._script_path}:')
            traceback.print_exc()

    def initialize(self):
        pass

    def is_configured(self):
        return self._module is not None and self._load_error is None

    def is_customizable(self):
        return False

    @property
    def prefs(self):
        if self._config_obj is None:
            from calibre.utils.config import JSONConfig
            self._config_obj = JSONConfig('metadata_sources/%s.json' % self.name)
            self._config_obj.defaults['ignore_fields'] = []
            for opt in self.options:
                self._config_obj.defaults[opt.name] = opt.default
        return self._config_obj

    def identify(self, log, result_queue, abort, title=None, authors=None,
                 identifiers={}, timeout=30):
        if self._module is None or 'identify' not in self.capabilities:
            return
        identify_func = getattr(self._module, 'identify', None)
        if identify_func is None:
            return
        try:
            results = identify_func(
                title=title,
                authors=authors or None,
                identifiers=identifiers or None,
                timeout=timeout,
            )
            if results:
                for i, mi in enumerate(results):
                    if abort.is_set():
                        break
                    if not hasattr(mi, 'source_relevance'):
                        mi.source_relevance = i
                    mi.source_plugin = self
                    result_queue.put(mi)
        except Exception:
            log.exception('Script source %s failed during identify' % self.name)

    def download_cover(self, log, result_queue, abort,
                       title=None, authors=None, identifiers={}, timeout=30, get_best_cover=False):
        if self._module is None or 'cover' not in self.capabilities:
            return
        cover_func = getattr(self._module, 'download_cover', None)
        if cover_func is None:
            return
        try:
            covers = cover_func(
                title=title,
                authors=authors or None,
                identifiers=identifiers or None,
                timeout=timeout,
            )
            if covers:
                for cover_data in covers:
                    if abort.is_set():
                        break
                    result_queue.put((self, cover_data))
        except Exception:
            log.exception('Script source %s failed during cover download' % self.name)


def load_script_sources():
    '''Load all script sources from the metadata_sources directory.
    Returns a list of ScriptSource instances.'''
    sources_dir = get_script_sources_dir()
    if not os.path.isdir(sources_dir):
        return []
    sources = []
    for entry in os.scandir(sources_dir):
        if entry.name.endswith('.py') and entry.is_file() and not entry.name.startswith('_'):
            try:
                source = ScriptSource(entry.path)
                if source.is_configured():
                    sources.append(source)
            except Exception:
                prints('Failed to load script source: %s' % entry.name)
                traceback.print_exc()
    return sources
