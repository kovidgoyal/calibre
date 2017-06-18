#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, json, subprocess, errno, hashlib
from setup import Command, build_cache_dir, edit_file
import __builtin__


def set_builtins(builtins):
    for x in builtins:
        if not hasattr(__builtin__, x):
            setattr(__builtin__, x, True)
            yield x


class Message:

    def __init__(self, filename, lineno, msg):
        self.filename, self.lineno, self.msg = filename, lineno, msg

    def __str__(self):
        return '%s:%s: %s' % (self.filename, self.lineno, self.msg)


class Check(Command):

    description = 'Check for errors in the calibre source code'

    CACHE = 'check.json'

    def get_files(self):
        for x in os.walk(self.j(self.SRC, 'calibre')):
            for f in x[-1]:
                y = self.j(x[0], f)
                if x[0].endswith('calibre/ebooks/markdown'):
                    continue
                if (f.endswith('.py') and f not in (
                        'feedparser.py', 'markdown.py', 'BeautifulSoup.py', 'dict_data.py',
                        'unicodepoints.py', 'krcodepoints.py', 'jacodepoints.py', 'vncodepoints.py', 'zhcodepoints.py') and
                        'prs500/driver.py' not in y) and not f.endswith('_ui.py'):
                    yield y
                if f.endswith('.coffee'):
                    yield y

        for x in os.walk(self.j(self.d(self.SRC), 'recipes')):
            for f in x[-1]:
                f = self.j(x[0], f)
                if f.endswith('.recipe'):
                    yield f

        for x in os.walk(self.j(self.SRC, 'pyj')):
            for f in x[-1]:
                f = self.j(x[0], f)
                if f.endswith('.pyj'):
                    yield f
        if self.has_changelog_check:
            yield self.j(self.d(self.SRC), 'Changelog.yaml')

    def read_file(self, f):
        with open(f, 'rb') as f:
            return f.read()

    def file_hash(self, f):
        try:
            return self.fhash_cache[f]
        except KeyError:
            self.fhash_cache[f] = ans = hashlib.sha1(self.read_file(f)).hexdigest()
            return ans

    def is_cache_valid(self, f, cache):
        return cache.get(f) == self.file_hash(f)

    @property
    def cache_file(self):
        return self.j(build_cache_dir(), self.CACHE)

    def save_cache(self, cache):
        with open(self.cache_file, 'wb') as f:
            json.dump(cache, f)

    def file_has_errors(self, f):
        ext = os.path.splitext(f)[1]
        if ext in {'.py', '.recipe'}:
            p = subprocess.Popen(['flake8-python2', '--filename', '*.py,*.recipe', f])
            return p.wait() != 0
        elif ext == '.pyj':
            p = subprocess.Popen(['rapydscript', 'lint', f])
            return p.wait() != 0
        elif ext == '.yaml':
            sys.path.insert(0, self.wn_path)
            import whats_new
            whats_new.render_changelog(self.j(self.d(self.SRC), 'Changelog.yaml'))
            sys.path.remove(self.wn_path)
        else:
            from calibre.utils.serve_coffee import check_coffeescript
            try:
                check_coffeescript(f)
            except:
                return True

    def run(self, opts):
        self.fhash_cache = {}
        cache = {}
        self.wn_path = os.path.expanduser('~/work/srv/main/static')
        self.has_changelog_check = os.path.exists(self.wn_path)
        try:
            cache = json.load(open(self.cache_file, 'rb'))
        except EnvironmentError as err:
            if err.errno != errno.ENOENT:
                raise
        dirty_files = tuple(f for f in self.get_files() if not self.is_cache_valid(f, cache))
        try:
            for i, f in enumerate(dirty_files):
                self.info('\tChecking', f)
                if self.file_has_errors(f):
                    self.info('%d files left to check' % (len(dirty_files) - i - 1))
                    edit_file(f)
                    if self.file_has_errors(f):
                        raise SystemExit(1)
                cache[f] = self.file_hash(f)
        finally:
            self.save_cache(cache)

    def report_errors(self, errors):
        for err in errors:
            self.info('\t\t', str(err))

    def clean(self):
        try:
            os.remove(self.cache_file)
        except EnvironmentError as err:
            if err.errno != errno.ENOENT:
                raise
