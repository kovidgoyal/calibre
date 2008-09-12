"""Beautiful Soup
Elixir and Tonic
"The Screen-Scraper's Friend"
v2.1.1
http://www.crummy.com/software/BeautifulSoup/

Beautiful Soup parses arbitrarily invalid XML- or HTML-like substance
into a tree representation. It provides methods and Pythonic idioms
that make it easy to search and modify the tree.

A well-formed XML/HTML document will yield a well-formed data
structure. An ill-formed XML/HTML document will yield a
correspondingly ill-formed data structure. If your document is only
locally well-formed, you can use this library to find and process the
well-formed part of it. The BeautifulSoup class has heuristics for
obtaining a sensible parse tree in the face of common HTML errors.

Beautiful Soup has no external dependencies. It works with Python 2.2
and up.

Beautiful Soup defines classes for four different parsing strategies:

 * BeautifulStoneSoup, for parsing XML, SGML, or your domain-specific
   language that kind of looks like XML.

 * BeautifulSoup, for parsing run-of-the-mill HTML code, be it valid
   or invalid.

 * ICantBelieveItsBeautifulSoup, for parsing valid but bizarre HTML
   that trips up BeautifulSoup.

 * BeautifulSOAP, for making it easier to parse XML documents that use
   lots of subelements containing a single string, where you'd prefer
   they put that string into an attribute (such as SOAP messages).

You can subclass BeautifulStoneSoup or BeautifulSoup to create a
parsing strategy specific to an XML schema or a particular bizarre
HTML document. Typically your subclass would just override
SELF_CLOSING_TAGS and/or NESTABLE_TAGS.
"""
from __future__ import generators

__author__ = "Leonard Richardson (leonardr@segfault.org)"
__version__ = "2.1.1"
__date__ = "$Date: 2004/10/18 00:14:20 $"
__copyright__ = "Copyright (c) 2004-2005 Leonard Richardson"
__license__ = "PSF"

from sgmllib import SGMLParser, SGMLParseError
import types
import re
import sgmllib

#This code makes Beautiful Soup able to parse XML with namespaces
sgmllib.tagfind = re.compile('[a-zA-Z][-_.:a-zA-Z0-9]*')

class NullType(object):

    """Similar to NoneType with a corresponding singleton instance
    'Null' that, unlike None, accepts any message and returns itself.

    Examples:
    >>> Null("send", "a", "message")("and one more",
    ...      "and what you get still") is Null
    True
    """

    def __new__(cls):                    return Null
    def __call__(self, *args, **kwargs): return Null
##    def __getstate__(self, *args):       return Null
    def __getattr__(self, attr):         return Null
    def __getitem__(self, item):         return Null
    def __setattr__(self, attr, value):  pass
    def __setitem__(self, item, value):  pass
    def __len__(self):                   return 0
    # FIXME: is this a python bug? otherwise ``for x in Null: pass``
    #        never terminates...
    def __iter__(self):                  return iter([])
    def __contains__(self, item):        return False
    def __repr__(self):                  return "Null"
Null = object.__new__(NullType)

