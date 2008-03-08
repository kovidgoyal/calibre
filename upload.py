#!/usr/bin/python
import sys, os, shutil, time
sys.path.append('src')
import subprocess
from subprocess import check_call as _check_call
from functools import partial
#from pyvix.vix import Host, VIX_SERVICEPROVIDER_VMWARE_WORKSTATION
import pysvn

from libprs500 import __version__, __appname__

PREFIX = "/var/www/vhosts/kovidgoyal.net/subdomains/libprs500"
DOWNLOADS = PREFIX+"/httpdocs/downloads"
DOCS = PREFIX+"/httpdocs/apidocs"
USER_MANUAL = PREFIX+'/httpdocs/user_manual'
HTML2LRF = "src/libprs500/ebooks/lrf/html/demo"
TXT2LRF  = "src/libprs500/ebooks/lrf/txt/demo"
check_call = partial(_check_call, shell=True)
#h = Host(hostType=VIX_SERVICEPROVIDER_VMWARE_WORKSTATION)


def tag_release():
    print 'Tagging release'
    base = 'https://kovid@svn.kovidgoyal.net/code/libprs500' 
    tag = base + '/tags/'+__version__
    client = pysvn.Client()
    client.exception_style = 1
    try:
        client.ls(tag)
    except pysvn.ClientError, err:
        if err.args[1][0][1] == 160013: # Tag does not exist
            def get_credentials(realm, username, may_save):
                return (True, 'kovid', input('Enter password for kovid: '), True)
            client.callback_get_login = get_credentials
            def get_log_message():
                return True, 'Tagging %s for release'%__version__
            client.callback_get_log_message = get_log_message
            client.copy(base+'/trunk', tag) 
            
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
    check_call('cd src/libprs500/ebooks/lrf/html/demo/ && zip -j /tmp/html-demo.zip * /tmp/html2lrf.lrf')
    check_call('''scp /tmp/html-demo.zip castalia:%s/'''%(DOWNLOADS,))
    check_call('''txt2lrf -t 'Demonstration of txt2lrf' -a 'Kovid Goyal' '''
               '''--header -o /tmp/txt2lrf.lrf %s/demo.txt'''%(TXT2LRF,) )
    check_call('cd src/libprs500/ebooks/lrf/txt/demo/ && zip -j /tmp/txt-demo.zip * /tmp/txt2lrf.lrf')
    check_call('''scp /tmp/txt-demo.zip castalia:%s/'''%(DOWNLOADS,))

def upload_installers():
    exe, dmg = installer_name('exe'), installer_name('dmg')
    if exe and os.path.exists(exe):
        check_call('''ssh castalia rm -f %s/libprs500\*.exe'''%(DOWNLOADS,))
        check_call('''scp %s castalia:%s/'''%(exe, DOWNLOADS))
        check_call('''ssh castalia rm -f %s/libprs500\*.dmg'''%(DOWNLOADS,))
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
    os.chdir('src/libprs500/manual')
    try:
        check_call('python make.py --validate')
        check_call('ssh castalia rm -rf %s/\\*'%USER_MANUAL)
        check_call('scp -r build/* castalia:%s'%USER_MANUAL)
    finally:
        os.chdir(cwd)

def main():
    upload = len(sys.argv) < 2
    shutil.rmtree('build')
    os.mkdir('build')
    shutil.rmtree('docs')
    os.mkdir('docs')
    check_call("sudo python setup.py develop", shell=True)
    check_call('make', shell=True)
    check_call('svn commit -m "Updated translations" src/libprs500/translations')
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
