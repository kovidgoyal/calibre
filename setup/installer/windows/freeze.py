#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Freeze app into executable using py2exe.
'''
QT_DIR           = 'C:\\Qt\\4.5.2'
LIBUSB_DIR       = 'C:\\libusb'
LIBUNRAR         = 'C:\\Program Files\\UnrarDLL\\unrar.dll'
IMAGEMAGICK_DIR  = 'C:\\ImageMagick'
SW               = r'C:\cygwin\home\kovid\sw'

import sys

def fix_module_finder():
    # ModuleFinder can't handle runtime changes to __path__, but win32com uses them
    import py2exe.mf as modulefinder
    import win32com
    for p in win32com.__path__[1:]:
        modulefinder.AddPackagePath("win32com", p)
    for extra in ["win32com.shell"]: #,"win32com.mapi"
        __import__(extra)
        m = sys.modules[extra]
        for p in m.__path__[1:]:
            modulefinder.AddPackagePath(extra, p)


import os, shutil, zipfile, glob, re
from distutils.core import setup
from setup import __version__ as VERSION, __appname__ as APPNAME, scripts, \
    basenames, SRC, Command

BASE_DIR = os.path.dirname(SRC)
ICONS = [os.path.abspath(os.path.join(BASE_DIR, 'icons', i)) for i in ('library.ico', 'viewer.ico')]
for icon in ICONS:
    if not os.access(icon, os.R_OK):
        raise Exception('No icon at '+icon)

VERSION = re.sub('[a-z]\d+', '', VERSION)
WINVER = VERSION+'.0'

PY2EXE_DIR = os.path.join(BASE_DIR, 'build','py2exe')

info = warn = None

class Win32Freeze(Command):

    description = 'Freeze windows calibre installation'

    def run(self, opts):
        global info, warn
        info, warn = self.info, self.warn
        main()

BOOT_COMMON = '''\
import sys, os
if sys.frozen == "windows_exe":
    class Stderr(object):
        softspace = 0
        _file = None
        _error = None
        def write(self, text, alert=sys._MessageBox, fname=os.path.expanduser('~\calibre.log')):
            if self._file is None and self._error is None:
                try:
                    self._file = open(fname, 'wb')
                except Exception, details:
                    self._error = details
                    import atexit
                    atexit.register(alert, 0,
                                    ("The logfile %s could not be opened: "
                                    "\\n%s\\n\\nTry setting the HOME environment "
                                    "variable to a directory for which you "
                                    "have write permission.") % (fname, details),
                                    "Errors occurred")
                else:
                    import atexit
                    #atexit.register(alert, 0,
                    #                "See the logfile '%s' for details" % fname,
                    #                "Errors occurred")
            if self._file is not None:
                self._file.write(text)
                self._file.flush()
        def flush(self):
            if self._file is not None:
                self._file.flush()

    #del sys._MessageBox
    #del Stderr

    class Blackhole(object):
        softspace = 0
        def write(self, text):
            pass
        def flush(self):
            pass
    sys.stdout = Stderr()
    sys.stderr = Stderr()
    del Blackhole

# Disable linecache.getline() which is called by
# traceback.extract_stack() when an exception occurs to try and read
# the filenames embedded in the packaged python code.  This is really
# annoying on windows when the d: or e: on our build box refers to
# someone elses removable or network drive so the getline() call
# causes it to ask them to insert a disk in that drive.
import linecache
def fake_getline(filename, lineno, module_globals=None):
    return ''
linecache.orig_getline = linecache.getline
linecache.getline = fake_getline

del linecache, fake_getline

fenc = sys.getfilesystemencoding( )
base = os.path.dirname(sys.executable.decode(fenc))
sys.resources_location = os.path.join(base, 'resources')
sys.extensions_location = os.path.join(base, 'plugins')

dv = os.environ.get('CALIBRE_DEVELOP_FROM', None)
if dv and os.path.exists(dv):
    sys.path.insert(0, os.path.abspath(dv))