class PageElement:
    """Contains the navigational information for some part of the page
    (either a tag or a piece of text)"""

    def setup(self, parent=Null, previous=Null):
        """Sets up the initial relations between this element and
        other elements."""
        self.parent = parent
        self.previous = previous
        self.next = Null
        self.previousSibling = Null
        self.nextSibling = Null
        if self.parent and self.parent.contents:
            self.previousSibling = self.parent.contents[-1]
            self.previousSibling.nextSibling = self

    def findNext(self, name=None, attrs={}, text=None):
        """Returns the first item that matches the given criteria and
        appears after this Tag in the document."""
        return self._first(self.fetchNext, name, attrs, text)
    firstNext = findNext

    def fetchNext(self, name=None, attrs={}, text=None, limit=None):
        """Returns all items that match the given criteria and appear
        before after Tag in the document."""
        return self._fetch(name, attrs, text, limit, self.nextGenerator)

    def findNextSibling(self, name=None, attrs={}, text=None):
        """Returns the closest sibling to this Tag that matches the
        given criteria and appears after this Tag in the document."""
        return self._first(self.fetchNextSiblings, name, attrs, text)
    firstNextSibling = findNextSibling

    def fetchNextSiblings(self, name=None, attrs={}, text=None, limit=None):
        """Returns the siblings of this Tag that match the given
        criteria and appear after this Tag in the document."""
        return self._fetch(name, attrs, text, limit, self.nextSiblingGenerator)

    def findPrevious(self, name=None, attrs={}, text=None):
        """Returns the first item that matches the given criteria and
        appears before this Tag in the document."""
        return self._first(self.fetchPrevious, name, attrs, text)

    def fetchPrevious(self, name=None, attrs={}, text=None, limit=None):
        """Returns all items that match the given criteria and appear
        before this Tag in the document."""
        return self._fetch(name, attrs, text, limit, self.previousGenerator)
    firstPrevious = findPrevious

    def findPreviousSibling(self, name=None, attrs={}, text=None):
        """Returns the closest sibling to this Tag that matches the
        given criteria and appears before this Tag in the document."""
        return self._first(self.fetchPreviousSiblings, name, attrs, text)
    firstPreviousSibling = findPreviousSibling

    def fetchPreviousSiblings(self, name=None, attrs={}, text=None,
                              limit=None):
        """Returns the siblings of this Tag that match the given
        criteria and appear before this Tag in the document."""
        return self._fetch(name, attrs, text, limit,
                           self.previousSiblingGenerator)

    def findParent(self, name=None, attrs={}):
        """Returns the closest parent of this Tag that matches the given
        criteria."""
        r = Null
        l = self.fetchParents(name, attrs, 1)
        if l:
            r = l[0]
        return r
    firstParent = findParent

    def fetchParents(self, name=None, attrs={}, limit=None):
        """Returns the parents of this Tag that match the given
        criteria."""
        return self._fetch(name, attrs, None, limit, self.parentGenerator)

    #These methods do the real heavy lifting.

    def _first(self, method, name, attrs, text):
        r = Null
        l = method(name, attrs, text, 1)
        if l:
            r = l[0]
        return r
    
    def _fetch(self, name, attrs, text, limit, generator):
        "Iterates over a generator looking for things that match."
        if not hasattr(attrs, 'items'):
            attrs = {'class' : attrs}

        results = []
        g = generator()
        while True:
            try:
                i = g.next()
            except StopIteration:
                break
            found = None
            if isinstance(i, Tag):
                if not text:
                    if not name or self._matches(i, name):
                        match = True
                        for attr, matchAgainst in attrs.items():
                            check = i.get(attr)
                            if not self._matches(check, matchAgainst):
                                match = False
                                break
                        if match:
                            found = i
            elif text:
                if self._matches(i, text):
                    found = i                    
            if found:
                results.append(found)
                if limit and len(results) >= limit:
                    break
        return results

    #Generators that can be used to navigate starting from both
    #NavigableTexts and Tags.                
    def nextGenerator(self):
        i = self
        while i:
            i = i.next
            yield i

    def nextSiblingGenerator(self):
        i = self
        while i:
            i = i.nextSibling
            yield i

    def previousGenerator(self):
        i = self
        while i:
            i = i.previous
            yield i

    def previousSiblingGenerator(self):
        i = self
        while i:
            i = i.previousSibling
            yield i

    def parentGenerator(self):
        i = self
        while i:
            i = i.parent
            yield i

    def _matches(self, chunk, howToMatch):
        #print 'looking for %s in %s' % (howToMatch, chunk)
        #
        # If given a list of items, return true if the list contains a
        # text element that matches.
        if isList(chunk) and not isinstance(chunk, Tag):
            for tag in chunk:
                if isinstance(tag, NavigableText) and self._matches(tag, howToMatch):
                    return True
            return False
        if callable(howToMatch):
            return howToMatch(chunk)
        if isinstance(chunk, Tag):
            #Custom match methods take the tag as an argument, but all other
            #ways of matching match the tag name as a string
            chunk = chunk.name
        #Now we know that chunk is a string
        if not isinstance(chunk, basestring):
            chunk = str(chunk)
        if hasattr(howToMatch, 'match'):
            # It's a regexp object.
            return howToMatch.search(chunk)
        if isList(howToMatch):
            return chunk in howToMatch
        if hasattr(howToMatch, 'items'):
            return howToMatch.has_key(chunk)
        #It's just a string
        return str(howToMatch) == chunk

class NavigableText(PageElement):

    def __getattr__(self, attr):
        "For backwards compatibility, text.string gives you text"
        if attr == 'string':
            return self
        else:
            raise AttributeError, "'%s' object has no attribute '%s'" % (self.__class__.__name__, attr)
        
class NavigableString(str, NavigableText):
    pass

class NavigableUnicodeString(unicode, NavigableText):
    pass

