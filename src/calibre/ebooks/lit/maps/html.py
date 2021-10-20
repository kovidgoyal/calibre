__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

"""
Microsoft LIT HTML tag and attribute tables, copied from ConvertLIT.
"""

TAGS = [
    None,
    None,
    None,
    "a",
    "acronym",
    "address",
    "applet",
    "area",
    "b",
    "base",
    "basefont",
    "bdo",
    "bgsound",
    "big",
    "blink",
    "blockquote",
    "body",
    "br",
    "button",
    "caption",
    "center",
    "cite",
    "code",
    "col",
    "colgroup",
    None,
    None,
    "dd",
    "del",
    "dfn",
    "dir",
    "div",
    "dl",
    "dt",
    "em",
    "embed",
    "fieldset",
    "font",
    "form",
    "frame",
    "frameset",
    None,
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "head",
    "hr",
    "html",
    "i",
    "iframe",
    "img",
    "input",
    "ins",
    "kbd",
    "label",
    "legend",
    "li",
    "link",
    "tag61",
    "map",
    "tag63",
    "tag64",
    "meta",
    "nextid",
    "nobr",
    "noembed",
    "noframes",
    "noscript",
    "object",
    "ol",
    "option",
    "p",
    "param",
    "plaintext",
    "pre",
    "q",
    "rp",
    "rt",
    "ruby",
    "s",
    "samp",
    "script",
    "select",
    "small",
    "span",
    "strike",
    "strong",
    "style",
    "sub",
    "sup",
    "table",
    "tbody",
    "tc",
    "td",
    "textarea",
    "tfoot",
    "th",
    "thead",
    "title",
    "tr",
    "tt",
    "u",
    "ul",
    "var",
    "wbr",
    None,
    ]

ATTRS0 = {
    0x8010: "tabindex",
    0x8046: "title",
    0x804b: "style",
    0x804d: "disabled",
    0x83ea: "class",
    0x83eb: "id",
    0x83fe: "datafld",
    0x83ff: "datasrc",
    0x8400: "dataformatas",
    0x87d6: "accesskey",
    0x9392: "lang",
    0x93ed: "language",
    0x93fe: "dir",
    0x9771: "onmouseover",
    0x9772: "onmouseout",
    0x9773: "onmousedown",
    0x9774: "onmouseup",
    0x9775: "onmousemove",
    0x9776: "onkeydown",
    0x9777: "onkeyup",
    0x9778: "onkeypress",
    0x9779: "onclick",
    0x977a: "ondblclick",
    0x977e: "onhelp",
    0x977f: "onfocus",
    0x9780: "onblur",
    0x9783: "onrowexit",
    0x9784: "onrowenter",
    0x9786: "onbeforeupdate",
    0x9787: "onafterupdate",
    0x978a: "onreadystatechange",
    0x9790: "onscroll",
    0x9794: "ondragstart",
    0x9795: "onresize",
    0x9796: "onselectstart",
    0x9797: "onerrorupdate",
    0x9799: "ondatasetchanged",
    0x979a: "ondataavailable",
    0x979b: "ondatasetcomplete",
    0x979c: "onfilterchange",
    0x979f: "onlosecapture",
    0x97a0: "onpropertychange",
    0x97a2: "ondrag",
    0x97a3: "ondragend",
    0x97a4: "ondragenter",
    0x97a5: "ondragover",
    0x97a6: "ondragleave",
    0x97a7: "ondrop",
    0x97a8: "oncut",
    0x97a9: "oncopy",
    0x97aa: "onpaste",
    0x97ab: "onbeforecut",
    0x97ac: "onbeforecopy",
    0x97ad: "onbeforepaste",
    0x97af: "onrowsdelete",
    0x97b0: "onrowsinserted",
    0x97b1: "oncellchange",
    0x97b2: "oncontextmenu",
    0x97b6: "onbeforeeditfocus",
    }