del sys
'''

try:
    import py2exe
    bc = py2exe.build_exe.py2exe
except ImportError:
    py2exe = object
    bc = object

class BuildEXE(bc):

    def run(self):
        py2exe.build_exe.py2exe.run(self)
        info('\nAdding plugins...')
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


        info('\nAdding resources...')
        tgt = os.path.join(self.dist_dir, 'resources')
        if os.path.exists(tgt):
            shutil.rmtree(tgt)
        shutil.copytree(os.path.join(BASE_DIR, 'resources'), tgt)

        info('\nAdding QtXml4.dll')
        shutil.copyfile(os.path.join(QT_DIR, 'bin', 'QtXml4.dll'),
                            os.path.join(self.dist_dir, 'QtXml4.dll'))
        info('\nAdding Qt plugins...')
        qt_prefix = QT_DIR
        plugdir = os.path.join(qt_prefix, 'plugins')
        for d in ('imageformats', 'codecs', 'iconengines'):
            info(d)
            imfd = os.path.join(plugdir, d)
            tg = os.path.join(self.dist_dir, d)
            if os.path.exists(tg):
                shutil.rmtree(tg)
            shutil.copytree(imfd, tg)

        info('Adding main scripts')
        f = zipfile.ZipFile(os.path.join(PY2EXE_DIR, 'library.zip'), 'a', zipfile.ZIP_DEFLATED)
        for i in scripts['console'] + scripts['gui']:
            f.write(i, i.partition('\\')[-1])
        f.close()

        info('Copying icons')
        for icon in ICONS:
            shutil.copyfile(icon, os.path.join(PY2EXE_DIR, os.path.basename(icon)))

        print
        print 'Adding third party dependencies'
        tdir = os.path.join(PY2EXE_DIR, 'driver')
        os.makedirs(tdir)
        for pat in ('*.dll', '*.sys', '*.cat', '*.inf'):
            for f in glob.glob(os.path.join(LIBUSB_DIR, pat)):
                shutil.copyfile(f, os.path.join(tdir, os.path.basename(f)))
        print '\tAdding unrar'
        shutil.copyfile(LIBUNRAR, os.path.join(PY2EXE_DIR, os.path.basename(LIBUNRAR)))

        print '\tAdding misc binary deps'
        bindir = os.path.join(SW, 'bin')
        shutil.copy2(os.path.join(bindir, 'pdftohtml.exe'), PY2EXE_DIR)
        for pat in ('*.dll', '*.xml'):
            for f in glob.glob(os.path.join(bindir, pat)):
                shutil.copy2(f, PY2EXE_DIR)
        for x in ('Microsoft.VC90.CRT', 'zlib1.dll', 'libxml2.dll'):
            shutil.copy2(os.path.join(bindir, x+'.manifest'), PY2EXE_DIR)
        shutil.copytree(os.path.join(SW, 'etc', 'fonts'),
						os.path.join(PY2EXE_DIR, 'fontconfig'))

        print
        print 'Doing DLL redirection' # See http://msdn.microsoft.com/en-us/library/ms682600(VS.85).aspx
        for f in glob.glob(os.path.join(PY2EXE_DIR, '*.exe')):
            open(f + '.local', 'w').write('\n')



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

    fix_module_finder()

    boot_common = os.path.join(sys.prefix, 'Lib', 'site-packages', 'py2exe',
    'boot_common.py')
    open(boot_common, 'wb').write(BOOT_COMMON)

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
                                             'email.iterators',
                                             'email.generator',
                                             'win32process', 'win32api', 'msvcrt',
                                             'win32event',
                                             'sqlite3.dump',
                                             'BeautifulSoup', 'pyreadline',
                                             'pydoc', 'IPython.Extensions.*',
                                             'calibre.web.feeds.recipes.*',
                                             'calibre.gui2.convert.*',
                                             'calibre.ebooks.lrf.fonts.prs500.*',
                                             'PyQt4.QtWebKit', 'PyQt4.QtNetwork',
                                             ],
                                  'packages'  : ['PIL', 'lxml', 'cherrypy',
                                                 'dateutil', 'dns'],
                                  'excludes'  : ["Tkconstants", "Tkinter", "tcl",
                                                 "_imagingtk", "ImageTk",
                                                 "FixTk",
                                                 'PyQt4.uic.port_v3.proxy_base'
                                                ],
                                  'dll_excludes' : ['mswsock.dll', 'tcl85.dll',
                                      'tk85.dll'],
                                 },
                    },

          )
    return 0



