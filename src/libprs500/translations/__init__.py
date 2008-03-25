__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Manage translation of user visible strings.
'''

import sys, os, cStringIO, tempfile, subprocess, functools
check_call = functools.partial(subprocess.check_call, shell=True)

from libprs500.translations.pygettext import main as pygettext
from libprs500.translations.msgfmt import main as msgfmt

TRANSLATIONS = [
                'sl',
                'de',
                'ca',
                'fr',
                'es',
                'it'
                ]

def source_files():
    ans = []
    for root, dirs, files in os.walk(os.getcwdu()):
        for name in files:
            if name.endswith('.py'):
                ans.append(os.path.abspath(os.path.join(root, name)))
    return ans
                

def main(args=sys.argv):
    tdir = os.path.dirname(__file__)
    files = source_files()
    buf = cStringIO.StringIO()
    print 'Creating translations template'
    pygettext(buf, ['-p', tdir]+files)
    src = buf.getvalue()
    fd, fname = tempfile.mkstemp(suffix='.pot')
    os.write(fd,src)

    translations = {}
    for tr in TRANSLATIONS:
        po = os.path.join(tdir, tr+'.po')
        if not os.path.exists(po):
            open(po, 'wb').write(src.replace('LANGUAGE', tr))
        else:
            print 'Merging', os.path.basename(po)
            check_call('msgmerge -v -U -N --backup=none '+po + ' ' + fname)
        buf = cStringIO.StringIO()
        print 'Compiling translations'
        msgfmt(buf, [po])
        translations[tr] = buf.getvalue()
    open(os.path.join(tdir, 'data.py'), 'wb').write('translations = '+repr(translations))
    os.close(fd)
    os.unlink(fname)
    return 0

if __name__ == '__main__':
    sys.exit(main())