class Tag(PageElement):

    """Represents a found HTML tag with its attributes and contents."""

    def __init__(self, name, attrs=None, parent=Null, previous=Null):
        "Basic constructor."
        self.name = name
        if attrs == None:
            attrs = []
        self.attrs = attrs
        self.contents = []
        self.setup(parent, previous)
        self.hidden = False

    def get(self, key, default=None):
        """Returns the value of the 'key' attribute for the tag, or
        the value given for 'default' if it doesn't have that
        attribute."""
        return self._getAttrMap().get(key, default)    

    def __getitem__(self, key):
        """tag[key] returns the value of the 'key' attribute for the tag,
        and throws an exception if it's not there."""
        return self._getAttrMap()[key]

    def __iter__(self):
        "Iterating over a tag iterates over its contents."
        return iter(self.contents)

    def __len__(self):
        "The length of a tag is the length of its list of contents."
        return len(self.contents)

    def __contains__(self, x):
        return x in self.contents

    def __nonzero__(self):
        "A tag is non-None even if it has no contents."
        return True

    def __setitem__(self, key, value):        
        """Setting tag[key] sets the value of the 'key' attribute for the
        tag."""
        self._getAttrMap()
        self.attrMap[key] = value
        found = False
        for i in range(0, len(self.attrs)):
            if self.attrs[i][0] == key:
                self.attrs[i] = (key, value)
                found = True
        if not found:
            self.attrs.append((key, value))
        self._getAttrMap()[key] = value

    def __delitem__(self, key):
        "Deleting tag[key] deletes all 'key' attributes for the tag."
        for item in self.attrs:
            if item[0] == key:
                self.attrs.remove(item)
                #We don't break because bad HTML can define the same
                #attribute multiple times.
            self._getAttrMap()
            if self.attrMap.has_key(key):
                del self.attrMap[key]

    def __call__(self, *args, **kwargs):
        """Calling a tag like a function is the same as calling its
        fetch() method. Eg. tag('a') returns a list of all the A tags
        found within this tag."""
        return apply(self.fetch, args, kwargs)

    def __getattr__(self, tag):
        if len(tag) > 3 and tag.rfind('Tag') == len(tag)-3:
            return self.first(tag[:-3])
        elif tag.find('__') != 0:
            return self.first(tag)

    def __eq__(self, other):
        """Returns true iff this tag has the same name, the same attributes,
        and the same contents (recursively) as the given tag.

        NOTE: right now this will return false if two tags have the
        same attributes in a different order. Should this be fixed?"""
        if not hasattr(other, 'name') or not hasattr(other, 'attrs') or not hasattr(other, 'contents') or self.name != other.name or self.attrs != other.attrs or len(self) != len(other):
            return False
        for i in range(0, len(self.contents)):
            if self.contents[i] != other.contents[i]:
                return False
        return True

    def __ne__(self, other):
        """Returns true iff this tag is not identical to the other tag,
        as defined in __eq__."""
        return not self == other

    def __repr__(self):
        """Renders this tag as a string."""
        return str(self)

    def __unicode__(self):
        return self.__str__(1)

    def __str__(self, needUnicode=None, showStructureIndent=None):
        """Returns a string or Unicode representation of this tag and
        its contents.

        NOTE: since Python's HTML parser consumes whitespace, this
        method is not certain to reproduce the whitespace present in
        the original string."""
        
        attrs = []
        if self.attrs:
            for key, val in self.attrs:
                attrs.append('%s="%s"' % (key, val))
        close = ''
        closeTag = ''
        if self.isSelfClosing():
            close = ' /'
        else:
            closeTag = '</%s>' % self.name
        indentIncrement = None        
        if showStructureIndent != None:
            indentIncrement = showStructureIndent
            if not self.hidden:
                indentIncrement += 1
        contents = self.renderContents(indentIncrement, needUnicode=needUnicode)        
        if showStructureIndent:
            space = '\n%s' % (' ' * showStructureIndent)
        if self.hidden:
            s = contents
        else:
            s = []
            attributeString = ''
            if attrs:
                attributeString = ' ' + ' '.join(attrs)            
            if showStructureIndent:
                s.append(space)
            s.append('<%s%s%s>' % (self.name, attributeString, close))
            s.append(contents)
            if closeTag and showStructureIndent != None:
                s.append(space)
            s.append(closeTag)
            s = ''.join(s)
        isUnicode = type(s) == types.UnicodeType
        if needUnicode and not isUnicode:
            s = unicode(s)
        elif isUnicode and needUnicode==False:
            s = str(s)
        return s

    def prettify(self, needUnicode=None):
        return self.__str__(needUnicode, showStructureIndent=True)

    def renderContents(self, showStructureIndent=None, needUnicode=None):
        """Renders the contents of this tag as a (possibly Unicode) 
        string."""
        s=[]
        for c in self:
            text = None
            if isinstance(c, NavigableUnicodeString) or type(c) == types.UnicodeType:
                text = unicode(c)
            elif isinstance(c, Tag):
                s.append(c.__str__(needUnicode, showStructureIndent))
            elif needUnicode:
                text = unicode(c)
            else:
                text = str(c)
            if text:
                if showStructureIndent != None:
                    if text[-1] == '\n':
                        text = text[:-1]
                s.append(text)
        return ''.join(s)    

    #Soup methods

    def firstText(self, text, recursive=True):
        """Convenience method to retrieve the first piece of text matching the
        given criteria. 'text' can be a string, a regular expression object,
        a callable that takes a string and returns whether or not the
        string 'matches', etc."""
        return self.first(recursive=recursive, text=text)

    def fetchText(self, text, recursive=True, limit=None):
        """Convenience method to retrieve all pieces of text matching the
        given criteria. 'text' can be a string, a regular expression object,
        a callable that takes a string and returns whether or not the
        string 'matches', etc."""
        return self.fetch(recursive=recursive, text=text, limit=limit)

    def first(self, name=None, attrs={}, recursive=True, text=None):
        """Return only the first child of this
        Tag matching the given criteria."""
        r = Null
        l = self.fetch(name, attrs, recursive, text, 1)
        if l:
            r = l[0]
        return r
    findChild = first

    def fetch(self, name=None, attrs={}, recursive=True, text=None,
              limit=None):
        """Extracts a list of Tag objects that match the given
        criteria.  You can specify the name of the Tag and any
        attributes you want the Tag to have.

        The value of a key-value pair in the 'attrs' map can be a
        string, a list of strings, a regular expression object, or a
        callable that takes a string and returns whether or not the
        string matches for some custom definition of 'matches'. The
        same is true of the tag name."""
        generator = self.recursiveChildGenerator
        if not recursive:
            generator = self.childGenerator
        return self._fetch(name, attrs, text, limit, generator)
    fetchChildren = fetch
    
    #Utility methods

    def isSelfClosing(self):
        """Returns true iff this is a self-closing tag as defined in the HTML
        standard.

        TODO: This is specific to BeautifulSoup and its subclasses, but it's
        used by __str__"""
        return self.name in BeautifulSoup.SELF_CLOSING_TAGS

    def append(self, tag):
        """Appends the given tag to the contents of this tag."""
        self.contents.append(tag)

    #Private methods

    def _getAttrMap(self):
        """Initializes a map representation of this tag's attributes,
        if not already initialized."""
        if not getattr(self, 'attrMap'):
            self.attrMap = {}
            for (key, value) in self.attrs:
                self.attrMap[key] = value 
        return self.attrMap

    #Generator methods
    def childGenerator(self):
        for i in range(0, len(self.contents)):
            yield self.contents[i]
        raise StopIteration
    
    def recursiveChildGenerator(self):
        stack = [(self, 0)]
        while stack:
            tag, start = stack.pop()
            if isinstance(tag, Tag):            
                for i in range(start, len(tag.contents)):
                    a = tag.contents[i]
                    yield a
                    if isinstance(a, Tag) and tag.contents:
                        if i < len(tag.contents) - 1:
                            stack.append((tag, i+1))
                        stack.append((a, 0))
                        break
        raise StopIteration


