#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, subprocess, hashlib, shutil, glob, stat, sys, time
from subprocess import check_call
from tempfile import NamedTemporaryFile, mkdtemp
from zipfile import ZipFile

if __name__ == '__main__':
    d = os.path.dirname
    sys.path.insert(0, d(d(os.path.abspath(__file__))))

from setup import Command, __version__, installer_name, __appname__

PREFIX = "/var/www/calibre-ebook.com"
DOWNLOADS = PREFIX+"/htdocs/downloads"
BETAS = DOWNLOADS +'/betas'
HTML2LRF = "calibre/ebooks/lrf/html/demo"
TXT2LRF  = "src/calibre/ebooks/lrf/txt/demo"
STAGING_HOST = 'download.calibre-ebook.com'
STAGING_USER = 'root'
STAGING_DIR = '/root/staging'

def installers():
    installers = list(map(installer_name, ('dmg', 'msi', 'tar.bz2')))
    installers.append(installer_name('tar.bz2', is64bit=True))
    installers.append(installer_name('msi', is64bit=True))
    installers.insert(0, 'dist/%s-%s.tar.xz'%(__appname__, __version__))
    installers.append('dist/%s-portable-installer-%s.exe'%(__appname__, __version__))
    return installers

def installer_description(fname):
    if fname.endswith('.tar.xz'):
        return 'Source code'
    if fname.endswith('.tar.bz2'):
        bits = '32' if 'i686' in fname else '64'
        return bits + 'bit Linux binary'
    if fname.endswith('.msi'):
        return 'Windows %sinstaller'%('64bit ' if '64bit' in fname else '')
    if fname.endswith('.dmg'):
        return 'OS X dmg'
    if fname.endswith('.exe'):
        return 'Calibre Portable'
    return 'Unknown file'

def upload_signatures():
    tdir = mkdtemp()
    for installer in installers():
        if not os.path.exists(installer):
            continue
        with open(installer, 'rb') as f:
            raw = f.read()
        fingerprint = hashlib.sha512(raw).hexdigest()
        fname = os.path.basename(installer+'.sha512')
        with open(os.path.join(tdir, fname), 'wb') as f:
            f.write(fingerprint)
    check_call('scp %s/*.sha512 divok:%s/signatures/' % (tdir, DOWNLOADS),
            shell=True)
    shutil.rmtree(tdir)

class ReUpload(Command):  # {{{

    description = 'Re-uplaod any installers present in dist/'

    sub_commands = ['upload_installers']

    def pre_sub_commands(self, opts):
        opts.replace = True

    def run(self, opts):
        upload_signatures()
        for x in installers():
            if os.path.exists(x):
                os.remove(x)
# }}}

# Data {{{
def get_google_data():
    with open(os.path.expanduser('~/work/env/private/googlecodecalibre'), 'rb') as f:
        gc_password, ga_un, pw = f.read().strip().split('|')

    return {
        'username':ga_un, 'password':pw, 'gc_password':gc_password,
        'path_map_server':'root@kovidgoyal.net',
        'path_map_location':'/var/www/status.calibre-ebook.com/googlepaths',
        # If you change this remember to change it in the
        # status.calibre-ebook.com server as well
        'project':'calibre-ebook'
    }

def get_sourceforge_data():
    return {'username':'kovidgoyal', 'project':'calibre'}

def send_data(loc):
    subprocess.check_call(['rsync', '--inplace', '--delete', '-r', '-z', '-h', '--progress', '-e', 'ssh -x',
        loc+'/', '%s@%s:%s'%(STAGING_USER, STAGING_HOST, STAGING_DIR)])

def gc_cmdline(ver, gdata):
    return [__appname__, ver, 'fmap', 'googlecode',
                gdata['project'], gdata['username'], gdata['password'],
                gdata['gc_password'], '--path-map-server',
                gdata['path_map_server'], '--path-map-location',
                gdata['path_map_location']]

def sf_cmdline(ver, sdata):
    return [__appname__, ver, 'fmap', 'sourceforge', sdata['project'],
            sdata['username']]

