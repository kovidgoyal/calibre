"""
INLINE PATTERNS
=============================================================================

Inline patterns such as *emphasis* are handled by means of auxiliary
objects, one per pattern.  Pattern objects must be instances of classes
that extend markdown.Pattern.  Each pattern object uses a single regular
expression and needs support the following methods:

    pattern.getCompiledRegExp() # returns a regular expression

    pattern.handleMatch(m) # takes a match object and returns
                           # an ElementTree element or just plain text

All of python markdown's built-in patterns subclass from Pattern,
but you can add additional patterns that don't.

Also note that all the regular expressions used by inline must
capture the whole block.  For this reason, they all start with
'^(.*)' and end with '(.*)!'.  In case with built-in expression
Pattern takes care of adding the "^(.*)" and "(.*)!".

Finally, the order in which regular expressions are applied is very
important - e.g. if we first replace http://.../ links with <a> tags
and _then_ try to replace inline html, we would end up with a mess.
So, we apply the expressions in the following order:

* escape and backticks have to go before everything else, so
  that we can preempt any markdown patterns by escaping them.

* then we handle auto-links (must be done before inline html)

* then we handle inline HTML.  At this point we will simply
  replace all inline HTML strings with a placeholder and add
  the actual HTML to a hash.

* then inline images (must be done before links)

* then bracketed links, first regular then reference-style

* finally we apply strong and emphasis
"""

import markdown
import re
from urlparse import urlparse, urlunparse
import sys
if sys.version >= "3.0":
    from html import entities as htmlentitydefs
else:
    import htmlentitydefs

"""
The actual regular expressions for patterns
-----------------------------------------------------------------------------
"""

NOBRACKET = r'[^\]\[]*'
BRK = ( r'\[('
        + (NOBRACKET + r'(\[')*6
        + (NOBRACKET+ r'\])*')*6
        + NOBRACKET + r')\]' )
NOIMG = r'(?<!\!)'

BACKTICK_RE = r'(?<!\\)(`+)(.+?)(?<!`)\2(?!`)' # `e=f()` or ``e=f("`")``
ESCAPE_RE = r'\\(.)'                             # \<
EMPHASIS_RE = r'(\*)([^\*]*)\2'                    # *emphasis*
STRONG_RE = r'(\*{2}|_{2})(.*?)\2'                      # **strong**
STRONG_EM_RE = r'(\*{3}|_{3})(.*?)\2'            # ***strong***

if markdown.SMART_EMPHASIS:
    EMPHASIS_2_RE = r'(?<!\S)(_)(\S.*?)\2'        # _emphasis_
else:
    EMPHASIS_2_RE = r'(_)(.*?)\2'                 # _emphasis_

LINK_RE = NOIMG + BRK + \
r'''\(\s*(<.*?>|((?:(?:\(.*?\))|[^\(\)]))*?)\s*((['"])(.*)\12)?\)'''
# [text](url) or [text](<url>)

IMAGE_LINK_RE = r'\!' + BRK + r'\s*\((<.*?>|([^\)]*))\)'
# ![alttxt](http://x.com/) or ![alttxt](<http://x.com/>)
REFERENCE_RE = NOIMG + BRK+ r'\s*\[([^\]]*)\]'           # [Google][3]
IMAGE_REFERENCE_RE = r'\!' + BRK + '\s*\[([^\]]*)\]' # ![alt text][2]
NOT_STRONG_RE = r'( \* )'                        # stand-alone * or _
AUTOLINK_RE = r'<((?:f|ht)tps?://[^>]*)>'        # <http://www.123.com>
AUTOMAIL_RE = r'<([^> \!]*@[^> ]*)>'               # <me@example.com>

HTML_RE = r'(\<([a-zA-Z/][^\>]*?|\!--.*?--)\>)'               # <...>
ENTITY_RE = r'(&[\#a-zA-Z0-9]*;)'               # &amp;
LINE_BREAK_RE = r'  \n'                     # two spaces at end of line
LINE_BREAK_2_RE = r'  $'                    # two spaces at end of text


