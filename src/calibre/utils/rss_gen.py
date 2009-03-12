"""PyRSS2Gen - A Python library for generating RSS 2.0 feeds."""

__name__ = "PyRSS2Gen"
__version__ = (1, 0, 0)
__author__ = "Andrew Dalke <dalke@dalkescientific.com>"

_generator_name = __name__ + "-" + ".".join(map(str, __version__))

import datetime

# Could make this the base class; will need to add 'publish'
class WriteXmlMixin:
    def write_xml(self, outfile, encoding = "iso-8859-1"):
        from xml.sax import saxutils
        handler = saxutils.XMLGenerator(outfile, encoding)
        handler.startDocument()
        self.publish(handler)
        handler.endDocument()

    def to_xml(self, encoding = "iso-8859-1"):
        try:
            import cStringIO as StringIO
        except ImportError:
            import StringIO
        f = StringIO.StringIO()
        self.write_xml(f, encoding)
        return f.getvalue()


def _element(handler, name, obj, d = {}):
    if isinstance(obj, basestring) or obj is None:
        # special-case handling to make the API easier
        # to use for the common case.
        handler.startElement(name, d)
        if obj is not None:
            handler.characters(obj)
        handler.endElement(name)
    else:
        # It better know how to emit the correct XML.
        obj.publish(handler)

def _opt_element(handler, name, obj):
    if obj is None:
        return
    _element(handler, name, obj)


def _format_date(dt):
    """convert a datetime into an RFC 822 formatted date

    Input date must be in GMT.
    """
    # Looks like:
    #   Sat, 07 Sep 2002 00:00:01 GMT
    # Can't use strftime because that's locale dependent
    #
    # Isn't there a standard way to do this for Python?  The
    # rfc822 and email.Utils modules assume a timestamp.  The
    # following is based on the rfc822 module.
    return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (
            ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dt.weekday()],
            dt.day,
            ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][dt.month-1],
            dt.year, dt.hour, dt.minute, dt.second)

        
##
# A couple simple wrapper objects for the fields which
# take a simple value other than a string.
class IntElement:
    """implements the 'publish' API for integers

    Takes the tag name and the integer value to publish.
    
    (Could be used for anything which uses str() to be published
    to text for XML.)
    """
    element_attrs = {}
    def __init__(self, name, val):
        self.name = name
        self.val = val
    def publish(self, handler):
        handler.startElement(self.name, self.element_attrs)
        handler.characters(str(self.val))
        handler.endElement(self.name)

class DateElement:
    """implements the 'publish' API for a datetime.datetime

    Takes the tag name and the datetime to publish.

    Converts the datetime to RFC 2822 timestamp (4-digit year).
    """
    def __init__(self, name, dt):
        self.name = name
        self.dt = dt
    def publish(self, handler):
        _element(handler, self.name, _format_date(self.dt))
####

class Category:
    """Publish a category element"""
    def __init__(self, category, domain = None):
        self.category = category
        self.domain = domain
    def publish(self, handler):
        d = {}
        if self.domain is not None:
            d["domain"] = self.domain
        _element(handler, "category", self.category, d)

class Cloud:
    """Publish a cloud"""
    def __init__(self, domain, port, path,
                 registerProcedure, protocol):
        self.domain = domain
        self.port = port
        self.path = path
        self.registerProcedure = registerProcedure
        self.protocol = protocol
    def publish(self, handler):
        _element(handler, "cloud", None, {
            "domain": self.domain,
            "port": str(self.port),
            "path": self.path,
            "registerProcedure": self.registerProcedure,
            "protocol": self.protocol})

class Image:
    """Publish a channel Image"""
    element_attrs = {}
    def __init__(self, url, title, link,
                 width = None, height = None, description = None):
        self.url = url
        self.title = title
        self.link = link
        self.width = width
        self.height = height
        self.description = description
        
    def publish(self, handler):
        handler.startElement("image", self.element_attrs)

        _element(handler, "url", self.url)
        _element(handler, "title", self.title)
        _element(handler, "link", self.link)

        width = self.width
        if isinstance(width, int):
            width = IntElement("width", width)
        _opt_element(handler, "width", width)
        
        height = self.height
        if isinstance(height, int):
            height = IntElement("height", height)
        _opt_element(handler, "height", height)

        _opt_element(handler, "description", self.description)

        handler.endElement("image")