def calibre_cmdline(ver):
    return [__appname__, ver, 'fmap', 'calibre']

def dbs_cmdline(ver):
    return [__appname__, ver, 'fmap', 'dbs']

def run_remote_upload(args):
    print 'Running remotely:', ' '.join(args)
    subprocess.check_call(['ssh', '-x', '%s@%s'%(STAGING_USER, STAGING_HOST),
        'cd', STAGING_DIR, '&&', 'python', 'hosting.py']+args)

# }}}

class UploadInstallers(Command):  # {{{

    def add_options(self, parser):
        parser.add_option('--replace', default=False, action='store_true', help=
                'Replace existing installers, when uploading to google')

    def run(self, opts):
        all_possible = set(installers())
        available = set(glob.glob('dist/*'))
        files = {x:installer_description(x) for x in
                all_possible.intersection(available)}
        sizes = {os.path.basename(x):os.path.getsize(x) for x in files}
        self.record_sizes(sizes)
        tdir = mkdtemp()
        backup = os.path.join('/mnt/external/calibre/%s' % __version__)
        if not os.path.exists(backup):
            os.mkdir(backup)
        try:
            self.upload_to_staging(tdir, backup, files)
            self.upload_to_calibre()
            self.upload_to_sourceforge()
            self.upload_to_dbs()
            # self.upload_to_google(opts.replace)
        finally:
            shutil.rmtree(tdir, ignore_errors=True)

    def record_sizes(self, sizes):
        print ('\nRecording dist sizes')
        args = ['%s:%s:%s' % (__version__, fname, size) for fname, size in sizes.iteritems()]
        check_call(['ssh', 'divok', 'dist_sizes'] + args)

    def upload_to_staging(self, tdir, backup, files):
        os.mkdir(tdir+'/dist')
        hosting = os.path.join(os.path.dirname(os.path.abspath(__file__)),
            'hosting.py')
        shutil.copyfile(hosting, os.path.join(tdir, 'hosting.py'))

        for f in files:
            for x in (tdir+'/dist', backup):
                dest = os.path.join(x, os.path.basename(f))
                shutil.copy2(f, x)
                os.chmod(dest, stat.S_IREAD|stat.S_IWRITE|stat.S_IRGRP|stat.S_IROTH)

        with open(os.path.join(tdir, 'fmap'), 'wb') as fo:
            for f, desc in files.iteritems():
                fo.write('%s: %s\n'%(f, desc))

        while True:
            try:
                send_data(tdir)
            except:
                print('\nUpload to staging failed, retrying in a minute')
                time.sleep(60)
            else:
                break

    def upload_to_google(self, replace):
        gdata = get_google_data()
        args = gc_cmdline(__version__, gdata)
        if replace:
            args = ['--replace'] + args
        run_remote_upload(args)

    def upload_to_sourceforge(self):
        sdata = get_sourceforge_data()
        args = sf_cmdline(__version__, sdata)
        run_remote_upload(args)

    def upload_to_calibre(self):
        run_remote_upload(calibre_cmdline(__version__))

    def upload_to_dbs(self):
        run_remote_upload(dbs_cmdline(__version__))
# }}}

class UploadUserManual(Command):  # {{{
    description = 'Build and upload the User Manual'
    sub_commands = ['manual']

    def build_plugin_example(self, path):
        from calibre import CurrentDir
        with NamedTemporaryFile(suffix='.zip') as f:
            os.fchmod(f.fileno(),
                stat.S_IRUSR|stat.S_IRGRP|stat.S_IROTH|stat.S_IWRITE)
            with CurrentDir(path):
                with ZipFile(f, 'w') as zf:
                    for x in os.listdir('.'):
                        if x.endswith('.swp'):
                            continue
                        zf.write(x)
                        if os.path.isdir(x):
                            for y in os.listdir(x):
                                zf.write(os.path.join(x, y))
            bname = self.b(path) + '_plugin.zip'
            dest = '%s/%s'%(DOWNLOADS, bname)
            subprocess.check_call(['scp', f.name, 'divok:'+dest])

    def run(self, opts):
        path = self.j(self.SRC, '..', 'manual', 'plugin_examples')
        for x in glob.glob(self.j(path, '*')):
            self.build_plugin_example(x)

        for host in ('download', 'files'):
            check_call(' '.join(['rsync', '-z', '-r', '--progress',
                'manual/.build/html/', '%s:/srv/manual/' % host]), shell=True)
