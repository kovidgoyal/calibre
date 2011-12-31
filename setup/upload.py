#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re, cStringIO, base64, httplib, subprocess, hashlib, shutil, time, \
    glob, stat, sys
from subprocess import check_call
from tempfile import NamedTemporaryFile, mkdtemp
from zipfile import ZipFile

from setup import Command, __version__, installer_name, __appname__

PREFIX = "/var/www/calibre-ebook.com"
DOWNLOADS = PREFIX+"/htdocs/downloads"
BETAS = DOWNLOADS +'/betas'
USER_MANUAL = '/var/www/localhost/htdocs/'
HTML2LRF = "calibre/ebooks/lrf/html/demo"
TXT2LRF  = "src/calibre/ebooks/lrf/txt/demo"
MOBILEREAD = 'ftp://dev.mobileread.com/calibre/'


def installers():
    installers = list(map(installer_name, ('dmg', 'msi', 'tar.bz2')))
    installers.append(installer_name('tar.bz2', is64bit=True))
    installers.insert(0, 'dist/%s-%s.tar.xz'%(__appname__, __version__))
    installers.append('dist/%s-portable-%s.zip'%(__appname__, __version__))
    return installers

def installer_description(fname):
    if fname.endswith('.tar.xz'):
        return 'Source code'
    if fname.endswith('.tar.bz2'):
        bits = '32' if 'i686' in fname else '64'
        return bits + 'bit Linux binary'
    if fname.endswith('.msi'):
        return 'Windows installer'
    if fname.endswith('.dmg'):
        return 'OS X dmg'
    if fname.endswith('.zip'):
        return 'Calibre Portable'
    return 'Unknown file'

class ReUpload(Command): # {{{

    description = 'Re-uplaod any installers present in dist/'

    sub_commands = ['upload_to_google_code', 'upload_to_sourceforge']

    def pre_sub_commands(self, opts):
        opts.re_upload = True

    def run(self, opts):
        for x in installers():
            if os.path.exists(x):
                os.remove(x)
# }}}

class ReadFileWithProgressReporting(file): # {{{

    def __init__(self, path, mode='rb'):
        file.__init__(self, path, mode)
        self.seek(0, os.SEEK_END)
        self._total = self.tell()
        self.seek(0)
        self.start_time = time.time()

    def __len__(self):
        return self._total

    def read(self, size):
        data = file.read(self, size)
        if data:
            self.report_progress(len(data))
        return data

    def report_progress(self, size):
        sys.stdout.write(b'\x1b[s')
        sys.stdout.write(b'\x1b[K')
        frac = float(self.tell())/self._total
        mb_pos = self.tell()/float(1024**2)
        mb_tot = self._total/float(1024**2)
        kb_pos = self.tell()/1024.0
        kb_rate = kb_pos/(time.time()-self.start_time)
        bit_rate = kb_rate * 1024
        eta = int((self._total - self.tell())/bit_rate) + 1
        eta_m, eta_s = eta / 60, eta % 60
        sys.stdout.write(
            '  %.1f%%   %.1f/%.1fMB %.1f KB/sec    %d minutes, %d seconds left'%(
                frac*100, mb_pos, mb_tot, kb_rate, eta_m, eta_s))
        sys.stdout.write(b'\x1b[u')
        if self.tell() >= self._total:
            sys.stdout.write('\n')
            t = int(time.time() - self.start_time) + 1
            print ('Upload took %d minutes and %d seconds at %.1f KB/sec' % (
                t/60, t%60, kb_rate))
        sys.stdout.flush()
# }}}

