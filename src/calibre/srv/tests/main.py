#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import unittest

from calibre.utils.run_tests import find_tests_in_package, run_tests


def find_tests() -> unittest.TestSuite:
    return find_tests_in_package('calibre.srv.tests')


if __name__ == '__main__':
    try:
        import init_calibre  # ruff: ignore[unused-import]
    except ImportError:
        pass
    run_tests(find_tests)