# }}}

class UploadDemo(Command):  # {{{

    description = 'Rebuild and upload various demos'

    def run(self, opts):
        check_call(
           '''ebook-convert %s/demo.html /tmp/html2lrf.lrf '''
           '''--title='Demonstration of html2lrf' --authors='Kovid Goyal' '''
           '''--header '''
           '''--serif-family "/usr/share/fonts/corefonts, Times New Roman" '''
           '''--mono-family  "/usr/share/fonts/corefonts, Andale Mono" '''
           ''''''%self.j(self.SRC, HTML2LRF), shell=True)

        check_call(
            'cd src/calibre/ebooks/lrf/html/demo/ && '
            'zip -j /tmp/html-demo.zip * /tmp/html2lrf.lrf', shell=True)

        check_call('scp /tmp/html-demo.zip divok:%s/'%(DOWNLOADS,), shell=True)
# }}}

class UploadToServer(Command):  # {{{

    description = 'Upload miscellaneous data to calibre server'

    def run(self, opts):
        check_call('ssh divok rm -f %s/calibre-\*.tar.xz'%DOWNLOADS, shell=True)
        # check_call('scp dist/calibre-*.tar.xz divok:%s/'%DOWNLOADS, shell=True)
        check_call('gpg --armor --detach-sign dist/calibre-*.tar.xz',
                shell=True)
        check_call('scp dist/calibre-*.tar.xz.asc divok:%s/signatures/'%DOWNLOADS,
                shell=True)
        check_call('ssh divok /usr/local/bin/update-calibre',
                   shell=True)
        check_call('''ssh divok echo %s \\> %s/latest_version'''
                   %(__version__, DOWNLOADS), shell=True)
        check_call('ssh divok /etc/init.d/apache2 graceful',
                   shell=True)
        upload_signatures()
# }}}

# Testing {{{

def write_files(fmap):
    for f in fmap:
        with open(f, 'wb') as f:
            f.write(os.urandom(100))
            f.write(b'a'*1000000)
    with open('fmap', 'wb') as fo:
        for f, desc in fmap.iteritems():
            fo.write('%s: %s\n'%(f, desc))

def setup_installers():
    ver = '0.0.1'
    files = {x.replace(__version__, ver):installer_description(x) for x in installers()}
    tdir = mkdtemp()
    os.chdir(tdir)
    return tdir, files, ver

def test_google_uploader():
    gdata = get_google_data()
    gdata['project'] = 'calibre-hosting-uploader'
    gdata['path_map_location'] += '-test'
    hosting = os.path.join(os.path.dirname(os.path.abspath(__file__)),
        'hosting.py')

    tdir, files, ver = setup_installers()
    try:
        os.mkdir('dist')
        write_files(files)
        shutil.copyfile(hosting, 'hosting.py')
        send_data(tdir)
        args = gc_cmdline(ver, gdata)

        print ('Doing initial upload')
        run_remote_upload(args)
        raw_input('Press Enter to proceed:')

        print ('\nDoing re-upload')
        run_remote_upload(['--replace']+args)
        raw_input('Press Enter to proceed:')

        nv = ver + '.1'
        files = {x.replace(__version__, nv):installer_description(x) for x in installers()}
        write_files(files)
        send_data(tdir)
        args[1] = nv
        print ('\nDoing update upload')
        run_remote_upload(args)
        print ('\nDont forget to delete any remaining files in the %s project'%
                gdata['project'])

    finally:
        shutil.rmtree(tdir)
# }}}

if __name__ == '__main__':
    test_google_uploader()

