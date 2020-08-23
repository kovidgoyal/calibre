#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os, subprocess, shutil
import tempfile
from functools import partial

j, d, a = os.path.join, os.path.dirname, os.path.abspath
BASE = d(a(__file__))
SPHINX_BUILD = ['sphinx-build']
is_ci = os.environ.get('CI') == 'true'

sys.path.insert(0, d(BASE))
from setup import __appname__, __version__
from calibre.ebooks.oeb.polish.container import epub_to_azw3
sys.path.remove(d(BASE))


def sphinx_build(language, base, builder='html', bdir='html', t=None, quiet=True, very_quiet=False):
    destdir = j(base, bdir)
    if not os.path.exists(destdir):
        os.makedirs(destdir)
    ans = SPHINX_BUILD + ['-D', ('language=' + language), '-b', builder]
    if quiet:
        ans.append('-q')
    if very_quiet:
        ans.append('-Q')
    if builder == 'html':
        ans += ['-w', j(destdir, 'sphinx-build-warnings.txt')]
    if t:
        ans += ['-t', t]
    ans += ['-d', j(base, 'doctrees'), BASE, destdir]
    print(' '.join(ans))
    subprocess.check_call(ans)
    return destdir


def build_manual(language, base):
    sb = partial(sphinx_build, language, base)
    onlinedir = sb(t='online')
    epubdir = sb('myepub', 'epub')
    latexdir = sb('mylatex', 'latex')
    pwd = os.getcwd()
    os.chdir(latexdir)

    def run_cmd(cmd):
        p = subprocess.Popen(cmd, stdout=open(os.devnull, 'wb'), stdin=subprocess.PIPE)
        p.stdin.close()
        return p.wait()
    try:
        for i in range(3):
            run_cmd(['xelatex', '-interaction=nonstopmode', 'calibre.tex'])
        run_cmd(['makeindex', '-s', 'python.ist', 'calibre.idx'])
        for i in range(2):
            run_cmd(['xelatex', '-interaction=nonstopmode', 'calibre.tex'])
        if not os.path.exists('calibre.pdf'):
            print('Failed to build pdf file, see calibre.log in the latex directory', file=sys.stderr)
            raise SystemExit(1)
    finally:
        os.chdir(pwd)
    epub_dest = j(onlinedir, 'calibre.epub')
    pdf_dest = j(onlinedir, 'calibre.pdf')
    shutil.copyfile(j(epubdir, 'calibre.epub'), epub_dest)
    shutil.copyfile(j(latexdir, 'calibre.pdf'), pdf_dest)
    epub_to_azw3(epub_dest)


def build_pot(base):
    cmd = SPHINX_BUILD + ['-b', 'gettext', '-t', 'online', '-t', 'gettext', '.', base]
    if is_ci:
        sp = eval(subprocess.check_output(['python', '-c', 'import sphinx; print(sphinx.__path__)']).decode('utf-8'))
        code = f'import sys, os; sys.path += [{os.path.dirname(sp[0])!r}]; from sphinx.cmd.build import main; main({cmd[1:]!r})'
        cmd = [sys.executable, '-c', code]
    print(' '.join(cmd))
    subprocess.check_call(cmd)
    os.remove(j(base, 'generated.pot'))
    return base


def build_linkcheck(base):
    cmd = SPHINX_BUILD + ['-b', 'linkcheck', '-t', 'online', '-t', 'linkcheck', '.', base]
    print(' '.join(cmd))
    subprocess.check_call(cmd)
    return base


def build_man_pages(language, base):
    os.environ['CALIBRE_BUILD_MAN_PAGES'] = '1'
    sphinx_build(language, base, builder='man', bdir=language, very_quiet=True)


if __name__ == '__main__':
    import argparse
    os.chdir(d(a(__file__)))
    os.environ['__appname__'] = __appname__
    os.environ['__version__'] = __version__
    if len(sys.argv) == 1:
        base = j(tempfile.gettempdir(), 'manual')
        os.environ['CALIBRE_OVERRIDE_LANG'] = language = 'en'
        if 'ALL_USER_MANUAL_LANGUAGES' not in os.environ:
            import json
            os.environ['ALL_USER_MANUAL_LANGUAGES'] = ' '.join(json.load(open('locale/completed.json', 'rb')))
        sphinx_build(language, base, t='online', quiet=False)
        print('Manual built in', j(base, 'html'))
    else:
        p = argparse.ArgumentParser()
        p.add_argument('language', help='The language to build for')
        p.add_argument('base', help='The destination directory')
        p.add_argument('--man-pages', default=False, action='store_true', help='Build man pages')
        p.add_argument('--quiet', default=False, action='store_true', help='Suppress warnings')
        args = p.parse_args()
        language, base = args.language, args.base
        if language == 'gettext':
            build_pot(base)
        elif language == 'linkcheck':
            build_linkcheck(base)
        elif args.man_pages:
            os.environ['CALIBRE_OVERRIDE_LANG'] = language
            build_man_pages(language, base)
        else:
            os.environ['CALIBRE_OVERRIDE_LANG'] = language
            build_manual(language, base)
            print('Manual for', language, 'built in', j(base, 'html'))
