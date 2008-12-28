#!/usr/bin/python
import sys, os, shutil, time, tempfile, socket, fcntl, struct, cStringIO, pycurl, re
sys.path.append('src')
import subprocess
from subprocess import check_call as _check_call
from functools import partial

def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])

try:
    HOST=get_ip_address('eth0')
except:
    HOST=get_ip_address('wlan0')
PROJECT=os.path.basename(os.getcwd())

from calibre import __version__, __appname__

PREFIX = "/var/www/calibre.kovidgoyal.net"
DOWNLOADS = PREFIX+"/htdocs/downloads"
DOCS = PREFIX+"/htdocs/apidocs"
USER_MANUAL = PREFIX+'/htdocs/user_manual'
HTML2LRF = "src/calibre/ebooks/lrf/html/demo"
TXT2LRF  = "src/calibre/ebooks/lrf/txt/demo"
MOBILEREAD = 'ftp://dev.mobileread.com/calibre/'
BUILD_SCRIPT ='''\
#!/bin/bash
export CALIBRE_BUILDBOT=1
cd ~/build && \
rsync -avz --exclude src/calibre/plugins --exclude calibre/src/calibre.egg-info --exclude docs --exclude .bzr --exclude .build --exclude build --exclude dist --exclude "*.pyc" --exclude "*.pyo" rsync://%(host)s/work/%(project)s . && \
cd %(project)s && \
%%s && \
rm -rf build/* dist/* && \
%%s %%s
'''%dict(host=HOST, project=PROJECT)
check_call = partial(_check_call, shell=True)
#h = Host(hostType=VIX_SERVICEPROVIDER_VMWARE_WORKSTATION)


def tag_release():
    print 'Tagging release'
    check_call('bzr tag '+__version__)
    check_call('bzr commit --unchanged -m "IGN:Tag release"')

def installer_name(ext):
    if ext in ('exe', 'dmg'):
        return 'dist/%s-%s.%s'%(__appname__, __version__, ext)
    return 'dist/%s-%s-i686.%s'%(__appname__, __version__, ext)

def start_vm(vm, ssh_host, build_script, sleep=75):
    vmware = ('vmware', '-q', '-x', '-n', vm)
    subprocess.Popen(vmware)
    t = tempfile.NamedTemporaryFile(suffix='.sh')
    t.write(build_script)
    t.flush()
    print 'Waiting for VM to startup'
    while subprocess.call('ping -q -c1 '+ssh_host, shell=True, stdout=open('/dev/null', 'w')) != 0:
        time.sleep(5)
    time.sleep(20)
    print 'Trying to SSH into VM'
    subprocess.check_call(('scp', t.name, ssh_host+':build-'+PROJECT))
    subprocess.check_call('ssh -t %s bash build-%s'%(ssh_host, PROJECT), shell=True)

def run_windows_install_jammer(installer):
    ibp = os.path.abspath('installer/windows')
    sys.path.insert(0, ibp)
    import build_installer
    sys.path.remove(ibp)
    build_installer.run_install_jammer(installer_name=os.path.basename(installer))
    if not os.path.exists(installer):
        raise Exception('Failed to run installjammer')

def build_windows(shutdown=True):
    installer = installer_name('exe')
    vm = '/vmware/Windows XP/Windows XP Professional.vmx'
    start_vm(vm, 'windows', BUILD_SCRIPT%('python setup.py develop', 'python','installer\\\\windows\\\\freeze.py'))
    if os.path.exists('build/py2exe'):
        shutil.rmtree('build/py2exe')
    subprocess.check_call(('scp', '-rp', 'windows:build/%s/build/py2exe'%PROJECT, 'build'))
    if not os.path.exists('build/py2exe'):
        raise Exception('Failed to run py2exe')
    if shutdown:
        subprocess.Popen(('ssh', 'windows', 'shutdown', '-s', '-t', '0'))
    run_windows_install_jammer(installer)
    return os.path.basename(installer)

def build_osx(shutdown=True):
    installer = installer_name('dmg')
    vm = '/vmware/Mac OSX/Mac OSX.vmx'
    python = '/Library/Frameworks/Python.framework/Versions/Current/bin/python'
    start_vm(vm, 'osx', (BUILD_SCRIPT%('sudo %s setup.py develop'%python, python, 'installer/osx/freeze.py')).replace('rm ', 'sudo rm '))
    subprocess.check_call(('scp', 'osx:build/%s/dist/*.dmg'%PROJECT, 'dist'))
    if not os.path.exists(installer):
        raise Exception('Failed to build installer '+installer)
    if shutdown:
        subprocess.Popen(('ssh', 'osx', 'sudo', '/sbin/shutdown', '-h', 'now'))
    return os.path.basename(installer)


def build_linux(*args, **kwargs):
    installer = installer_name('tar.bz2')
    exec open('installer/linux/freeze.py')
    freeze()
    if not os.path.exists(installer):
        raise Exception('Failed to build installer '+installer)
    return os.path.basename(installer)

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

