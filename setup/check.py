#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, cPickle, subprocess
from setup import Command
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

    CACHE = '.check-cache.pickle'

    def get_files(self, cache):
        for x in os.walk(self.j(self.SRC, 'calibre')):
            for f in x[-1]:
                y = self.j(x[0], f)
                mtime = os.stat(y).st_mtime
                if cache.get(y, 0) == mtime:
                    continue
                if (f.endswith('.py') and f not in (
                        'feedparser.py', 'pyparsing.py', 'markdown.py') and
                        'prs500/driver.py' not in y):
                    yield y, mtime
                if f.endswith('.coffee'):
                    yield y, mtime

        for x in os.walk(self.j(self.d(self.SRC), 'recipes')):
            for f in x[-1]:
                f = self.j(x[0], f)
                mtime = os.stat(f).st_mtime
                if f.endswith('.recipe') and cache.get(f, 0) != mtime:
                    yield f, mtime

    def run(self, opts):
        cache = {}
        if os.path.exists(self.CACHE):
            cache = cPickle.load(open(self.CACHE, 'rb'))
        for f, mtime in self.get_files(cache):
            self.info('\tChecking', f)
            errors = False
            ext = os.path.splitext(f)[1]
            if ext in {'.py', '.recipe'}:
                p = subprocess.Popen(['flake8', '--ignore=E,W', f])
                if p.wait() != 0:
                    errors = True
            else:
                from calibre.utils.serve_coffee import check_coffeescript
                try:
                    check_coffeescript(f)
                except:
                    errors = True
            if errors:
                cPickle.dump(cache, open(self.CACHE, 'wb'), -1)
                subprocess.call(['gvim', '-S',
                                 self.j(self.SRC, '../session.vim'), '-f', f])
                raise SystemExit(1)
            cache[f] = mtime
        cPickle.dump(cache, open(self.CACHE, 'wb'), -1)
        wn_path = os.path.expanduser('~/work/servers/src/calibre_servers/main')
        if os.path.exists(wn_path):
            sys.path.insert(0, wn_path)
            self.info('\tChecking Changelog...')
            os.environ['DJANGO_SETTINGS_MODULE'] = 'calibre_servers.status.settings'
            import whats_new
            whats_new.test()
            sys.path.remove(wn_path)

    def report_errors(self, errors):
        for err in errors:
            self.info('\t\t', str(err))

