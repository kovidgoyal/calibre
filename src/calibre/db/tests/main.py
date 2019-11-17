#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from calibre.utils.run_tests import find_tests_in_dir, run_tests


def find_tests():
    base = os.path.dirname(os.path.abspath(__file__))
    return find_tests_in_dir(base)


if __name__ == '__main__':
    try:
        import init_calibre  # noqa
    except ImportError:
        pass
    run_tests(find_tests)