ATTRS3 = {
    0x0001: "href",
    0x03ec: "target",
    0x03ee: "rel",
    0x03ef: "rev",
    0x03f0: "urn",
    0x03f1: "methods",
    0x8001: "name",
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS5 = {
    0x9399: "clear",
    }
ATTRS6 = {
    0x8001: "name",
    0x8006: "width",
    0x8007: "height",
    0x804a: "align",
    0x8bbb: "classid",
    0x8bbc: "data",
    0x8bbf: "codebase",
    0x8bc0: "codetype",
    0x8bc1: "code",
    0x8bc2: "type",
    0x8bc5: "vspace",
    0x8bc6: "hspace",
    0x978e: "onerror",
    }
ATTRS7 = {
    0x0001: "href",
    0x03ea: "shape",
    0x03eb: "coords",
    0x03ed: "target",
    0x03ee: "alt",
    0x03ef: "nohref",
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS8 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS9 = {
    0x03ec: "href",
    0x03ed: "target",
    }
ATTRS10 = {
    0x938b: "color",
    0x939b: "face",
    0x93a3: "size",
    }
ATTRS12 = {
    0x03ea: "src",
    0x03eb: "loop",
    0x03ec: "volume",
    0x03ed: "balance",
    }
ATTRS13 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS15 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x9399: "clear",
    }
ATTRS16 = {
    0x07db: "link",
    0x07dc: "alink",
    0x07dd: "vlink",
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x938a: "background",
    0x938b: "text",
    0x938e: "nowrap",
    0x93ae: "topmargin",
    0x93af: "rightmargin",
    0x93b0: "bottommargin",
    0x93b1: "leftmargin",
    0x93b6: "bgproperties",
    0x93d8: "scroll",
    0x977b: "onselect",
    0x9791: "onload",
    0x9792: "onunload",
    0x9798: "onbeforeunload",
    0x97b3: "onbeforeprint",
    0x97b4: "onafterprint",
    0xfe0c: "bgcolor",
    }
ATTRS17 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x9399: "clear",
    }
ATTRS18 = {
    0x07d1: "type",
    0x8001: "name",
    }
ATTRS19 = {
    0x8046: "title",
    0x8049: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x93a8: "valign",
    }
ATTRS20 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x9399: "clear",
    }
ATTRS21 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS22 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS23 = {
    0x03ea: "span",
    0x8006: "width",
    0x8049: "align",
    0x93a8: "valign",
    0xfe0c: "bgcolor",
    }
ATTRS24 = {
    0x03ea: "span",
    0x8006: "width",
    0x8049: "align",
    0x93a8: "valign",
    0xfe0c: "bgcolor",
    }
ATTRS27 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x938e: "nowrap",
    }
ATTRS29 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS31 = {
    0x8046: "title",
    0x8049: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x938e: "nowrap",
    }
ATTRS32 = {
    0x03ea: "compact",
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS33 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x938e: "nowrap",
    }
ATTRS34 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS35 = {
    0x8001: "name",
    0x8006: "width",
    0x8007: "height",
    0x804a: "align",
    0x8bbd: "palette",
    0x8bbe: "pluginspage",
    # 0x8bbf: "codebase",
    0x8bbf: "src",
    0x8bc1: "units",
    0x8bc2: "type",
    0x8bc3: "hidden",
    }
ATTRS36 = {
    0x804a: "align",
    }
ATTRS37 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x938b: "color",
    0x939b: "face",
    0x939c: "size",
    }
ATTRS38 = {
    0x03ea: "action",
    0x03ec: "enctype",
    0x03ed: "method",
    0x03ef: "target",
    0x03f4: "accept-charset",
    0x8001: "name",
    0x977c: "onsubmit",
    0x977d: "onreset",
    }
ATTRS39 = {
    0x8000: "align",
    0x8001: "name",
    0x8bb9: "src",
    0x8bbb: "border",
    0x8bbc: "frameborder",
    0x8bbd: "framespacing",
    0x8bbe: "marginwidth",
    0x8bbf: "marginheight",
    0x8bc0: "noresize",
    0x8bc1: "scrolling",
    0x8fa2: "bordercolor",
    }
