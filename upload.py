#!/usr/bin/python
import tempfile
import sys, os, shutil, time
sys.path.append('src')
import subprocess
from subprocess import check_call as _check_call
from functools import partial
#from pyvix.vix import Host, VIX_SERVICEPROVIDER_VMWARE_WORKSTATION

from calibre import __version__, __appname__

PREFIX = "/var/www/calibre.kovidgoyal.net"
DOWNLOADS = PREFIX+"/htdocs/downloads"
DOCS = PREFIX+"/htdocs/apidocs"
USER_MANUAL = PREFIX+'/htdocs/user_manual'
HTML2LRF = "src/calibre/ebooks/lrf/html/demo"
TXT2LRF  = "src/calibre/ebooks/lrf/txt/demo"
check_call = partial(_check_call, shell=True)
#h = Host(hostType=VIX_SERVICEPROVIDER_VMWARE_WORKSTATION)


def tag_release():
    print 'Tagging release'
    check_call('bzr tag '+__version__)
    check_call('bzr commit --unchanged -m "IGN:Tag release"')
            
def build_installer(installer, vm, timeout=25):
    if os.path.exists(installer):
        os.unlink(installer)
    f = open('dist/auto', 'wb')
    f.write('\n')
    f.close()
    print 'Building installer %s ...'%installer
    vmware = ('vmware', '-q', '-x', '-n', vm)
    try:
        p = subprocess.Popen(vmware)
        print 'Waiting...',
        minutes = 0
        sys.stdout.flush()
        while p.returncode is None and minutes < timeout and not os.path.exists(installer):
            p.poll()
            time.sleep(60)
            minutes += 1
            print minutes,
            sys.stdout.flush()
        print
        if not os.path.exists(installer):
            raise Exception('Failed to build installer '+installer)
    finally:
        os.unlink('dist/auto')
    
        
    return os.path.basename(installer)

def installer_name(ext):
    if ext in ('exe', 'dmg'):
        return 'dist/%s-%s.%s'%(__appname__, __version__, ext)
    return 'dist/%s-%s-i686.%s'%(__appname__, __version__, ext)

def build_windows():
    installer = installer_name('exe')
    vm = '/vmware/Windows XP/Windows XP Professional.vmx'
    return build_installer(installer, vm, 20)
    

def build_osx():
    installer = installer_name('dmg')
    vm = '/vmware/Mac OSX/Mac OSX.vmx'
    vmware = ('vmware', '-q', '-x', '-n', vm)
    subprocess.Popen(vmware)
    print 'Waiting for OS X to boot up...'
    time.sleep(120)
    print 'Trying to ssh into the OS X server'
    subprocess.check_call(('ssh', 'osx', '/Users/kovid/bin/build-calibre'))
    if not os.path.exists(installer):
        raise Exception('Failed to build installer '+installer)
    subprocess.Popen(('ssh', 'osx', 'sudo', '/sbin/shutdown', '-h', '+1'))
    return os.path.basename(installer)
    #return build_installer(installer, vm, 20)
  