def curl_list_dir(url=MOBILEREAD, listonly=1):
    c = pycurl.Curl()
    c.setopt(pycurl.URL, url)
    c.setopt(c.FTP_USE_EPSV, 1)
    c.setopt(c.NETRC, c.NETRC_REQUIRED)
    c.setopt(c.FTPLISTONLY, listonly)
    c.setopt(c.FTP_CREATE_MISSING_DIRS, 1)
    b = cStringIO.StringIO()
    c.setopt(c.WRITEFUNCTION, b.write)
    c.perform()
    c.close()
    return b.getvalue().split() if listonly else b.getvalue().splitlines()

def curl_delete_file(path, url=MOBILEREAD):
    c = pycurl.Curl()
    c.setopt(pycurl.URL, url)
    c.setopt(c.FTP_USE_EPSV, 1)
    c.setopt(c.NETRC, c.NETRC_REQUIRED)
    print 'Deleting file %s on %s'%(path, url)
    c.setopt(c.QUOTE, ['dele '+ path])
    c.perform()
    c.close()


def curl_upload_file(stream, url):
    c = pycurl.Curl()
    c.setopt(pycurl.URL, url)
    c.setopt(pycurl.UPLOAD, 1)
    c.setopt(c.NETRC, c.NETRC_REQUIRED)
    c.setopt(pycurl.READFUNCTION, stream.read)
    stream.seek(0, 2)
    c.setopt(pycurl.INFILESIZE_LARGE, stream.tell())
    stream.seek(0)
    c.setopt(c.NOPROGRESS, 0)
    c.setopt(c.FTP_CREATE_MISSING_DIRS, 1)
    print 'Uploading file %s to url %s' % (getattr(stream, 'name', ''), url)
    try:
        c.perform()
        c.close()
    except:
        pass
    files = curl_list_dir(listonly=0)
    for line in files:
        line = line.split()
        if url.endswith(line[-1]):
            size = long(line[4])
            stream.seek(0,2)
            if size != stream.tell():
                raise RuntimeError('curl failed to upload %s correctly'%getattr(stream, 'name', ''))



def upload_installer(name):
    if not os.path.exists(name):
        return
    bname = os.path.basename(name)
    pat = re.compile(bname.replace(__version__, r'\d+\.\d+\.\d+'))
    for f in curl_list_dir():
        if pat.search(f):
            curl_delete_file('/calibre/'+f)
    curl_upload_file(open(name, 'rb'), MOBILEREAD+os.path.basename(name))

def upload_installers():
    for i in ('dmg', 'exe', 'tar.bz2'):
        upload_installer(installer_name(i))

    check_call('''ssh divok echo %s \\> %s/latest_version'''%(__version__, DOWNLOADS))


def upload_docs():
    check_call('''epydoc --config epydoc.conf''')
    check_call('''scp -r docs/html divok:%s/'''%(DOCS,))
    check_call('''epydoc -v --config epydoc-pdf.conf''')
    check_call('''scp docs/pdf/api.pdf divok:%s/'''%(DOCS,))

def upload_user_manual():
    check_call('python setup.py manual')
    check_call('scp -r src/calibre/manual/.build/html/* divok:%s'%USER_MANUAL)
    
def build_src_tarball():
    check_call('bzr export dist/calibre-%s.tar.gz'%__version__)

def upload_src_tarball():
    check_call('ssh divok rm -f %s/calibre-\*.tar.gz'%DOWNLOADS)
    check_call('scp dist/calibre-*.tar.gz divok:%s/'%DOWNLOADS)

def stage_one():
    check_call('sudo rm -rf build src/calibre/plugins/*', shell=True)
    os.mkdir('build')
    shutil.rmtree('docs')
    os.mkdir('docs')
    check_call('python setup.py build_ext build', shell=True)
    check_call('sudo python setup.py develop', shell=True)
    tag_release()
    upload_demo()

def stage_two():
    subprocess.check_call('rm -rf dist/*', shell=True)
    build_installers()

def stage_three():
    print 'Uploading installers...'
    upload_installers()
    print 'Uploading documentation...'
    #upload_docs()
    upload_user_manual()
    print 'Uploading to PyPI...'
    check_call('rm -f dist/*')
    check_call('python setup.py register')
    check_call('sudo rm -rf build src/calibre/plugins/*')
    os.mkdir('build')
    check_call('python2.5 setup.py build_ext bdist_egg --exclude-source-files upload')
    check_call('sudo rm -rf build src/calibre/plugins/*')
    os.mkdir('build')
    check_call('python setup.py build_ext bdist_egg --exclude-source-files upload')
    check_call('python setup.py sdist upload')
    upload_src_tarball()
    check_call('''rm -rf dist/* build/*''')
    check_call('''ssh divok bzr update /var/www/calibre.kovidgoyal.net/calibre/''')

def betas():
    subprocess.check_call('rm -f dist/*', shell=True)
    build_installers()
    check_call('ssh divok rm -f  /var/www/calibre.kovidgoyal.net/htdocs/downloads/betas/*')
    check_call('scp dist/* divok:/var/www/calibre.kovidgoyal.net/htdocs/downloads/betas/')

def main(args=sys.argv):
    print 'Starting stage one...'
    stage_one()
    print 'Starting stage two...'
    stage_two()
    print 'Starting stage three...'
    stage_three()
    print 'Finished'
    return 0


if __name__ == '__main__':
    sys.exit(main())
