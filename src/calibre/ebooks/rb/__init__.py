# -*- coding: utf-8 -*-


__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

from polyglot.builtins import unicode_type

HEADER = b'\xb0\x0c\xb0\x0c\x02\x00NUVO\x00\x00\x00\x00'


class RocketBookError(Exception):
    pass


def unique_name(name, used_names):
    name = os.path.basename(name)
    if len(name) < 32 and name not in used_names:
        return name
    else:
        ext = os.path.splitext(name)[1][:3]
        base_name = name[:22]
        for i in range(0, 9999):
            name = '%s-%s.%s' % (unicode_type(i).rjust('0', 4)[:4], base_name, ext)
            if name not in used_names:
                break
        return name
