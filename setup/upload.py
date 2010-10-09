#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re, cStringIO, base64, httplib, subprocess, hashlib, shutil
from subprocess import check_call
from tempfile import NamedTemporaryFile, mkdtemp

from setup import Command, __version__, installer_name, __appname__

PREFIX = "/var/www/calibre-ebook.com"
DOWNLOADS = PREFIX+"/htdocs/downloads"
BETAS = DOWNLOADS +'/betas'
USER_MANUAL = PREFIX+'/htdocs/user_manual'
HTML2LRF = "calibre/ebooks/lrf/html/demo"
TXT2LRF  = "src/calibre/ebooks/lrf/txt/demo"
MOBILEREAD = 'ftp://dev.mobileread.com/calibre/'


def installers():
    installers = list(map(installer_name, ('dmg', 'msi', 'tar.bz2')))
    installers.append(installer_name('tar.bz2', is64bit=True))
    installers.insert(0, 'dist/%s-%s.tar.gz'%(__appname__, __version__))
    return installers

def installer_description(fname):
    if fname.endswith('.tar.gz'):
        return 'Source code'
    if fname.endswith('.tar.bz2'):
        bits = '32' if 'i686' in fname else '64'
        return bits + 'bit Linux binary'
    if fname.endswith('.msi'):
        return 'Windows installer'
    if fname.endswith('.dmg'):
        return 'OS X dmg'
    return 'Unknown file'


class UploadToGoogleCode(Command):

    USERNAME = 'kovidgoyal'
    # Password can be gotten by going to
    # http://code.google.com/hosting/settings
    # while logged into gmail
    PASSWORD_FILE = os.path.expanduser('~/.googlecodecalibre')
    OFFLINEIMAP   = os.path.expanduser('~/work/kde/conf/offlineimap/rc')
    GPATHS = '/var/www/status.calibre-ebook.com/googlepaths'
    UPLOAD_HOST = 'calibre-ebook.googlecode.com'
    FILES_LIST = 'http://code.google.com/p/calibre-ebook/downloads/list'

    def run(self, opts):
        self.opts = opts
        self.password = open(self.PASSWORD_FILE).read().strip()
        self.paths = {}
        self.old_files = self.get_files_hosted_by_google_code()

        for fname in installers():
            self.info('Uploading', fname)
            typ = 'Type-Source' if fname.endswith('.gz') else 'Type-Installer'
            ext = os.path.splitext(fname)[1][1:]
            op  = 'OpSys-'+{'msi':'Windows','dmg':'OSX','bz2':'Linux','gz':'All'}[ext]
            desc = installer_description(fname)
            path = self.upload(os.path.abspath(fname), desc,
                    labels=[typ, op, 'Featured'])
            self.info('\tUploaded to:', path)
            self.paths[os.path.basename(fname)] = path
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
            self.br.open('http://code.google.com/p/calibre-ebook/downloads/delete?name=%s'%fname)
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
        f = open(file_path, 'rb')
        file_content = f.read()
        f.close()

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

    def upload(self, fname, desc, labels=[]):
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

        server = httplib.HTTPSConnection(self.UPLOAD_HOST)
        server.request('POST', upload_uri, body, headers)
        resp = server.getresponse()
        server.close()

        if resp.status == 201:
            return resp.getheader('Location')

        print 'Failed to upload with code %d and reason: %s'%(resp.status,
                resp.reason)
        raise Exception('Failed to upload '+fname)





class UploadToSourceForge(Command):

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
            self.info('Uploading', x)
            check_call(['rsync', '-v', '-e', 'ssh -x', x,
                '%s,%s@frs.sourceforge.net:%s'%(self.USERNAME, self.PROJECT,
                    self.rdir+'/')])

    def run(self, opts):
        self.opts = opts
        self.upload_installers()


class UploadInstallers(Command):
    description = 'Upload any installers present in dist/'
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

class UploadUserManual(Command):
    description = 'Build and upload the User Manual'
    sub_commands = ['manual']

    def run(self, opts):
        check_call(' '.join(['scp', '-r', 'src/calibre/manual/.build/html/*',
                    'divok:%s'%USER_MANUAL]), shell=True)


class UploadDemo(Command):

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

class UploadToServer(Command):

    description = 'Upload miscellaneous data to calibre server'

    def run(self, opts):
        check_call('ssh divok rm -f %s/calibre-\*.tar.gz'%DOWNLOADS, shell=True)
        check_call('scp dist/calibre-*.tar.gz divok:%s/'%DOWNLOADS, shell=True)
        check_call('gpg --armor --detach-sign dist/calibre-*.tar.gz',
                shell=True)
        check_call('scp dist/calibre-*.tar.gz.asc divok:%s/signatures/'%DOWNLOADS,
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



