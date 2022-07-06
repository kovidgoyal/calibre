#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, subprocess, hashlib, shutil, glob, stat, sys, time, json
from subprocess import check_call
from tempfile import NamedTemporaryFile, mkdtemp, gettempdir
from zipfile import ZipFile
from polyglot.builtins import iteritems
from polyglot.urllib import urlopen, Request

if __name__ == '__main__':
    d = os.path.dirname
    sys.path.insert(0, d(d(os.path.abspath(__file__))))

from setup import Command, __version__, __appname__, installer_names

DOWNLOADS = '/srv/main/downloads'
HTML2LRF = "calibre/ebooks/lrf/html/demo"
TXT2LRF = "src/calibre/ebooks/lrf/txt/demo"
STAGING_HOST = 'download.calibre-ebook.com'
BACKUP_HOST = 'code.calibre-ebook.com'
STAGING_USER = BACKUP_USER = 'root'
STAGING_DIR = '/root/staging'
BACKUP_DIR = '/binaries'


def installer_description(fname):
    if fname.endswith('.tar.xz'):
        return 'Source code'
    if fname.endswith('.txz'):
        return ('ARM' if 'arm64' in fname else 'AMD') + ' 64-bit Linux binary'
    if fname.endswith('.msi'):
        return 'Windows installer'
    if fname.endswith('.dmg'):
        return 'macOS dmg'
    if fname.endswith('.exe'):
        return 'Calibre Portable'
    return 'Unknown file'


def upload_signatures():
    tdir = mkdtemp()
    scp = ['scp']
    try:
        for installer in installer_names():
            if not os.path.exists(installer):
                continue
            sig = os.path.join(tdir, os.path.basename(installer + '.sig'))
            scp.append(sig)
            check_call([
                os.environ['PENV'] + '/gpg-as-kovid', '--output', sig,
                '--detach-sig', installer
            ])
            with open(installer, 'rb') as f:
                raw = f.read()
            fingerprint = hashlib.sha512(raw).hexdigest()
            sha512 = os.path.join(tdir, os.path.basename(installer + '.sha512'))
            with open(sha512, 'w') as f:
                f.write(fingerprint)
            scp.append(sha512)
        for srv in 'code main'.split():
            check_call(scp + ['{0}:/srv/{0}/signatures/'.format(srv)])
            check_call(
                ['ssh', srv, 'chown', '-R', 'http:http', '/srv/%s/signatures' % srv]
            )
    finally:
        shutil.rmtree(tdir)


class ReUpload(Command):  # {{{

    description = 'Re-upload any installers present in dist/'

    sub_commands = ['upload_installers']

    def pre_sub_commands(self, opts):
        opts.replace = True
        exists = {x for x in installer_names() if os.path.exists(x)}
        if not exists:
            print('There appear to be no installers!')
            raise SystemExit(1)

    def run(self, opts):
        for x in installer_names():
            if os.path.exists(x):
                os.remove(x)


# }}}


# Data {{{
def get_github_data():
    with open(os.environ['PENV'] + '/github-token', 'rb') as f:
        un, pw = f.read().decode('utf-8').strip().split(':')
    return {'username': un, 'password': pw}


def get_sourceforge_data():
    return {'username': 'kovidgoyal', 'project': 'calibre'}


def get_fosshub_data():
    with open(os.environ['PENV'] + '/fosshub', 'rb') as f:
        return f.read().decode('utf-8').strip()


def send_data(loc):
    subprocess.check_call([
        'rsync', '--inplace', '--delete', '-r', '-zz', '-h', '--info=progress2', '-e',
        'ssh -x', loc + '/', f'{STAGING_USER}@{STAGING_HOST}:{STAGING_DIR}'
    ])


def send_to_backup(loc):
    host = f'{BACKUP_USER}@{BACKUP_HOST}'
    dest = f'{BACKUP_DIR}/{__version__}'
    subprocess.check_call(['ssh', '-x', host, 'mkdir', '-p', dest])
    subprocess.check_call([
        'rsync', '--inplace', '--delete', '-r', '-zz', '-h', '--info=progress2', '-e',
        'ssh -x', loc + '/', f'{host}:{dest}/'
    ])


