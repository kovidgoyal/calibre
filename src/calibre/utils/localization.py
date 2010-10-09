#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, locale, re, cStringIO, cPickle
from gettext import GNUTranslations

_available_translations = None

def available_translations():
    global _available_translations
    if _available_translations is None:
        stats = P('localization/stats.pickle')
        if os.path.exists(stats):
            stats = cPickle.load(open(stats, 'rb'))
        else:
            stats = {}
        _available_translations = [x for x in stats if stats[x] > 0.1]
    return _available_translations

def get_lang():
    'Try to figure out what language to display the interface in'
    from calibre.utils.config import prefs
    lang = prefs['language']
    lang = os.environ.get('CALIBRE_OVERRIDE_LANG', lang)
    if lang is not None:
        return lang
    lang = locale.getdefaultlocale(['LANGUAGE', 'LC_ALL', 'LC_CTYPE',
                                    'LC_MESSAGES', 'LANG'])[0]
    if lang is None and os.environ.has_key('LANG'): # Needed for OS X
        try:
            lang = os.environ['LANG']
        except:
            pass
    if lang:
        match = re.match('[a-z]{2,3}(_[A-Z]{2}){0,1}', lang)
        if match:
            lang = match.group()
    if lang == 'zh':
        lang = 'zh_CN'
    if lang is None:
        lang = 'en'
    return lang

def messages_path(lang):
    return P('localization/locales/%s/LC_MESSAGES'%lang)

def get_lc_messages_path(lang):
    hlang = None
    if lang in available_translations():
        hlang = lang
    else:
        xlang = lang.split('_')[0]
        if xlang in available_translations():
            hlang = xlang
    if hlang is not None:
        return messages_path(hlang)
    return None


def set_translators():
    # To test different translations invoke as
    # CALIBRE_OVERRIDE_LANG=de_DE.utf8 program
    lang = get_lang()
    if lang:
        buf = iso639 = None
        if os.access(lang+'.po', os.R_OK):
            from calibre.translations.msgfmt import make
            buf = cStringIO.StringIO()
            make(lang+'.po', buf)
            buf = cStringIO.StringIO(buf.getvalue())

        mpath = get_lc_messages_path(lang)
        if mpath is not None:
            if buf is None:
                buf = open(os.path.join(mpath, 'messages.mo'), 'rb')
            mpath = mpath.replace(os.sep+'nds'+os.sep, os.sep+'de'+os.sep)
            isof = os.path.join(mpath, 'iso639.mo')
            if os.path.exists(isof):
                iso639 = open(isof, 'rb')

        if buf is not None:
            t = GNUTranslations(buf)
            if iso639 is not None:
                iso639 = GNUTranslations(iso639)
                t.add_fallback(iso639)
            t.install(unicode=True)

_iso639 = None
_extra_lang_codes = {
        'pt_BR' : _('Brazilian Portuguese'),
        'en_GB' : _('English (UK)'),
        'zh_CN' : _('Simplified Chinese'),
        'zh_HK' : _('Chinese (HK)'),
        'zh_TW' : _('Traditional Chinese'),
        'en'    : _('English'),
        'en_AU' : _('English (Australia)'),
        'en_NZ' : _('English (New Zealand)'),
        'en_CA' : _('English (Canada)'),
        'en_IN' : _('English (India)'),
        'en_TH' : _('English (Thailand)'),
        'en_CY' : _('English (Cyprus)'),
        'en_PK' : _('English (Pakistan)'),
        'en_IL' : _('English (Israel)'),
        'en_SG' : _('English (Singapore)'),
        'en_YE' : _('English (Yemen)'),
        'en_IE' : _('English (Ireland)'),
        'en_CN' : _('English (China)'),
        'es_PY' : _('Spanish (Paraguay)'),
        'de_AT' : _('German (AT)'),
        'fr_BE' : _('French (BE)'),
        'nl'    : _('Dutch (NL)'),
        'nl_BE' : _('Dutch (BE)'),
        'und'   : _('Unknown')
        }

def get_language(lang):
    global _iso639
    if lang in _extra_lang_codes:
        return _extra_lang_codes[lang]
    ip = P('localization/iso639.pickle')
    if not os.path.exists(ip):
        return lang
    if _iso639 is None:
        _iso639 = cPickle.load(open(ip, 'rb'))
    ans = lang
    lang = lang.split('_')[0].lower()
    if len(lang) == 2:
        ans = _iso639['by_2'].get(lang, ans)
    elif len(lang) == 3:
        if lang in _iso639['by_3b']:
            ans = _iso639['by_3b'][lang]
        else:
            ans = _iso639['by_3t'].get(lang, ans)
    return _(ans)


def set_qt_translator(translator):
    lang = get_lang()
    if lang is not None:
        if lang == 'nds':
            lang = 'de'
        mpath = get_lc_messages_path(lang)
        if mpath is not None:
            p = os.path.join(mpath, 'qt.qm')
            if os.path.exists(p):
                return translator.load(p)
    return False

