#!/usr/bin/env python

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

# Setup code {{{
import codecs
import sys
import threading

from calibre.utils.config_base import prefs, tweaks
from calibre_extensions import icu as _icu
from polyglot.builtins import cmp

_locale = None
cmp

_none = ''
_none2 = b''
_cmap = {}

icu_unicode_version = _icu.unicode_version
_nmodes = {m:getattr(_icu, m) for m in ('NFC', 'NFD', 'NFKC', 'NFKD')}


# Ensure that the python internal filesystem and default encodings are not ASCII
def is_ascii(name):
    try:
        return codecs.lookup(name).name == b'ascii'
    except (TypeError, LookupError):
        return True


try:
    if is_ascii(sys.getdefaultencoding()):
        _icu.set_default_encoding(b'utf-8')
except:
    import traceback
    traceback.print_exc()

try:
    if is_ascii(sys.getfilesystemencoding()):
        _icu.set_filesystem_encoding(b'utf-8')
except:
    import traceback
    traceback.print_exc()
del is_ascii


thread_local_collator_cache = threading.local()


def collator(strength=None, numeric=None, ignore_alternate_chars=None, upper_first=None):
    global _locale
    if _locale is None:
        if tweaks['locale_for_sorting']:
            _locale = tweaks['locale_for_sorting']
        else:
            from calibre.utils.localization import get_lang
            _locale = get_lang()
    key = strength, numeric, ignore_alternate_chars, upper_first
    try:
        ans = thread_local_collator_cache.cache.get(key)
    except AttributeError:
        thread_local_collator_cache.cache = {}
        ans = None
    if ans is not None:
        return ans
    if all(x is None for x in key):
        try:
            ans = _icu.Collator(_locale)
        except Exception as e:
            print(f'Failed to load collator for locale: {_locale!r} with error {e!r}, using English', file=sys.stderr)
            _locale = 'en'
            ans = _icu.Collator(_locale)
    else:
        ans = collator().clone()
        if strength is not None:
            ans.strength = strength
        if numeric is not None:
            ans.numeric = numeric
        if upper_first is not None:
            ans.upper_first = upper_first
        if ignore_alternate_chars is not None:
            try:
                ans.set_attribute(_icu.UCOL_ALTERNATE_HANDLING, _icu.UCOL_SHIFTED if ignore_alternate_chars else _icu.UCOL_NON_IGNORABLE)
            except AttributeError:
                pass  # people running from source without latest binary

    thread_local_collator_cache.cache[key] = ans
    return ans


def change_locale(locale=None):
    global _locale
    _locale = locale
    try:
        thread_local_collator_cache.cache.clear()
    except AttributeError:
        pass


def primary_collator():
    'Ignores case differences and accented chars'
    return collator(strength=_icu.UCOL_PRIMARY)


def primary_collator_without_punctuation():
    'Ignores space and punctuation and case differences and accented chars'
    return collator(strength=_icu.UCOL_PRIMARY, ignore_alternate_chars=True)


def sort_collator():
    'Ignores case differences and recognizes numbers in strings (if the tweak is set)'
    return collator(strength=_icu.UCOL_SECONDARY, numeric=prefs['numeric_collation'])


def non_numeric_sort_collator():
    'Ignores case differences only'
    return collator(strength=_icu.UCOL_SECONDARY, numeric=False)


def numeric_collator():
    'Uses natural sorting for numbers inside strings so something2 will sort before something10'
    return collator(strength=_icu.UCOL_SECONDARY, numeric=True)


def case_sensitive_collator():
    'Always sorts upper case letter before lower case'
    return collator(numeric=prefs['numeric_collation'], upper_first=True)


def make_sort_key_func(collator_function, func_name='sort_key'):
    func = None

    def sort_key(a):
        nonlocal func
        if func is None:
            func = getattr(collator_function(), func_name)

        try:
            return func(a)
        except TypeError:
            if isinstance(a, bytes):
                try:
                    a = a.decode(sys.getdefaultencoding())
                except ValueError:
                    return a
                return func(a)
        return b''

    return sort_key


def make_two_arg_func(collator_function, func_name='strcmp'):
    func = None

    def two_args(a, b):
        nonlocal func
        if func is None:
            func = getattr(collator_function(), func_name)

        try:
            return func(a, b)
        except TypeError:
            if isinstance(a, bytes):
                try:
                    a = a.decode(sys.getdefaultencoding())
                except Exception:
                    return cmp(a, b)
            elif a is None:
                a = ''
            if isinstance(b, bytes):
                try:
                    b = b.decode(sys.getdefaultencoding())
                except Exception:
                    return cmp(a, b)
            elif b is None:
                b = ''
            return func(a, b)

    return two_args