def gh_cmdline(ver, data):
    return [
        __appname__, ver, 'fmap', 'github', __appname__, data['username'],
        data['password']
    ]


def sf_cmdline(ver, sdata):
    return [
        __appname__, ver, 'fmap', 'sourceforge', sdata['project'], sdata['username']
    ]


def calibre_cmdline(ver):
    return [__appname__, ver, 'fmap', 'calibre']


def run_remote_upload(args):
    print('Running remotely:', ' '.join(args))
    subprocess.check_call([
        'ssh', '-x', f'{STAGING_USER}@{STAGING_HOST}', 'cd', STAGING_DIR, '&&',
        'python', 'hosting.py'
    ] + args)


# }}}


def upload_to_fosshub():
    # https://devzone.fosshub.com/dashboard/restApi
    # fosshub has no API to do partial uploads, so we always upload all files.
    api_key = get_fosshub_data()

    def request(path, data=None):
        r = Request('https://api.fosshub.com/rest/' + path.lstrip('/'),
                headers={
                    'Content-Type': 'application/json',
                    'X-auth-key': api_key,
                    'User-Agent': 'calibre'
        })
        res = urlopen(r, data=data)
        ans = json.loads(res.read())
        if ans.get('error'):
            raise SystemExit(ans['error'])
        if res.getcode() != 200:
            raise SystemExit(f'Request to {path} failed with response code: {res.getcode()}')
        # from pprint import pprint
        # pprint(ans)
        return ans['status'] if 'status' in ans else ans['data']

    print('Sending upload request to fosshub...')
    project_id = None

    for project in request('projects'):
        if project['name'].lower() == 'calibre':
            project_id = project['id']
            break
    else:
        raise SystemExit('No calibre project found')

    files = set(installer_names())
    entries = []
    for fname in files:
        desc = installer_description(fname)
        url = 'https://download.calibre-ebook.com/{}/{}'.format(
            __version__, os.path.basename(fname)
        )
        entries.append({
            'fileUrl': url,
            'type': desc,
            'version': __version__,
        })
    jq = {
        'version': __version__,
        'files': entries,
        'publish': True,
        'isOldRelease': False,
    }
    data = json.dumps(jq)
    # print(data)
    data = data.encode('utf-8')
    if not request(f'projects/{project_id}/releases/', data=data):
        raise SystemExit('Failed to queue publish job with fosshub')


class UploadInstallers(Command):  # {{{

    def add_options(self, parser):
        parser.add_option(
            '--replace',
            default=False,
            action='store_true',
            help='Replace existing installers'
        )

    def run(self, opts):
        # return upload_to_fosshub()
        all_possible = set(installer_names())
        available = set(glob.glob('dist/*'))
        files = {
            x: installer_description(x)
            for x in all_possible.intersection(available)
        }
        for x in files:
            os.chmod(x, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
        sizes = {os.path.basename(x): os.path.getsize(x) for x in files}
        self.record_sizes(sizes)
        tdir = mkdtemp()
        try:
            self.upload_to_staging(tdir, files)
            self.upload_to_calibre()
            if opts.replace:
                upload_signatures()
                check_call('ssh code /apps/update-calibre-version.py'.split())
            # self.upload_to_sourceforge()
            upload_to_fosshub()
            self.upload_to_github(opts.replace)
        finally:
            shutil.rmtree(tdir, ignore_errors=True)

    def record_sizes(self, sizes):
        print('\nRecording dist sizes')
        args = [
            f'{__version__}:{fname}:{size}'
            for fname, size in iteritems(sizes)
        ]
        check_call(['ssh', 'code', '/usr/local/bin/dist_sizes'] + args)

    def upload_to_staging(self, tdir, files):
        os.mkdir(tdir + '/dist')
        hosting = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'hosting.py'
        )
        shutil.copyfile(hosting, os.path.join(tdir, 'hosting.py'))

        for f in files:
            for x in (tdir + '/dist',):
                dest = os.path.join(x, os.path.basename(f))
                shutil.copy2(f, x)
                os.chmod(
                    dest, stat.S_IREAD | stat.S_IWRITE | stat.S_IRGRP | stat.S_IROTH
                )

        with open(os.path.join(tdir, 'fmap'), 'wb') as fo:
            for f, desc in iteritems(files):
                fo.write((f'{f}: {desc}\n').encode())

        while True:
            try:
                send_data(tdir)
            except:
                print('\nUpload to staging failed, retrying in a minute')
                time.sleep(60)
            else:
                break

        while True:
            try:
                send_to_backup(tdir)
            except:
                print('\nUpload to backup failed, retrying in a minute')
                time.sleep(60)
            else:
                break

    def upload_to_github(self, replace):
        data = get_github_data()
        args = gh_cmdline(__version__, data)
        if replace:
            args = ['--replace'] + args
        run_remote_upload(args)

    def upload_to_sourceforge(self):
        sdata = get_sourceforge_data()
        args = sf_cmdline(__version__, sdata)
        run_remote_upload(args)

    def upload_to_calibre(self):
        run_remote_upload(calibre_cmdline(__version__))