def isList(l):
    """Convenience method that works with all 2.x versions of Python
    to determine whether or not something is listlike."""
    return hasattr(l, '__iter__') \
           or (type(l) in (types.ListType, types.TupleType))

def buildTagMap(default, *args):
    """Turns a list of maps, lists, or scalars into a single map.
    Used to build the SELF_CLOSING_TAGS and NESTABLE_TAGS maps out
    of lists and partial maps."""
    built = {}
    for portion in args:
        if hasattr(portion, 'items'):
            #It's a map. Merge it.
            for k,v in portion.items():
                built[k] = v
        elif isList(portion):
            #It's a list. Map each item to the default.
            for k in portion:
                built[k] = default
        else:
            #It's a scalar. Map it to the default.
            built[portion] = default
    return built

class BeautifulStoneSoup(Tag, SGMLParser):

    """This class contains the basic parser and fetch code. It defines
    a parser that knows nothing about tag behavior except for the
    following:
   
      You can't close a tag without closing all the tags it encloses.
      That is, "<foo><bar></foo>" actually means
      "<foo><bar></bar></foo>".

    [Another possible explanation is "<foo><bar /></foo>", but since
    this class defines no SELF_CLOSING_TAGS, it will never use that
    explanation.]

    This class is useful for parsing XML or made-up markup languages,
    or when BeautifulSoup makes an assumption counter to what you were
    expecting."""

    SELF_CLOSING_TAGS = {}
    NESTABLE_TAGS = {}
    RESET_NESTING_TAGS = {}
    QUOTE_TAGS = {}

    #As a public service we will by default silently replace MS smart quotes
    #and similar characters with their HTML or ASCII equivalents.
    MS_CHARS = { '\x80' : '&euro;',
                 '\x81' : ' ',
                 '\x82' : '&sbquo;',
                 '\x83' : '&fnof;',
                 '\x84' : '&bdquo;',
                 '\x85' : '&hellip;',
                 '\x86' : '&dagger;',
                 '\x87' : '&Dagger;',
                 '\x88' : '&caret;',
                 '\x89' : '%',
                 '\x8A' : '&Scaron;',
                 '\x8B' : '&lt;',
                 '\x8C' : '&OElig;',
                 '\x8D' : '?',
                 '\x8E' : 'Z',
                 '\x8F' : '?',
                 '\x90' : '?',
                 '\x91' : '&lsquo;',
                 '\x92' : '&rsquo;',
                 '\x93' : '&ldquo;',
                 '\x94' : '&rdquo;',
                 '\x95' : '&bull;',
                 '\x96' : '&ndash;',
                 '\x97' : '&mdash;',
                 '\x98' : '&tilde;',
                 '\x99' : '&trade;',
                 '\x9a' : '&scaron;',
                 '\x9b' : '&gt;',
                 '\x9c' : '&oelig;',
                 '\x9d' : '?',
                 '\x9e' : 'z',
                 '\x9f' : '&Yuml;',}

    PARSER_MASSAGE = [(re.compile('(<[^<>]*)/>'),
                       lambda(x):x.group(1) + ' />'),
                      (re.compile('<!\s+([^<>]*)>'),
                       lambda(x):'<!' + x.group(1) + '>'),
                      (re.compile("([\x80-\x9f])"),
                       lambda(x): BeautifulStoneSoup.MS_CHARS.get(x.group(1)))
                      ]

    ROOT_TAG_NAME = '[document]'

    def __init__(self, text=None, avoidParserProblems=True,
                 initialTextIsEverything=True):
        """Initialize this as the 'root tag' and feed in any text to
        the parser.

        NOTE about avoidParserProblems: sgmllib will process most bad
        HTML, and BeautifulSoup has tricks for dealing with some HTML
        that kills sgmllib, but Beautiful Soup can nonetheless choke
        or lose data if your data uses self-closing tags or
        declarations incorrectly. By default, Beautiful Soup sanitizes
        its input to avoid the vast majority of these problems. The
        problems are relatively rare, even in bad HTML, so feel free
        to pass in False to avoidParserProblems if they don't apply to
        you, and you'll get better performance. The only reason I have
        this turned on by default is so I don't get so many tech
        support questions.

        The two most common instances of invalid HTML that will choke
        sgmllib are fixed by the default parser massage techniques:

         <br/> (No space between name of closing tag and tag close)
         <! --Comment--> (Extraneous whitespace in declaration)

        You can pass in a custom list of (RE object, replace method)
        tuples to get Beautiful Soup to scrub your input the way you
        want."""
        Tag.__init__(self, self.ROOT_TAG_NAME)
        if avoidParserProblems \
           and not isList(avoidParserProblems):
            avoidParserProblems = self.PARSER_MASSAGE            
        self.avoidParserProblems = avoidParserProblems
        SGMLParser.__init__(self)
        self.quoteStack = []
        self.hidden = 1
        self.reset()
        if hasattr(text, 'read'):
            #It's a file-type object.
            text = text.read()
        if text:
            self.feed(text)
        if initialTextIsEverything:
            self.done()

    def __getattr__(self, methodName):
        """This method routes method call requests to either the SGMLParser
        superclass or the Tag superclass, depending on the method name."""
        if methodName.find('start_') == 0 or methodName.find('end_') == 0 \
               or methodName.find('do_') == 0:
            return SGMLParser.__getattr__(self, methodName)
        elif methodName.find('__') != 0:
            return Tag.__getattr__(self, methodName)
        else:
            raise AttributeError

    def feed(self, text):
        if self.avoidParserProblems:
            for fix, m in self.avoidParserProblems:
                text = fix.sub(m, text)
        SGMLParser.feed(self, text)

    def done(self):
        """Called when you're done parsing, so that the unclosed tags can be
        correctly processed."""
        self.endData() #NEW
        while self.currentTag.name != self.ROOT_TAG_NAME:
            self.popTag()
            
    def reset(self):
        SGMLParser.reset(self)
        self.currentData = []
        self.currentTag = None
        self.tagStack = []
        self.pushTag(self)        
    
    def popTag(self):
        tag = self.tagStack.pop()
        # Tags with just one string-owning child get the child as a
        # 'string' property, so that soup.tag.string is shorthand for
        # soup.tag.contents[0]
        if len(self.currentTag.contents) == 1 and \
           isinstance(self.currentTag.contents[0], NavigableText):
            self.currentTag.string = self.currentTag.contents[0]

        #print "Pop", tag.name
        if self.tagStack:
            self.currentTag = self.tagStack[-1]
        return self.currentTag

    def pushTag(self, tag):
        #print "Push", tag.name
        if self.currentTag:
            self.currentTag.append(tag)
        self.tagStack.append(tag)
        self.currentTag = self.tagStack[-1]

    def endData(self):
        currentData = ''.join(self.currentData)
        if currentData:
            if not currentData.strip():
                if '\n' in currentData:
                    currentData = '\n'
                else:
                    currentData = ' '
            c = NavigableString
            if type(currentData) == types.UnicodeType:
                c = NavigableUnicodeString
            o = c(currentData)
            o.setup(self.currentTag, self.previous)
            if self.previous:
                self.previous.next = o
            self.previous = o
            self.currentTag.contents.append(o)
        self.currentData = []

    def _popToTag(self, name, inclusivePop=True):
        """Pops the tag stack up to and including the most recent
        instance of the given tag. If inclusivePop is false, pops the tag
        stack up to but *not* including the most recent instqance of
        the given tag."""
        if name == self.ROOT_TAG_NAME:
            return            

        numPops = 0
        mostRecentTag = None
        for i in range(len(self.tagStack)-1, 0, -1):
            if name == self.tagStack[i].name:
                numPops = len(self.tagStack)-i
                break
        if not inclusivePop:
            numPops = numPops - 1

        for i in range(0, numPops):
            mostRecentTag = self.popTag()
        return mostRecentTag    

    def _smartPop(self, name):

        """We need to pop up to the previous tag of this type, unless
        one of this tag's nesting reset triggers comes between this
        tag and the previous tag of this type, OR unless this tag is a
        generic nesting trigger and another generic nesting trigger
        comes between this tag and the previous tag of this type.

        Examples:
         <p>Foo<b>Bar<p> should pop to 'p', not 'b'.
         <p>Foo<table>Bar<p> should pop to 'table', not 'p'.
         <p>Foo<table><tr>Bar<p> should pop to 'tr', not 'p'.
         <p>Foo<b>Bar<p> should pop to 'p', not 'b'.

         <li><ul><li> *<li>* should pop to 'ul', not the first 'li'.
         <tr><table><tr> *<tr>* should pop to 'table', not the first 'tr'
         <td><tr><td> *<td>* should pop to 'tr', not the first 'td'
        """

        nestingResetTriggers = self.NESTABLE_TAGS.get(name)
        isNestable = nestingResetTriggers != None
        isResetNesting = self.RESET_NESTING_TAGS.has_key(name)
        popTo = None
        inclusive = True
        for i in range(len(self.tagStack)-1, 0, -1):
            p = self.tagStack[i]
            if (not p or p.name == name) and not isNestable:
                #Non-nestable tags get popped to the top or to their
                #last occurance.
                popTo = name
                break
            if (nestingResetTriggers != None
                and p.name in nestingResetTriggers) \
                or (nestingResetTriggers == None and isResetNesting
                    and self.RESET_NESTING_TAGS.has_key(p.name)):
                
                #If we encounter one of the nesting reset triggers
                #peculiar to this tag, or we encounter another tag
                #that causes nesting to reset, pop up to but not
                #including that tag.

                popTo = p.name
                inclusive = False
                break
            p = p.parent
        if popTo:
            self._popToTag(popTo, inclusive)

    def unknown_starttag(self, name, attrs, selfClosing=0):
        #print "Start tag %s" % name
        if self.quoteStack:
            #This is not a real tag.
            #print "<%s> is not real!" % name
            attrs = ''.join(map(lambda(x, y): ' %s="%s"' % (x, y), attrs))
            self.handle_data('<%s%s>' % (name, attrs))
            return
        self.endData()
        if not name in self.SELF_CLOSING_TAGS and not selfClosing:
            self._smartPop(name)
        tag = Tag(name, attrs, self.currentTag, self.previous)        
        if self.previous:
            self.previous.next = tag
        self.previous = tag
        self.pushTag(tag)
        if selfClosing or name in self.SELF_CLOSING_TAGS:
            self.popTag()                
        if name in self.QUOTE_TAGS:
            #print "Beginning quote (%s)" % name
            self.quoteStack.append(name)
            self.literal = 1

    def unknown_endtag(self, name):
        if self.quoteStack and self.quoteStack[-1] != name:
            #This is not a real end tag.
            #print "</%s> is not real!" % name
            self.handle_data('</%s>' % name)
            return
        self.endData()
        self._popToTag(name)
        if self.quoteStack and self.quoteStack[-1] == name:
            self.quoteStack.pop()
            self.literal = (len(self.quoteStack) > 0)

    def handle_data(self, data):
        self.currentData.append(data)

    def handle_pi(self, text):
        "Propagate processing instructions right through."
        self.handle_data("<?%s>" % text)

    def handle_comment(self, text):
        "Propagate comments right through."
        self.handle_data("<!--%s-->" % text)

    def handle_charref(self, ref):
        "Propagate char refs right through."
        self.handle_data('&#%s;' % ref)

    def handle_entityref(self, ref):
        "Propagate entity refs right through."
        self.handle_data('&%s;' % ref)
        
    def handle_decl(self, data):
        "Propagate DOCTYPEs and the like right through."
        self.handle_data('<!%s>' % data)

    def parse_declaration(self, i):
        """Treat a bogus SGML declaration as raw data. Treat a CDATA
        declaration as regular data."""
        j = None
        if self.rawdata[i:i+9] == '<![CDATA[':
             k = self.rawdata.find(']]>', i)
             if k == -1:
                 k = len(self.rawdata)
             self.handle_data(self.rawdata[i+9:k])
             j = k+3
        else:
            try:
                j = SGMLParser.parse_declaration(self, i)
            except SGMLParseError:
                toHandle = self.rawdata[i:]
                self.handle_data(toHandle)
                j = i + len(toHandle)
        return j

