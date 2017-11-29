#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, errno, cPickle, sys, re
from locale import localeconv
from collections import OrderedDict, namedtuple
from future_builtins import map
from threading import Lock

from calibre import as_unicode, prints
from calibre.constants import cache_dir, get_windows_number_formats, iswindows

from calibre.utils.localization import canonicalize_lang


def force_to_bool(val):
    if isinstance(val, (str, unicode)):
        try:
            val = icu_lower(val)
            if not val:
                val = None
            elif val in [_('yes'), _('checked'), 'true', 'yes']:
                val = True
            elif val in [_('no'), _('unchecked'), 'false', 'no']:
                val = False
            else:
                val = bool(int(val))
        except:
            val = None
    return val


_fuzzy_title_patterns = None


def fuzzy_title_patterns():
    global _fuzzy_title_patterns
    if _fuzzy_title_patterns is None:
        from calibre.ebooks.metadata import get_title_sort_pat
        _fuzzy_title_patterns = tuple((re.compile(pat, re.IGNORECASE) if
            isinstance(pat, basestring) else pat, repl) for pat, repl in
                [
                    (r'[\[\](){}<>\'";,:#]', ''),
                    (get_title_sort_pat(), ''),
                    (r'[-._]', ' '),
                    (r'\s+', ' ')
                ]
        )
    return _fuzzy_title_patterns


def fuzzy_title(title):
    title = icu_lower(title.strip())
    for pat, repl in fuzzy_title_patterns():
        title = pat.sub(repl, title)
    return title


def find_identical_books(mi, data):
    author_map, aid_map, title_map, lang_map = data
    found_books = None
    for a in mi.authors:
        author_ids = author_map.get(icu_lower(a))
        if author_ids is None:
            return set()
        books_by_author = {book_id for aid in author_ids for book_id in aid_map.get(aid, ())}
        if found_books is None:
            found_books = books_by_author
        else:
            found_books &= books_by_author
        if not found_books:
            return set()

    ans = set()
    titleq = fuzzy_title(mi.title)
    for book_id in found_books:
        title = title_map.get(book_id, '')
        if fuzzy_title(title) == titleq:
            ans.add(book_id)

    langq = tuple(filter(lambda x: x and x != 'und', map(canonicalize_lang, mi.languages or ())))
    if not langq:
        return ans

    def lang_matches(book_id):
        book_langq = lang_map.get(book_id)
        return not book_langq or langq == book_langq

    return {book_id for book_id in ans if lang_matches(book_id)}


Entry = namedtuple('Entry', 'path size timestamp thumbnail_size')


class CacheError(Exception):
    pass


