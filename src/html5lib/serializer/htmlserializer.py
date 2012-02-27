try:
    frozenset
except NameError:
    # Import from the sets module for python 2.3
    from sets import ImmutableSet as frozenset

import gettext
_ = gettext.gettext

from html5lib.constants import voidElements, booleanAttributes, spaceCharacters
from html5lib.constants import rcdataElements

from xml.sax.saxutils import escape

spaceCharacters = u"".join(spaceCharacters)

try:
    from codecs import register_error, xmlcharrefreplace_errors
except ImportError:
    unicode_encode_errors = "strict"
else:
    unicode_encode_errors = "htmlentityreplace"

    from html5lib.constants import entities

    encode_entity_map = {}
    for k, v in entities.items():
        if v != "&" and encode_entity_map.get(v) != k.lower():
            # prefer &lt; over &LT; and similarly for &amp;, &gt;, etc.
            encode_entity_map[v] = k

    def htmlentityreplace_errors(exc):
        if isinstance(exc, (UnicodeEncodeError, UnicodeTranslateError)):
            res = []
            for c in exc.object[exc.start:exc.end]:
                e = encode_entity_map.get(c)
                if e:
                    res.append("&")
                    res.append(e)
                    if not e.endswith(";"):
                        res.append(";")
                else:
                    res.append(c.encode(exc.encoding, "xmlcharrefreplace"))
            return (u"".join(res), exc.end)
        else:
            return xmlcharrefreplace_errors(exc)

    register_error(unicode_encode_errors, htmlentityreplace_errors)

    del register_error

def encode(text, encoding):
    return text.encode(encoding, unicode_encode_errors)

