#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, StringIO, urllib2, urlparse, base64, hashlib, httplib, socket
from ConfigParser import ConfigParser

from setup import Command, __appname__, __version__
from setup.install import Sdist

class Metadata(object):

    name = __appname__
    version = __version__
    author = 'Kovid Goyal'
    author_email = 'kovid@kovidgoyal.net'
    url = 'http://calibre-ebook.com'
    description = 'E-book management application.'
    long_description = open('README.md', 'rb').read()
    license = 'GPL'
    keywords = ['e-book', 'ebook', 'news', 'reading', 'catalog', 'books']
    platforms = ['Linux', 'Windows', 'OS X']
    classifiers    = [
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: X11 Applications :: Qt',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Hardware :: Hardware Drivers'
    ]


class PyPIRC(object):

    DEFAULT_REPOSITORY = 'http://pypi.python.org/pypi'
    DEFAULT_REALM = 'pypi'
    RC = os.path.expanduser('~/.pypirc')


    def read_pypirc(self):
        repository = self.DEFAULT_REPOSITORY
        realm = self.DEFAULT_REALM

        config = ConfigParser()
        config.read(self.RC)
        sections = config.sections()
        if 'distutils' in sections:
            # let's get the list of servers
            index_servers = config.get('distutils', 'index-servers')
            _servers = [server.strip() for server in
                        index_servers.split('\n')
                        if server.strip() != '']
            if _servers == []:
                # nothing set, let's try to get the default pypi
                if 'pypi' in sections:
                    _servers = ['pypi']
                else:
                    # the file is not properly defined, returning
                    # an empty dict
                    return {}
            for server in _servers:
                current = {'server': server}
                current['username'] = config.get(server, 'username')
                current['password'] = config.get(server, 'password')

                # optional params
                for key, default in (('repository',
                                        self.DEFAULT_REPOSITORY),
                                        ('realm', self.DEFAULT_REALM)):
                    if config.has_option(server, key):
                        current[key] = config.get(server, key)
                    else:
                        current[key] = default
                if (current['server'] == repository or
                    current['repository'] == repository):
                    return current
        elif 'server-login' in sections:
            # old format
            server = 'server-login'
            if config.has_option(server, 'repository'):
                repository = config.get(server, 'repository')
            else:
                repository = self.DEFAULT_REPOSITORY
            return {'username': config.get(server, 'username'),
                    'password': config.get(server, 'password'),
                    'repository': repository,
                    'server': server,
                    'realm': self.DEFAULT_REALM}

        return {}


class PyPIRegister(Command):

    description = 'Register distribution with PyPI'

    def add_options(self, parser):
        parser.add_option('--show-response', default=False, action='store_true',
            help='Show server responses')

    def run(self, opts):
        self.show_response = opts.show_response
        config = PyPIRC().read_pypirc()
        self.repository = config['repository']
        self.realm = config['realm']
        #self.verify_metadata()
        self.send_metadata(config['username'], config['password'])

    def send_metadata(self, username, password):
        auth = urllib2.HTTPPasswordMgr()
        host = urlparse.urlparse(self.repository)[1]
        auth.add_password(self.realm, host, username, password)
        # send the info to the server and report the result
        code, result = self.post_to_server(self.build_post_data('submit'),
            auth)
        self.info('Server response (%s): %s' % (code, result))

    def verify_metadata(self):
        ''' Send the metadata to the package index server to be checked.
        '''
        # send the info to the server and report the result
        (code, result) = self.post_to_server(self.build_post_data('verify'))
        print 'Server response (%s): %s'%(code, result)

    def build_post_data(self, action):
        # figure the data to send - the metadata plus some additional
        # information used by the package server
        meta = Metadata
        data = {
            ':action': action,
            'metadata_version' : '1.0',
            'name': Metadata.name,
            'version': Metadata.version,
            'summary': Metadata.description,
            'home_page': Metadata.url,
            'author': Metadata.author,
            'author_email': Metadata.author_email,
            'license': Metadata.license,
            'description': Metadata.long_description,
            'keywords': meta.keywords,
            'platform': meta.platforms,
            'classifiers': Metadata.classifiers,
            'download_url': 'UNKNOWN',
            # PEP 314
            'provides': [],
            'requires': [],
            'obsoletes': [],
        }
        if data['provides'] or data['requires'] or data['obsoletes']:
            data['metadata_version'] = '1.1'
        return data

    def post_to_server(self, data, auth=None):
        ''' Post a query to the server, and return a string response.
        '''
        self.info('Registering %s to %s' % (data['name'],
                                                self.repository))
        # Build up the MIME payload for the urllib2 POST data
        boundary = '--------------GHSKFJDLGDS7543FJKLFHRE75642756743254'
        sep_boundary = '\n--' + boundary
        end_boundary = sep_boundary + '--'
        body = StringIO.StringIO()
        for key, value in data.items():
            # handle multiple entries for the same name
            if type(value) not in (type([]), type( () )):
                value = [value]
            for value in value:
                value = unicode(value).encode("utf-8")
                body.write(sep_boundary)
                body.write('\nContent-Disposition: form-data; name="%s"'%key)
                body.write("\n\n")
                body.write(value)
                if value and value[-1] == '\r':
                    body.write('\n')  # write an extra newline (lurve Macs)
        body.write(end_boundary)
        body.write("\n")
        body = body.getvalue()

        # build the Request
        headers = {
            'Content-type': 'multipart/form-data; boundary=%s; charset=utf-8'%boundary,
            'Content-length': str(len(body))
        }
        req = urllib2.Request(self.repository, body, headers)

        # handle HTTP and include the Basic Auth handler
        opener = urllib2.build_opener(
            urllib2.HTTPBasicAuthHandler(password_mgr=auth)
        )
        data = ''
        try:
            result = opener.open(req)
        except urllib2.HTTPError, e:
            if self.show_response:
                data = e.fp.read()
            result = e.code, e.msg
        except urllib2.URLError, e:
            result = 500, str(e)
        else:
            if self.show_response:
                data = result.read()
            result = 200, 'OK'
        if self.show_response:
            print '-'*75, data, '-'*75
        return result