class ThumbnailCache(object):

    ' This is a persistent disk cache to speed up loading and resizing of covers '

    def __init__(self,
                 max_size=1024,  # The maximum disk space in MB
                 name='thumbnail-cache',  # The name of this cache (should be unique in location)
                 thumbnail_size=(100, 100),   # The size of the thumbnails, can be changed
                 location=None,   # The location for this cache, if None cache_dir() is used
                 test_mode=False,  # Used for testing
                 min_disk_cache=0):  # If the size is set less than or equal to this value, the cache is disabled.
        self.location = os.path.join(location or cache_dir(), name)
        if max_size <= min_disk_cache:
            max_size = 0
        self.max_size = int(max_size * (1024**2))
        self.group_id = 'group'
        self.thumbnail_size = thumbnail_size
        self.size_changed = False
        self.lock = Lock()
        self.min_disk_cache = min_disk_cache
        if test_mode:
            self.log = self.fail_on_error

    def log(self, *args, **kwargs):
        kwargs['file'] = sys.stderr
        prints(*args, **kwargs)

    def fail_on_error(self, *args, **kwargs):
        msg = ' '.join(args)
        raise CacheError(msg)

    def _do_delete(self, path):
        try:
            os.remove(path)
        except EnvironmentError as err:
            self.log('Failed to delete cached thumbnail file:', as_unicode(err))

    def _load_index(self):
        'Load the index, automatically removing incorrectly sized thumbnails and pruning to fit max_size'
        try:
            os.makedirs(self.location)
        except OSError as err:
            if err.errno != errno.EEXIST:
                self.log('Failed to make thumbnail cache dir:', as_unicode(err))
        self.total_size = 0
        self.items = OrderedDict()
        order = self._read_order()

        def listdir(*args):
            try:
                return os.listdir(os.path.join(*args))
            except EnvironmentError:
                return ()  # not a directory or no permission or whatever
        entries = ('/'.join((parent, subdir, entry))
                   for parent in listdir(self.location)
                   for subdir in listdir(self.location, parent)
                   for entry in listdir(self.location, parent, subdir))

        invalidate = set()
        try:
            with open(os.path.join(self.location, 'invalidate'), 'rb') as f:
                raw = f.read()
        except EnvironmentError as err:
            if getattr(err, 'errno', None) != errno.ENOENT:
                self.log('Failed to read thumbnail invalidate data:', as_unicode(err))
        else:
            try:
                os.remove(os.path.join(self.location, 'invalidate'))
            except EnvironmentError as err:
                self.log('Failed to remove thumbnail invalidate data:', as_unicode(err))
            else:
                def record(line):
                    try:
                        uuid, book_id = line.partition(' ')[0::2]
                        book_id = int(book_id)
                        return (uuid, book_id)
                    except Exception:
                        return None
                invalidate = {record(x) for x in raw.splitlines()}
        items = []
        try:
            for entry in entries:
                try:
                    uuid, name = entry.split('/')[0::2]
                    book_id, timestamp, size, thumbnail_size = name.split('-')
                    book_id, timestamp, size = int(book_id), float(timestamp), int(size)
                    thumbnail_size = tuple(map(int, thumbnail_size.partition('x')[0::2]))
                except (ValueError, TypeError, IndexError, KeyError, AttributeError):
                    continue
                key = (uuid, book_id)
                path = os.path.join(self.location, entry)
                if self.thumbnail_size == thumbnail_size and key not in invalidate:
                    items.append((key, Entry(path, size, timestamp, thumbnail_size)))
                    self.total_size += size
                else:
                    self._do_delete(path)
        except EnvironmentError as err:
            self.log('Failed to read thumbnail cache dir:', as_unicode(err))

        self.items = OrderedDict(sorted(items, key=lambda x:order.get(hash(x[0]), 0)))
        self._apply_size()

    def _invalidate_sizes(self):
        if self.size_changed:
            size = self.thumbnail_size
            remove = (key for key, entry in self.items.iteritems() if size != entry.thumbnail_size)
            for key in remove:
                self._remove(key)
            self.size_changed = False

    def _remove(self, key):
        entry = self.items.pop(key, None)
        if entry is not None:
            self._do_delete(entry.path)
            self.total_size -= entry.size

    def _apply_size(self):
        while self.total_size > self.max_size and self.items:
            entry = self.items.popitem(last=False)[1]
            self._do_delete(entry.path)
            self.total_size -= entry.size

    def _write_order(self):
        if hasattr(self, 'items'):
            try:
                with open(os.path.join(self.location, 'order'), 'wb') as f:
                    f.write(cPickle.dumps(tuple(map(hash, self.items)), -1))
            except EnvironmentError as err:
                self.log('Failed to save thumbnail cache order:', as_unicode(err))

    def _read_order(self):
        order = {}
        try:
            with open(os.path.join(self.location, 'order'), 'rb') as f:
                order = cPickle.loads(f.read())
                order = {k:i for i, k in enumerate(order)}
        except Exception as err:
            if getattr(err, 'errno', None) != errno.ENOENT:
                self.log('Failed to load thumbnail cache order:', as_unicode(err))
        return order

    def shutdown(self):
        with self.lock:
            self._write_order()

    def set_group_id(self, group_id):
        with self.lock:
            self.group_id = group_id

    def set_thumbnail_size(self, width, height):
        with self.lock:
            self.thumbnail_size = (width, height)
            self.size_changed = True

    def insert(self, book_id, timestamp, data):
        if self.max_size < len(data):
            return
        with self.lock:
            if not hasattr(self, 'total_size'):
                self._load_index()
            self._invalidate_sizes()
            ts = ('%.2f' % timestamp).replace('.00', '')
            path = '%s%s%s%s%d-%s-%d-%dx%d' % (
                self.group_id, os.sep, book_id % 100, os.sep,
                book_id, ts, len(data), self.thumbnail_size[0], self.thumbnail_size[1])
            path = os.path.join(self.location, path)
            key = (self.group_id, book_id)
            e = self.items.pop(key, None)
            self.total_size -= getattr(e, 'size', 0)
            try:
                with open(path, 'wb') as f:
                    f.write(data)
            except EnvironmentError as err:
                d = os.path.dirname(path)
                if not os.path.exists(d):
                    try:
                        os.makedirs(d)
                        with open(path, 'wb') as f:
                            f.write(data)
                    except EnvironmentError as err:
                        self.log('Failed to write cached thumbnail:', path, as_unicode(err))
                        return self._apply_size()
                else:
                    self.log('Failed to write cached thumbnail:', path, as_unicode(err))
                    return self._apply_size()
            self.items[key] = Entry(path, len(data), timestamp, self.thumbnail_size)
            self.total_size += len(data)
            self._apply_size()

    def __len__(self):
        with self.lock:
            try:
                return len(self.items)
            except AttributeError:
                self._load_index()
                return len(self.items)

    def __contains__(self, book_id):
        with self.lock:
            try:
                return (self.group_id, book_id) in self.items
            except AttributeError:
                self._load_index()
                return (self.group_id, book_id) in self.items

    def __getitem__(self, book_id):
        with self.lock:
            if not hasattr(self, 'total_size'):
                self._load_index()
            self._invalidate_sizes()
            key = (self.group_id, book_id)
            entry = self.items.pop(key, None)
            if entry is None:
                return None, None
            if entry.thumbnail_size != self.thumbnail_size:
                try:
                    os.remove(entry.path)
                except EnvironmentError as err:
                    if getattr(err, 'errno', None) != errno.ENOENT:
                        self.log('Failed to remove cached thumbnail:', entry.path, as_unicode(err))
                self.total_size -= entry.size
                return None, None
            self.items[key] = entry
            try:
                with open(entry.path, 'rb') as f:
                    data = f.read()
            except EnvironmentError as err:
                self.log('Failed to read cached thumbnail:', entry.path, as_unicode(err))
                return None, None
            return data, entry.timestamp

    def invalidate(self, book_ids):
        with self.lock:
            if hasattr(self, 'total_size'):
                for book_id in book_ids:
                    self._remove((self.group_id, book_id))
            elif os.path.exists(self.location):
                try:
                    raw = '\n'.join('%s %d' % (self.group_id, book_id) for book_id in book_ids)
                    with open(os.path.join(self.location, 'invalidate'), 'ab') as f:
                        f.write(raw.encode('ascii'))
                except EnvironmentError as err:
                    self.log('Failed to write invalidate thumbnail record:', as_unicode(err))

    @property
    def current_size(self):
        with self.lock:
            if not hasattr(self, 'total_size'):
                self._load_index()
            return self.total_size

    def empty(self):
        with self.lock:
            try:
                os.remove(os.path.join(self.location, 'order'))
            except EnvironmentError:
                pass
            if not hasattr(self, 'total_size'):
                self._load_index()
            for entry in self.items.itervalues():
                self._do_delete(entry.path)
            self.total_size = 0
            self.items = OrderedDict()

    def __hash__(self):
        return id(self)

    def set_size(self, size_in_mb):
        if size_in_mb <= self.min_disk_cache:
            size_in_mb = 0
        size_in_mb = max(0, size_in_mb)
        with self.lock:
            self.max_size = int(size_in_mb * (1024**2))
            if hasattr(self, 'total_size'):
                self._apply_size()


number_separators = None


def atof(string):
    # Python 2.x does not handle unicode number separators correctly, so we
    # have to implement our own
    global number_separators
    if number_separators is None:
        if iswindows:
            number_separators = get_windows_number_formats()
        else:
            lc = localeconv()
            t, d = lc['thousands_sep'], lc['decimal_point']
            if isinstance(t, bytes):
                t = t.decode('utf-8', 'ignore') or ','
            if isinstance(d, bytes):
                d = d.decode('utf-8', 'ignore') or '.'
            number_separators = t, d
    return float(string.replace(number_separators[1], '.').replace(number_separators[0], ''))
