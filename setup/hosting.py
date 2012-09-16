#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, time, sys, traceback, subprocess, urllib2, re, base64, httplib
from argparse import ArgumentParser, FileType
from subprocess import check_call
from tempfile import NamedTemporaryFile#, mkdtemp
from collections import OrderedDict

import mechanize
from lxml import html

def login_to_google(username, password):
    br = mechanize.Browser()
    br.addheaders = [('User-agent',
        'Mozilla/5.0 (X11; Linux x86_64; rv:9.0) Gecko/20100101 Firefox/9.0')]
    br.set_handle_robots(False)
    br.open('https://accounts.google.com/ServiceLogin?service=code')
    br.select_form(nr=0)
    br.form['Email'] = username
    br.form['Passwd'] = password
    raw = br.submit().read()
    if re.search(br'(?i)<title>.*?Account Settings</title>', raw) is None:
        x = re.search(br'(?is)<title>.*?</title>', raw)
        if x is not None:
            print ('Title of post login page: %s'%x.group())
        #open('/tmp/goog.html', 'wb').write(raw)
        raise ValueError(('Failed to login to google with credentials: %s %s'
            '\nGoogle sometimes requires verification when logging in from a '
            'new IP address. Use lynx to login and supply the verification, '
            'at: lynx -accept_all_cookies https://accounts.google.com/ServiceLogin?service=code')
                %(username, password))
    return br

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

class Base(object):  # {{{

    def __init__(self):
        self.d = os.path.dirname
        self.j = os.path.join
        self.a = os.path.abspath
        self.b = os.path.basename
        self.s = os.path.splitext
        self.e = os.path.exists

    def info(self, *args, **kwargs):
        print(*args, **kwargs)
        sys.stdout.flush()

    def warn(self, *args, **kwargs):
        print('\n'+'_'*20, 'WARNING','_'*20)
        print(*args, **kwargs)
        print('_'*50)
        sys.stdout.flush()

#}}}