class UploadToGoogleCode(Command): # {{{

    USERNAME = 'kovidgoyal'
    # Password can be gotten by going to
    # http://code.google.com/hosting/settings
    # while logged into gmail
    PASSWORD_FILE = os.path.expanduser('~/.googlecodecalibre')
    OFFLINEIMAP   = os.path.expanduser('~/work/kde/conf/offlineimap/rc')
    GPATHS = '/var/www/status.calibre-ebook.com/googlepaths'
    # If you change this, remember to change the default URL used by
    # http://calibre-ebook.com as well
    GC_PROJECT = 'calibre-ebook-ii'

    UPLOAD_HOST = '%s.googlecode.com'%GC_PROJECT
    FILES_LIST = 'http://code.google.com/p/%s/downloads/list'%GC_PROJECT
    DELETE_URL = 'http://code.google.com/p/%s/downloads/delete?name=%%s'%GC_PROJECT

    def add_options(self, parser):
        parser.add_option('--re-upload', default=False, action='store_true',
                help='Re-upload all installers currently in dist/')

    def re_upload(self):
        fnames = set([os.path.basename(x) for x in installers() if not
                x.endswith('.tar.xz') and os.path.exists(x)])
        existing = set(self.old_files.keys()).intersection(fnames)
        br = self.login_to_gmail()
        for x in fnames:
            src = os.path.join('dist', x)
            if not os.access(src, os.R_OK):
                continue
            if x in existing:
                self.info('Deleting', x)
                br.open(self.DELETE_URL%x)
                br.select_form(predicate=lambda y: 'delete.do' in y.action)
                br.form.find_control(name='delete')
                br.submit(name='delete')
            self.upload_one(src)

    def upload_one(self, fname):
        self.info('\nUploading', fname)
        typ = 'Type-' + ('Source' if fname.endswith('.xz') else 'Archive' if
                fname.endswith('.zip') else 'Installer')
        ext = os.path.splitext(fname)[1][1:]
        op  = 'OpSys-'+{'msi':'Windows','zip':'Windows',
                'dmg':'OSX','bz2':'Linux','xz':'All'}[ext]
        desc = installer_description(fname)
        start = time.time()
        for i in range(5):
            try:
                path = self.upload(os.path.abspath(fname), desc,
                    labels=[typ, op, 'Featured'])
            except KeyboardInterrupt:
                raise SystemExit(1)
            except:
                import traceback
                traceback.print_exc()
                print ('\nUpload failed, trying again in 30 secs')
                time.sleep(30)
            else:
                break
        self.info('Uploaded to:', path, 'in', int(time.time() - start),
                'seconds')
        return path

    def run(self, opts):
        self.opts = opts
        self.password = open(self.PASSWORD_FILE).read().strip()
        self.paths = {}
        self.old_files = self.get_files_hosted_by_google_code()

        if opts.re_upload:
            return self.re_upload()

        for fname in installers():
            bname = os.path.basename(fname)
            if bname in self.old_files:
                path = 'http://%s.googlecode.com/files/%s'%(self.GC_PROJECT,
                        bname)
                self.info(
                    '%s already uploaded, skipping. Assuming URL is: %s'%(
                        bname, path))
                self.old_files.pop(bname)
            else:
                path = self.upload_one(fname)
            self.paths[bname] = path
        self.info('Updating path map')
        self.info(repr(self.paths))
        raw = subprocess.Popen(['ssh', 'divok', 'cat', self.GPATHS],
                stdout=subprocess.PIPE).stdout.read()
        paths = eval(raw)
        paths.update(self.paths)
        rem = [x for x in paths if __version__ not in x]
        for x in rem: paths.pop(x)
        raw = ['%r : %r,'%(k, v) for k, v in paths.items()]
        raw = '{\n\n%s\n\n}\n'%('\n'.join(raw))
        t = NamedTemporaryFile()
        t.write(raw)
        t.flush()
        check_call(['scp', t.name, 'divok:'+self.GPATHS])
        self.br = self.login_to_gmail()
        self.delete_old_files()
        #if len(self.get_files_hosted_by_google_code()) > len(installers()):
        #    self.warn('Some old files were not deleted from Google Code')

    def login_to_gmail(self):
        import mechanize
        self.info('Logging into Gmail')
        raw = open(self.OFFLINEIMAP).read()
        pw = re.search(r'(?s)remoteuser = .*@gmail.com.*?remotepass = (\S+)',
                raw).group(1).strip()
        br = mechanize.Browser()
        br.set_handle_robots(False)
        br.open('http://gmail.com')
        br.select_form(nr=0)
        br.form['Email'] = self.USERNAME
        br.form['Passwd'] = pw
        br.submit()
        return br

    def get_files_hosted_by_google_code(self):
        import urllib2
        from lxml import html
        self.info('Getting existing files in google code')
        raw = urllib2.urlopen(self.FILES_LIST).read()
        root = html.fromstring(raw)
        ans = {}
        for a in root.xpath('//td[@class="vt id col_0"]/a[@href]'):
            ans[a.text.strip()] = a.get('href')
        return ans

    def delete_old_files(self):
        self.info('Deleting old files from Google Code...')
        for fname in self.old_files:
            ext = fname.rpartition('.')[-1]
            if ext in ('flv', 'mp4', 'ogg', 'avi'):
                continue
            self.info('\tDeleting', fname)
            self.br.open(self.DELETE_URL%fname)
            self.br.select_form(predicate=lambda x: 'delete.do' in x.action)
            self.br.form.find_control(name='delete')
            self.br.submit(name='delete')

    def encode_upload_request(self, fields, file_path):
        BOUNDARY = '----------Googlecode_boundary_reindeer_flotilla'
        CRLF = '\r\n'

        body = []

        # Add the metadata about the upload first
        for key, value in fields:
            body.extend(
            ['--' + BOUNDARY,
            'Content-Disposition: form-data; name="%s"' % key,
            '',
            value,
            ])

        # Now add the file itself
        file_name = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            file_content = f.read()

        body.extend(
            ['--' + BOUNDARY,
            'Content-Disposition: form-data; name="filename"; filename="%s"'
            % file_name,
            # The upload server determines the mime-type, no need to set it.
            'Content-Type: application/octet-stream',
            '',
            file_content,
            ])

        # Finalize the form body
        body.extend(['--' + BOUNDARY + '--', ''])

        return 'multipart/form-data; boundary=%s' % BOUNDARY, CRLF.join(body)

    def upload(self, fname, desc, labels=[], retry=0):
        form_fields = [('summary', desc)]
        form_fields.extend([('label', l.strip()) for l in labels])

        content_type, body = self.encode_upload_request(form_fields, fname)
        upload_uri = '/files'
        auth_token = base64.b64encode('%s:%s'% (self.USERNAME, self.password))
        headers = {
            'Authorization': 'Basic %s' % auth_token,
            'User-Agent': 'Calibre googlecode.com uploader v0.1.0',
            'Content-Type': content_type,
            }

        with NamedTemporaryFile(delete=False) as f:
            f.write(body)

        try:
            body = ReadFileWithProgressReporting(f.name)
            server = httplib.HTTPSConnection(self.UPLOAD_HOST)
            server.request('POST', upload_uri, body, headers)
            resp = server.getresponse()
            server.close()
        finally:
            os.remove(f.name)

        if resp.status == 201:
            return resp.getheader('Location')

        print 'Failed to upload with code %d and reason: %s'%(resp.status,
                resp.reason)
        if retry < 1:
            print 'Retrying in 5 seconds....'
            time.sleep(5)
            return self.upload(fname, desc, labels=labels, retry=retry+1)
        raise Exception('Failed to upload '+fname)

