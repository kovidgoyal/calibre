__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Manage the PyQt build system pyrcc4, pylupdate4, lrelease and friends.
'''

import sys, os, subprocess, cStringIO, compiler, re
from functools import partial

from PyQt4.uic import compileUi

check_call = partial(subprocess.check_call, shell=True)
sys.path.insert(1, os.path.abspath('..%s..'%os.sep))

from calibre import __appname__
from calibre.path import path

def find_forms():
    forms = []
    for root, dirs, files in os.walk('.'):
        for name in files:
            if name.endswith('.ui'):
                forms.append(os.path.abspath(os.path.join(root, name)))
        
    return forms

def form_to_compiled_form(form):
    return form.rpartition('.')[0]+'_ui.py'

def build_forms(forms):
    for form in forms:
        compiled_form = form_to_compiled_form(form) 
        if not os.path.exists(compiled_form) or os.stat(form).st_mtime > os.stat(compiled_form).st_mtime:
            print 'Compiling form', form
            buf = cStringIO.StringIO()
            compileUi(form, buf)
            dat = buf.getvalue()
            dat = dat.replace('__appname__', __appname__)
            dat = dat.replace('import images_rc', 'from calibre.gui2 import images_rc')
            dat = dat.replace('from library import', 'from calibre.gui2.library import')
            dat = dat.replace('from widgets import', 'from calibre.gui2.widgets import')
            dat = re.compile(r'QtGui.QApplication.translate\(.+?,\s+"(.+?)(?<!\\)",.+?\)', re.DOTALL).sub(r'_("\1")', dat)
            open(compiled_form, 'wb').write(dat)
            
                
def build_images():
    p = path('images')
    mtime = p.mtime
    for x in p.walk():
        mtime = max(x.mtime, mtime)
    images = path('images_rc.py')
    if not images.exists() or mtime > images.mtime:
        print 'Compiling images...'
        files = []
        for x in p.walk():
            if '.svn' in x or '.bzr' in x or x.isdir():
                continue
            alias = ' alias="library"' if x == p/'library.png' else ''
            files.append('<file%s>%s</file>'%(alias, x))
        qrc = '<RCC>\n<qresource prefix="/">\n%s\n</qresource>\n</RCC>'%'\n'.join(files)
        f = open('images.qrc', 'wb')
        f.write(qrc)
        f.close()
        check_call(' '.join(['pyrcc4', '-o', images, 'images.qrc']))
        compiler.compileFile(images)
        os.utime(images, None)
        os.utime(images, None)
        print 'Size of images:', '%.2f MB'%(path(images+'c').size/(1024*1024.))
        
            
def build(forms):
    build_forms(forms)
    build_images()

def clean(forms):
    for form in forms:
        compiled_form = form_to_compiled_form(form)
        if os.path.exists(compiled_form):
            print 'Removing compiled form', compiled_form
            os.unlink(compiled_form)
    print 'Removing compiled images'
    os.unlink('images_rc.py')
    os.unlink('images_rc.pyc')

def main(args=sys.argv):
    
    if not os.getcwd().endswith('gui2'):
        raise Exception('Must be run from the gui2 directory')
    
    forms = find_forms()
    if len(args) == 1:
        args.append('all')
    
    if   args[1] == 'all':
        build(forms)
    elif args[1] == 'clean':
        clean(forms)
    elif args[1] == 'test':
        build(forms)
        print 'Running main.py'
        subprocess.call('python main.py', shell=True)
    else:
        print 'Usage: %s [all|clean|test]'%(args[0])
        return 1 
    
    return 0

if __name__ == '__main__':
    sys.exit(main())