class BeautifulSoup(BeautifulStoneSoup):

    """This parser knows the following facts about HTML:

    * Some tags have no closing tag and should be interpreted as being
      closed as soon as they are encountered.

    * The text inside some tags (ie. 'script') may contain tags which
      are not really part of the document and which should be parsed
      as text, not tags. If you want to parse the text as tags, you can
      always fetch it and parse it explicitly.

    * Tag nesting rules:

      Most tags can't be nested at all. For instance, the occurance of
      a <p> tag should implicitly close the previous <p> tag.

       <p>Para1<p>Para2
        should be transformed into:
       <p>Para1</p><p>Para2

      Some tags can be nested arbitrarily. For instance, the occurance
      of a <blockquote> tag should _not_ implicitly close the previous
      <blockquote> tag.

       Alice said: <blockquote>Bob said: <blockquote>Blah
        should NOT be transformed into:
       Alice said: <blockquote>Bob said: </blockquote><blockquote>Blah

      Some tags can be nested, but the nesting is reset by the
      interposition of other tags. For instance, a <tr> tag should
      implicitly close the previous <tr> tag within the same <table>,
      but not close a <tr> tag in another table.

       <table><tr>Blah<tr>Blah
        should be transformed into:
       <table><tr>Blah</tr><tr>Blah
        but,
       <tr>Blah<table><tr>Blah
        should NOT be transformed into
       <tr>Blah<table></tr><tr>Blah

    Differing assumptions about tag nesting rules are a major source
    of problems with the BeautifulSoup class. If BeautifulSoup is not
    treating as nestable a tag your page author treats as nestable,
    try ICantBelieveItsBeautifulSoup before writing your own
    subclass."""

    SELF_CLOSING_TAGS = buildTagMap(None, ['br' , 'hr', 'input', 'img', 'meta',
                                           'spacer', 'link', 'frame', 'base'])

    QUOTE_TAGS = {'script': None}
    
    #According to the HTML standard, each of these inline tags can
    #contain another tag of the same type. Furthermore, it's common
    #to actually use these tags this way.
    NESTABLE_INLINE_TAGS = ['span', 'font', 'q', 'object', 'bdo', 'sub', 'sup',
                            'center']

    #According to the HTML standard, these block tags can contain
    #another tag of the same type. Furthermore, it's common
    #to actually use these tags this way.
    NESTABLE_BLOCK_TAGS = ['blockquote', 'div', 'fieldset', 'ins', 'del']

    #Lists can contain other lists, but there are restrictions.    
    NESTABLE_LIST_TAGS = { 'ol' : [],
                           'ul' : [],
                           'li' : ['ul', 'ol'],
                           'dl' : [],
                           'dd' : ['dl'],
                           'dt' : ['dl'] }

    #Tables can contain other tables, but there are restrictions.    
    NESTABLE_TABLE_TAGS = {'table' : [], 
                           'tr' : ['table', 'tbody', 'tfoot', 'thead'],
                           'td' : ['tr'],
                           'th' : ['tr'],
                           }

    NON_NESTABLE_BLOCK_TAGS = ['address', 'form', 'p', 'pre']

    #If one of these tags is encountered, all tags up to the next tag of
    #this type are popped.
    RESET_NESTING_TAGS = buildTagMap(None, NESTABLE_BLOCK_TAGS, 'noscript',
                                     NON_NESTABLE_BLOCK_TAGS,
                                     NESTABLE_LIST_TAGS,
                                     NESTABLE_TABLE_TAGS)

    NESTABLE_TAGS = buildTagMap([], NESTABLE_INLINE_TAGS, NESTABLE_BLOCK_TAGS,
                                NESTABLE_LIST_TAGS, NESTABLE_TABLE_TAGS)
    
