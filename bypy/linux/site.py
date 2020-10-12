#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import builtins
import os
import sys

import _sitebuiltins


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
        elif os.path.isdir('/etc/ssl/certs'):
            os.environ['SSL_CERT_DIR'] = '/etc/ssl/certs'


def set_helper():
    builtins.help = _sitebuiltins._Helper()


def main():
    sys.argv[0] = sys.calibre_basename
    set_helper()
    setup_openssl_environment()
    set_quit()
    mod = __import__(sys.calibre_module, fromlist=[1])
    func = getattr(mod, sys.calibre_function)
    return func()


if __name__ == '__main__':
    main()
