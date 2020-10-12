#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

"""
Provides abstraction for metadata reading.writing from a variety of ebook formats.
"""
import os, sys, re

from calibre import relpath, guess_type, prints, force_unicode
from calibre.utils.config_base import tweaks
from polyglot.builtins import codepoint_to_chr, unicode_type, range, map, zip, getcwd, iteritems, itervalues, as_unicode
from polyglot.urllib import quote, unquote, urlparse


try:
    _author_pat = re.compile(tweaks['authors_split_regex'])
except Exception:
    prints('Author split regexp:', tweaks['authors_split_regex'],
            'is invalid, using default')
    _author_pat = re.compile(r'(?i),?\s+(and|with)\s+')


def string_to_authors(raw):
    if not raw:
        return []
    raw = raw.replace('&&', '\uffff')
    raw = _author_pat.sub('&', raw)
    authors = [a.strip().replace('\uffff', '&') for a in raw.split('&')]
    return [a for a in authors if a]


def authors_to_string(authors):
    if authors is not None:
        return ' & '.join([a.replace('&', '&&') for a in authors if a])
    else:
        return ''


def remove_bracketed_text(src, brackets=None):
    if brackets is None:
        brackets = {'(': ')', '[': ']', '{': '}'}
    from collections import Counter
    counts = Counter()
    buf = []
    src = force_unicode(src)
    rmap = {v: k for k, v in iteritems(brackets)}
    for char in src:
        if char in brackets:
            counts[char] += 1
        elif char in rmap:
            idx = rmap[char]
            if counts[idx] > 0:
                counts[idx] -= 1
        elif sum(itervalues(counts)) < 1:
            buf.append(char)
    return ''.join(buf)


def author_to_author_sort(author, method=None):
    if not author:
        return ''
    sauthor = remove_bracketed_text(author).strip()
    tokens = sauthor.split()
    if len(tokens) < 2:
        return author
    if method is None:
        method = tweaks['author_sort_copy_method']

    ltoks = frozenset(x.lower() for x in tokens)
    copy_words = frozenset(x.lower() for x in tweaks['author_name_copywords'])
    if ltoks.intersection(copy_words):
        method = 'copy'

    if method == 'copy':
        return author

    prefixes = {force_unicode(y).lower() for y in tweaks['author_name_prefixes']}
    prefixes |= {y+'.' for y in prefixes}
    while True:
        if not tokens:
            return author
        tok = tokens[0].lower()
        if tok in prefixes:
            tokens = tokens[1:]
        else:
            break

    suffixes = {force_unicode(y).lower() for y in tweaks['author_name_suffixes']}
    suffixes |= {y+'.' for y in suffixes}

    suffix = ''
    while True:
        if not tokens:
            return author
        last = tokens[-1].lower()
        if last in suffixes:
            suffix = tokens[-1] + ' ' + suffix
            tokens = tokens[:-1]
        else:
            break
    suffix = suffix.strip()

    if method == 'comma' and ',' in ''.join(tokens):
        return author

    atokens = tokens[-1:] + tokens[:-1]
    num_toks = len(atokens)
    if suffix:
        atokens.append(suffix)

    if method != 'nocomma' and num_toks > 1:
        atokens[0] += ','

    return ' '.join(atokens)


def authors_to_sort_string(authors):
    return ' & '.join(map(author_to_author_sort, authors))


_title_pats = {}


def get_title_sort_pat(lang=None):
    ans = _title_pats.get(lang, None)
    if ans is not None:
        return ans
    q = lang
    from calibre.utils.localization import canonicalize_lang, get_lang
    if lang is None:
        q = tweaks['default_language_for_title_sort']
        if q is None:
            q = get_lang()
    q = canonicalize_lang(q) if q else q
    data = tweaks['per_language_title_sort_articles']
    try:
        ans = data.get(q, None)
    except AttributeError:
        ans = None  # invalid tweak value
    try:
        ans = frozenset(ans) if ans else frozenset(data['eng'])
    except:
        ans = frozenset((r'A\s+', r'The\s+', r'An\s+'))
    ans = '|'.join(ans)
    ans = '^(%s)'%ans
    try:
        ans = re.compile(ans, re.IGNORECASE)
    except:
        ans = re.compile(r'^(A|The|An)\s+', re.IGNORECASE)
    _title_pats[lang] = ans
    return ans