# }}}


class UploadUserManual(Command):  # {{{
    description = 'Build and upload the User Manual'
    sub_commands = ['manual']

    def build_plugin_example(self, path):
        from calibre import CurrentDir
        with NamedTemporaryFile(suffix='.zip') as f:
            os.fchmod(
                f.fileno(), stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH |
                stat.S_IWRITE
            )
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
            dest = f'{DOWNLOADS}/{bname}'
            subprocess.check_call(['scp', f.name, 'main:' + dest])

    def run(self, opts):
        path = self.j(self.SRC, '..', 'manual', 'plugin_examples')
        for x in glob.glob(self.j(path, '*')):
            self.build_plugin_example(x)

        srcdir = self.j(gettempdir(), 'user-manual-build', 'en', 'html') + '/'
        check_call(
            ' '.join(
                ['rsync', '-zz', '-rl', '--info=progress2', srcdir, 'main:/srv/manual/']
            ),
            shell=True
        )
        check_call('ssh main chown -R http:http /srv/manual'.split())


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
            '''''' % self.j(self.SRC, HTML2LRF),
            shell=True
        )

        lrf = self.j(self.SRC, 'calibre', 'ebooks', 'lrf', 'html', 'demo')
        check_call(
            'cd %s && zip -j /tmp/html-demo.zip * /tmp/html2lrf.lrf' % lrf,
            shell=True
        )

        check_call(f'scp /tmp/html-demo.zip main:{DOWNLOADS}/', shell=True)


# }}}


class UploadToServer(Command):  # {{{

    description = 'Upload miscellaneous data to calibre server'

    def run(self, opts):
        check_call('scp translations/website/locales.zip main:/srv/main/'.split())
        check_call('scp translations/changelog/locales.zip main:/srv/main/changelog-locales.zip'.split())
        check_call('ssh main /apps/static/generate.py'.split())
        src_file = glob.glob('dist/calibre-*.tar.xz')[0]
        upload_signatures()
        check_call(['git', 'push'])
        check_call([
            os.environ['PENV'] + '/gpg-as-kovid', '--armor', '--yes',
            '--detach-sign', src_file
        ])
        check_call(['scp', src_file + '.asc', 'code:/srv/code/signatures/'])
        check_call('ssh code /usr/local/bin/update-calibre-code.py'.split())
        check_call(
            ('ssh code /apps/update-calibre-version.py ' + __version__).split()
        )
        check_call((
            'ssh main /usr/local/bin/update-calibre-version.py %s && /usr/local/bin/update-calibre-code.py && /apps/static/generate.py'
            % __version__
        ).split())


# }}}
