__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Manage translation of user visible strings.
'''

import sys, os, cStringIO, tempfile, subprocess, functools, tarfile, re, time, \
       glob, urllib2, shutil 
check_call = functools.partial(subprocess.check_call, shell=True)

try:
    from calibre.translations.pygettext import main as pygettext
    from calibre.translations.msgfmt import main as msgfmt
except ImportError:
    sys.path.insert(1, os.path.abspath('..'))
    from calibre.translations.pygettext import main as pygettext
    from calibre.translations.msgfmt import main as msgfmt


def source_files():
    ans = []
    for root, dirs, files in os.walk(os.path.dirname(os.getcwdu())):
        for name in files:
            if name.endswith('.py'):
                ans.append(os.path.abspath(os.path.join(root, name)))
    return ans
                

def create_pot():
    files = source_files()
    buf = cStringIO.StringIO()
    print 'Creating translations template'
    tempdir = tempfile.mkdtemp()
    pygettext(buf, ['-p', tempdir]+files)
    src = buf.getvalue()
    pot = os.path.join(tempdir, 'calibre.pot')
    f = open(pot, 'wb')
    f.write(src)
    f.close()
    print 'Translations template:', pot
    return pot
    

def compile_translations():
    translations = {}
    print 'Compiling translations...'
    for po in glob.glob('*.po'):
        lang = os.path.basename(po).partition('.')[0]
        buf = cStringIO.StringIO()
        print 'Compiling', lang
        msgfmt(buf, [po])
        translations[lang] = buf.getvalue()
        open('compiled.py', 'wb').write('translations = '+repr(translations))

def import_from_launchpad(url):
    f = open('/tmp/launchpad_export.tar.gz', 'wb')
    shutil.copyfileobj(urllib2.urlopen(url), f)
    f.close()
    tf = tarfile.open('/tmp/launchpad_export.tar.gz', 'r:gz')
    next = tf.next()
    while next is not None:
        if next.isfile() and next.name.endswith('.po'):
            po = re.search(r'-([a-z]{2,3}\.po)', next.name).group(1)
            out = os.path.abspath(os.path.join('.', os.path.basename(po)))
            print 'Updating', '%6s'%po, '-->', out
            open(out, 'wb').write(tf.extractfile(next).read())
        next = tf.next()
    
    return 0

def main(args=sys.argv):
    if len(args) > 1:
        if args[1] == 'pot':
            create_pot()
        else:
            import_from_launchpad(args[1])            
    else:
        compile_translations()
    return 0
        
if __name__ == '__main__':
    sys.exit(main())
