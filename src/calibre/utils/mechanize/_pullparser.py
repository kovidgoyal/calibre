"""A simple "pull API" for HTML parsing, after Perl's HTML::TokeParser.

Examples

This program extracts all links from a document.  It will print one
line for each link, containing the URL and the textual description
between the <A>...</A> tags:

import pullparser, sys
f = file(sys.argv[1])
p = pullparser.PullParser(f)
for token in p.tags("a"):
    if token.type == "endtag": continue
    url = dict(token.attrs).get("href", "-")
    text = p.get_compressed_text(endat=("endtag", "a"))
    print "%s\t%s" % (url, text)

This program extracts the <TITLE> from the document:

import pullparser, sys
f = file(sys.argv[1])
p = pullparser.PullParser(f)
if p.get_tag("title"):
    title = p.get_compressed_text()
    print "Title: %s" % title


Copyright 2003-2006 John J. Lee <jjl@pobox.com>
Copyright 1998-2001 Gisle Aas (original libwww-perl code)

This code is free software; you can redistribute it and/or modify it
under the terms of the BSD or ZPL 2.1 licenses.

"""

import re, htmlentitydefs
import sgmllib, HTMLParser

from _html import unescape, unescape_charref


class NoMoreTokensError(Exception): pass

class Token:
    """Represents an HTML tag, declaration, processing instruction etc.

    Behaves as both a tuple-like object (ie. iterable) and has attributes
    .type, .data and .attrs.

    >>> t = Token("starttag", "a", [("href", "http://www.python.org/")])
    >>> t == ("starttag", "a", [("href", "http://www.python.org/")])
    True
    >>> (t.type, t.data) == ("starttag", "a")
    True
    >>> t.attrs == [("href", "http://www.python.org/")]
    True

    Public attributes

    type: one of "starttag", "endtag", "startendtag", "charref", "entityref",
     "data", "comment", "decl", "pi", after the corresponding methods of
     HTMLParser.HTMLParser
    data: For a tag, the tag name; otherwise, the relevant data carried by the
     tag, as a string
    attrs: list of (name, value) pairs representing HTML attributes
     (or None if token does not represent an opening tag)

    """
    def __init__(self, type, data, attrs=None):
        self.type = type
        self.data = data
        self.attrs = attrs
    def __iter__(self):
        return iter((self.type, self.data, self.attrs))
    def __eq__(self, other):
        type, data, attrs = other
        if (self.type == type and
            self.data == data and
            self.attrs == attrs):
            return True
        else:
            return False
    def __ne__(self, other): return not self.__eq__(other)
    def __repr__(self):
        args = ", ".join(map(repr, [self.type, self.data, self.attrs]))
        return self.__class__.__name__+"(%s)" % args

def iter_until_exception(fn, exception, *args, **kwds):
    while 1:
        try:
            yield fn(*args, **kwds)
        except exception:
            raise StopIteration


