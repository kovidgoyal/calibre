#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>


import cgi
import mimetypes
import os
import posixpath
import re
import shutil
from collections import defaultdict
from contextlib import closing
from functools import partial
from io import BytesIO
from multiprocessing.dummy import Pool
from tempfile import NamedTemporaryFile

from calibre import as_unicode, sanitize_file_name as sanitize_file_name_base
from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES, barename, iterlinks
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.ptempfile import TemporaryDirectory
from calibre.web import get_download_filename_from_response
from polyglot.builtins import iteritems
from polyglot.urllib import urlopen, urlparse
from polyglot.binary import from_base64_bytes


def is_external(url):
    try:
        purl = urlparse(url)
    except Exception:
        return False
    return purl.scheme in ('http', 'https', 'file', 'ftp', 'data')


def iterhtmllinks(container, name):
    for el, attr, link, pos in iterlinks(container.parsed(name)):
        tag = barename(el.tag).lower()
        if tag != 'a' and is_external(link):
            yield el, attr, link


def get_external_resources(container):
    ans = defaultdict(list)
    for name, media_type in iteritems(container.mime_map):
        if container.has_name(name) and container.exists(name):
            if media_type in OEB_DOCS:
                for el, attr, link in iterhtmllinks(container, name):
                    ans[link].append(name)
            elif media_type in OEB_STYLES:
                for link in container.iterlinks(name, get_line_numbers=False):
                    if is_external(link):
                        ans[link].append(name)
    return dict(ans)


def get_filename(original_url_parsed, response):
    ans = get_download_filename_from_response(response) or posixpath.basename(original_url_parsed.path) or 'unknown'
    ct = response.info().get('Content-Type', '')
    if ct:
        ct = cgi.parse_header(ct)[0].lower()
        if ct:
            mt = guess_type(ans)
            if mt != ct:
                exts = mimetypes.guess_all_extensions(ct)
                if exts:
                    ans += exts[0]
    return ans


def get_content_length(response):
    cl = response.info().get('Content-Length')
    try:
        return int(cl)
    except Exception:
        return -1


class ProgressTracker(object):

    def __init__(self, fobj, url, sz, progress_report):
        self.fobj = fobj
        self.progress_report = progress_report
        self.url, self.sz = url, sz
        self.close, self.flush, self.name = fobj.close, fobj.flush, fobj.name

    def write(self, x):
        ret = self.fobj.write(x)
        try:
            self.progress_report(self.url, self.fobj.tell(), self.sz)
        except Exception:
            pass
        return ret


def sanitize_file_name(x):
    from calibre.ebooks.oeb.polish.check.parsing import make_filename_safe
    x = sanitize_file_name_base(x)
    while '..' in x:
        x = x.replace('..', '.')
    return make_filename_safe(x)


def download_one(tdir, timeout, progress_report, data_uri_map, url):
    try:
        purl = urlparse(url)
        data_url_key = None
        with NamedTemporaryFile(dir=tdir, delete=False) as df:
            if purl.scheme == 'file':
                src = lopen(purl.path, 'rb')
                filename = os.path.basename(src)
                sz = (src.seek(0, os.SEEK_END), src.tell(), src.seek(0))[1]
            elif purl.scheme == 'data':
                prefix, payload = purl.path.split(',', 1)
                parts = prefix.split(';')
                if parts and parts[-1].lower() == 'base64':
                    payload = re.sub(r'\s+', '', payload)
                    payload = from_base64_bytes(payload)
                else:
                    payload = payload.encode('utf-8')
                seen_before = data_uri_map.get(payload)
                if seen_before is not None:
                    return True, (url, filename, seen_before, guess_type(seen_before))
                data_url_key = payload
                src = BytesIO(payload)
                sz = len(payload)
                ext = 'unknown'
                for x in parts:
                    if '=' not in x and '/' in x:
                        exts = mimetypes.guess_all_extensions(x)
                        if exts:
                            ext = exts[0]
                            break
                filename = 'data-uri.' + ext
            else:
                src = urlopen(url, timeout=timeout)
                filename = get_filename(purl, src)
                sz = get_content_length(src)
            progress_report(url, 0, sz)
            dest = ProgressTracker(df, url, sz, progress_report)
            with closing(src):
                shutil.copyfileobj(src, dest)
            if data_url_key is not None:
                data_uri_map[data_url_key] = dest.name
            filename = sanitize_file_name(filename)
            mt = guess_type(filename)
            if mt in OEB_DOCS:
                raise ValueError('The external resource {} looks like a HTML document ({})'.format(url, filename))
            if not mt or mt == 'application/octet-stream' or '.' not in filename:
                raise ValueError('The external resource {} is not of a known type'.format(url))
            return True, (url, filename, dest.name, mt)
    except Exception as err:
        return False, (url, as_unicode(err))


def download_external_resources(container, urls, timeout=60, progress_report=lambda url, done, total: None):
    failures = {}
    replacements = {}
    data_uri_map = {}
    with TemporaryDirectory('editor-download') as tdir:
        pool = Pool(10)
        with closing(pool):
            for ok, result in pool.imap_unordered(partial(download_one, tdir, timeout, progress_report, data_uri_map), urls):
                if ok:
                    url, suggested_filename, downloaded_file, mt = result
                    with lopen(downloaded_file, 'rb') as src:
                        name = container.add_file(suggested_filename, src, mt, modify_name_if_needed=True)
                    replacements[url] = name
                else:
                    url, err = result
                    failures[url] = err
    return replacements, failures


def replacer(url_map):
    def replace(url):
        r = url_map.get(url)
        replace.replaced |= r != url
        return url if r is None else r
    replace.replaced = False
    return replace


def replace_resources(container, urls, replacements):
    url_maps = defaultdict(dict)
    changed = False
    for url, names in iteritems(urls):
        replacement = replacements.get(url)
        if replacement is not None:
            for name in names:
                url_maps[name][url] = container.name_to_href(replacement, name)
    for name, url_map in iteritems(url_maps):
        r = replacer(url_map)
        container.replace_links(name, r)
        changed |= r.replaced
    return changed