class GoogleCode(Base):# {{{

    def __init__(self,
            # A mapping of filenames to file descriptions. The descriptions are
            # used to populate the description field for the upload on google
            # code
            files,

            # The unix name for the application.
            appname,

            # The version being uploaded
            version,

            # Google account username
            username,

            # Googlecode.com password
            password,

            # Google account password
            gmail_password,

            # The name of the google code project we are uploading to
            gc_project,

            # Server to which to upload the mapping of file names to google
            # code URLs. If not None, upload is performed via shelling out to
            # ssh, so you must have ssh-agent setup with the authenticated key
            # and ssh agent forwarding enabled
            gpaths_server=None,
            # The path on gpaths_server to which to upload the mapping data
            gpaths=None,

            # If True, files are replaced, otherwise existing files are skipped
            reupload=False,

            # The pattern to match filenames for the files being uploaded and
            # extract version information from them. Must have a named group
            # named version
            filename_pattern=r'{appname}-(?:portable-installer-)?(?P<version>.+?)(?:-(?:i686|x86_64|32bit|64bit))?\.(?:zip|exe|msi|dmg|tar\.bz2|tar\.xz|txz|tbz2)'

            ):
        self.username, self.password, = username, password
        self.gmail_password, self.gc_project = gmail_password, gc_project
        self.reupload, self.files, self.version = reupload, files, version
        self.gpaths, self.gpaths_server = gpaths, gpaths_server

        self.upload_host = '%s.googlecode.com'%gc_project
        self.files_list = 'http://code.google.com/p/%s/downloads/list'%gc_project
        self.delete_url = 'http://code.google.com/p/%s/downloads/delete?name=%%s'%gc_project

        self.filename_pat = re.compile(filename_pattern.format(appname=appname))
        for x in self.files:
            if self.filename_pat.match(os.path.basename(x)) is None:
                raise ValueError(('The filename %s does not match the '
                        'filename pattern')%os.path.basename(x))

    def upload_one(self, fname, retries=2):
        self.info('\nUploading', fname)
        typ = 'Type-' + ('Source' if fname.endswith('.xz') else 'Archive' if
                fname.endswith('.zip') else 'Installer')
        ext = os.path.splitext(fname)[1][1:]
        op  = 'OpSys-'+{'msi':'Windows','zip':'Windows',
                'dmg':'OSX','bz2':'Linux','xz':'All'}[ext]
        desc = self.files[fname]
        start = time.time()
        for i in range(retries):
            try:
                path = self.upload(os.path.abspath(fname), desc,
                    labels=[typ, op, 'Featured'], retry=100)
            except KeyboardInterrupt:
                raise SystemExit(1)
            except:
                traceback.print_exc()
                print ('\nUpload failed, trying again in 30 secs.',
                        '%d retries left.'%(retries-1))
                time.sleep(30)
            else:
                break
        self.info('Uploaded to:', path, 'in', int(time.time() - start),
                'seconds')
        return path

    def re_upload(self):
        fnames = {os.path.basename(x):x for x in self.files}
        existing = self.old_files.intersection(set(fnames))
        br = self.login_to_google()
        for x, src in fnames.iteritems():
            if not os.access(src, os.R_OK):
                continue
            if x in existing:
                self.info('Deleting', x)
                br.open(self.delete_url%x)
                br.select_form(predicate=lambda y: 'delete.do' in y.action)
                br.form.find_control(name='delete')
                br.submit(name='delete')
            self.upload_one(src)

    def __call__(self):
        self.paths = {}
        self.old_files = self.get_old_files()
        if self.reupload:
            return self.re_upload()

        for fname in self.files:
            bname = os.path.basename(fname)
            if bname in self.old_files:
                path = 'http://%s.googlecode.com/files/%s'%(self.gc_project,
                        bname)
                self.info(
                    '%s already uploaded, skipping. Assuming URL is: %s'%(
                        bname, path))
                self.old_files.remove(bname)
            else:
                path = self.upload_one(fname)
            self.paths[bname] = path
        self.info('Updating path map')
        for k, v in self.paths.iteritems():
            self.info('\t%s => %s'%(k, v))
        if self.gpaths and self.gpaths_server:
            raw = subprocess.Popen(['ssh', self.gpaths_server, 'cat', self.gpaths],
                    stdout=subprocess.PIPE).stdout.read()
            paths = eval(raw) if raw else {}
            paths.update(self.paths)
            rem = [x for x in paths if self.version not in x]
            for x in rem: paths.pop(x)
            raw = ['%r : %r,'%(k, v) for k, v in paths.items()]
            raw = '{\n\n%s\n\n}\n'%('\n'.join(raw))
            with NamedTemporaryFile() as t:
                t.write(raw)
                t.flush()
                check_call(['scp', t.name, '%s:%s'%(self.gpaths_server,
                    self.gpaths)])
        if self.old_files:
            self.br = self.login_to_google()
            self.delete_old_files()

    def login_to_google(self):
        self.info('Logging into Google')
        return login_to_google(self.username, self.gmail_password)

    def get_files_hosted_by_google_code(self):
        self.info('Getting existing files in google code:', self.gc_project)
        raw = urllib2.urlopen(self.files_list).read()
        root = html.fromstring(raw)
        ans = {}
        for a in root.xpath('//td[@class="vt id col_0"]/a[@href]'):
            ans[a.text.strip()] = a.get('href')
        return ans

    def get_old_files(self):
        ans = set()
        for fname in self.get_files_hosted_by_google_code():
            m = self.filename_pat.match(fname)
            if m is not None:
                ans.add(fname)
        return ans

    def delete_old_files(self):
        if not self.old_files:
            return
        self.info('Deleting old files from Google Code...')
        for fname in self.old_files:
            self.info('\tDeleting', fname)
            self.br.open(self.delete_url%fname)
            self.br.select_form(predicate=lambda x: 'delete.do' in x.action)
            self.br.form.find_control(name='delete')
            self.br.submit(name='delete')

    def encode_upload_request(self, fields, file_path):
        BOUNDARY = '----------Googlecode_boundary_reindeer_flotilla'

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
        body = [x.encode('ascii') if isinstance(x, unicode) else x for x in
                body]

        return ('multipart/form-data; boundary=%s' % BOUNDARY,
                b'\r\n'.join(body))

    def upload(self, fname, desc, labels=[], retry=0):
        form_fields = [('summary', desc)]
        form_fields.extend([('label', l.strip()) for l in labels])

        content_type, body = self.encode_upload_request(form_fields, fname)
        upload_uri = '/files'
        auth_token = base64.b64encode('%s:%s'% (self.username, self.password))
        headers = {
            'Authorization': 'Basic %s' % auth_token,
            'User-Agent': 'googlecode.com uploader v1',
            'Content-Type': content_type,
            }

        with NamedTemporaryFile(delete=False) as f:
            f.write(body)

        try:
            body = ReadFileWithProgressReporting(f.name)
            server = httplib.HTTPSConnection(self.upload_host)
            server.request('POST', upload_uri, body, headers)
            resp = server.getresponse()
            server.close()
        finally:
            os.remove(f.name)

        if resp.status == 201:
            return resp.getheader('Location')

        print ('Failed to upload with code %d and reason: %s'%(resp.status,
                resp.reason))
        if retry < 1:
            print ('Retrying in 5 seconds....')
            time.sleep(5)
            return self.upload(fname, desc, labels=labels, retry=retry+1)
        raise Exception('Failed to upload '+fname)