class PyPIUpload(PyPIRegister):

    description = 'Upload source distribution to PyPI'

    sub_commands = ['sdist', 'pypi_register']

    def add_options(self, parser):
        pass

    def run(self, opts):
        self.show_response = opts.show_response
        config = PyPIRC().read_pypirc()
        self.repository = config['repository']
        self.realm = config['realm']
        self.username = config['username']
        self.password = config['password']
        self.upload_file('sdist', '', Sdist.DEST)


    def upload_file(self, command, pyversion, filename):
        # Sign if requested
        #if self.sign:
        #    gpg_args = ["gpg", "--detach-sign", "-a", filename]
        #    if self.identity:
        #        gpg_args[2:2] = ["--local-user", self.identity]
        #    spawn(gpg_args,
        #          dry_run=self.dry_run)

        # Fill in the data - send all the meta-data in case we need to
        # register a new release
        content = open(filename,'rb').read()
        meta = Metadata
        md5 = hashlib.md5()
        md5.update(content)
        data = {
            # action
            ':action': 'file_upload',
            'protcol_version': '1',

            # identify release
            'name': meta.name,
            'version': meta.version,

            # file content
            'content': (os.path.basename(filename),content),
            'filetype': command,
            'pyversion': pyversion,
            'md5_digest': md5.hexdigest(),

            # additional meta-data
            'metadata_version' : '1.0',
            'summary': meta.description,
            'home_page': meta.url,
            'author': meta.author,
            'author_email': meta.author_email,
            'license': meta.license,
            'description': meta.long_description,
            'keywords': meta.keywords,
            'platform': meta.platforms,
            'classifiers': meta.classifiers,
            'download_url': 'UNKNOWN',
            # PEP 314
            'provides': [],
            'requires': [],
            'obsoletes': [],
            }
        comment = ''
        data['comment'] = comment

        #if self.sign:
        #    data['gpg_signature'] = (os.path.basename(filename) + ".asc",
        #                             open(filename+".asc").read())

        # set up the authentication
        auth = "Basic " + base64.encodestring(self.username + ":" + self.password).strip()

        # Build up the MIME payload for the POST data
        boundary = '--------------GHSKFJDLGDS7543FJKLFHRE75642756743254'
        sep_boundary = '\n--' + boundary
        end_boundary = sep_boundary + '--'
        body = StringIO.StringIO()
        for key, value in data.items():
            # handle multiple entries for the same name
            if type(value) != type([]):
                value = [value]
            for value in value:
                if type(value) is tuple:
                    fn = ';filename="%s"' % value[0]
                    value = value[1]
                else:
                    fn = ""
                value = str(value)
                body.write(sep_boundary)
                body.write('\nContent-Disposition: form-data; name="%s"'%key)
                body.write(fn)
                body.write("\n\n")
                body.write(value)
                if value and value[-1] == '\r':
                    body.write('\n')  # write an extra newline (lurve Macs)
        body.write(end_boundary)
        body.write("\n")
        body = body.getvalue()

        self.info("Submitting %s to %s" % (filename, self.repository))

        # build the Request
        # We can't use urllib2 since we need to send the Basic
        # auth right with the first request
        schema, netloc, url, params, query, fragments = \
            urlparse.urlparse(self.repository)
        assert not params and not query and not fragments
        if schema == 'http':
            http = httplib.HTTPConnection(netloc)
        elif schema == 'https':
            http = httplib.HTTPSConnection(netloc)
        else:
            raise AssertionError("unsupported schema "+schema)

        data = ''
        try:
            http.connect()
            http.putrequest("POST", url)
            http.putheader('Content-type',
                           'multipart/form-data; boundary=%s'%boundary)
            http.putheader('Content-length', str(len(body)))
            http.putheader('Authorization', auth)
            http.endheaders()
            http.send(body)
        except socket.error, e:
            self.warn(str(e))
            raise SystemExit(1)

        r = http.getresponse()
        if r.status == 200:
            self.info('Server response (%s): %s' % (r.status, r.reason))
        else:
            self.info('Upload failed (%s): %s' % (r.status, r.reason))
            raise SystemExit(1)
        if self.show_response:
            print '-'*75, r.read(), '-'*75
