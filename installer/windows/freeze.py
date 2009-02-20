#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Freeze app into executable using py2exe.
'''
QT_DIR           = 'C:\\Qt\\4.4.3'
LIBUSB_DIR       = 'C:\\libusb'
LIBUNRAR         = 'C:\\Program Files\\UnrarDLL\\unrar.dll'
PDFTOHTML        = 'C:\\pdftohtml\\pdftohtml.exe'
IMAGEMAGICK_DIR  = 'C:\\ImageMagick'
FONTCONFIG_DIR   = 'C:\\fontconfig'
VC90             = r'C:\VC90.CRT'

import sys, os, py2exe, shutil, zipfile, glob, subprocess, re
from distutils.core import setup
from distutils.filelist import FileList
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, BASE_DIR)
from setup import VERSION, APPNAME, entry_points, scripts, basenames
sys.path.remove(BASE_DIR)

ICONS = [os.path.abspath(os.path.join(BASE_DIR, 'icons', i)) for i in ('library.ico', 'viewer.ico')]
for icon in ICONS:
    if not os.access(icon, os.R_OK):
        raise Exception('No icon at '+icon)

VERSION = re.sub('[a-z]\d+', '', VERSION)
WINVER = VERSION+'.0'

PY2EXE_DIR = os.path.join(BASE_DIR, 'build','py2exe')

class BuildEXE(py2exe.build_exe.py2exe):
    
    def run(self):
        py2exe.build_exe.py2exe.run(self)
        print 'Adding plugins...'
        tgt = os.path.join(self.dist_dir, 'plugins')
        if not os.path.exists(tgt):
            os.mkdir(tgt)
        for f in glob.glob(os.path.join(BASE_DIR, 'src', 'calibre', 'plugins', '*.dll')):
            shutil.copyfile(f, os.path.join(self.dist_dir, os.path.basename(f)))
        for f in glob.glob(os.path.join(BASE_DIR, 'src', 'calibre', 'plugins', '*.pyd')):
            shutil.copyfile(f, os.path.join(tgt, os.path.basename(f)))
        for f in glob.glob(os.path.join(BASE_DIR, 'src', 'calibre', 'plugins', '*.manifest')):
            shutil.copyfile(f, os.path.join(tgt, os.path.basename(f)))
        shutil.copyfile('LICENSE', os.path.join(self.dist_dir, 'LICENSE'))
        print
        print 'Adding QtXml4.dll'
        shutil.copyfile(os.path.join(QT_DIR, 'bin', 'QtXml4.dll'),
                            os.path.join(self.dist_dir, 'QtXml4.dll'))
        print 'Adding Qt plugins...',
        qt_prefix = QT_DIR
        plugdir = os.path.join(qt_prefix, 'plugins')
        for d in ('imageformats', 'codecs', 'iconengines'):
            print d,
            imfd = os.path.join(plugdir, d)
            tg = os.path.join(self.dist_dir, d)
            if os.path.exists(tg):
                shutil.rmtree(tg)
            shutil.copytree(imfd, tg)
            
        print 
        print 'Adding main scripts'
        f = zipfile.ZipFile(os.path.join(PY2EXE_DIR, 'library.zip'), 'a', zipfile.ZIP_DEFLATED)
        for i in scripts['console'] + scripts['gui']:
            f.write(i, i.partition('\\')[-1])
        f.close()
        
        print
        print 'Copying icons'
        for icon in ICONS:
            shutil.copyfile(icon, os.path.join(PY2EXE_DIR, os.path.basename(icon)))
        
        print
        print 'Adding third party dependencies'
        print '\tAdding devcon'
        tdir = os.path.join(PY2EXE_DIR, 'driver')
        os.makedirs(tdir)
        for pat in ('*.dll', '*.sys', '*.cat', '*.inf'):
            for f in glob.glob(os.path.join(LIBUSB_DIR, pat)):
                shutil.copyfile(f, os.path.join(tdir, os.path.basename(f)))
        print '\tAdding unrar'
        shutil.copyfile(LIBUNRAR, os.path.join(PY2EXE_DIR, os.path.basename(LIBUNRAR)))
        print '\tAdding pdftohtml'
        shutil.copyfile(PDFTOHTML, os.path.join(PY2EXE_DIR, os.path.basename(PDFTOHTML)))
        print '\tAdding ImageMagick'
        for f in os.listdir(IMAGEMAGICK_DIR):
            shutil.copyfile(os.path.join(IMAGEMAGICK_DIR, f), os.path.join(PY2EXE_DIR, f))
        print '\tCopying fontconfig'
        for f in glob.glob(os.path.join(FONTCONFIG_DIR, '*')):
            tgt = os.path.join(PY2EXE_DIR, os.path.basename(f))
            if os.path.isdir(f):
                shutil.copytree(f, tgt)
            else:
                shutil.copyfile(f, tgt)
                
        print 
        print 'Doing DLL redirection' # See http://msdn.microsoft.com/en-us/library/ms682600(VS.85).aspx
        for f in glob.glob(os.path.join(PY2EXE_DIR, '*.exe')):
            open(f + '.local', 'w').write('\n')
        
        print
        print 'Adding Windows runtime dependencies...'
        for f in glob.glob(os.path.join(VC90, '*')):
            shutil.copyfile(f, os.path.join(PY2EXE_DIR, os.path.basename(f)))
        
    
def exe_factory(dest_base, script, icon_resources=None):
    exe = {
           'dest_base'       : dest_base,
           'script'          : script,
           'name'            : dest_base,
           'version'         : WINVER,
           'description'     : 'calibre - E-book library management',
           'author'          : 'Kovid Goyal',
           'copyright'       : '(c) Kovid Goyal, 2008',
           'company'         : 'kovidgoyal.net',
           }
    if icon_resources is not None:
        exe['icon_resources'] = icon_resources
    return exe

def main(args=sys.argv):
    sys.argv[1:2] = ['py2exe']
    if os.path.exists(PY2EXE_DIR):
        shutil.rmtree(PY2EXE_DIR)

    console = [exe_factory(basenames['console'][i], scripts['console'][i])
               for i in range(len(scripts['console']))]
    setup(
          cmdclass = {'py2exe': BuildEXE},
          windows = [
                     exe_factory(APPNAME, scripts['gui'][0], [(1, ICONS[0])]),
                     exe_factory('lrfviewer', scripts['gui'][1], [(1, ICONS[1])]),
                     exe_factory('ebook-viewer', scripts['gui'][2], [(1, ICONS[1])]),
                    ],
          console = console,
          options = { 'py2exe' : {'compressed': 1,
                                  'optimize'  : 2,
                                  'dist_dir'  : PY2EXE_DIR,
                                  'includes'  : [
                                             'sip', 'pkg_resources', 'PyQt4.QtSvg',
                                             'mechanize', 'ClientForm', 'wmi',
                                             'win32file', 'pythoncom', 
                                             'win32process', 'win32api', 'msvcrt',
                                             'win32event', 'calibre.ebooks.lrf.any.*',
                                             'calibre.ebooks.lrf.feeds.*',
                                             'BeautifulSoup', 'pyreadline',
                                             'pydoc', 'IPython.Extensions.*',
                                             'calibre.web.feeds.recipes.*',
                                             'calibre.ebooks.lrf.fonts.prs500.*',
                                             'PyQt4.QtWebKit', 'PyQt4.QtNetwork',
                                             ],
                                  'packages'  : ['PIL', 'lxml', 'cherrypy',
                                                 'dateutil'],
                                  'excludes'  : ["Tkconstants", "Tkinter", "tcl",
                                                 "_imagingtk", "ImageTk", "FixTk"
                                                ],
                                  'dll_excludes' : ['mswsock.dll'],
                                 },
                    },
          
          )
    return 0

if __name__ == '__main__':
    sys.exit(main())
