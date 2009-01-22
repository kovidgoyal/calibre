'''
Dynamic language lookup of translations for user-visible strings.
'''

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

from cStringIO import StringIO
from gettext import GNUTranslations
from calibre.translations.compiled import translations

__all__ = ['translate']

_CACHE = {}

def translate(lang, text):
    trans = None
    if lang in _CACHE:
        trans = _CACHE[lang]
    elif lang in translations:
        buf = StringIO(translations[lang])
        trans = GNUTranslations(buf)
        _CACHE[lang] = trans
    if trans is None:
        return getattr(__builtins__, '_', lambda x: x)(text)
    return trans.ugettext(text)