ATTRS40 = {
    0x03e9: "rows",
    0x03ea: "cols",
    0x03eb: "border",
    0x03ec: "bordercolor",
    0x03ed: "frameborder",
    0x03ee: "framespacing",
    0x8001: "name",
    0x9791: "onload",
    0x9792: "onunload",
    0x9798: "onbeforeunload",
    0x97b3: "onbeforeprint",
    0x97b4: "onafterprint",
    }
ATTRS42 = {
    0x8046: "title",
    0x8049: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x9399: "clear",
    }
ATTRS43 = {
    0x8046: "title",
    0x8049: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x9399: "clear",
    }
ATTRS44 = {
    0x8046: "title",
    0x8049: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x9399: "clear",
    }
ATTRS45 = {
    0x8046: "title",
    0x8049: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x9399: "clear",
    }
ATTRS46 = {
    0x8046: "title",
    0x8049: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x9399: "clear",
    }
ATTRS47 = {
    0x8046: "title",
    0x8049: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x9399: "clear",
    }
ATTRS49 = {
    0x03ea: "noshade",
    0x8006: "width",
    0x8007: "size",
    0x8046: "title",
    0x8049: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x938b: "color",
    }
ATTRS51 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS52 = {
    0x8001: "name",
    0x8006: "width",
    0x8007: "height",
    0x804a: "align",
    0x8bb9: "src",
    0x8bbb: "border",
    0x8bbc: "frameborder",
    0x8bbd: "framespacing",
    0x8bbe: "marginwidth",
    0x8bbf: "marginheight",
    0x8bc0: "noresize",
    0x8bc1: "scrolling",
    0x8fa2: "vspace",
    0x8fa3: "hspace",
    }
ATTRS53 = {
    0x03eb: "alt",
    0x03ec: "src",
    0x03ed: "border",
    0x03ee: "vspace",
    0x03ef: "hspace",
    0x03f0: "lowsrc",
    0x03f1: "vrml",
    0x03f2: "dynsrc",
    0x03f4: "loop",
    0x03f6: "start",
    0x07d3: "ismap",
    0x07d9: "usemap",
    0x8001: "name",
    0x8006: "width",
    0x8007: "height",
    0x8046: "title",
    0x804a: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x978d: "onabort",
    0x978e: "onerror",
    0x9791: "onload",
    }
ATTRS54 = {
    0x07d1: "type",
    0x07d3: "size",
    0x07d4: "maxlength",
    0x07d6: "readonly",
    0x07d8: "indeterminate",
    0x07da: "checked",
    0x07db: "alt",
    0x07dc: "src",
    0x07dd: "border",
    0x07de: "vspace",
    0x07df: "hspace",
    0x07e0: "lowsrc",
    0x07e1: "vrml",
    0x07e2: "dynsrc",
    0x07e4: "loop",
    0x07e5: "start",
    0x8001: "name",
    0x8006: "width",
    0x8007: "height",
    0x804a: "align",
    0x93ee: "value",
    0x977b: "onselect",
    0x978d: "onabort",
    0x978e: "onerror",
    0x978f: "onchange",
    0x9791: "onload",
    }
ATTRS56 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS57 = {
    0x03e9: "for",
    }
ATTRS58 = {
    0x804a: "align",
    }
ATTRS59 = {
    0x03ea: "value",
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x939a: "type",
    }
ATTRS60 = {
    0x03ee: "href",
    0x03ef: "rel",
    0x03f0: "rev",
    0x03f1: "type",
    0x03f9: "media",
    0x03fa: "target",
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x978e: "onerror",
    0x9791: "onload",
    }
ATTRS61 = {
    0x9399: "clear",
    }
