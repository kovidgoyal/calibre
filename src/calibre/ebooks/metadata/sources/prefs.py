#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.utils.config import JSONConfig

msprefs = JSONConfig('metadata_sources/global.json')
msprefs.defaults['txt_comments'] = False
msprefs.defaults['ignore_fields'] = []
msprefs.defaults['user_default_ignore_fields'] = []
msprefs.defaults['max_tags'] = 20
msprefs.defaults['wait_after_first_identify_result'] = 30  # seconds
msprefs.defaults['wait_after_first_cover_result'] = 60  # seconds
msprefs.defaults['swap_author_names'] = False
msprefs.defaults['fewer_tags'] = True
msprefs.defaults['find_first_edition_date'] = False

# Google covers are often poor quality (scans/errors) but they have high
# resolution, so they trump covers from better sources. So make sure they
# are only used if no other covers are found.
msprefs.defaults['cover_priorities'] = {'Google':2, 'Google Images':2, 'Big Book Search':2}



