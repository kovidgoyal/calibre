__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Manage translation of user visible strings.
'''

import sys, os, cStringIO, tempfile, subprocess, functools, tarfile, re
check_call = functools.partial(subprocess.check_call, shell=True)

try:
    from calibre.translations.pygettext import main as pygettext
    from calibre.translations.msgfmt import main as msgfmt
except ImportError:
    sys.path.insert(1, os.path.abspath('..'))
    from calibre.translations.pygettext import main as pygettext
    from calibre.translations.msgfmt import main as msgfmt



TRANSLATIONS = [
                'sl',
                'de',
                'ca',
                'fr',
                'es',
                'it',
                'bg',
                'nds',
                'ru',
                ]

def source_files():
    ans = []
    for root, dirs, files in os.walk(os.getcwdu()):
        for name in files:
            if name.endswith('.py'):
                ans.append(os.path.abspath(os.path.join(root, name)))
    return ans
                

def update_po_files(tarball):
    if not os.getcwd().endswith('translations'):
        os.chdir('translations')
    tf = tarfile.open(tarball, 'r:gz')
    next = tf.next()
    while next is not None:
        if next.name.endswith('.po'):
            po = re.search(r'-([a-z]{2,3}\.po)', next.name).group(1)
            print 'Updating', po
            tf.extract(next, os.path.abspath(po))
        next = tf.next()
    
    return 0

def main(args=sys.argv):
    if args[-1].endswith('.tar.gz'):
        return update_po_files(args[-1])
    tdir = os.path.dirname(__file__)
    files = source_files()
    buf = cStringIO.StringIO()
    print 'Creating translations template'
    pygettext(buf, ['-p', tdir]+files)
    src = buf.getvalue()
    tempdir = tempfile.mkdtemp()
    tf = tarfile.open(os.path.join(tempdir, 'translations.tar.bz2'), 'w:bz2')
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
        tf.add(po, os.path.basename(po))
        buf = cStringIO.StringIO()
        print 'Compiling translations'
        msgfmt(buf, [po])
        translations[tr] = buf.getvalue()
    open(os.path.join(tdir, 'data.py'), 'wb').write('translations = '+repr(translations))
    os.close(fd)
    tf.add(fname, 'strings.pot')
    tf.close()
    os.unlink(fname)
    print 'Translations tarball is in', os.path.join(tempdir, 'translations.tar.bz2')
    return 0

if __name__ == '__main__':
    sys.exit(main())