class ICantBelieveItsBeautifulSoup(BeautifulSoup):

    """The BeautifulSoup class is oriented towards skipping over
    common HTML errors like unclosed tags. However, sometimes it makes
    errors of its own. For instance, consider this fragment:

     <b>Foo<b>Bar</b></b>

    This is perfectly valid (if bizarre) HTML. However, the
    BeautifulSoup class will implicitly close the first b tag when it
    encounters the second 'b'. It will think the author wrote
    "<b>Foo<b>Bar", and didn't close the first 'b' tag, because
    there's no real-world reason to bold something that's already
    bold. When it encounters '</b></b>' it will close two more 'b'
    tags, for a grand total of three tags closed instead of two. This
    can throw off the rest of your document structure. The same is
    true of a number of other tags, listed below.

    It's much more common for someone to forget to close (eg.) a 'b'
    tag than to actually use nested 'b' tags, and the BeautifulSoup
    class handles the common case. This class handles the
    not-co-common case: where you can't believe someone wrote what
    they did, but it's valid HTML and BeautifulSoup screwed up by
    assuming it wouldn't be.

    If this doesn't do what you need, try subclassing this class or
    BeautifulSoup, and providing your own list of NESTABLE_TAGS."""

    I_CANT_BELIEVE_THEYRE_NESTABLE_INLINE_TAGS = \
     ['em', 'big', 'i', 'small', 'tt', 'abbr', 'acronym', 'strong',
      'cite', 'code', 'dfn', 'kbd', 'samp', 'strong', 'var', 'b',
      'big']

    I_CANT_BELIEVE_THEYRE_NESTABLE_BLOCK_TAGS = ['noscript']

    NESTABLE_TAGS = buildTagMap([], BeautifulSoup.NESTABLE_TAGS,
                                I_CANT_BELIEVE_THEYRE_NESTABLE_BLOCK_TAGS,
                                I_CANT_BELIEVE_THEYRE_NESTABLE_INLINE_TAGS)