# }}}

class UploadToSourceForge(Command): # {{{

    description = 'Upload release files to sourceforge'

    USERNAME = 'kovidgoyal'
    PROJECT  = 'calibre'
    BASE     = '/home/frs/project/c/ca/'+PROJECT

    @property
    def rdir(self):
        return self.BASE+'/'+__version__

    def upload_installers(self):
        for x in installers():
            if not os.path.exists(x): continue
            start = time.time()
            self.info('Uploading', x)
            for i in range(5):
                try:
                    check_call(['rsync', '-z', '--progress', '-e', 'ssh -x', x,
                    '%s,%s@frs.sourceforge.net:%s'%(self.USERNAME, self.PROJECT,
                        self.rdir+'/')])
                except KeyboardInterrupt:
                    raise SystemExit(1)
                except:
                    print ('\nUpload failed, trying again in 30 seconds')
                    time.sleep(30)
                else:
                    break
            print 'Uploaded in', int(time.time() - start), 'seconds'
            print ('\n')

    def run(self, opts):
        self.opts = opts
        self.upload_installers()

# }}}

class UploadInstallers(Command): # {{{
    description = 'Upload any installers present in dist/ to mobileread'
    def curl_list_dir(self, url=MOBILEREAD, listonly=1):
        import pycurl
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

    def curl_delete_file(self, path, url=MOBILEREAD):
        import pycurl
        c = pycurl.Curl()
        c.setopt(pycurl.URL, url)
        c.setopt(c.FTP_USE_EPSV, 1)
        c.setopt(c.NETRC, c.NETRC_REQUIRED)
        self.info('Deleting file %s on %s'%(path, url))
        c.setopt(c.QUOTE, ['dele '+ path])
        c.perform()
        c.close()


    def curl_upload_file(self, stream, url):
        import pycurl
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
        self.info('Uploading file %s to url %s' % (getattr(stream, 'name', ''),
            url))
        try:
            c.perform()
            c.close()
        except:
            pass
        files = self.curl_list_dir(listonly=0)
        for line in files:
            line = line.split()
            if url.endswith(line[-1]):
                size = long(line[4])
                stream.seek(0,2)
                if size != stream.tell():
                    raise RuntimeError('curl failed to upload %s correctly'%getattr(stream, 'name', ''))

    def upload_installer(self, name):
        if not os.path.exists(name):
            return
        bname = os.path.basename(name)
        pat = re.compile(bname.replace(__version__, r'\d+\.\d+\.\d+'))
        for f in self.curl_list_dir():
            if pat.search(f):
                self.curl_delete_file('/calibre/'+f)
        self.curl_upload_file(open(name, 'rb'), MOBILEREAD+os.path.basename(name))

    def run(self, opts):
        self.info('Uploading installers...')
        installers = list(map(installer_name, ('dmg', 'msi', 'tar.bz2')))
        installers.append(installer_name('tar.bz2', is64bit=True))
        map(self.upload_installer, installers)
