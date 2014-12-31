#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

builtin_snips = {
    '<<' : {
        'description': _('Insert a HTML tag'),
        'template': '<$1>${2*}</$1>',
    },

    '</' : {
        'description': _('Insert a self closing HTML tag'),
        'template': '<$1/>$2',
    },

    '<a' : {
        'description': _('Insert a HTML link'),
        'template': '<a href="$1">${2*}</a>',
    },
}