# }}}

class SourceForge(Base): # {{{

    # Note that you should manually ssh once to username,project@frs.sourceforge.net
    # on the staging server so that the host key is setup

    def __init__(self, files, project, version, username, replace=False):
        self.username, self.project, self.version = username, project, version
        self.base = '/home/frs/project/c/ca/'+project
        self.rdir = self.base + '/' + version
        self.files = files

    def __call__(self):
        for x in self.files:
            start = time.time()
            self.info('Uploading', x)
            for i in range(5):
                try:
                    check_call(['rsync', '-h', '-z', '--progress', '-e', 'ssh -x', x,
                    '%s,%s@frs.sourceforge.net:%s'%(self.username, self.project,
                        self.rdir+'/')])
                except KeyboardInterrupt:
                    raise SystemExit(1)
                except:
                    print ('\nUpload failed, trying again in 30 seconds')
                    time.sleep(30)
                else:
                    break
            print ('Uploaded in', int(time.time() - start), 'seconds\n\n')

# }}}

# CLI {{{
def cli_parser():
    epilog='Copyright Kovid Goyal 2012'

    p = ArgumentParser(
            description='Upload project files to a hosting service automatically',
            epilog=epilog
            )
    a = p.add_argument
    a('appname', help='The name of the application, all files to'
            ' upload should begin with this name')
    a('version', help='The version of the application, all files to'
            ' upload should contain this version')
    a('file_map', type=FileType('rb'),
            help='A file containing a mapping of files to be uploaded to '
            'descriptions of the files. The descriptions will be visible '
            'to users trying to get the file from the hosting service. '
            'The format of the file is filename: description, with one per '
            'line. filename can be a path to the file relative to the current '
            'directory.')
    a('--replace', action='store_true', default=False,
            help='If specified, existing files are replaced, otherwise '
            'they are skipped.')

    subparsers = p.add_subparsers(help='Where to upload to', dest='service',
            title='Service', description='Hosting service to upload to')
    gc = subparsers.add_parser('googlecode', help='Upload to googlecode',
            epilog=epilog)
    sf = subparsers.add_parser('sourceforge', help='Upload to sourceforge',
            epilog=epilog)
    cron = subparsers.add_parser('cron', help='Call script from cron')

    a = gc.add_argument

    a('project',
            help='The name of the project on google code we are uploading to')
    a('username',
            help='Username to log into your google account')
    a('password',
            help='Password to log into your google account')
    a('gc_password',
            help='Password for google code hosting.'
            ' Get it from http://code.google.com/hosting/settings')

    a('--path-map-server',
            help='A server to which the mapping of filenames to googlecode '
            'URLs will be uploaded. The upload happens via ssh, so you must '
            'have a working ssh agent')
    a('--path-map-location',
            help='Path on the server where the path map is placed.')

    a = sf.add_argument
    a('project',
            help='The name of the project on sourceforge we are uploading to')
    a('username',
            help='Sourceforge username')

    a = cron.add_argument
    a('username',
            help='Username to log into your google account')
    a('password',
            help='Password to log into your google account')

    return p

def main(args=None):
    cli = cli_parser()
    args = cli.parse_args(args)
    files = {}
    if args.service != 'cron':
        with args.file_map as f:
            for line in f:
                fname, _, desc = line.partition(':')
                fname, desc = fname.strip(), desc.strip()
                if fname and desc:
                    files[fname] = desc

    ofiles = OrderedDict()
    for x in sorted(files, key=lambda x:os.stat(x).st_size, reverse=True):
        ofiles[x] = files[x]

    if args.service == 'googlecode':
        gc = GoogleCode(ofiles, args.appname, args.version, args.username,
                args.gc_password, args.password, args.project,
                gpaths_server=args.path_map_server,
                gpaths=args.path_map_location, reupload=args.replace)
        gc()
    elif args.service == 'sourceforge':
        sf = SourceForge(ofiles, args.project, args.version, args.username,
                replace=args.replace)
        sf()
    elif args.service == 'cron':
        login_to_google(args.username, args.password)

if __name__ == '__main__':
    main()
# }}}