# }}}

class UploadUserManual(Command): # {{{
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
                        if x.endswith('.swp'): continue
                        zf.write(x)
                        if os.path.isdir(x):
                            for y in os.listdir(x):
                                zf.write(os.path.join(x, y))
            bname = self.b(path) + '_plugin.zip'
            dest = '%s/%s'%(DOWNLOADS, bname)
            subprocess.check_call(['scp', f.name, 'divok:'+dest])

    def run(self, opts):
        path = self.j(self.SRC, 'calibre', 'manual', 'plugin_examples')
        for x in glob.glob(self.j(path, '*')):
            self.build_plugin_example(x)

        check_call(' '.join(['rsync', '-z', '-r', '--progress',
            'src/calibre/manual/.build/html/',
                    'bugs:%s'%USER_MANUAL]), shell=True)
# }}}

class UploadDemo(Command): # {{{

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

class UploadToServer(Command): # {{{

    description = 'Upload miscellaneous data to calibre server'

    def run(self, opts):
        check_call('ssh divok rm -f %s/calibre-\*.tar.xz'%DOWNLOADS, shell=True)
        #check_call('scp dist/calibre-*.tar.xz divok:%s/'%DOWNLOADS, shell=True)
        check_call('gpg --armor --detach-sign dist/calibre-*.tar.xz',
                shell=True)
        check_call('scp dist/calibre-*.tar.xz.asc divok:%s/signatures/'%DOWNLOADS,
                shell=True)
        check_call('ssh divok bzr update /usr/local/calibre',
                   shell=True)
        check_call('''ssh divok echo %s \\> %s/latest_version'''\
                   %(__version__, DOWNLOADS), shell=True)
        check_call('ssh divok /etc/init.d/apache2 graceful',
                   shell=True)
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
# }}}


