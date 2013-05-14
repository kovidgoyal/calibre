#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

# Setup code {{{
import sys
from functools import partial

from calibre.constants import plugins
from calibre.utils.config_base import tweaks

_icu = _collator = _primary_collator = _sort_collator = None
_locale = None

_none = u''
_none2 = b''

def get_locale():
    global _locale
    if _locale is None:
        from calibre.utils.localization import get_lang
        if tweaks['locale_for_sorting']:
            _locale = tweaks['locale_for_sorting']
        else:
            _locale = get_lang()
    return _locale

def load_icu():
    global _icu
    if _icu is None:
        _icu = plugins['icu'][0]
        if _icu is None:
            print 'Loading ICU failed with: ', plugins['icu'][1]
        else:
            if not getattr(_icu, 'ok', False):
                print 'icu not ok'
                _icu = None
    return _icu

def load_collator():
    'The default collator for most locales takes both case and accented letters into account'
    global _collator
    if _collator is None:
        icu = load_icu()
        if icu is not None:
            _collator = icu.Collator(get_locale())
    return _collator

def primary_collator():
    'Ignores case differences and accented characters'
    global _primary_collator
    if _primary_collator is None:
        _primary_collator = _collator.clone()
        _primary_collator.strength = _icu.UCOL_PRIMARY
    return _primary_collator

def sort_collator():
    'Ignores case differences and recognizes numbers in strings'
    global _sort_collator
    if _sort_collator is None:
        _sort_collator = _collator.clone()
        _sort_collator.strength = _icu.UCOL_SECONDARY
        if tweaks['numeric_collation']:
            try:
                _sort_collator.numeric = True
            except AttributeError:
                pass
    return _sort_collator

def py_sort_key(obj):
    if not obj:
        return _none
    return obj.lower()

def icu_sort_key(collator, obj):
    if not obj:
        return _none2
    try:
        try:
            return _sort_collator.sort_key(obj)
        except AttributeError:
            return sort_collator().sort_key(obj)
    except TypeError:
        if isinstance(obj, unicode):
            obj = obj.replace(u'\0', u'')
        else:
            obj = obj.replace(b'\0', b'')
        return _sort_collator.sort_key(obj)

def icu_change_case(upper, locale, obj):
    func = _icu.upper if upper else _icu.lower
    try:
        return func(locale, obj)
    except TypeError:
        if isinstance(obj, unicode):
            obj = obj.replace(u'\0', u'')
        else:
            obj = obj.replace(b'\0', b'')
        return func(locale, obj)

def py_find(pattern, source):
    pos = source.find(pattern)
    if pos > -1:
        return pos, len(pattern)
    return -1, -1

def icu_find(collator, pattern, source):
    try:
        return collator.find(pattern, source)
    except TypeError:
        return collator.find(unicode(pattern), unicode(source))

def icu_startswith(collator, a, b):
    try:
        return collator.startswith(a, b)
    except TypeError:
        return collator.startswith(unicode(a), unicode(b))

def py_case_sensitive_sort_key(obj):
    if not obj:
        return _none
    return obj

def icu_case_sensitive_sort_key(collator, obj):
    if not obj:
        return _none2
    return collator.sort_key(obj)

def icu_strcmp(collator, a, b):
    return collator.strcmp(lower(a), lower(b))

def py_strcmp(a, b):
    return cmp(a.lower(), b.lower())

def icu_case_sensitive_strcmp(collator, a, b):
    return collator.strcmp(a, b)

def icu_capitalize(s):
    s = lower(s)
    return s.replace(s[0], upper(s[0]), 1) if s else s

_cmap = {}
def icu_contractions(collator):
    global _cmap
    ans = _cmap.get(collator, None)
    if ans is None:
        ans = collator.contractions()
        ans = frozenset(filter(None, ans)) if ans else {}
        _cmap[collator] = ans
    return ans

def icu_collation_order(collator, a):
    try:
        return collator.collation_order(a)
    except TypeError:
        return collator.collation_order(unicode(a))

load_icu()
load_collator()
_icu_not_ok = _icu is None or _collator is None

try:
    senc = sys.getdefaultencoding()
    if not senc or senc.lower() == 'ascii':
        _icu.set_default_encoding('utf-8')
    del senc
except:
    pass

try:
    fenc = sys.getfilesystemencoding()
    if not fenc or fenc.lower() == 'ascii':
        _icu.set_filesystem_encoding('utf-8')
    del fenc
except:
    pass


# }}}

################# The string functions ########################################

sort_key = py_sort_key if _icu_not_ok else partial(icu_sort_key, _collator)

strcmp = py_strcmp if _icu_not_ok else partial(icu_strcmp, _collator)

case_sensitive_sort_key = py_case_sensitive_sort_key if _icu_not_ok else \
        partial(icu_case_sensitive_sort_key, _collator)

case_sensitive_strcmp = cmp if _icu_not_ok else icu_case_sensitive_strcmp

upper = (lambda s: s.upper()) if _icu_not_ok else \
    partial(icu_change_case, True, get_locale())

lower = (lambda s: s.lower()) if _icu_not_ok else \
    partial(icu_change_case, False, get_locale())

