#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Freeze app into executable using py2exe.
'''
QT_DIR           = 'C:\\Qt\\4.4.0'
DEVCON           = 'C:\\devcon\\i386\\devcon.exe'
LIBUSB_DIR       = 'C:\\libusb'
LIBUNRAR         = 'C:\\Program Files\\UnrarDLL\\unrar.dll'
CLIT             = 'C:\\clit\\clit.exe'
PDFTOHTML        = 'C:\\pdftohtml\\pdftohtml.exe'
IMAGEMAGICK_DIR  = 'C:\\ImageMagick'
FONTCONFIG_DIR   = 'C:\\fontconfig'


import sys, os, py2exe, shutil, zipfile, glob, subprocess
from distutils.core import setup
from distutils.filelist import FileList
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, BASE_DIR)
from setup import VERSION, APPNAME, entry_points, scripts, basenames
sys.path.remove(BASE_DIR)

PY2EXE_DIR = os.path.join(BASE_DIR, 'build','py2exe')

class BuildEXE(py2exe.build_exe.py2exe):
    manifest_resource_id = 0
     
    MANIFEST_TEMPLATE = '''
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0"> 
  <assemblyIdentity version="%(version)s"
     processorArchitecture="x86"
     name="net.kovidgoyal.%(prog)s"
     type="win32"
     /> 
  <description>Ebook management application</description> 
  <!-- Identify the application security requirements. -->
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v2">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel
          level="asInvoker"
          uiAccess="false"/>
        </requestedPrivileges>
       </security>
  </trustInfo>
</assembly>
'''
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
        qtsvgdll = None
        for other in self.other_depends:
            if 'qtsvg4.dll' in other.lower():
                qtsvgdll = other
                break
        shutil.copyfile('LICENSE', os.path.join(self.dist_dir, 'LICENSE'))
        print
        if qtsvgdll:
            print 'Adding', qtsvgdll
            shutil.copyfile(qtsvgdll, os.path.join(self.dist_dir, os.path.basename(qtsvgdll)))
            qtxmldll = os.path.join(os.path.dirname(qtsvgdll), 'QtXml4.dll')
            print 'Adding', qtxmldll
            shutil.copyfile(qtxmldll, 
                            os.path.join(self.dist_dir, os.path.basename(qtxmldll)))
        print 'Adding Qt plugins...',
        qt_prefix = QT_DIR
        if qtsvgdll:
            qt_prefix = os.path.dirname(os.path.dirname(qtsvgdll))
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
        print 'Adding third party dependencies'
        print '\tAdding devcon'
        tdir = os.path.join(PY2EXE_DIR, 'driver')
        os.makedirs(tdir)
        for pat in ('*.dll', '*.sys', '*.cat', '*.inf'):
            for f in glob.glob(os.path.join(LIBUSB_DIR, pat)):
                shutil.copyfile(f, os.path.join(tdir, os.path.basename(f)))
        shutil.copyfile(DEVCON, os.path.join(tdir, os.path.basename(DEVCON)))
        print '\tAdding unrar'
        shutil.copyfile(LIBUNRAR, os.path.join(PY2EXE_DIR, os.path.basename(LIBUNRAR)))
        print '\tAdding ConvertLIT'
        shutil.copyfile(CLIT, os.path.join(PY2EXE_DIR, os.path.basename(CLIT)))
        print '\tAdding pdftohtml'
        shutil.copyfile(PDFTOHTML, os.path.join(PY2EXE_DIR, os.path.basename(PDFTOHTML)))
        print '\tAdding ImageMagick'
        shutil.copytree(IMAGEMAGICK_DIR, os.path.join(PY2EXE_DIR, 'ImageMagick'))
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
        
        
    @classmethod
    def manifest(cls, prog):
        cls.manifest_resource_id += 1
        return (24, cls.manifest_resource_id, 
                cls.MANIFEST_TEMPLATE % dict(prog=prog, version=VERSION+'.0'))


def main(args=sys.argv):
    sys.argv[1:2] = ['py2exe']
    if os.path.exists(PY2EXE_DIR):
        shutil.rmtree(PY2EXE_DIR)

    console = [dict(dest_base=basenames['console'][i], script=scripts['console'][i])
               for i in range(len(scripts['console']))]
    
    setup(
          cmdclass = {'py2exe': BuildEXE},
          windows = [
                     {'script'          : scripts['gui'][0],
                      'dest_base'       : APPNAME,
                      'icon_resources'  : [(1, os.path.join(BASE_DIR, 'icons', 'library.ico'))],
                      'other_resources' : [BuildEXE.manifest(APPNAME)],
                      },
                      {'script'         : scripts['gui'][1],
                      'dest_base'       : 'lrfviewer',
                      'icon_resources'  : [(1, os.path.join(BASE_DIR, 'icons', 'viewer.ico'))],
                      'other_resources' : [BuildEXE.manifest('lrfviewer')],
                      },
                      ],
          console = console,
          options = { 'py2exe' : {'compressed': 1,
                                  'optimize'  : 2,
                                  'dist_dir'  : PY2EXE_DIR,
                                  'includes'  : [
                                             'sip', 'pkg_resources', 'PyQt4.QtSvg',
                                             'mechanize', 'ClientForm', 'wmi',
                                             'win32file', 'pythoncom', 'rtf2xml',
                                             'win32process', 'win32api', 'msvcrt',
                                             'win32event', 'calibre.ebooks.lrf.any.*',
                                             'calibre.ebooks.lrf.feeds.*',
                                             'lxml', 'lxml._elementpath', 'genshi',
                                             'path', 'pydoc', 'IPython.Extensions.*',
                                             'calibre.web.feeds.recipes.*',
                                             'PyQt4.QtWebKit', 'PyQt4.QtNetwork',
                                             ],
                                  'packages'  : ['PIL'],
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