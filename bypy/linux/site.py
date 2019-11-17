#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2016, Kovid Goyal <kovid at kovidgoyal.net>

import sys
import encodings  # noqa
import __builtin__
import locale
import os
import codecs


def set_default_encoding():
    try:
        locale.setlocale(locale.LC_ALL, '')
    except:
        print ('WARNING: Failed to set default libc locale, using en_US.UTF-8')
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    try:
        enc = locale.getdefaultlocale()[1]
    except Exception:
        enc = None
    if not enc:
        enc = locale.nl_langinfo(locale.CODESET)
    if not enc or enc.lower() == 'ascii':
        enc = 'UTF-8'
    try:
        enc = codecs.lookup(enc).name
    except LookupError:
        enc = 'UTF-8'
    sys.setdefaultencoding(enc)
    del sys.setdefaultencoding


class _Helper(object):
    """Define the builtin 'help'.
    This is a wrapper around pydoc.help (with a twist).

    """

    def __repr__(self):
        return "Type help() for interactive help, " \
            "or help(object) for help about object."

    def __call__(self, *args, **kwds):
        import pydoc
        return pydoc.help(*args, **kwds)


def set_helper():
    __builtin__.help = _Helper()


def setup_openssl_environment():
    # Workaround for Linux distros that have still failed to get their heads
    # out of their asses and implement a common location for SSL certificates.
    # It's not that hard people, there exists a wonderful tool called the symlink
    # See http://www.mobileread.com/forums/showthread.php?t=256095
    if b'SSL_CERT_FILE' not in os.environ and b'SSL_CERT_DIR' not in os.environ:
        if os.access('/etc/pki/tls/certs/ca-bundle.crt', os.R_OK):
            os.environ['SSL_CERT_FILE'] = '/etc/pki/tls/certs/ca-bundle.crt'
        elif os.path.isdir('/etc/ssl/certs'):
            os.environ['SSL_CERT_DIR'] = '/etc/ssl/certs'


def main():
    try:
        sys.argv[0] = sys.calibre_basename
        dfv = os.environ.get('CALIBRE_DEVELOP_FROM', None)
        if dfv and os.path.exists(dfv):
            sys.path.insert(0, os.path.abspath(dfv))
        set_default_encoding()
        set_helper()
        setup_openssl_environment()
        mod = __import__(sys.calibre_module, fromlist=[1])
        func = getattr(mod, sys.calibre_function)
        return func()
    except SystemExit as err:
        if err.code is None:
            return 0
        if isinstance(err.code, int):
            return err.code
        print (err.code)
        return 1
    except:
        import traceback
        traceback.print_exc()
    return 1
