#!/usr/bin/env calibre-debug
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import tempfile
from functools import partial

from calibre import __appname__, __version__
from calibre.utils.icu import upper  # ensure encoding is set to utf-8
del upper
import sys, os, subprocess, shutil

SPHINX_BUILD = 'sphinx-build2'

j, d, a = os.path.join, os.path.dirname, os.path.abspath

def sphinx_build(language, base, builder='html', bdir='html', t=None, quiet=True):
    destdir = j(base, bdir)
    if not os.path.exists(destdir):
        os.makedirs(destdir)
    ans = [SPHINX_BUILD, '-D', ('language=' + language), '-b', builder]
    if quiet:
        ans.append('-q')
    if builder == 'html':
        ans += ['-w', j(destdir, 'sphinx-build-warnings.txt')]
    if t:
        ans += ['-t', t]
    ans += ['-d', j(base, 'doctrees'), '.', destdir]
    print(' '.join(ans))
    subprocess.check_call(ans)
    return destdir

def build_manual(language, base):
    sb = partial(sphinx_build, language, base)
    onlinedir = sb(t='online')
    epubdir = sb('myepub', 'epub')
    latexdir = sb('mylatex', 'latex')
    pwd = os.getcwdu()
    os.chdir(latexdir)
    def run_cmd(cmd):
        p = subprocess.Popen(cmd, stdout=open(os.devnull, 'wb'), stdin=subprocess.PIPE)
        p.stdin.close()
        return p.wait()
    try:
        for i in xrange(3):
            run_cmd(['pdflatex', '-interaction=nonstopmode', 'calibre.tex'])
        run_cmd(['makeindex', '-s', 'python.ist', 'calibre.idx'])
        for i in xrange(2):
            run_cmd(['pdflatex', '-interaction=nonstopmode', 'calibre.tex'])
        if not os.path.exists('calibre.pdf'):
            print('Failed to build pdf file, see calibre.log in the latex directory', file=sys.stderr)
            raise SystemExit(1)
    finally:
        os.chdir(pwd)
    epub_dest = j(onlinedir, 'calibre.epub')
    pdf_dest = j(onlinedir, 'calibre.pdf')
    shutil.copyfile(j(epubdir, 'calibre.epub'), epub_dest)
    shutil.copyfile(j(latexdir, 'calibre.pdf'), pdf_dest)
    from calibre.ebooks.oeb.polish.container import epub_to_azw3
    epub_to_azw3(epub_dest)

def build_pot(base):
    cmd = [SPHINX_BUILD, '-b', 'gettext', '-t', 'online', '.', base]
    print (' '.join(cmd))
    subprocess.check_call(cmd)
    os.remove(j(base, 'generated.pot'))
    return base

if __name__ == '__main__':
    os.chdir(d(a(__file__)))
    os.environ['__appname__'] = __appname__
    os.environ['__version__'] = __version__
    if len(sys.argv) == 1:
        base = j(tempfile.gettempdir(), 'manual')
        os.environ['CALIBRE_OVERRIDE_LANG'] = language = 'en'
        sphinx_build(language, base, t='online', quiet=False)
    else:
        language, base  = sys.argv[1:]
        if language == 'gettext':
            build_pot(base)
        else:
            os.environ['CALIBRE_OVERRIDE_LANG'] = language
            build_manual(language, base)
    if language != 'gettext':
        print ('Manual for', language, 'built in', j(base, 'html'))
