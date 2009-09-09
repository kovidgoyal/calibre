'''
Dynamic language lookup of translations for user-visible strings.
'''

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import os

from gettext import GNUTranslations
from calibre.utils.localization import get_lc_messages_path

__all__ = ['translate']

_CACHE = {}

def translate(lang, text):
    trans = None
    if lang in _CACHE:
        trans = _CACHE[lang]
    else:
        mpath = get_lc_messages_path(lang)
        if mpath is not None:
            p = os.path.join(mpath, 'messages.mo')
            if os.path.exists(p):
                trans = GNUTranslations(open(p, 'rb'))
                _CACHE[lang] = trans
    if trans is None:
        return getattr(__builtins__, '_', lambda x: x)(text)
    return trans.ugettext(text)