_ignore_starts = '\'"'+''.join(codepoint_to_chr(x) for x in
        list(range(0x2018, 0x201e))+[0x2032, 0x2033])


def title_sort(title, order=None, lang=None):
    if order is None:
        order = tweaks['title_series_sorting']
    title = title.strip()
    if order == 'strictly_alphabetic':
        return title
    if title and title[0] in _ignore_starts:
        title = title[1:]
    match = get_title_sort_pat(lang).search(title)
    if match:
        try:
            prep = match.group(1)
        except IndexError:
            pass
        else:
            title = title[len(prep):] + ', ' + prep
            if title[0] in _ignore_starts:
                title = title[1:]
    return title.strip()


coding = list(zip(
[1000,900,500,400,100,90,50,40,10,9,5,4,1],
["M","CM","D","CD","C","XC","L","XL","X","IX","V","IV","I"]
))


def roman(num):
    if num <= 0 or num >= 4000 or int(num) != num:
        return unicode_type(num)
    result = []
    for d, r in coding:
        while num >= d:
            result.append(r)
            num -= d
    return ''.join(result)


def fmt_sidx(i, fmt='%.2f', use_roman=False):
    if i is None or i == '':
        i = 1
    try:
        i = float(i)
    except TypeError:
        return unicode_type(i)
    if int(i) == float(i):
        return roman(int(i)) if use_roman else '%d'%int(i)
    return fmt%i


class Resource(object):

    '''
    Represents a resource (usually a file on the filesystem or a URL pointing
    to the web. Such resources are commonly referred to in OPF files.

    They have the interface:

    :member:`path`
    :member:`mime_type`
    :method:`href`

    '''

    def __init__(self, href_or_path, basedir=getcwd(), is_path=True):
        self._href = None
        self._basedir = basedir
        self.path = None
        self.fragment = ''
        try:
            self.mime_type = guess_type(href_or_path)[0]
        except:
            self.mime_type = None
        if self.mime_type is None:
            self.mime_type = 'application/octet-stream'
        if is_path:
            path = href_or_path
            if not os.path.isabs(path):
                path = os.path.abspath(os.path.join(basedir, path))
            if isinstance(path, bytes):
                path = path.decode(sys.getfilesystemencoding())
            self.path = path
        else:
            url = urlparse(href_or_path)
            if url[0] not in ('', 'file'):
                self._href = href_or_path
            else:
                pc = url[2]
                if isinstance(pc, unicode_type):
                    pc = pc.encode('utf-8')
                pc = unquote(pc).decode('utf-8')
                self.path = os.path.abspath(os.path.join(basedir, pc.replace('/', os.sep)))
                self.fragment = unquote(url[-1])

    def href(self, basedir=None):
        '''
        Return a URL pointing to this resource. If it is a file on the filesystem
        the URL is relative to `basedir`.

        `basedir`: If None, the basedir of this resource is used (see :method:`set_basedir`).
        If this resource has no basedir, then the current working directory is used as the basedir.
        '''
        if basedir is None:
            if self._basedir:
                basedir = self._basedir
            else:
                basedir = getcwd()
        if self.path is None:
            return self._href
        f = self.fragment.encode('utf-8') if isinstance(self.fragment, unicode_type) else self.fragment
        frag = '#'+as_unicode(quote(f)) if self.fragment else ''
        if self.path == basedir:
            return ''+frag
        try:
            rpath = relpath(self.path, basedir)
        except OSError:  # On windows path and basedir could be on different drives
            rpath = self.path
        if isinstance(rpath, unicode_type):
            rpath = rpath.encode('utf-8')
        return as_unicode(quote(rpath.replace(os.sep, '/')))+frag

    def set_basedir(self, path):
        self._basedir = path

    def basedir(self):
        return self._basedir

    def __repr__(self):
        return 'Resource(%s, %s)'%(repr(self.path), repr(self.href()))