title_case = (lambda s: s.title()) if _icu_not_ok else \
    partial(_icu.title, get_locale())

capitalize = (lambda s: s.capitalize()) if _icu_not_ok else \
    (lambda s: icu_capitalize(s))

find = (py_find if _icu_not_ok else partial(icu_find, _collator))

contractions = ((lambda : {}) if _icu_not_ok else (partial(icu_contractions,
    _collator)))

def primary_strcmp(a, b):
    'strcmp that ignores case and accents on letters'
    if _icu_not_ok:
        from calibre.utils.filenames import ascii_text
        return py_strcmp(ascii_text(a), ascii_text(b))
    try:
        return _primary_collator.strcmp(a, b)
    except AttributeError:
        return primary_collator().strcmp(a, b)

def primary_find(pat, src):
    'find that ignores case and accents on letters'
    if _icu_not_ok:
        from calibre.utils.filenames import ascii_text
        return py_find(ascii_text(pat), ascii_text(src))
    try:
        return icu_find(_primary_collator, pat, src)
    except AttributeError:
        return icu_find(primary_collator(), pat, src)

def primary_sort_key(val):
    'A sort key that ignores case and diacritics'
    if _icu_not_ok:
        from calibre.utils.filenames import ascii_text
        return ascii_text(val).lower()
    try:
        return _primary_collator.sort_key(val)
    except AttributeError:
        return primary_collator().sort_key(val)

def primary_startswith(a, b):
    if _icu_not_ok:
        from calibre.utils.filenames import ascii_text
        return ascii_text(a).lower().startswith(ascii_text(b).lower())
    try:
        return icu_startswith(_primary_collator, a, b)
    except AttributeError:
        return icu_startswith(primary_collator(), a, b)

def collation_order(a):
    if _icu_not_ok:
        return (ord(a[0]), 1) if a else (0, 0)
    try:
        return icu_collation_order(_sort_collator, a)
    except AttributeError:
        return icu_collation_order(sort_collator(), a)

################################################################################

def test():  # {{{
    from calibre import prints
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
    c.numeric = True
    gs = list(sorted(german, key=c.sort_key))
    if gs != create(german_good):
        print 'German sorting failed'
        return
    print
    french = create(french)
    c = _icu.Collator('fr')
    c.numeric = True
    fs = list(sorted(french, key=c.sort_key))
    if fs != create(french_good):
        print 'French sorting failed (note that French fails with icu < 4.6)'
        return
    test_strcmp(german + french)

    print '\nTesting case transforms in current locale'
    from calibre.utils.titlecase import titlecase
    for x in ('a', 'Alice\'s code', 'macdonald\'s machine', '02 the wars'):
        print 'Upper:     ', x, '->', 'py:', x.upper().encode('utf-8'), 'icu:', upper(x).encode('utf-8')
        print 'Lower:     ', x, '->', 'py:', x.lower().encode('utf-8'), 'icu:', lower(x).encode('utf-8')
        print 'Title:     ', x, '->', 'py:', x.title().encode('utf-8'), 'icu:', title_case(x).encode('utf-8'), 'titlecase:', titlecase(x).encode('utf-8')
        print 'Capitalize:', x, '->', 'py:', x.capitalize().encode('utf-8'), 'icu:', capitalize(x).encode('utf-8')
        print

    print '\nTesting primary collation'
    for k, v in {u'pèché': u'peche', u'flüße':u'Flusse',
            u'Štepánek':u'ŠtepaneK'}.iteritems():
        if primary_strcmp(k, v) != 0:
            prints('primary_strcmp() failed with %s != %s'%(k, v))
            return
        if primary_find(v, u' '+k)[0] != 1:
            prints('primary_find() failed with %s not in %s'%(v, k))
            return

    global _primary_collator
    orig = _primary_collator
    _primary_collator = _icu.Collator('es')
    if primary_strcmp(u'peña', u'pena') == 0:
        print 'Primary collation in Spanish locale failed'
        return
    _primary_collator = orig

    print '\nTesting contractions'
    c = _icu.Collator('cs')
    if icu_contractions(c) != frozenset([u'Z\u030c', u'z\u030c', u'Ch',
        u'C\u030c', u'ch', u'cH', u'c\u030c', u's\u030c', u'r\u030c', u'CH',
        u'S\u030c', u'R\u030c']):
        print 'Contractions for the Czech language failed'
        return

    print '\nTesting startswith'
    p = primary_startswith
    if (not p('asd', 'asd') or not p('asd', 'A') or
            not p('x', '')):
        print 'startswith() failed'
        return

    print '\nTesting collation_order()'
    for group in [
        ('Šaa', 'Smith', 'Solženicyn', 'Štepánek'),
        ('calibre', 'Charon', 'Collins'),
        ('01', '1'),
        ('1', '11', '13'),
    ]:
        last = None
        for x in group:
            val = icu_collation_order(sort_collator(), x)
            if val[1] != 1:
                prints('collation_order() returned incorrect length for', x)
            if last is None:
                last = val
            else:
                if val != last:
                    prints('collation_order() returned incorrect value for', x)
            last = val

# }}}

if __name__ == '__main__':
    test()

