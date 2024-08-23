#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import ssl
from contextlib import closing

from calibre import get_proxies
from calibre.utils.resources import get_path as P
from polyglot import http_client
from polyglot.urllib import urlsplit


class HTTPError(ValueError):

    def __init__(self, url, code):
        msg = '%s returned an unsupported http response code: %d (%s)' % (
                url, code, http_client.responses.get(code, None))
        ValueError.__init__(self, msg)
        self.code = code
        self.url = url


class HTTPSConnection(http_client.HTTPSConnection):

    def __init__(self, *args, **kwargs):
        cafile = kwargs.pop('cert_file', None)
        if cafile is None:
            kwargs['context'] = ssl._create_unverified_context()
        else:
            kwargs['context'] = ssl.create_default_context(cafile=cafile)
        if kwargs.pop('disable_x509_strict_checking', False):
            # python 3.13 forces VERIFY_X509_STRICT which breaks with the
            # private certificate used for downloads from code.calibre-ebook.com
            kwargs['context'].verify_flags &= ~ssl.VERIFY_X509_STRICT
        else:
            kwargs['context'].verify_flags |= ssl.VERIFY_X509_STRICT
        http_client.HTTPSConnection.__init__(self, *args, **kwargs)


def get_https_resource_securely(
    url, cacerts='calibre-ebook-root-CA.crt', timeout=60, max_redirects=5, ssl_version=None, headers=None, get_response=False):
    '''
    Download the resource pointed to by url using https securely (verify server
    certificate).  Ensures that redirects, if any, are also downloaded
    securely. Needs a CA certificates bundle (in PEM format) to verify the
    server's certificates.

    You can pass cacerts=None to download using SSL but without verifying the server certificate.
    '''
    disable_x509_strict_checking = cacerts == 'calibre-ebook-root-CA.crt'
    cert_file = None
    if cacerts is not None:
        cert_file = P(cacerts, allow_user_override=False)
    p = urlsplit(url)
    if p.scheme != 'https':
        raise ValueError(f'URL {url} scheme must be https, not {p.scheme!r}')

    hostname, port = p.hostname, p.port
    proxies = get_proxies()
    has_proxy = False
    for q in ('https', 'http'):
        if q in proxies:
            try:
                h, po = proxies[q].rpartition(':')[::2]
                po = int(po)
                if h:
                    hostname, port, has_proxy = h, po, True
                    break
            except Exception:
                # Invalid proxy, ignore
                pass

    c = HTTPSConnection(hostname, port, cert_file=cert_file, timeout=timeout, disable_x509_strict_checking=disable_x509_strict_checking)
    if has_proxy:
        c.set_tunnel(p.hostname, p.port)

    with closing(c):
        c.connect()  # This is needed for proxy connections
        path = p.path or '/'
        if p.query:
            path += '?' + p.query
        c.request('GET', path, headers=headers or {})
        response = c.getresponse()
        if response.status in (http_client.MOVED_PERMANENTLY, http_client.FOUND, http_client.SEE_OTHER):
            if max_redirects <= 0:
                raise ValueError('Too many redirects, giving up')
            newurl = response.getheader('Location', None)
            if newurl is None:
                raise ValueError('%s returned a redirect response with no Location header' % url)
            return get_https_resource_securely(
                newurl, cacerts=cacerts, timeout=timeout, max_redirects=max_redirects-1, get_response=get_response)
        if response.status != http_client.OK:
            raise HTTPError(url, response.status)
        if get_response:
            return response
        return response.read()


if __name__ == '__main__':
    print(get_https_resource_securely('https://code.calibre-ebook.com/latest'))