class Guid:
    """Publish a guid

    Defaults to being a permalink, which is the assumption if it's
    omitted.  Hence strings are always permalinks.
    """
    def __init__(self, guid, isPermaLink = 1):
        self.guid = guid
        self.isPermaLink = isPermaLink
    def publish(self, handler):
        d = {}
        if self.isPermaLink:
            d["isPermaLink"] = "true"
        else:
            d["isPermaLink"] = "false"
        _element(handler, "guid", self.guid, d)

class TextInput:
    """Publish a textInput

    Apparently this is rarely used.
    """
    element_attrs = {}
    def __init__(self, title, description, name, link):
        self.title = title
        self.description = description
        self.name = name
        self.link = link

    def publish(self, handler):
        handler.startElement("textInput", self.element_attrs)
        _element(handler, "title", self.title)
        _element(handler, "description", self.description)
        _element(handler, "name", self.name)
        _element(handler, "link", self.link)
        handler.endElement("textInput")
        

class Enclosure:
    """Publish an enclosure"""
    def __init__(self, url, length, type):
        self.url = url
        self.length = length
        self.type = type
    def publish(self, handler):
        _element(handler, "enclosure", None,
                 {"url": self.url,
                  "length": str(self.length),
                  "type": self.type,
                  })

class Source:
    """Publish the item's original source, used by aggregators"""
    def __init__(self, name, url):
        self.name = name
        self.url = url
    def publish(self, handler):
        _element(handler, "source", self.name, {"url": self.url})

class SkipHours:
    """Publish the skipHours

    This takes a list of hours, as integers.
    """
    element_attrs = {}
    def __init__(self, hours):
        self.hours = hours
    def publish(self, handler):
        if self.hours:
            handler.startElement("skipHours", self.element_attrs)
            for hour in self.hours:
                _element(handler, "hour", str(hour))
            handler.endElement("skipHours")

class SkipDays:
    """Publish the skipDays

    This takes a list of days as strings.
    """
    element_attrs = {}
    def __init__(self, days):
        self.days = days
    def publish(self, handler):
        if self.days:
            handler.startElement("skipDays", self.element_attrs)
            for day in self.days:
                _element(handler, "day", day)
            handler.endElement("skipDays")

