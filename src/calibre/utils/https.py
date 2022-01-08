#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import ssl, socket, re
from contextlib import closing

from calibre import get_proxies
from polyglot import http_client
from polyglot.urllib import urlsplit
has_ssl_verify = hasattr(ssl, 'create_default_context') and hasattr(ssl, '_create_unverified_context')


class HTTPError(ValueError):

    def __init__(self, url, code):
        msg = '%s returned an unsupported http response code: %d (%s)' % (
                url, code, http_client.responses.get(code, None))
        ValueError.__init__(self, msg)
        self.code = code
        self.url = url


if has_ssl_verify:
    class HTTPSConnection(http_client.HTTPSConnection):

        def __init__(self, ssl_version, *args, **kwargs):
            cafile = kwargs.pop('cert_file', None)
            if cafile is None:
                kwargs['context'] = ssl._create_unverified_context()
            else:
                kwargs['context'] = ssl.create_default_context(cafile=cafile)
            http_client.HTTPSConnection.__init__(self, *args, **kwargs)
else:
    # Check certificate hostname {{{
    # Implementation taken from python 3
    class CertificateError(ValueError):
        pass

    def _dnsname_match(dn, hostname, max_wildcards=1):
        """Matching according to RFC 6125, section 6.4.3

        http://tools.ietf.org/html/rfc6125#section-6.4.3
        """
        pats = []
        if not dn:
            return False

        parts = dn.split(r'.')
        leftmost, remainder = parts[0], parts[1:]

        wildcards = leftmost.count('*')
        if wildcards > max_wildcards:
            # Issue #17980: avoid denials of service by refusing more
            # than one wildcard per fragment.  A survery of established
            # policy among SSL implementations showed it to be a
            # reasonable choice.
            raise CertificateError(
                "too many wildcards in certificate DNS name: " + repr(dn))

        # speed up common case w/o wildcards
        if not wildcards:
            return dn.lower() == hostname.lower()

        # RFC 6125, section 6.4.3, subitem 1.
        # The client SHOULD NOT attempt to match a presented identifier in which
        # the wildcard character comprises a label other than the left-most label.
        if leftmost == '*':
            # When '*' is a fragment by itself, it matches a non-empty dotless
            # fragment.
            pats.append('[^.]+')
        elif leftmost.startswith('xn--') or hostname.startswith('xn--'):
            # RFC 6125, section 6.4.3, subitem 3.
            # The client SHOULD NOT attempt to match a presented identifier
            # where the wildcard character is embedded within an A-label or
            # U-label of an internationalized domain name.
            pats.append(re.escape(leftmost))
        else:
            # Otherwise, '*' matches any dotless string, e.g. www*
            pats.append(re.escape(leftmost).replace(r'\*', '[^.]*'))

        # add the remaining fragments, ignore any wildcards
        for frag in remainder:
            pats.append(re.escape(frag))

        pat = re.compile(r'\A' + r'\.'.join(pats) + r'\Z', re.IGNORECASE)
        return pat.match(hostname)

    def match_hostname(cert, hostname):
        """Verify that *cert* (in decoded format as returned by
        SSLSocket.getpeercert()) matches the *hostname*.  RFC 2818 and RFC 6125
        rules are followed, but IP addresses are not accepted for *hostname*.

        CertificateError is raised on failure. On success, the function
        returns nothing.
        """
        if not cert:
            raise ValueError("empty or no certificate")
        dnsnames = []
        san = cert.get('subjectAltName', ())
        for key, value in san:
            if key == 'DNS':
                if _dnsname_match(value, hostname):
                    return
                dnsnames.append(value)
        if not dnsnames:
            # The subject is only checked when there is no dNSName entry
            # in subjectAltName
            for sub in cert.get('subject', ()):
                for key, value in sub:
                    # XXX according to RFC 2818, the most specific Common Name
                    # must be used.
                    if key == 'commonName':
                        if _dnsname_match(value, hostname):
                            return
                        dnsnames.append(value)
        if len(dnsnames) > 1:
            raise CertificateError("hostname %r "
                "doesn't match either of %s"
                % (hostname, ', '.join(map(repr, dnsnames))))
        elif len(dnsnames) == 1:
            raise CertificateError("hostname %r "
                "doesn't match %r"
                % (hostname, dnsnames[0]))
        else:
            raise CertificateError("no appropriate commonName or "
                "subjectAltName fields were found")
    # }}}

    class HTTPSConnection(http_client.HTTPSConnection):

        def __init__(self, ssl_version, *args, **kwargs):
            http_client.HTTPSConnection.__init__(self, *args, **kwargs)
            self.calibre_ssl_version = ssl_version

        def connect(self):
            """Connect to a host on a given (SSL) port, properly verifying the SSL
            certificate, both that it is valid and that its declared hostnames
            match the hostname we are connecting to."""

            sock = socket.create_connection((self.host, self.port),
                                            self.timeout, self.source_address)
            if self._tunnel_host:
                self.sock = sock
                self._tunnel()
            self.sock = ssl.wrap_socket(sock, cert_reqs=ssl.CERT_REQUIRED, ca_certs=self.cert_file, ssl_version=self.calibre_ssl_version)
            getattr(ssl, 'match_hostname', match_hostname)(self.sock.getpeercert(), self.host)


def get_https_resource_securely(
    url, cacerts='calibre-ebook-root-CA.crt', timeout=60, max_redirects=5, ssl_version=None, headers=None, get_response=False):
    '''
    Download the resource pointed to by url using https securely (verify server
    certificate).  Ensures that redirects, if any, are also downloaded
    securely. Needs a CA certificates bundle (in PEM format) to verify the
    server's certificates.

    You can pass cacerts=None to download using SSL but without verifying the server certificate.
    '''
    if ssl_version is None:
        try:
            ssl_version = ssl.PROTOCOL_TLSv1_2
        except AttributeError:
            ssl_version = ssl.PROTOCOL_TLSv1  # old python
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

    c = HTTPSConnection(ssl_version, hostname, port, cert_file=cert_file, timeout=timeout)
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
                newurl, cacerts=cacerts, timeout=timeout, max_redirects=max_redirects-1, ssl_version=ssl_version, get_response=get_response)
        if response.status != http_client.OK:
            raise HTTPError(url, response.status)
        if get_response:
            return response
        return response.read()


if __name__ == '__main__':
    print(get_https_resource_securely('https://code.calibre-ebook.com/latest'))
