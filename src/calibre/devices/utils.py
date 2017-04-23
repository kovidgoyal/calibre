#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, time, re
from functools import partial

from calibre.devices.errors import DeviceError, WrongDestinationError, FreeSpaceError


def sanity_check(on_card, files, card_prefixes, free_space):
    if on_card == 'carda' and not card_prefixes[0]:
        raise WrongDestinationError(_(
            'The reader has no storage card %s. You may have changed '
            'the default send to device action. Right click on the "Send '
            'to device" button and reset the default action to be '
            '"Send to main memory".')%'A')
    elif on_card == 'cardb' and not card_prefixes[1]:
        raise WrongDestinationError(_(
            'The reader has no storage card %s. You may have changed '
            'the default send to device action. Right click on the "Send '
            'to device" button and reset the default action to be '
            '"Send to main memory".')%'B')
    elif on_card and on_card not in ('carda', 'cardb'):
        raise DeviceError(_('Selected slot: %s is not supported.') % on_card)

    size = 0
    for f in files:
        size += os.path.getsize(getattr(f, 'name', f))

    if not on_card and size > free_space[0] - 2*1024*1024:
        raise FreeSpaceError(_("There is insufficient free space in main memory"))
    if on_card == 'carda' and size > free_space[1] - 1024*1024:
        raise FreeSpaceError(_("There is insufficient free space on the storage card"))
    if on_card == 'cardb' and size > free_space[2] - 1024*1024:
        raise FreeSpaceError(_("There is insufficient free space on the storage card"))


def build_template_regexp(template):
    from calibre import prints

    def replfunc(match, seen=None):
        v = match.group(1)
        if v in ['authors', 'author_sort']:
            v = 'author'
        if v in ('title', 'series', 'series_index', 'isbn', 'author'):
            if v not in seen:
                seen.add(v)
                return '(?P<' + v + '>.+?)'
        return '(.+?)'
    s = set()
    f = partial(replfunc, seen=s)

    try:
        template = template.rpartition('/')[2]
        return re.compile(re.sub('{([^}]*)}', f, template) + '([_\d]*$)')
    except:
        prints(u'Failed to parse template: %r'%template)
        template = u'{title} - {authors}'
        return re.compile(re.sub('{([^}]*)}', f, template) + '([_\d]*$)')


def create_upload_path(mdata, fname, template, sanitize,
        prefix_path='',
        path_type=os.path,
        maxlen=250,
        use_subdirs=True,
        news_in_folder=True,
        filename_callback=lambda x, y:x,
        sanitize_path_components=lambda x: x
        ):
    from calibre.library.save_to_disk import get_components, config
    from calibre.utils.filenames import shorten_components_to

    special_tag = None
    if mdata.tags:
        for t in mdata.tags:
            if t.startswith(_('News')) or t.startswith('/'):
                special_tag = t
                break

    if mdata.tags and _('News') in mdata.tags:
        try:
            p = mdata.pubdate
            date  = (p.year, p.month, p.day)
        except:
            today = time.localtime()
            date = (today[0], today[1], today[2])
        template = u"{title}_%d-%d-%d" % date

    fname = sanitize(fname)
    ext = path_type.splitext(fname)[1]

    opts = config().parse()
    if not isinstance(template, unicode):
        template = template.decode('utf-8')
    app_id = str(getattr(mdata, 'application_id', ''))
    id_ = mdata.get('id', fname)
    extra_components = get_components(template, mdata, id_,
            timefmt=opts.send_timefmt, length=maxlen-len(app_id)-1,
            sanitize_func=sanitize, last_has_extension=False)
    if not extra_components:
        extra_components.append(sanitize(filename_callback(fname,
            mdata)))
    else:
        extra_components[-1] = sanitize(filename_callback(extra_components[-1]+ext, mdata))

    if extra_components[-1] and extra_components[-1][0] in ('.', '_'):
        extra_components[-1] = 'x' + extra_components[-1][1:]

    if special_tag is not None:
        name = extra_components[-1]
        extra_components = []
        tag = special_tag
        if tag.startswith(_('News')):
            if news_in_folder:
                extra_components.append('News')
        else:
            for c in tag.split('/'):
                c = sanitize(c)
                if not c:
                    continue
                extra_components.append(c)
        extra_components.append(name)

    if not use_subdirs:
        extra_components = extra_components[-1:]

    def remove_trailing_periods(x):
        ans = x
        while ans.endswith('.'):
            ans = ans[:-1].strip()
        if not ans:
            ans = 'x'
        return ans

    extra_components = list(map(remove_trailing_periods, extra_components))
    components = shorten_components_to(maxlen - len(prefix_path), extra_components)
    components = sanitize_path_components(components)
    if prefix_path:
        filepath = path_type.join(prefix_path, *components)
    else:
        filepath = path_type.join(*components)

    return filepath