def dequote(string):
    """Remove quotes from around a string."""
    if ( ( string.startswith('"') and string.endswith('"'))
         or (string.startswith("'") and string.endswith("'")) ):
        return string[1:-1]
    else:
        return string

ATTR_RE = re.compile("\{@([^\}]*)=([^\}]*)}") # {@id=123}

def handleAttributes(text, parent):
    """Set values of an element based on attribute definitions ({@id=123})."""
    def attributeCallback(match):
        parent.set(match.group(1), match.group(2).replace('\n', ' '))
    return ATTR_RE.sub(attributeCallback, text)


"""
The pattern classes
-----------------------------------------------------------------------------
"""

class Pattern:
    """Base class that inline patterns subclass. """

    def __init__ (self, pattern, markdown_instance=None):
        """
        Create an instant of an inline pattern.

        Keyword arguments:

        * pattern: A regular expression that matches a pattern

        """
        self.pattern = pattern
        self.compiled_re = re.compile("^(.*?)%s(.*?)$" % pattern, re.DOTALL)

        # Api for Markdown to pass safe_mode into instance
        self.safe_mode = False
        if markdown_instance:
            self.markdown = markdown_instance

    def getCompiledRegExp (self):
        """ Return a compiled regular expression. """
        return self.compiled_re

    def handleMatch(self, m):
        """Return a ElementTree element from the given match.

        Subclasses should override this method.

        Keyword arguments:

        * m: A re match object containing a match of the pattern.

        """
        pass

    def type(self):
        """ Return class name, to define pattern type """
        return self.__class__.__name__

BasePattern = Pattern # for backward compatibility

class SimpleTextPattern (Pattern):
    """ Return a simple text of group(2) of a Pattern. """
    def handleMatch(self, m):
        text = m.group(2)
        if text == markdown.INLINE_PLACEHOLDER_PREFIX:
            return None
        return text

class SimpleTagPattern (Pattern):
    """
    Return element of type `tag` with a text attribute of group(3)
    of a Pattern.

    """
    def __init__ (self, pattern, tag):
        Pattern.__init__(self, pattern)
        self.tag = tag

    def handleMatch(self, m):
        el = markdown.etree.Element(self.tag)
        el.text = m.group(3)
        return el


class SubstituteTagPattern (SimpleTagPattern):
    """ Return a eLement of type `tag` with no children. """
    def handleMatch (self, m):
        return markdown.etree.Element(self.tag)


class BacktickPattern (Pattern):
    """ Return a `<code>` element containing the matching text. """
    def __init__ (self, pattern):
        Pattern.__init__(self, pattern)
        self.tag = "code"

    def handleMatch(self, m):
        el = markdown.etree.Element(self.tag)
        el.text = markdown.AtomicString(m.group(3).strip())
        return el


class DoubleTagPattern (SimpleTagPattern):
    """Return a ElementTree element nested in tag2 nested in tag1.

    Useful for strong emphasis etc.

    """
    def handleMatch(self, m):
        tag1, tag2 = self.tag.split(",")
        el1 = markdown.etree.Element(tag1)
        el2 = markdown.etree.SubElement(el1, tag2)
        el2.text = m.group(3)
        return el1


class HtmlPattern (Pattern):
    """ Store raw inline html and return a placeholder. """
    def handleMatch (self, m):
        rawhtml = m.group(2)
        inline = True
        place_holder = self.markdown.htmlStash.store(rawhtml)
        return place_holder


