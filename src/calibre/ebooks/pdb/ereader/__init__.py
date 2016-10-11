# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os


class EreaderError(Exception):
    pass


def image_name(name, taken_names=[]):
    name = os.path.basename(name)

    if len(name) > 32:
        cut = len(name) - 32
        names = name[:10]
        namee = name[10+cut:]
        name = '%s%s.png' % (names, namee)

    while name in taken_names:
        for i in xrange(999999999999999999999999999):
            name = '%s%s.png' % (name[:-len('%s' % i)], i)

    name = name.ljust(32, '\x00')[:32]

    return name

