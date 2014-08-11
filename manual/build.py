#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.utils.icu import upper  # ensure encoding is set to utf-8
del upper
import sys, os, subprocess, shutil

j, d, a = os.path.join, os.path.dirname, os.path.abspath

def build_manual(language, base):

    def sphinx_build(builder='html', bdir='html', t=None):
        destdir = j(base, bdir)
        os.makedirs(destdir)
        ans = ['sphinx-build2', '-D', ('language=' + language), '-q', '-b', builder]
        if builder == 'html':
            ans += ['-w', j(destdir, 'sphinx-build-warnings.txt')]
        if t:
            ans += ['-t', t]
        ans += ['-d', j(base, 'doctrees'), '.', destdir]
        print(' '.join(ans))
        subprocess.check_call(ans)
        return destdir

    onlinedir = sphinx_build(t='online')
    epubdir = sphinx_build('myepub', 'epub')
    latexdir = sphinx_build('mylatex', 'latex')
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

if __name__ == '__main__':
    language, base, src, __appname__, __version__ = sys.argv[1:]
    os.chdir(src)
    os.environ['__appname__'] = __appname__
    os.environ['__version__'] = __version__
    build_manual(language, base)