def make_change_case_func(which):

    def change_case(x):
        try:
            try:
                return _icu.change_case(x, which, _locale)
            except NotImplementedError:
                pass
            collator()  # sets _locale
            return _icu.change_case(x, which, _locale)
        except TypeError:
            if isinstance(x, bytes):
                try:
                    x = x.decode(sys.getdefaultencoding())
                except ValueError:
                    return x
                return _icu.change_case(x, which, _locale)
            raise
    return change_case
# }}}


# ################ The string functions ########################################
sort_key = make_sort_key_func(sort_collator)
numeric_sort_key = make_sort_key_func(numeric_collator)
primary_sort_key = make_sort_key_func(primary_collator)
case_sensitive_sort_key = make_sort_key_func(case_sensitive_collator)
collation_order = make_sort_key_func(sort_collator, 'collation_order')
collation_order_for_partitioning = make_sort_key_func(non_numeric_sort_collator, 'collation_order')

strcmp = make_two_arg_func(sort_collator)
case_sensitive_strcmp = make_two_arg_func(case_sensitive_collator)
primary_strcmp = make_two_arg_func(primary_collator)
upper = make_change_case_func(_icu.UPPER_CASE)
lower = make_change_case_func(_icu.LOWER_CASE)
title_case = make_change_case_func(_icu.TITLE_CASE)


def capitalize(x):
    try:
        return upper(x[0]) + lower(x[1:])
    except (IndexError, TypeError, AttributeError):
        return x


try:
    swapcase = _icu.swap_case
except AttributeError:  # For people running from source
    swapcase = lambda x:x.swapcase()

find = make_two_arg_func(collator, 'find')
primary_find = make_two_arg_func(primary_collator, 'find')
primary_no_punc_find = make_two_arg_func(primary_collator_without_punctuation, 'find')
contains = make_two_arg_func(collator, 'contains')
primary_contains = make_two_arg_func(primary_collator, 'contains')
primary_no_punc_contains = make_two_arg_func(primary_collator_without_punctuation, 'contains')
startswith = make_two_arg_func(collator, 'startswith')
primary_startswith = make_two_arg_func(primary_collator, 'startswith')
safe_chr = _icu.chr
ord_string = _icu.ord_string


def character_name(string):
    try:
        return _icu.character_name(str(string)) or None
    except (TypeError, ValueError, KeyError):
        pass


def character_name_from_code(code):
    try:
        return _icu.character_name_from_code(code) or ''
    except (TypeError, ValueError, KeyError):
        return ''


def normalize(text, mode='NFC'):
    # This is very slightly slower than using unicodedata.normalize, so stick with
    # that unless you have very good reasons not too. Also, it's speed
    # decreases on wide python builds, where conversion to/from ICU's string
    # representation is slower.
    return _icu.normalize(_nmodes[mode], str(text))


def contractions(col=None):
    global _cmap
    col = col or collator()
    ans = _cmap.get(col, None)
    if ans is None:
        ans = col.contractions()
        ans = frozenset(filter(None, ans))
        _cmap[col] = ans
    return ans


def partition_by_first_letter(items, reverse=False, key=lambda x:x):
    # Build a list of 'equal' first letters by noticing changes
    # in ICU's 'ordinal' for the first letter.
    from collections import OrderedDict
    items = sorted(items, key=lambda x:sort_key(key(x)), reverse=reverse)
    ans = OrderedDict()
    last_c, last_ordnum = ' ', 0
    for item in items:
        c = icu_upper(key(item) or ' ')
        ordnum, ordlen = collation_order(c)
        if last_ordnum != ordnum:
            last_c = c[0:1]
            last_ordnum = ordnum
        try:
            ans[last_c].append(item)
        except KeyError:
            ans[last_c] = [item]
    return ans


# Return the number of unicode codepoints in a string
string_length = len

# Return the number of UTF-16 codepoints in a string
utf16_length = _icu.utf16_length


def remove_accents_icu(txt: str) -> str:
    t = getattr(remove_accents_icu, 'transliterator', None)
    if t is None:
        t = _icu.Transliterator('remove_accents', '''\
:: NFD (NFC);
:: [:Nonspacing Mark:] Remove;
:: NFC (NFD);
''')
        setattr(remove_accents_icu, 'transliterator', t)
    return t.transliterate(txt)


def remove_accents_regex(txt: str) -> str:
    pat = getattr(remove_accents_regex, 'pat', None)
    if pat is None:
        import regex
        import unicodedata
        pat = regex.compile(r'\p{Mn}', flags=regex.UNICODE)
        setattr(remove_accents_regex, 'pat', pat)
        setattr(remove_accents_regex, 'normalize', unicodedata.normalize)
    normalize = remove_accents_regex.normalize
    return normalize('NFKC', pat.sub('', normalize('NFKD', txt)))


remove_accents = remove_accents_regex  # more robust and faster

################################################################################
if __name__ == '__main__':
    from calibre.utils.icu_test import run
    run(verbosity=4)
