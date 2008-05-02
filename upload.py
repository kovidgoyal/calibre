#!/usr/bin/python
import sys, os, shutil, time
sys.path.append('src')
import subprocess
from subprocess import check_call as _check_call
from functools import partial
#from pyvix.vix import Host, VIX_SERVICEPROVIDER_VMWARE_WORKSTATION

from calibre import __version__, __appname__

PREFIX = "/var/www/calibre.kovidgoyal.net"
DOWNLOADS = PREFIX+"/httpdocs/downloads"
DOCS = PREFIX+"/httpdocs/apidocs"
USER_MANUAL = PREFIX+'/httpdocs/user_manual'
HTML2LRF = "src/calibre/ebooks/lrf/html/demo"
TXT2LRF  = "src/calibre/ebooks/lrf/txt/demo"
check_call = partial(_check_call, shell=True)
#h = Host(hostType=VIX_SERVICEPROVIDER_VMWARE_WORKSTATION)


def tag_release():
    print 'Tagging release'
    check_call('bzr tag '+__version__) 
            
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
    return 'dist/%s-%s.%s'%(__appname__, __version__, ext)

def build_windows():
    installer = installer_name('exe')
    vm = '/vmware/Windows XP/Windows XP Professional.vmx'
    return build_installer(installer, vm, 20)
    

def build_osx():
    installer = installer_name('dmg')
    vm = '/vmware/Mac OSX/Mac OSX.vmx'
    return build_installer(installer, vm, 20)

def build_installers():
    return build_windows(), build_osx()

def upload_demo():
    check_call('''html2lrf --title='Demonstration of html2lrf' --author='Kovid Goyal' '''
               '''--header --output=/tmp/html2lrf.lrf %s/demo.html '''
               '''--serif-family "/usr/share/fonts/corefonts, Times New Roman" '''
               '''--mono-family  "/usr/share/fonts/corefonts, Andale Mono" '''
               ''''''%(HTML2LRF,))
    check_call('cd src/calibre/ebooks/lrf/html/demo/ && zip -j /tmp/html-demo.zip * /tmp/html2lrf.lrf')
    check_call('''scp /tmp/html-demo.zip castalia:%s/'''%(DOWNLOADS,))
    check_call('''txt2lrf -t 'Demonstration of txt2lrf' -a 'Kovid Goyal' '''
               '''--header -o /tmp/txt2lrf.lrf %s/demo.txt'''%(TXT2LRF,) )
    check_call('cd src/calibre/ebooks/lrf/txt/demo/ && zip -j /tmp/txt-demo.zip * /tmp/txt2lrf.lrf')
    check_call('''scp /tmp/txt-demo.zip castalia:%s/'''%(DOWNLOADS,))

def upload_installers():
    exe, dmg = installer_name('exe'), installer_name('dmg')
    if exe and os.path.exists(exe):
        check_call('''ssh castalia rm -f %s/calibre\*.exe'''%(DOWNLOADS,))
        check_call('''scp %s castalia:%s/'''%(exe, DOWNLOADS))
        check_call('''ssh castalia rm -f %s/calibre\*.dmg'''%(DOWNLOADS,))
    if dmg and os.path.exists(dmg):
        check_call('''scp %s castalia:%s/'''%(dmg, DOWNLOADS))
        check_call('''ssh castalia chmod a+r %s/\*'''%(DOWNLOADS,))
        check_call('''ssh castalia /root/bin/update-installer-links %s %s'''%(exe, dmg))

def upload_docs():
    check_call('''epydoc --config epydoc.conf''')
    check_call('''scp -r docs/html castalia:%s/'''%(DOCS,))
    check_call('''epydoc -v --config epydoc-pdf.conf''')
    check_call('''scp docs/pdf/api.pdf castalia:%s/'''%(DOCS,))

def upload_user_manual():
    cwd = os.getcwdu()
    os.chdir('src/calibre/manual')
    try:
        check_call('make clean html')
        check_call('ssh castalia rm -rf %s/\\*'%USER_MANUAL)
        check_call('scp -r .build/html/* castalia:%s'%USER_MANUAL)
    finally:
        os.chdir(cwd)

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
    if upload:
        print 'Uploading installers...'
        upload_installers()
        print 'Uploading to PyPI'
        check_call('''python setup.py register bdist_egg --exclude-source-files upload''')
        upload_docs()
        upload_user_manual()
        check_call('''rm -rf dist/* build/*''')
    
if __name__ == '__main__':
    main()
