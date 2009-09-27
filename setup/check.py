#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, cPickle, subprocess
from operator import attrgetter
from setup import Command

def check_for_python_errors(filename, builtins):
    from pyflakes import checker, ast

    contents = open(filename, 'rb').read()

    try:
        tree = ast.parse(contents, filename)
    except:
        import traceback
        traceback.print_exc()
        try:
            value = sys.exc_info()[1]
            lineno, offset, line = value[1][1:]
        except IndexError:
            lineno, offset, line = 1, 0, ''
        if line.endswith("\n"):
            line = line[:-1]

        return [SyntaxError(filename, lineno, offset, str(value))]
    else:
        w = checker.Checker(tree, filename, builtins = builtins)
        w.messages.sort(key = attrgetter('lineno'))
        return w.messages


class Check(Command):

    description = 'Check for errors in the calibre source code'

    BUILTINS = ['_', '__', 'dynamic_property', 'I', 'P']
    CACHE = '.check-cache.pickle'

    def run(self, opts):
        cache = {}
        if os.path.exists(self.CACHE):
            cache = cPickle.load(open(self.CACHE, 'rb'))
        for x in os.walk(self.j(self.SRC, 'calibre')):
            for f in x[-1]:
                f = self.j(x[0], f)
                mtime = os.stat(f).st_mtime
                if f.endswith('.py') and cache.get(f, 0) != mtime and \
                        self.b(f) not in ('ptempfile.py', 'feedparser.py',
                        'pyparsing.py', 'markdown.py') and 'genshi' not in f and \
                        'prs500/driver.py' not in f:
                    self.info('\tChecking', f)
                    w = check_for_python_errors(f, self.BUILTINS)
                    if w:
                        self.report_errors(w)
                        cPickle.dump(cache, open(self.CACHE, 'wb'), -1)
                        subprocess.call(['gvim', '-f', f])
                        raise SystemExit(1)
                    cache[f] = mtime
        cPickle.dump(cache, open(self.CACHE, 'wb'), -1)


    def report_errors(self, errors):
        for err in errors:
            if isinstance(err, SyntaxError):
                print '\t\tSyntax Error'
            else:
                col = getattr(err, 'col', 0) if getattr(err, 'col', 0) else 0
                lineno = err.lineno if err.lineno else 0
                self.info('\t\t%d:%d:'%(lineno, col),
                        err.message%err.message_args)