def _build_linux():
    cwd = os.getcwd()
    tbz2 = os.path.join(cwd, installer_name('tar.bz2'))
    SPEC="""\
HOME           = '%s'
PYINSTALLER    = HOME+'/build/pyinstaller'
CALIBREPREFIX  = HOME+'/work/calibre'
CLIT           = '/usr/bin/clit'
PDFTOHTML      = '/usr/bin/pdftohtml'
LIBUNRAR       = '/usr/lib/libunrar.so'
QTDIR          = '/usr/lib/qt4'
QTDLLS         = ('QtCore', 'QtGui', 'QtNetwork', 'QtSvg', 'QtXml')

import glob, sys, subprocess, tarfile
CALIBRESRC     = os.path.join(CALIBREPREFIX, 'src')
CALIBREPLUGINS = os.path.join(CALIBRESRC, 'calibre', 'plugins')

subprocess.check_call(('/usr/bin/sudo', 'chown', '-R', 'kovid:users', glob.glob('/usr/lib/python*/site-packages/')[-1]))

loader = os.path.join('/tmp', 'calibre_installer_loader.py')
if not os.path.exists(loader):
    open(loader, 'wb').write('''
import sys, os
sys.frozen_path = os.getcwd()
os.chdir(os.environ.get("ORIGWD", "."))
sys.path.insert(0, os.path.join(sys.frozen_path, "library.pyz"))
sys.path.insert(0, sys.frozen_path)
from PyQt4.QtCore import QCoreApplication
QCoreApplication.setLibraryPaths([sys.frozen_path, os.path.join(sys.frozen_path, "plugins")])
''')
excludes = ['gtk._gtk', 'gtk.glade', 'qt', 'matplotlib.nxutils', 'matplotlib._cntr',
            'matplotlib.ttconv', 'matplotlib._image', 'matplotlib.ft2font',
            'matplotlib._transforms', 'matplotlib._agg', 'matplotlib.backends._backend_agg',
            'matplotlib.axes', 'matplotlib', 'matplotlib.pyparsing',
            'TKinter', 'atk', 'gobject._gobject', 'pango']
temp = ['IPython.Extensions.ipy_profile_none']

recipes = ['calibre', 'web', 'feeds', 'recipes']
prefix  = '.'.join(recipes)+'.'
for f in glob.glob(os.path.join(CALIBRESRC, *(recipes+['*.py']))):
    temp.append(prefix + os.path.basename(f).partition('.')[0])
hook = '/tmp/hook-calibre.py'
open(hook, 'wb').write('hiddenimports = %%s'%%repr(temp) + '\\n')

sys.path.insert(0, CALIBRESRC)
from calibre.linux import entry_points

executables, scripts = ['calibre_postinstall', 'parallel'], \
                       [os.path.join(CALIBRESRC, 'calibre', 'linux.py'), os.path.join(CALIBRESRC, 'calibre', 'parallel.py')]

for entry in entry_points['console_scripts'] + entry_points['gui_scripts']:
    fields = entry.split('=')
    executables.append(fields[0].strip())
    scripts.append(os.path.join(CALIBRESRC, *map(lambda x: x.strip(), fields[1].split(':')[0].split('.')))+'.py')

recipes = Analysis(glob.glob(os.path.join(CALIBRESRC, 'calibre', 'web', 'feeds', 'recipes', '*.py')),
                   pathex=[CALIBRESRC], hookspath=[os.path.dirname(hook)], excludes=excludes)
analyses = [Analysis([os.path.join(HOMEPATH,'support/_mountzlib.py'), os.path.join(HOMEPATH,'support/useUnicode.py'), loader, script],
             pathex=[PYINSTALLER, CALIBRESRC, CALIBREPLUGINS], excludes=excludes) for script in scripts]

pyz = TOC()
binaries = TOC()

for a in analyses:
    pyz = a.pure + pyz
    binaries = a.binaries + binaries
pyz = PYZ(pyz + recipes.pure, name='library.pyz')

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
        plugins.append(('plugins/'+f.replace(plugdir, ''), f, 'BINARY'))
binaries += plugins

manifest = '/tmp/manifest'
open(manifest, 'wb').write('\\n'.join(executables))
from calibre import __version__
version = '/tmp/version'
open(version, 'wb').write(__version__)
coll = COLLECT(binaries, pyz, [('manifest', manifest, 'DATA'), ('version', version, 'DATA')],
               *built_executables,
               **dict(strip=True,
               upx=False,
               excludes=excludes,
               name='dist'))

print 'Building tarball...'
tf = tarfile.open('%s', 'w:bz2')
os.chdir(os.path.join(HOMEPATH, 'calibre', 'dist'))
for f in os.listdir('.'):
    tf.add(f)
    
"""%('/mnt/hgfs/giskard/', tbz2)
    os.chdir(os.path.expanduser('~/build/pyinstaller'))
    open('calibre/calibre.spec', 'wb').write(SPEC)
    try:
        subprocess.check_call(('/usr/bin/python', '-O', 'Build.py', 'calibre/calibre.spec'))
    finally:
        os.chdir(cwd)
    return os.path.basename(tbz2)

def build_linux():
    vm = '/vmware/linux/libprs500-gentoo.vmx'
    vmware = ('vmware', '-q', '-x', '-n', vm)
    subprocess.Popen(vmware)
    print 'Waiting for linux to boot up...'
    time.sleep(60)
    check_call('ssh linux make -C /mnt/hgfs/giskard/work/calibre all egg linux_binary')
    check_call('ssh sudo poweroff')

def build_installers():
    return build_linux(), build_windows(), build_osx()