class LinkPattern (Pattern):
    """ Return a link element from the given match. """
    def handleMatch(self, m):
        el = markdown.etree.Element("a")
        el.text = m.group(2)
        title = m.group(11)
        href = m.group(9)

        if href:
            if href[0] == "<":
                href = href[1:-1]
            el.set("href", self.sanitize_url(href.strip()))
        else:
            el.set("href", "")

        if title:
            title = dequote(title) #.replace('"', "&quot;")
            el.set("title", title)
        return el

    def sanitize_url(self, url):
        """
        Sanitize a url against xss attacks in "safe_mode".

        Rather than specifically blacklisting `javascript:alert("XSS")` and all
        its aliases (see <http://ha.ckers.org/xss.html>), we whitelist known
        safe url formats. Most urls contain a network location, however some
        are known not to (i.e.: mailto links). Script urls do not contain a
        location. Additionally, for `javascript:...`, the scheme would be
        "javascript" but some aliases will appear to `urlparse()` to have no
        scheme. On top of that relative links (i.e.: "foo/bar.html") have no
        scheme. Therefore we must check "path", "parameters", "query" and
        "fragment" for any literal colons. We don't check "scheme" for colons
        because it *should* never have any and "netloc" must allow the form:
        `username:password@host:port`.

        """
        locless_schemes = ['', 'mailto', 'news']
        scheme, netloc, path, params, query, fragment = url = urlparse(url)
        safe_url = False
        if netloc != '' or scheme in locless_schemes:
            safe_url = True

        for part in url[2:]:
            if ":" in part:
                safe_url = False

        if self.markdown.safeMode and not safe_url:
            return ''
        else:
            return urlunparse(url)

class ImagePattern(LinkPattern):
    """ Return a img element from the given match. """
    def handleMatch(self, m):
        el = markdown.etree.Element("img")
        src_parts = m.group(9).split()
        if src_parts:
            src = src_parts[0]
            if src[0] == "<" and src[-1] == ">":
                src = src[1:-1]
            el.set('src', self.sanitize_url(src))
        else:
            el.set('src', "")
        if len(src_parts) > 1:
            el.set('title', dequote(" ".join(src_parts[1:])))

        if markdown.ENABLE_ATTRIBUTES:
            truealt = handleAttributes(m.group(2), el)
        else:
            truealt = m.group(2)

        el.set('alt', truealt)
        return el

class ReferencePattern(LinkPattern):
    """ Match to a stored reference and return link element. """
    def handleMatch(self, m):
        if m.group(9):
            id = m.group(9).lower()
        else:
            # if we got something like "[Google][]"
            # we'll use "google" as the id
            id = m.group(2).lower()

        if not id in self.markdown.references: # ignore undefined refs
            return None
        href, title = self.markdown.references[id]

        text = m.group(2)
        return self.makeTag(href, title, text)

    def makeTag(self, href, title, text):
        el = markdown.etree.Element('a')

        el.set('href', self.sanitize_url(href))
        if title:
            el.set('title', title)

        el.text = text
        return el


class ImageReferencePattern (ReferencePattern):
    """ Match to a stored reference and return img element. """
    def makeTag(self, href, title, text):
        el = markdown.etree.Element("img")
        el.set("src", self.sanitize_url(href))
        if title:
            el.set("title", title)
        el.set("alt", text)
        return el


class AutolinkPattern (Pattern):
    """ Return a link Element given an autolink (`<http://example/com>`). """
    def handleMatch(self, m):
        el = markdown.etree.Element("a")
        el.set('href', m.group(2))
        el.text = markdown.AtomicString(m.group(2))
        return el

class AutomailPattern (Pattern):
    """
    Return a mailto link Element given an automail link (`<foo@example.com>`).
    """
    def handleMatch(self, m):
        el = markdown.etree.Element('a')
        email = m.group(2)
        if email.startswith("mailto:"):
            email = email[len("mailto:"):]

        def codepoint2name(code):
            """Return entity definition by code, or the code if not defined."""
            entity = htmlentitydefs.codepoint2name.get(code)
            if entity:
                return "%s%s;" % (markdown.AMP_SUBSTITUTE, entity)
            else:
                return "%s#%d;" % (markdown.AMP_SUBSTITUTE, code)

        letters = [codepoint2name(ord(letter)) for letter in email]
        el.text = markdown.AtomicString(''.join(letters))

        mailto = "mailto:" + email
        mailto = "".join([markdown.AMP_SUBSTITUTE + '#%d;' %
                          ord(letter) for letter in mailto])
        el.set('href', mailto)
        return el

