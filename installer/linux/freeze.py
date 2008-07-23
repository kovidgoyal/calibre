#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Create linux binary.
'''
import glob, sys, subprocess, tarfile, os, re, py_compile, shutil
HOME           = '/home/kovid'
PYINSTALLER    = os.path.expanduser('~/build/pyinstaller')
CALIBREPREFIX  = '___'
CLIT           = '/usr/bin/clit'
PDFTOHTML      = '/usr/bin/pdftohtml'
LIBUNRAR       = '/usr/lib/libunrar.so'
QTDIR          = '/usr/lib/qt4'
QTDLLS         = ('QtCore', 'QtGui', 'QtNetwork', 'QtSvg', 'QtXml')
EXTRAS         = ('/usr/lib/python2.5/site-packages/PIL', os.path.expanduser('~/ipython/IPython'))


CALIBRESRC     = os.path.join(CALIBREPREFIX, 'src')
CALIBREPLUGINS = os.path.join(CALIBRESRC, 'calibre', 'plugins')

sys.path.insert(0, CALIBRESRC)
from calibre import __version__
from calibre.parallel import PARALLEL_FUNCS
from calibre.web.feeds.recipes import recipes
hiddenimports = map(lambda x: x[0], PARALLEL_FUNCS.values())
hiddenimports += ['lxml._elementpath', 'keyword', 'codeop', 'commands', 'shlex', 'pydoc']
hiddenimports += map(lambda x: x.__module__, recipes)
open(os.path.join(PYINSTALLER, 'hooks', 'hook-calibre.parallel.py'), 'wb').write('hiddenimports = %s'%repr(hiddenimports))

def run_pyinstaller(args=sys.argv):
    subprocess.check_call(('/usr/bin/sudo', 'chown', '-R', 'kovid:users', glob.glob('/usr/lib/python*/site-packages/')[-1]))
    subprocess.check_call('rm -rf %(py)s/dist/* %(py)s/build/*'%dict(py=PYINSTALLER), shell=True)
    cp = HOME+'/build/'+os.path.basename(os.getcwd())
    spec = open(os.path.join(PYINSTALLER, 'calibre', 'calibre.spec'), 'wb')
    raw = re.sub(r'CALIBREPREFIX\s+=\s+\'___\'', 'CALIBREPREFIX = '+repr(cp),
                 open(__file__).read())
    spec.write(raw)
    spec.close()
    os.chdir(PYINSTALLER)
    shutil.rmtree('calibre/dist')
    os.mkdir('calibre/dist')
    subprocess.check_call('python -OO Build.py calibre/calibre.spec', shell=True)
                
    return 0


if __name__ == '__main__' and 'freeze.py' in __file__:
    sys.exit(run_pyinstaller())


loader = os.path.join(os.path.expanduser('~/temp'), 'calibre_installer_loader.py')
if not os.path.exists(loader):
    open(loader, 'wb').write('''
import sys, os
sys.frozen_path = os.getcwd()
os.chdir(os.environ.get("ORIGWD", "."))
sys.path.insert(0, os.path.join(sys.frozen_path, "library.pyz"))
sys.path.insert(0, sys.frozen_path)
from PyQt4.QtCore import QCoreApplication
QCoreApplication.setLibraryPaths([sys.frozen_path, os.path.join(sys.frozen_path, "qtplugins")])
''')
excludes = ['gtk._gtk', 'gtk.glade', 'qt', 'matplotlib.nxutils', 'matplotlib._cntr',
            'matplotlib.ttconv', 'matplotlib._image', 'matplotlib.ft2font',
            'matplotlib._transforms', 'matplotlib._agg', 'matplotlib.backends._backend_agg',
            'matplotlib.axes', 'matplotlib', 'matplotlib.pyparsing',
            'TKinter', 'atk', 'gobject._gobject', 'pango', 'PIL', 'Image', 'IPython']


sys.path.insert(0, CALIBRESRC)
from calibre.linux import entry_points

executables, scripts = ['calibre_postinstall', 'calibre-parallel'], \
                       [os.path.join(CALIBRESRC, 'calibre', 'linux.py'), os.path.join(CALIBRESRC, 'calibre', 'parallel.py')]

for entry in entry_points['console_scripts'] + entry_points['gui_scripts']:
    fields = entry.split('=')
    executables.append(fields[0].strip())
    scripts.append(os.path.join(CALIBRESRC, *map(lambda x: x.strip(), fields[1].split(':')[0].split('.')))+'.py')

analyses = [Analysis([os.path.join(HOMEPATH,'support/_mountzlib.py'), os.path.join(HOMEPATH,'support/useUnicode.py'), loader, script],
             pathex=[PYINSTALLER, CALIBRESRC], excludes=excludes) for script in scripts]

pyz = TOC()
binaries = TOC()

for a in analyses:
    pyz = a.pure + pyz
    binaries = a.binaries + binaries
pyz = PYZ(pyz, name='library.pyz')

built_executables = []
for script, exe, a in zip(scripts, executables, analyses):
    built_executables.append(EXE(PYZ(TOC()),
    a.scripts+[('O','','OPTION'),],
    exclude_binaries=1,
    name=os.path.join('buildcalibre', exe),
    debug=False,
    strip=True,
    upx=False,
    excludes=excludes,
    console=1))

print 'Adding plugins...'
for f in glob.glob(os.path.join(CALIBREPLUGINS, '*.so')):
    binaries += [('plugins/'+os.path.basename(f), f, 'BINARY')]
for f in glob.glob(os.path.join(CALIBREPLUGINS, '*.so.*')):
    binaries += [(os.path.basename(f), f, 'BINARY')]

print 'Adding external programs...'
binaries += [('clit', CLIT, 'BINARY'), ('pdftohtml', PDFTOHTML, 'BINARY'),
             ('libunrar.so', LIBUNRAR, 'BINARY')]
qt = []
for dll in QTDLLS:
    path = os.path.join(QTDIR, 'lib'+dll+'.so.4')
    qt.append((os.path.basename(path), path, 'BINARY'))
binaries += qt

plugins = []
plugdir = os.path.join(QTDIR, 'plugins')
for dirpath, dirnames, filenames in os.walk(plugdir):
    for f in filenames:
        if not f.endswith('.so') or 'designer' in dirpath or 'codcs' in dirpath or 'sqldrivers' in dirpath : continue
        f = os.path.join(dirpath, f)
        plugins.append(('qtplugins/'+f.replace(plugdir, ''), f, 'BINARY'))
binaries += plugins

manifest = '/tmp/manifest'
open(manifest, 'wb').write('\n'.join(executables))
version = '/tmp/version'
open(version, 'wb').write(__version__)
coll = COLLECT(binaries, pyz, 
               [('manifest', manifest, 'DATA'), ('version', version, 'DATA')],
               *built_executables,
               **dict(strip=True,
               upx=False,
               excludes=excludes,
               name='dist'))

os.chdir(os.path.join(HOMEPATH, 'calibre', 'dist'))
for folder in EXTRAS:
    subprocess.check_call('cp -rf %s .'%folder, shell=True)

print 'Building tarball...'
tbz2 = 'calibre-%s-i686.tar.bz2'%__version__
tf = tarfile.open(os.path.join('/tmp', tbz2), 'w:bz2')

for f in os.listdir('.'):
    tf.add(f)