class _AbstractParser:
    chunk = 1024
    compress_re = re.compile(r"\s+")
    def __init__(self, fh, textify={"img": "alt", "applet": "alt"},
                 encoding="ascii", entitydefs=None):
        """
        fh: file-like object (only a .read() method is required) from which to
         read HTML to be parsed
        textify: mapping used by .get_text() and .get_compressed_text() methods
         to represent opening tags as text
        encoding: encoding used to encode numeric character references by
         .get_text() and .get_compressed_text() ("ascii" by default)

        entitydefs: mapping like {"amp": "&", ...} containing HTML entity
         definitions (a sensible default is used).  This is used to unescape
         entities in .get_text() (and .get_compressed_text()) and attribute
         values.  If the encoding can not represent the character, the entity
         reference is left unescaped.  Note that entity references (both
         numeric - e.g. &#123; or &#xabc; - and non-numeric - e.g. &amp;) are
         unescaped in attribute values and the return value of .get_text(), but
         not in data outside of tags.  Instead, entity references outside of
         tags are represented as tokens.  This is a bit odd, it's true :-/

        If the element name of an opening tag matches a key in the textify
        mapping then that tag is converted to text.  The corresponding value is
        used to specify which tag attribute to obtain the text from.  textify
        maps from element names to either:

          - an HTML attribute name, in which case the HTML attribute value is
            used as its text value along with the element name in square
            brackets (eg."alt text goes here[IMG]", or, if the alt attribute
            were missing, just "[IMG]")
          - a callable object (eg. a function) which takes a Token and returns
            the string to be used as its text value

        If textify has no key for an element name, nothing is substituted for
        the opening tag.

        Public attributes:

        encoding and textify: see above

        """
        self._fh = fh
        self._tokenstack = []  # FIFO
        self.textify = textify
        self.encoding = encoding
        if entitydefs is None:
            entitydefs = htmlentitydefs.name2codepoint
        self._entitydefs = entitydefs

    def __iter__(self): return self

    def tags(self, *names):
        return iter_until_exception(self.get_tag, NoMoreTokensError, *names)

    def tokens(self, *tokentypes):
        return iter_until_exception(self.get_token, NoMoreTokensError, *tokentypes)

    def next(self):
        try:
            return self.get_token()
        except NoMoreTokensError:
            raise StopIteration()

    def get_token(self, *tokentypes):
        """Pop the next Token object from the stack of parsed tokens.

        If arguments are given, they are taken to be token types in which the
        caller is interested: tokens representing other elements will be
        skipped.  Element names must be given in lower case.

        Raises NoMoreTokensError.

        """
        while 1:
            while self._tokenstack:
                token = self._tokenstack.pop(0)
                if tokentypes:
                    if token.type in tokentypes:
                        return token
                else:
                    return token
            data = self._fh.read(self.chunk)
            if not data:
                raise NoMoreTokensError()
            self.feed(data)

    def unget_token(self, token):
        """Push a Token back onto the stack."""
        self._tokenstack.insert(0, token)

    def get_tag(self, *names):
        """Return the next Token that represents an opening or closing tag.

        If arguments are given, they are taken to be element names in which the
        caller is interested: tags representing other elements will be skipped.
        Element names must be given in lower case.

        Raises NoMoreTokensError.

        """
        while 1:
            tok = self.get_token()
            if tok.type not in ["starttag", "endtag", "startendtag"]:
                continue
            if names:
                if tok.data in names:
                    return tok
            else:
                return tok

    def get_text(self, endat=None):
        """Get some text.

        endat: stop reading text at this tag (the tag is included in the
         returned text); endtag is a tuple (type, name) where type is
         "starttag", "endtag" or "startendtag", and name is the element name of
         the tag (element names must be given in lower case)

        If endat is not given, .get_text() will stop at the next opening or
        closing tag, or when there are no more tokens (no exception is raised).
        Note that .get_text() includes the text representation (if any) of the
        opening tag, but pushes the opening tag back onto the stack.  As a
        result, if you want to call .get_text() again, you need to call
        .get_tag() first (unless you want an empty string returned when you
        next call .get_text()).

        Entity references are translated using the value of the entitydefs
        constructor argument (a mapping from names to characters like that
        provided by the standard module htmlentitydefs).  Named entity
        references that are not in this mapping are left unchanged.

        The textify attribute is used to translate opening tags into text: see
        the class docstring.

        """
        text = []
        tok = None
        while 1:
            try:
                tok = self.get_token()
            except NoMoreTokensError:
                # unget last token (not the one we just failed to get)
                if tok: self.unget_token(tok)
                break
            if tok.type == "data":
                text.append(tok.data)
            elif tok.type == "entityref":
                t = unescape("&%s;"%tok.data, self._entitydefs, self.encoding)
                text.append(t)
            elif tok.type == "charref":
                t = unescape_charref(tok.data, self.encoding)
                text.append(t)
            elif tok.type in ["starttag", "endtag", "startendtag"]:
                tag_name = tok.data
                if tok.type in ["starttag", "startendtag"]:
                    alt = self.textify.get(tag_name)
                    if alt is not None:
                        if callable(alt):
                            text.append(alt(tok))
                        elif tok.attrs is not None:
                            for k, v in tok.attrs:
                                if k == alt:
                                    text.append(v)
                            text.append("[%s]" % tag_name.upper())
                if endat is None or endat == (tok.type, tag_name):
                    self.unget_token(tok)
                    break
        return "".join(text)

    def get_compressed_text(self, *args, **kwds):
        """
        As .get_text(), but collapses each group of contiguous whitespace to a
        single space character, and removes all initial and trailing
        whitespace.

        """
        text = self.get_text(*args, **kwds)
        text = text.strip()
        return self.compress_re.sub(" ", text)

    def handle_startendtag(self, tag, attrs):
        self._tokenstack.append(Token("startendtag", tag, attrs))
    def handle_starttag(self, tag, attrs):
        self._tokenstack.append(Token("starttag", tag, attrs))
    def handle_endtag(self, tag):
        self._tokenstack.append(Token("endtag", tag))
    def handle_charref(self, name):
        self._tokenstack.append(Token("charref", name))
    def handle_entityref(self, name):
        self._tokenstack.append(Token("entityref", name))
    def handle_data(self, data):
        self._tokenstack.append(Token("data", data))
    def handle_comment(self, data):
        self._tokenstack.append(Token("comment", data))
    def handle_decl(self, decl):
        self._tokenstack.append(Token("decl", decl))
    def unknown_decl(self, data):
        # XXX should this call self.error instead?
        #self.error("unknown declaration: " + `data`)
        self._tokenstack.append(Token("decl", data))
    def handle_pi(self, data):
        self._tokenstack.append(Token("pi", data))

    def unescape_attr(self, name):
        return unescape(name, self._entitydefs, self.encoding)
    def unescape_attrs(self, attrs):
        escaped_attrs = []
        for key, val in attrs:
            escaped_attrs.append((key, self.unescape_attr(val)))
        return escaped_attrs

class PullParser(_AbstractParser, HTMLParser.HTMLParser):
    def __init__(self, *args, **kwds):
        HTMLParser.HTMLParser.__init__(self)
        _AbstractParser.__init__(self, *args, **kwds)
    def unescape(self, name):
        # Use the entitydefs passed into constructor, not
        # HTMLParser.HTMLParser's entitydefs.
        return self.unescape_attr(name)

class TolerantPullParser(_AbstractParser, sgmllib.SGMLParser):
    def __init__(self, *args, **kwds):
        sgmllib.SGMLParser.__init__(self)
        _AbstractParser.__init__(self, *args, **kwds)
    def unknown_starttag(self, tag, attrs):
        attrs = self.unescape_attrs(attrs)
        self._tokenstack.append(Token("starttag", tag, attrs))
    def unknown_endtag(self, tag):
        self._tokenstack.append(Token("endtag", tag))


def _test():
   import doctest, _pullparser
   return doctest.testmod(_pullparser)

if __name__ == "__main__":
   _test()
