__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

"""
Microsoft LIT OPF tag and attribute tables, copied from ConvertLIT.
"""


TAGS = [
    None,
    "package",
    "dc:Title",
    "dc:Creator",
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    "manifest",
    "item",
    "spine",
    "itemref",
    "metadata",
    "dc-metadata",
    "dc:Subject",
    "dc:Description",
    "dc:Publisher",
    "dc:Contributor",
    "dc:Date",
    "dc:Type",
    "dc:Format",
    "dc:Identifier",
    "dc:Source",
    "dc:Language",
    "dc:Relation",
    "dc:Coverage",
    "dc:Rights",
    "x-metadata",
    "meta",
    "tours",
    "tour",
    "site",
    "guide",
    "reference",
    None,
   ]

ATTRS = {
    0x0001: "href",
    0x0002: "%never-used",
    0x0003: "%guid",
    0x0004: "%minimum_level",
    0x0005: "%attr5",
    0x0006: "id",
    0x0007: "href",
    0x0008: "media-type",
    0x0009: "fallback",
    0x000A: "idref",
    0x000B: "xmlns:dc",
    0x000C: "xmlns:oebpackage",
    0x000D: "role",
    0x000E: "file-as",
    0x000F: "event",
    0x0010: "scheme",
    0x0011: "title",
    0x0012: "type",
    0x0013: "unique-identifier",
    0x0014: "name",
    0x0015: "content",
    0x0016: "xml:lang",
    }

TAGS_ATTRS = [{} for i in range(43)]

MAP = (TAGS, ATTRS, TAGS_ATTRS)