ATTRS62 = {
    0x8001: "name",
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS63 = {
    0x1771: "scrolldelay",
    0x1772: "direction",
    0x1773: "behavior",
    0x1774: "scrollamount",
    0x1775: "loop",
    0x1776: "vspace",
    0x1777: "hspace",
    0x1778: "truespeed",
    0x8006: "width",
    0x8007: "height",
    0x9785: "onbounce",
    0x978b: "onfinish",
    0x978c: "onstart",
    0xfe0c: "bgcolor",
    }
ATTRS65 = {
    0x03ea: "http-equiv",
    0x03eb: "content",
    0x03ec: "url",
    0x03f6: "charset",
    0x8001: "name",
    }
ATTRS66 = {
    0x03f5: "n",
    }
ATTRS71 = {
    # 0x8000: "border",
    0x8000: "usemap",
    0x8001: "name",
    0x8006: "width",
    0x8007: "height",
    0x8046: "title",
    0x804a: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x8bbb: "classid",
    0x8bbc: "data",
    0x8bbf: "codebase",
    0x8bc0: "codetype",
    0x8bc1: "code",
    0x8bc2: "type",
    0x8bc5: "vspace",
    0x8bc6: "hspace",
    0x978e: "onerror",
    }
ATTRS72 = {
    0x03eb: "compact",
    0x03ec: "start",
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x939a: "type",
    }
ATTRS73 = {
    0x03ea: "selected",
    0x03eb: "value",
    }
ATTRS74 = {
    0x8046: "title",
    0x8049: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x9399: "clear",
    }
ATTRS75 = {
    # 0x8000: "name",
    # 0x8000: "value",
    0x8000: "type",
    }
ATTRS76 = {
    0x9399: "clear",
    }
ATTRS77 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x9399: "clear",
    }
ATTRS78 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS82 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS83 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS84 = {
    0x03ea: "src",
    0x03ed: "for",
    0x03ee: "event",
    0x03f0: "defer",
    0x03f2: "type",
    0x978e: "onerror",
    }
ATTRS85 = {
    0x03eb: "size",
    0x03ec: "multiple",
    0x8000: "align",
    0x8001: "name",
    0x978f: "onchange",
    }
ATTRS86 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS87 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS88 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS89 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS90 = {
    0x03eb: "type",
    0x03ef: "media",
    0x8046: "title",
    0x978e: "onerror",
    0x9791: "onload",
    }
ATTRS91 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS92 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS93 = {
    0x03ea: "cols",
    0x03eb: "border",
    0x03ec: "rules",
    0x03ed: "frame",
    0x03ee: "cellspacing",
    0x03ef: "cellpadding",
    0x03fa: "datapagesize",
    0x8006: "width",
    0x8007: "height",
    0x8046: "title",
    0x804a: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x938a: "background",
    0x93a5: "bordercolor",
    0x93a6: "bordercolorlight",
    0x93a7: "bordercolordark",
    0xfe0c: "bgcolor",
    }
ATTRS94 = {
    0x8049: "align",
    0x93a8: "valign",
    0xfe0c: "bgcolor",
    }
ATTRS95 = {
    0x8049: "align",
    0x93a8: "valign",
    }
ATTRS96 = {
    0x07d2: "rowspan",
    0x07d3: "colspan",
    0x8006: "width",
    0x8007: "height",
    0x8046: "title",
    0x8049: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x938a: "background",
    0x938e: "nowrap",
    0x93a5: "bordercolor",
    0x93a6: "bordercolorlight",
    0x93a7: "bordercolordark",
    0x93a8: "valign",
    0xfe0c: "bgcolor",
    }
ATTRS97 = {
    0x1b5a: "rows",
    0x1b5b: "cols",
    0x1b5c: "wrap",
    0x1b5d: "readonly",
    0x8001: "name",
    0x977b: "onselect",
    0x978f: "onchange",
    }
ATTRS98 = {
    0x8049: "align",
    0x93a8: "valign",
    0xfe0c: "bgcolor",
    }
ATTRS99 = {
    0x07d2: "rowspan",
    0x07d3: "colspan",
    0x8006: "width",
    0x8007: "height",
    0x8046: "title",
    0x8049: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x938a: "background",
    0x938e: "nowrap",
    0x93a5: "bordercolor",
    0x93a6: "bordercolorlight",
    0x93a7: "bordercolordark",
    0x93a8: "valign",
    0xfe0c: "bgcolor",
    }
