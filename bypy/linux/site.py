#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import builtins
import os
import sys

import _sitebuiltins

USER_SITE = None


def set_quit():
    eof = 'Ctrl-D (i.e. EOF)'
    builtins.quit = _sitebuiltins.Quitter('quit', eof)
    builtins.exit = _sitebuiltins.Quitter('exit', eof)


def setup_openssl_environment():
    # Workaround for Linux distros that have still failed to get their heads
    # out of their asses and implement a common location for SSL certificates.
    # It's not that hard people, there exists a wonderful tool called the symlink
    # See http://www.mobileread.com/forums/showthread.php?t=256095
    if 'SSL_CERT_FILE' not in os.environ and 'SSL_CERT_DIR' not in os.environ:
        if os.access('/etc/pki/tls/certs/ca-bundle.crt', os.R_OK):
            os.environ['SSL_CERT_FILE'] = '/etc/pki/tls/certs/ca-bundle.crt'
        # morons in Fedora removed the bundle file in Fedora 44.
        # https://fedoraproject.org/wiki/Changes/droppingOfCertPemFile
        # Hopefully there does not exist another distro that uses this dir for something else.
        elif os.path.isdir('/etc/pki/tls/certs'):
            os.environ['SSL_CERT_DIR'] = '/etc/pki/tls/certs'
        elif os.path.isdir('/etc/ssl/certs'):
            os.environ['SSL_CERT_DIR'] = '/etc/ssl/certs'


def preload_libxml2():
    # QtWebEngineProcess on some ancient Linux systems probes for GPU backends
    # which loads swrast_dri.so which links against system libxml2, which
    # overwrites or global libxml2 symbols.
    # So we preload lxml and html5_parser as a workaround.
    # Thankfully this is basically only needed for ancient Debian as modern
    # mesa uses libexpat not libxml2.
    # We need a specific version of libxml2 as html5-parser checks the version,
    # so preload it to ensure we have the correct one.
    from html5_parser import parse
    setattr(preload_libxml2, 'parse', parse)


def set_helper():
    builtins.help = _sitebuiltins._Helper()


def main():
    sys.argv[0] = sys.calibre_basename
    set_helper()
    setup_openssl_environment()
    preload_libxml2()
    set_quit()
    mod = __import__(sys.calibre_module, fromlist=[1])
    func = getattr(mod, sys.calibre_function)
    return func()


if __name__ == '__main__':
    main()
