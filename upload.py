#!/usr/bin/python
import sys, os, shutil, time
sys.path.append('src')
import subprocess
from subprocess import check_call as _check_call
from functools import partial
#from pyvix.vix import Host, VIX_SERVICEPROVIDER_VMWARE_WORKSTATION
import pysvn

PREFIX = "/var/www/vhosts/kovidgoyal.net/subdomains/libprs500"
DOWNLOADS = PREFIX+"/httpdocs/downloads"
DOCS = PREFIX+"/httpdocs/apidocs"
HTML2LRF = "src/libprs500/ebooks/lrf/html/demo"
TXT2LRF  = "src/libprs500/ebooks/lrf/txt/demo"
check_call = partial(_check_call, shell=True)
#h = Host(hostType=VIX_SERVICEPROVIDER_VMWARE_WORKSTATION)


def tag_release():
    from libprs500 import __version__
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
        if not os.path.exists(installer):
            raise Exception('Failed to build windows installer')
    finally:
        os.unlink('dist/auto')
    
        
    return os.path.basename(installer)


def build_windows():
    from libprs500 import __version__
    installer = 'dist/libprs500-%s.exe'%__version__
    vm = '/vmware/Windows XP/Windows XP Professional.vmx'
    return build_installer(installer, vm, 20)
    

def build_osx():
    from libprs500 import __version__
    installer = 'dist/libprs500-%s.dmg'%__version__
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

def upload_installers(exe, dmg):
    if exe and os.path.exists(os.path.join('dist', exe)):
        check_call('''ssh castalia rm -f %s/libprs500\*.exe'''%(DOWNLOADS,))
        check_call('''scp dist/%s castalia:%s/'''%(exe, DOWNLOADS))
        check_call('''ssh castalia rm -f %s/libprs500\*.dmg'''%(DOWNLOADS,))
    if dmg and os.path.exists(os.path.join('dist', dmg)):
        check_call('''scp dist/%s castalia:%s/'''%(dmg, DOWNLOADS))
        check_call('''ssh castalia chmod a+r %s/\*'''%(DOWNLOADS,))
        check_call('''ssh castalia /root/bin/update-installer-links %s %s'''%(exe, dmg))

def upload_docs():
    check_call('''epydoc --config epydoc.conf''')
    check_call('''scp -r docs/html castalia:%s/'''%(DOCS,))
    check_call('''epydoc -v --config epydoc-pdf.conf''')
    check_call('''scp docs/pdf/api.pdf castalia:%s/'''%(DOCS,))

    

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
    exe, dmg = build_installers()
    if upload:
        print 'Uploading installers...'
        upload_installers(exe, dmg)
        print 'Uploading to PyPI'
        check_call('''python setup.py register bdist_egg --exclude-source-files upload''')
        upload_docs()
        check_call('''rm -rf dist/* build/*''')
    
if __name__ == '__main__':
    main()
