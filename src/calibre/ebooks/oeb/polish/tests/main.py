#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.utils.run_tests import find_tests_in_package, run_tests


def find_tests():
    return find_tests_in_package('calibre.ebooks.oeb.polish.tests')


if __name__ == '__main__':
    try:
        import init_calibre  # noqa
    except ImportError:
        pass
    run_tests(find_tests)