class ResourceCollection(object):

    def __init__(self):
        self._resources = []

    def __iter__(self):
        for r in self._resources:
            yield r

    def __len__(self):
        return len(self._resources)

    def __getitem__(self, index):
        return self._resources[index]

    def __bool__(self):
        return len(self._resources) > 0

    def __str__(self):
        resources = map(repr, self)
        return '[%s]'%', '.join(resources)

    def __repr__(self):
        return unicode_type(self)

    def append(self, resource):
        if not isinstance(resource, Resource):
            raise ValueError('Can only append objects of type Resource')
        self._resources.append(resource)

    def remove(self, resource):
        self._resources.remove(resource)

    def replace(self, start, end, items):
        'Same as list[start:end] = items'
        self._resources[start:end] = items

    @staticmethod
    def from_directory_contents(top, topdown=True):
        collection = ResourceCollection()
        for spec in os.walk(top, topdown=topdown):
            path = os.path.abspath(os.path.join(spec[0], spec[1]))
            res = Resource.from_path(path)
            res.set_basedir(top)
            collection.append(res)
        return collection

    def set_basedir(self, path):
        for res in self:
            res.set_basedir(path)


def MetaInformation(title, authors=(_('Unknown'),)):
    ''' Convenient encapsulation of book metadata, needed for compatibility
        @param title: title or ``_('Unknown')`` or a MetaInformation object
        @param authors: List of strings or []
    '''
    from calibre.ebooks.metadata.book.base import Metadata
    mi = None
    if hasattr(title, 'title') and hasattr(title, 'authors'):
        mi = title
        title = mi.title
        authors = mi.authors
    return Metadata(title, authors, other=mi)


def check_isbn10(isbn):
    try:
        digits = tuple(map(int, isbn[:9]))
        products = [(i+1)*digits[i] for i in range(9)]
        check = sum(products)%11
        if (check == 10 and isbn[9] == 'X') or check == int(isbn[9]):
            return isbn
    except Exception:
        pass
    return None


def check_isbn13(isbn):
    try:
        digits = tuple(map(int, isbn[:12]))
        products = [(1 if i%2 ==0 else 3)*digits[i] for i in range(12)]
        check = 10 - (sum(products)%10)
        if check == 10:
            check = 0
        if unicode_type(check) == isbn[12]:
            return isbn
    except Exception:
        pass
    return None


def check_isbn(isbn):
    if not isbn:
        return None
    isbn = re.sub(r'[^0-9X]', '', isbn.upper())
    all_same = re.match(r'(\d)\1{9,12}$', isbn)
    if all_same is not None:
        return None
    if len(isbn) == 10:
        return check_isbn10(isbn)
    if len(isbn) == 13:
        return check_isbn13(isbn)
    return None


def check_issn(issn):
    if not issn:
        return None
    issn = re.sub(r'[^0-9X]', '', issn.upper())
    try:
        digits = tuple(map(int, issn[:7]))
        products = [(8 - i) * d for i, d in enumerate(digits)]
        check = 11 - sum(products) % 11
        if (check == 10 and issn[7] == 'X') or check == int(issn[7]):
            return issn
    except Exception:
        pass
    return None


def format_isbn(isbn):
    cisbn = check_isbn(isbn)
    if not cisbn:
        return isbn
    i = cisbn
    if len(i) == 10:
        return '-'.join((i[:2], i[2:6], i[6:9], i[9]))
    return '-'.join((i[:3], i[3:5], i[5:9], i[9:12], i[12]))


def check_doi(doi):
    'Check if something that looks like a DOI is present anywhere in the string'
    if not doi:
        return None
    doi_check = re.search(r'10\.\d{4}/\S+', doi)
    if doi_check is not None:
        return doi_check.group()
    return None


def rating_to_stars(value, allow_half_stars=False, star='★', half='⯨'):
    r = max(0, min(int(value or 0), 10))
    ans = star * (r // 2)
    if allow_half_stars and r % 2:
        ans += half
    return ans