class RSS2(WriteXmlMixin):
    """The main RSS class.

    Stores the channel attributes, with the "category" elements under
    ".categories" and the RSS items under ".items".
    """
    
    rss_attrs = {"version": "2.0"}
    element_attrs = {}
    def __init__(self,
                 title,
                 link,
                 description,

                 language = None,
                 copyright = None,
                 managingEditor = None,
                 webMaster = None,
                 pubDate = None,  # a datetime, *in* *GMT*
                 lastBuildDate = None, # a datetime
                 
                 categories = None, # list of strings or Category
                 generator = _generator_name,
                 docs = "http://blogs.law.harvard.edu/tech/rss",
                 cloud = None,    # a Cloud
                 ttl = None,      # integer number of minutes

                 image = None,     # an Image
                 rating = None,    # a string; I don't know how it's used
                 textInput = None, # a TextInput
                 skipHours = None, # a SkipHours with a list of integers
                 skipDays = None,  # a SkipDays with a list of strings

                 items = None,     # list of RSSItems
                 ):
        self.title = title
        self.link = link
        self.description = description
        self.language = language
        self.copyright = copyright
        self.managingEditor = managingEditor

        self.webMaster = webMaster
        self.pubDate = pubDate
        self.lastBuildDate = lastBuildDate
        
        if categories is None:
            categories = []
        self.categories = categories
        self.generator = generator
        self.docs = docs
        self.cloud = cloud
        self.ttl = ttl
        self.image = image
        self.rating = rating
        self.textInput = textInput
        self.skipHours = skipHours
        self.skipDays = skipDays

        if items is None:
            items = []
        self.items = items

    def publish(self, handler):
        handler.startElement("rss", self.rss_attrs)
        handler.startElement("channel", self.element_attrs)
        _element(handler, "title", self.title)
        _element(handler, "link", self.link)
        _element(handler, "description", self.description)

        self.publish_extensions(handler)
        
        _opt_element(handler, "language", self.language)
        _opt_element(handler, "copyright", self.copyright)
        _opt_element(handler, "managingEditor", self.managingEditor)
        _opt_element(handler, "webMaster", self.webMaster)

        pubDate = self.pubDate
        if isinstance(pubDate, datetime.datetime):
            pubDate = DateElement("pubDate", pubDate)
        _opt_element(handler, "pubDate", pubDate)

        lastBuildDate = self.lastBuildDate
        if isinstance(lastBuildDate, datetime.datetime):
            lastBuildDate = DateElement("lastBuildDate", lastBuildDate)
        _opt_element(handler, "lastBuildDate", lastBuildDate)

        for category in self.categories:
            if isinstance(category, basestring):
                category = Category(category)
            category.publish(handler)

        _opt_element(handler, "generator", self.generator)
        _opt_element(handler, "docs", self.docs)

        if self.cloud is not None:
            self.cloud.publish(handler)

        ttl = self.ttl
        if isinstance(self.ttl, int):
            ttl = IntElement("ttl", ttl)
        _opt_element(handler, "tt", ttl)

        if self.image is not None:
            self.image.publish(handler)

        _opt_element(handler, "rating", self.rating)
        if self.textInput is not None:
            self.textInput.publish(handler)
        if self.skipHours is not None:
            self.skipHours.publish(handler)
        if self.skipDays is not None:
            self.skipDays.publish(handler)

        for item in self.items:
            item.publish(handler)

        handler.endElement("channel")
        handler.endElement("rss")

    def publish_extensions(self, handler):
        # Derived classes can hook into this to insert
        # output after the three required fields.
        pass

    
    
class RSSItem(WriteXmlMixin):
    """Publish an RSS Item"""
    element_attrs = {}
    def __init__(self,
                 title = None,  # string
                 link = None,   # url as string
                 description = None, # string
                 author = None,      # email address as string
                 categories = None,  # list of string or Category
                 comments = None,  # url as string
                 enclosure = None, # an Enclosure
                 guid = None,    # a unique string
                 pubDate = None, # a datetime
                 source = None,  # a Source
                 ):
        
        if title is None and description is None:
            raise TypeError(
                "must define at least one of 'title' or 'description'")
        self.title = title
        self.link = link
        self.description = description
        self.author = author
        if categories is None:
            categories = []
        self.categories = categories
        self.comments = comments
        self.enclosure = enclosure
        self.guid = guid
        self.pubDate = pubDate
        self.source = source
        # It sure does get tedious typing these names three times...

    def publish(self, handler):
        handler.startElement("item", self.element_attrs)
        _opt_element(handler, "title", self.title)
        _opt_element(handler, "link", self.link)
        self.publish_extensions(handler)
        _opt_element(handler, "description", self.description)
        _opt_element(handler, "author", self.author)

        for category in self.categories:
            if isinstance(category, basestring):
                category = Category(category)
            category.publish(handler)
        
        _opt_element(handler, "comments", self.comments)
        if self.enclosure is not None:
            self.enclosure.publish(handler)
        _opt_element(handler, "guid", self.guid)

        pubDate = self.pubDate
        if isinstance(pubDate, datetime.datetime):
            pubDate = DateElement("pubDate", pubDate)
        _opt_element(handler, "pubDate", pubDate)

        if self.source is not None:
            self.source.publish(handler)
        
        handler.endElement("item")

    def publish_extensions(self, handler):
        # Derived classes can hook into this to insert
        # output after the title and link elements
        pass