ATTRS100 = {
    0x8049: "align",
    0x93a8: "valign",
    0xfe0c: "bgcolor",
    }
ATTRS102 = {
    0x8007: "height",
    0x8046: "title",
    0x8049: "align",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x93a5: "bordercolor",
    0x93a6: "bordercolorlight",
    0x93a7: "bordercolordark",
    0x93a8: "valign",
    0xfe0c: "bgcolor",
    }
ATTRS103 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS104 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS105 = {
    0x03eb: "compact",
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    0x939a: "type",
    }
ATTRS106 = {
    0x8046: "title",
    0x804b: "style",
    0x83ea: "class",
    0x83eb: "id",
    }
ATTRS108 = {
    0x9399: "clear",
    }

TAGS_ATTRS = [
    None,
    None,
    None,
    ATTRS3,   # a
    None,     # acronym
    ATTRS5,   # address
    ATTRS6,   # applet
    ATTRS7,   # area
    ATTRS8,   # b
    ATTRS9,   # base
    ATTRS10,  # basefont
    None,     # bdo
    ATTRS12,  # bgsound
    ATTRS13,  # big
    None,     # blink
    ATTRS15,  # blockquote
    ATTRS16,  # body
    ATTRS17,  # br
    ATTRS18,  # button
    ATTRS19,  # caption
    ATTRS20,  # center
    ATTRS21,  # cite
    ATTRS22,  # code
    ATTRS23,  # col
    ATTRS24,  # colgroup
    None,
    None,
    ATTRS27,  # dd
    None,     # del
    ATTRS29,  # dfn
    None,     # dir
    ATTRS31,  # div
    ATTRS32,  # dl
    ATTRS33,  # dt
    ATTRS34,  # em
    ATTRS35,  # embed
    ATTRS36,  # fieldset
    ATTRS37,  # font
    ATTRS38,  # form
    ATTRS39,  # frame
    ATTRS40,  # frameset
    None,
    ATTRS42,  # h1
    ATTRS43,  # h2
    ATTRS44,  # h3
    ATTRS45,  # h4
    ATTRS46,  # h5
    ATTRS47,  # h6
    None,     # head
    ATTRS49,  # hr
    None,     # html
    ATTRS51,  # i
    ATTRS52,  # iframe
    ATTRS53,  # img
    ATTRS54,  # input
    None,     # ins
    ATTRS56,  # kbd
    ATTRS57,  # label
    ATTRS58,  # legend
    ATTRS59,  # li
    ATTRS60,  # link
    ATTRS61,  # tag61
    ATTRS62,  # map
    ATTRS63,  # tag63
    None,     # tag64
    ATTRS65,  # meta
    ATTRS66,  # nextid
    None,     # nobr
    None,     # noembed
    None,     # noframes
    None,     # noscript
    ATTRS71,  # object
    ATTRS72,  # ol
    ATTRS73,  # option
    ATTRS74,  # p
    ATTRS75,  # param
    ATTRS76,  # plaintext
    ATTRS77,  # pre
    ATTRS78,  # q
    None,     # rp
    None,     # rt
    None,     # ruby
    ATTRS82,  # s
    ATTRS83,  # samp
    ATTRS84,  # script
    ATTRS85,  # select
    ATTRS86,  # small
    ATTRS87,  # span
    ATTRS88,  # strike
    ATTRS89,  # strong
    ATTRS90,  # style
    ATTRS91,  # sub
    ATTRS92,  # sup
    ATTRS93,  # table
    ATTRS94,  # tbody
    ATTRS95,  # tc
    ATTRS96,  # td
    ATTRS97,  # textarea
    ATTRS98,  # tfoot
    ATTRS99,  # th
    ATTRS100,  # thead
    None,     # title
    ATTRS102,  # tr
    ATTRS103,  # tt
    ATTRS104,  # u
    ATTRS105,  # ul
    ATTRS106,  # var
    None,     # wbr
    None,
    ]

MAP = (TAGS, ATTRS0, TAGS_ATTRS)