def upload_demo():
    check_call('''html2lrf --title='Demonstration of html2lrf' --author='Kovid Goyal' '''
               '''--header --output=/tmp/html2lrf.lrf %s/demo.html '''
               '''--serif-family "/usr/share/fonts/corefonts, Times New Roman" '''
               '''--mono-family  "/usr/share/fonts/corefonts, Andale Mono" '''
               ''''''%(HTML2LRF,))
    check_call('cd src/calibre/ebooks/lrf/html/demo/ && zip -j /tmp/html-demo.zip * /tmp/html2lrf.lrf')
    check_call('''scp /tmp/html-demo.zip divok:%s/'''%(DOWNLOADS,))
    check_call('''txt2lrf -t 'Demonstration of txt2lrf' -a 'Kovid Goyal' '''
               '''--header -o /tmp/txt2lrf.lrf %s/demo.txt'''%(TXT2LRF,) )
    check_call('cd src/calibre/ebooks/lrf/txt/demo/ && zip -j /tmp/txt-demo.zip * /tmp/txt2lrf.lrf')
    check_call('''scp /tmp/txt-demo.zip divok:%s/'''%(DOWNLOADS,))

def upload_installers():
    exe, dmg, tbz2 = installer_name('exe'), installer_name('dmg'), installer_name('tar.bz2')
    if exe and os.path.exists(exe):
        check_call('''ssh divok rm -f %s/calibre\*.exe'''%(DOWNLOADS,))
        check_call('''scp %s divok:%s/'''%(exe, DOWNLOADS))
    if dmg and os.path.exists(dmg):
        check_call('''ssh divok rm -f %s/calibre\*.dmg'''%(DOWNLOADS,)) 
        check_call('''scp %s divok:%s/'''%(dmg, DOWNLOADS))
    if tbz2 and os.path.exists(tbz2):
        check_call('''ssh divok rm -f %s/calibre-\*-i686.tar.bz2 %s/latest-linux-binary.tar.bz2'''%(DOWNLOADS,DOWNLOADS))
        check_call('''scp %s divok:%s/'''%(tbz2, DOWNLOADS))
        check_call('''ssh divok ln -s %s/calibre-\*-i686.tar.bz2 %s/latest-linux-binary.tar.bz2'''%(DOWNLOADS,DOWNLOADS))
    check_call('''ssh divok chmod a+r %s/\*'''%(DOWNLOADS,))
        
def upload_docs():
    check_call('''epydoc --config epydoc.conf''')
    check_call('''scp -r docs/html divok:%s/'''%(DOCS,))
    check_call('''epydoc -v --config epydoc-pdf.conf''')
    check_call('''scp docs/pdf/api.pdf divok:%s/'''%(DOCS,))

def upload_user_manual():
    cwd = os.getcwdu()
    os.chdir('src/calibre/manual')
    try:
        check_call('make clean html')
        check_call('ssh divok rm -rf %s/\\*'%USER_MANUAL)
        check_call('scp -r .build/html/* divok:%s'%USER_MANUAL)
    finally:
        os.chdir(cwd)
        
def build_tarball():
    cwd = os.getcwd()
    check_call('bzr export dist/calibre-%s.tar.bz2'%__version__)
    
def upload_tarball():
    check_call('ssh divok rm -f %s/calibre-\*.tar.bz2'%DOWNLOADS)
    check_call('scp dist/calibre-*.tar.bz2 divok:%s/'%DOWNLOADS)

    

def main():
    upload = len(sys.argv) < 2
    shutil.rmtree('build')
    os.mkdir('build')
    shutil.rmtree('docs')
    os.mkdir('docs')
    check_call("sudo python setup.py develop", shell=True)
    check_call('sudo rm src/%s/gui2/images_rc.pyc'%__appname__, shell=True)
    check_call('make', shell=True)
    tag_release()
    upload_demo()
    build_installers()
    build_tarball()
    if upload:
        print 'Uploading installers...'
        upload_installers()
        print 'Uploading to PyPI'
        upload_tarball()
        upload_docs()
        upload_user_manual()
        check_call('rm -f dist/*.bz2 dist/*.exe dist/*.dmg')
        check_call('python setup.py register upload')
        check_call('''rm -rf dist/* build/*''')
    
if __name__ == '__main__':
    main()
