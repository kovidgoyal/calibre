#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from calibre.constants import plugins

_icu = _collator = None
_locale = None

_none = u''
_none2 = b''

def get_locale():
    global _locale
    if _locale is None:
        from calibre.utils.localization import get_lang
        _locale = get_lang()
    return _locale

def load_icu():
    global _icu
    if _icu is None:
        _icu = plugins['icu'][0]
        if _icu is None:
            print plugins['icu'][1]
        else:
            if not _icu.ok:
                print 'icu not ok'
                _icu = None
    return _icu

def load_collator():
    global _collator
    if _collator is None:
        icu = load_icu()
        if icu is not None:
            _collator = icu.Collator(get_locale())
    return _collator


def py_sort_key(obj):
    if not obj:
        return _none
    return obj.lower()

def icu_sort_key(collator, obj):
    if not obj:
        return _none2
    return collator.sort_key(obj.lower())

def py_case_sensitive_sort_key(obj):
    if not obj:
        return _none
    return obj

def icu_case_sensitive_sort_key(collator, obj):
    if not obj:
        return _none2
    return collator.sort_key(obj)

def icu_strcmp(collator, a, b):
    return collator.strcmp(a.lower(), b.lower())

def py_strcmp(a, b):
    return cmp(a.lower(), b.lower())

def icu_case_sensitive_strcmp(collator, a, b):
    return collator.strcmp(a, b)


load_icu()
load_collator()
_icu_not_ok = _icu is None or _collator is None


################# The string functions ########################################
sort_key = py_sort_key if _icu_not_ok else partial(icu_sort_key, _collator)

strcmp = py_strcmp if _icu_not_ok else partial(icu_strcmp, _collator)

case_sensitive_sort_key = py_case_sensitive_sort_key if _icu_not_ok else \
        icu_case_sensitive_sort_key

case_sensitive_strcmp = cmp if _icu_not_ok else icu_case_sensitive_strcmp

upper = (lambda s: s.upper()) if _icu_not_ok else \
    partial(_icu.upper, get_locale())

lower = (lambda s: s.lower()) if _icu_not_ok else \
    partial(_icu.lower, get_locale())

title_case = (lambda s: s.title()) if _icu_not_ok else \
    partial(_icu.title, get_locale())
################################################################################

def test(): # {{{
    # Data {{{
    german = '''
    Sonntag
Montag
Dienstag
Januar
Februar
März
Fuße
Fluße
Flusse
flusse
fluße
flüße
flüsse
'''
    german_good = '''
    Dienstag
Februar
flusse
Flusse
fluße
Fluße
flüsse
flüße
Fuße
Januar
März
Montag
Sonntag'''
    french = '''
dimanche
lundi
mardi
janvier
février
mars
déjà
Meme
deja
même
dejà
bpef
bœg
Boef
Mémé
bœf
boef
bnef
pêche
pèché
pêché
pêche
pêché'''
    french_good = '''
            bnef
        boef
        Boef
        bœf
        bœg
        bpef
        deja
        dejà
        déjà
        dimanche
        février
        janvier
        lundi
        mardi
        mars
        Meme
        Mémé
        même
        pèché
        pêche
        pêche
        pêché
        pêché'''
    # }}}

    def create(l):
        l = l.decode('utf-8').splitlines()
        return [x.strip() for x in l if x.strip()]

    def test_strcmp(entries):
        for x in entries:
            for y in entries:
                if strcmp(x, y) != cmp(sort_key(x), sort_key(y)):
                    print 'strcmp failed for %r, %r'%(x, y)

    german = create(german)
    c = _icu.Collator('de')
    print 'Sorted german:: (%s)'%c.actual_locale
    gs = list(sorted(german, key=c.sort_key))
    for x in gs:
        print '\t', x.encode('utf-8')
    if gs != create(german_good):
        print 'German failed'
        return
    print
    french = create(french)
    c = _icu.Collator('fr')
    print 'Sorted french:: (%s)'%c.actual_locale
    fs = list(sorted(french, key=c.sort_key))
    for x in fs:
        print '\t', x.encode('utf-8')
    if fs != create(french_good):
        print 'French failed (note that French fails with icu < 4.6 i.e. on windows and OS X)'
        return
    test_strcmp(german + french)

    print '\nTesting case transforms in current locale'
    for x in ('a', 'Alice\'s code'):
        print 'Upper:', x, '->', 'py:', x.upper().encode('utf-8'), 'icu:', upper(x).encode('utf-8')
        print 'Lower:', x, '->', 'py:', x.lower().encode('utf-8'), 'icu:', lower(x).encode('utf-8')
        print 'Title:', x, '->', 'py:', x.title().encode('utf-8'), 'icu:', title_case(x).encode('utf-8')
        print

# }}}

