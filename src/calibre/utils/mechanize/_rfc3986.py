"""RFC 3986 URI parsing and relative reference resolution / absolutization.

(aka splitting and joining)

Copyright 2006 John J. Lee <jjl@pobox.com>

This code is free software; you can redistribute it and/or modify it under
the terms of the BSD or ZPL 2.1 licenses (see the file COPYING.txt
included with the distribution).

"""

# XXX Wow, this is ugly.  Overly-direct translation of the RFC ATM.

import sys, re, posixpath, urllib

## def chr_range(a, b):
##     return "".join(map(chr, range(ord(a), ord(b)+1)))

## UNRESERVED_URI_CHARS = ("ABCDEFGHIJKLMNOPQRSTUVWXYZ"
##                         "abcdefghijklmnopqrstuvwxyz"
##                         "0123456789"
##                         "-_.~")
## RESERVED_URI_CHARS = "!*'();:@&=+$,/?#[]"
## URI_CHARS = RESERVED_URI_CHARS+UNRESERVED_URI_CHARS+'%'
# this re matches any character that's not in URI_CHARS
BAD_URI_CHARS_RE = re.compile("[^A-Za-z0-9\-_.~!*'();:@&=+$,/?%#[\]]")


def clean_url(url, encoding):
    # percent-encode illegal URI characters
    # Trying to come up with test cases for this gave me a headache, revisit
    # when do switch to unicode.
    # Somebody else's comments (lost the attribution):
##     - IE will return you the url in the encoding you send it
##     - Mozilla/Firefox will send you latin-1 if there's no non latin-1
##     characters in your link. It will send you utf-8 however if there are...
    if type(url) == type(""):
        url = url.decode(encoding, "replace")
    url = url.strip()
    # for second param to urllib.quote(), we want URI_CHARS, minus the
    # 'always_safe' characters that urllib.quote() never percent-encodes
    return urllib.quote(url.encode(encoding), "!*'();:@&=+$,/?%#[]~")

def is_clean_uri(uri):
    """
    >>> is_clean_uri("ABC!")
    True
    >>> is_clean_uri(u"ABC!")
    True
    >>> is_clean_uri("ABC|")
    False
    >>> is_clean_uri(u"ABC|")
    False
    >>> is_clean_uri("http://example.com/0")
    True
    >>> is_clean_uri(u"http://example.com/0")
    True
    """
    # note module re treats bytestrings as through they were decoded as latin-1
    # so this function accepts both unicode and bytestrings
    return not bool(BAD_URI_CHARS_RE.search(uri))


SPLIT_MATCH = re.compile(
    r"^(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?").match
def urlsplit(absolute_uri):
    """Return scheme, authority, path, query, fragment."""
    match = SPLIT_MATCH(absolute_uri)
    if match:
        g = match.groups()
        return g[1], g[3], g[4], g[6], g[8]

def urlunsplit(parts):
    scheme, authority, path, query, fragment = parts
    r = []
    append = r.append
    if scheme is not None:
        append(scheme)
        append(":")
    if authority is not None:
        append("//")
        append(authority)
    append(path)
    if query is not None:
        append("?")
        append(query)
    if fragment is not None:
        append("#")
        append(fragment)
    return "".join(r)

def urljoin(base_uri, uri_reference):
    return urlunsplit(urljoin_parts(urlsplit(base_uri),
                                    urlsplit(uri_reference)))

# oops, this doesn't do the same thing as the literal translation
# from the RFC below
## def urljoin_parts(base_parts, reference_parts):
##     scheme, authority, path, query, fragment = base_parts
##     rscheme, rauthority, rpath, rquery, rfragment = reference_parts

##     # compute target URI path
##     if rpath == "":
##         tpath = path
##     else:
##         tpath = rpath
##         if not tpath.startswith("/"):
##             tpath = merge(authority, path, tpath)
##         tpath = posixpath.normpath(tpath)

##     if rscheme is not None:
##         return (rscheme, rauthority, tpath, rquery, rfragment)
##     elif rauthority is not None:
##         return (scheme, rauthority, tpath, rquery, rfragment)
##     elif rpath == "":
##         if rquery is not None:
##             tquery = rquery
##         else:
##             tquery = query
##         return (scheme, authority, tpath, tquery, rfragment)
##     else:
##         return (scheme, authority, tpath, rquery, rfragment)

def urljoin_parts(base_parts, reference_parts):
    scheme, authority, path, query, fragment = base_parts
    rscheme, rauthority, rpath, rquery, rfragment = reference_parts

    if rscheme == scheme:
        rscheme = None

    if rscheme is not None:
        tscheme, tauthority, tpath, tquery = (
            rscheme, rauthority, remove_dot_segments(rpath), rquery)
    else:
        if rauthority is not None:
            tauthority, tpath, tquery = (
                rauthority, remove_dot_segments(rpath), rquery)
        else:
            if rpath == "":
                tpath = path
                if rquery is not None:
                    tquery = rquery
                else:
                    tquery = query
            else:
                if rpath.startswith("/"):
                    tpath = remove_dot_segments(rpath)
                else:
                    tpath = merge(authority, path, rpath)
                    tpath = remove_dot_segments(tpath)
                tquery = rquery
            tauthority = authority
        tscheme = scheme
    tfragment = rfragment
    return (tscheme, tauthority, tpath, tquery, tfragment)

# um, something *vaguely* like this is what I want, but I have to generate
# lots of test cases first, if only to understand what it is that
# remove_dot_segments really does...
## def remove_dot_segments(path):
##     if path == '':
##         return ''
##     comps = path.split('/')
##     new_comps = []
##     for comp in comps:
##         if comp in ['.', '']:
##             if not new_comps or new_comps[-1]:
##                 new_comps.append('')
##             continue
##         if comp != '..':
##             new_comps.append(comp)
##         elif new_comps:
##             new_comps.pop()
##     return '/'.join(new_comps)


def remove_dot_segments(path):
    r = []
    while path:
        # A
        if path.startswith("../"):
            path = path[3:]
            continue
        if path.startswith("./"):
            path = path[2:]
            continue
        # B
        if path.startswith("/./"):
            path = path[2:]
            continue
        if path == "/.":
            path = "/"
            continue
        # C
        if path.startswith("/../"):
            path = path[3:]
            if r:
                r.pop()
            continue
        if path == "/..":
            path = "/"
            if r:
                r.pop()
            continue
        # D
        if path == ".":
            path = path[1:]
            continue
        if path == "..":
            path = path[2:]
            continue
        # E
        start = 0
        if path.startswith("/"):
            start = 1
        ii = path.find("/", start)
        if ii < 0:
            ii = None
        r.append(path[:ii])
        if ii is None:
            break
        path = path[ii:]
    return "".join(r)

def merge(base_authority, base_path, ref_path):
    # XXXX Oddly, the sample Perl implementation of this by Roy Fielding
    # doesn't even take base_authority as a parameter, despite the wording in
    # the RFC suggesting otherwise.  Perhaps I'm missing some obvious identity.
    #if base_authority is not None and base_path == "":
    if base_path == "":
        return "/" + ref_path
    ii = base_path.rfind("/")
    if ii >= 0:
        return base_path[:ii+1] + ref_path
    return ref_path

if __name__ == "__main__":
    import doctest
    doctest.testmod()
