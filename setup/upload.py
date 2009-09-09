#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, re, cStringIO
from subprocess import check_call

from setup import Command, __version__, installer_name

PREFIX = "/var/www/calibre.kovidgoyal.net"
DOWNLOADS = PREFIX+"/htdocs/downloads"
BETAS = DOWNLOADS +'/betas'
DOCS = PREFIX+"/htdocs/apidocs"
USER_MANUAL = PREFIX+'/htdocs/user_manual'
HTML2LRF = "calibre/ebooks/lrf/html/demo"
TXT2LRF  = "src/calibre/ebooks/lrf/txt/demo"
MOBILEREAD = 'ftp://dev.mobileread.com/calibre/'



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
        installers = list(map(installer_name, ('dmg', 'exe', 'tar.bz2')))
        installers.append(installer_name('tar.bz2', is64bit=True))
        map(self.upload_installer, installers)

        check_call('''ssh divok echo %s \\> %s/latest_version'''\
                   %(__version__, DOWNLOADS), shell=True)

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