class HTMLSerializer(object):

    quote_attr_values = False
    quote_char = '"'
    use_best_quote_char = True
    minimize_boolean_attributes = True

    use_trailing_solidus = False
    space_before_trailing_solidus = True
    escape_lt_in_attrs = False
    escape_rcdata = False

    inject_meta_charset = True
    strip_whitespace = False
    sanitize = False
    omit_optional_tags = True

    options = ("quote_attr_values", "quote_char", "use_best_quote_char",
          "minimize_boolean_attributes", "use_trailing_solidus",
          "space_before_trailing_solidus", "omit_optional_tags",
          "strip_whitespace", "inject_meta_charset", "escape_lt_in_attrs",
          "escape_rcdata", 'use_trailing_solidus', "sanitize")

    def __init__(self, **kwargs):
        if kwargs.has_key('quote_char'):
            self.use_best_quote_char = False
        for attr in self.options:
            setattr(self, attr, kwargs.get(attr, getattr(self, attr)))
        self.errors = []
        self.strict = False

    def serialize(self, treewalker, encoding=None):
        in_cdata = False
        self.errors = []
        if encoding and self.inject_meta_charset:
            from html5lib.filters.inject_meta_charset import Filter
            treewalker = Filter(treewalker, encoding)
        # XXX: WhitespaceFilter should be used before OptionalTagFilter
        # for maximum efficiently of this latter filter
        if self.strip_whitespace:
            from html5lib.filters.whitespace import Filter
            treewalker = Filter(treewalker)
        if self.sanitize:
            from html5lib.filters.sanitizer import Filter
            treewalker = Filter(treewalker)
        if self.omit_optional_tags:
            from html5lib.filters.optionaltags import Filter
            treewalker = Filter(treewalker)
        for token in treewalker:
            type = token["type"]
            if type == "Doctype":
                doctype = u"<!DOCTYPE %s" % token["name"]
                
                if token["publicId"]:
                    doctype += u' PUBLIC "%s"' % token["publicId"]
                elif token["systemId"]:
                    doctype += u" SYSTEM"
                if token["systemId"]:                
                    if token["systemId"].find(u'"') >= 0:
                        if token["systemId"].find(u"'") >= 0:
                            self.serializeError(_("System identifer contains both single and double quote characters"))
                        quote_char = u"'"
                    else:
                        quote_char = u'"'
                    doctype += u" %s%s%s" % (quote_char, token["systemId"], quote_char)
                
                doctype += u">"
                
                if encoding:
                    yield doctype.encode(encoding)
                else:
                    yield doctype

            elif type in ("Characters", "SpaceCharacters"):
                if type == "SpaceCharacters" or in_cdata:
                    if in_cdata and token["data"].find("</") >= 0:
                        self.serializeError(_("Unexpected </ in CDATA"))
                    if encoding:
                        yield token["data"].encode(encoding, "strict")
                    else:
                        yield token["data"]
                elif encoding:
                    yield encode(escape(token["data"]), encoding)
                else:
                    yield escape(token["data"])

            elif type in ("StartTag", "EmptyTag"):
                name = token["name"]
                if name in rcdataElements and not self.escape_rcdata:
                    in_cdata = True
                elif in_cdata:
                    self.serializeError(_("Unexpected child element of a CDATA element"))
                attrs = token["data"]
                if hasattr(attrs, "items"):
                    attrs = attrs.items()
                attrs.sort()
                attributes = []
                for k,v in attrs:
                    if encoding:
                        k = k.encode(encoding, "strict")
                    attributes.append(' ')

                    attributes.append(k)
                    if not self.minimize_boolean_attributes or \
                      (k not in booleanAttributes.get(name, tuple()) \
                      and k not in booleanAttributes.get("", tuple())):
                        attributes.append("=")
                        if self.quote_attr_values or not v:
                            quote_attr = True
                        else:
                            quote_attr = reduce(lambda x,y: x or (y in v),
                                spaceCharacters + ">\"'=", False)
                        v = v.replace("&", "&amp;")
                        if self.escape_lt_in_attrs: v = v.replace("<", "&lt;")
                        if encoding:
                            v = encode(v, encoding)
                        if quote_attr:
                            quote_char = self.quote_char
                            if self.use_best_quote_char:
                                if "'" in v and '"' not in v:
                                    quote_char = '"'
                                elif '"' in v and "'" not in v:
                                    quote_char = "'"
                            if quote_char == "'":
                                v = v.replace("'", "&#39;")
                            else:
                                v = v.replace('"', "&quot;")
                            attributes.append(quote_char)
                            attributes.append(v)
                            attributes.append(quote_char)
                        else:
                            attributes.append(v)
                if name in voidElements and self.use_trailing_solidus:
                    if self.space_before_trailing_solidus:
                        attributes.append(" /")
                    else:
                        attributes.append("/")
                if encoding:
                    yield "<%s%s>" % (name.encode(encoding, "strict"), "".join(attributes))
                else:
                    yield u"<%s%s>" % (name, u"".join(attributes))

            elif type == "EndTag":
                name = token["name"]
                if name in rcdataElements:
                    in_cdata = False
                elif in_cdata:
                    self.serializeError(_("Unexpected child element of a CDATA element"))
                end_tag = u"</%s>" % name
                if encoding:
                    end_tag = end_tag.encode(encoding, "strict")
                yield end_tag

            elif type == "Comment":
                data = token["data"]
                if data.find("--") >= 0:
                    self.serializeError(_("Comment contains --"))
                comment = u"<!--%s-->" % token["data"]
                if encoding:
                    comment = comment.encode(encoding, unicode_encode_errors)
                yield comment

            else:
                self.serializeError(token["data"])

    def render(self, treewalker, encoding=None):
        if encoding:
            return "".join(list(self.serialize(treewalker, encoding)))
        else:
            return u"".join(list(self.serialize(treewalker)))

    def serializeError(self, data="XXX ERROR MESSAGE NEEDED"):
        # XXX The idea is to make data mandatory.
        self.errors.append(data)
        if self.strict:
            raise SerializeError

def SerializeError(Exception):
    """Error in serialized tree"""
    pass