class BeautifulSOAP(BeautifulStoneSoup):
    """This class will push a tag with only a single string child into
    the tag's parent as an attribute. The attribute's name is the tag
    name, and the value is the string child. An example should give
    the flavor of the change:

    <foo><bar>baz</bar></foo>
     =>
    <foo bar="baz"><bar>baz</bar></foo>

    You can then access fooTag['bar'] instead of fooTag.barTag.string.

    This is, of course, useful for scraping structures that tend to
    use subelements instead of attributes, such as SOAP messages. Note
    that it modifies its input, so don't print the modified version
    out.

    I'm not sure how many people really want to use this class; let me
    know if you do. Mainly I like the name."""

    def popTag(self):
        if len(self.tagStack) > 1:
            tag = self.tagStack[-1]
            parent = self.tagStack[-2]
            parent._getAttrMap()
            if (isinstance(tag, Tag) and len(tag.contents) == 1 and
                isinstance(tag.contents[0], NavigableText) and 
                not parent.attrMap.has_key(tag.name)):
                parent[tag.name] = tag.contents[0]
        BeautifulStoneSoup.popTag(self)

#Enterprise class names! It has come to our attention that some people
#think the names of the Beautiful Soup parser classes are too silly
#and "unprofessional" for use in enterprise screen-scraping. We feel
#your pain! For such-minded folk, the Beautiful Soup Consortium And
#All-Night Kosher Bakery recommends renaming this file to
#"RobustParser.py" (or, in cases of extreme enterprisitude,
#"RobustParserBeanInterface.class") and using the following
#enterprise-friendly class aliases:
class RobustXMLParser(BeautifulStoneSoup):
    pass
class RobustHTMLParser(BeautifulSoup):
    pass
class RobustWackAssHTMLParser(ICantBelieveItsBeautifulSoup):
    pass
class SimplifyingSOAPParser(BeautifulSOAP):
    pass

###


#By default, act as an HTML pretty-printer.
if __name__ == '__main__':
    import sys
    soup = BeautifulStoneSoup(sys.stdin.read())
    print soup.prettify()
