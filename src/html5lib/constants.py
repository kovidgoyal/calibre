import string, gettext
_ = gettext.gettext

try:
    frozenset
except NameError:
    # Import from the sets module for python 2.3
    from sets import Set as set
    from sets import ImmutableSet as frozenset

EOF = None

E = {
    "null-character": 
       _(u"Null character in input stream, replaced with U+FFFD."),
    "invalid-character": 
       _(u"Invalid codepoint in stream."),
    "incorrectly-placed-solidus":
       _(u"Solidus (/) incorrectly placed in tag."),
    "incorrect-cr-newline-entity":
       _(u"Incorrect CR newline entity, replaced with LF."),
    "illegal-windows-1252-entity":
       _(u"Entity used with illegal number (windows-1252 reference)."),
    "cant-convert-numeric-entity":
       _(u"Numeric entity couldn't be converted to character "
         u"(codepoint U+%(charAsInt)08x)."),
    "illegal-codepoint-for-numeric-entity":
       _(u"Numeric entity represents an illegal codepoint: "
         u"U+%(charAsInt)08x."),
    "numeric-entity-without-semicolon":
       _(u"Numeric entity didn't end with ';'."),
    "expected-numeric-entity-but-got-eof":
       _(u"Numeric entity expected. Got end of file instead."),
    "expected-numeric-entity":
       _(u"Numeric entity expected but none found."),
    "named-entity-without-semicolon":
       _(u"Named entity didn't end with ';'."),
    "expected-named-entity":
       _(u"Named entity expected. Got none."),
    "attributes-in-end-tag":
       _(u"End tag contains unexpected attributes."),
    "expected-tag-name-but-got-right-bracket":
       _(u"Expected tag name. Got '>' instead."),
    "expected-tag-name-but-got-question-mark":
       _(u"Expected tag name. Got '?' instead. (HTML doesn't "
         u"support processing instructions.)"),
    "expected-tag-name":
       _(u"Expected tag name. Got something else instead"),
    "expected-closing-tag-but-got-right-bracket":
       _(u"Expected closing tag. Got '>' instead. Ignoring '</>'."),
    "expected-closing-tag-but-got-eof":
       _(u"Expected closing tag. Unexpected end of file."),
    "expected-closing-tag-but-got-char":
       _(u"Expected closing tag. Unexpected character '%(data)s' found."),
    "eof-in-tag-name":
       _(u"Unexpected end of file in the tag name."),
    "expected-attribute-name-but-got-eof":
       _(u"Unexpected end of file. Expected attribute name instead."),
    "eof-in-attribute-name":
       _(u"Unexpected end of file in attribute name."),
    "invalid-character-in-attribute-name":
        _(u"Invalid chracter in attribute name"),
    "duplicate-attribute":
       _(u"Dropped duplicate attribute on tag."),
    "expected-end-of-tag-name-but-got-eof":
       _(u"Unexpected end of file. Expected = or end of tag."),
    "expected-attribute-value-but-got-eof":
       _(u"Unexpected end of file. Expected attribute value."),
    "expected-attribute-value-but-got-right-bracket":
       _(u"Expected attribute value. Got '>' instead."),
    "eof-in-attribute-value-double-quote":
       _(u"Unexpected end of file in attribute value (\")."),
    "eof-in-attribute-value-single-quote":
       _(u"Unexpected end of file in attribute value (')."),
    "eof-in-attribute-value-no-quotes":
       _(u"Unexpected end of file in attribute value."),
    "unexpected-EOF-after-solidus-in-tag":
        _(u"Unexpected end of file in tag. Expected >"),
    "unexpected-character-after-soldius-in-tag":
        _(u"Unexpected character after / in tag. Expected >"),
    "expected-dashes-or-doctype":
       _(u"Expected '--' or 'DOCTYPE'. Not found."),
    "incorrect-comment":
       _(u"Incorrect comment."),
    "eof-in-comment":
       _(u"Unexpected end of file in comment."),
    "eof-in-comment-end-dash":
       _(u"Unexpected end of file in comment (-)"),
    "unexpected-dash-after-double-dash-in-comment":
       _(u"Unexpected '-' after '--' found in comment."),
    "eof-in-comment-double-dash":
       _(u"Unexpected end of file in comment (--)."),
    "unexpected-char-in-comment":
       _(u"Unexpected character in comment found."),
    "need-space-after-doctype":
       _(u"No space after literal string 'DOCTYPE'."),
    "expected-doctype-name-but-got-right-bracket":
       _(u"Unexpected > character. Expected DOCTYPE name."),
    "expected-doctype-name-but-got-eof":
       _(u"Unexpected end of file. Expected DOCTYPE name."),
    "eof-in-doctype-name":
       _(u"Unexpected end of file in DOCTYPE name."),
    "eof-in-doctype":
       _(u"Unexpected end of file in DOCTYPE."),
    "expected-space-or-right-bracket-in-doctype":
       _(u"Expected space or '>'. Got '%(data)s'"),
    "unexpected-end-of-doctype":
       _(u"Unexpected end of DOCTYPE."),
    "unexpected-char-in-doctype":
       _(u"Unexpected character in DOCTYPE."),
    "eof-in-innerhtml":
       _(u"XXX innerHTML EOF"),
    "unexpected-doctype":
       _(u"Unexpected DOCTYPE. Ignored."),
    "non-html-root":
       _(u"html needs to be the first start tag."),
    "expected-doctype-but-got-eof":
       _(u"Unexpected End of file. Expected DOCTYPE."),
    "unknown-doctype":
       _(u"Erroneous DOCTYPE."),
    "expected-doctype-but-got-chars":
       _(u"Unexpected non-space characters. Expected DOCTYPE."),
    "expected-doctype-but-got-start-tag":
       _(u"Unexpected start tag (%(name)s). Expected DOCTYPE."),
    "expected-doctype-but-got-end-tag":
       _(u"Unexpected end tag (%(name)s). Expected DOCTYPE."),
    "end-tag-after-implied-root":
       _(u"Unexpected end tag (%(name)s) after the (implied) root element."),
    "expected-named-closing-tag-but-got-eof":
       _(u"Unexpected end of file. Expected end tag (%(name)s)."),
    "two-heads-are-not-better-than-one":
       _(u"Unexpected start tag head in existing head. Ignored."),
    "unexpected-end-tag":
       _(u"Unexpected end tag (%(name)s). Ignored."),
    "unexpected-start-tag-out-of-my-head":
       _(u"Unexpected start tag (%(name)s) that can be in head. Moved."),
    "unexpected-start-tag":
       _(u"Unexpected start tag (%(name)s)."),
    "missing-end-tag":
       _(u"Missing end tag (%(name)s)."),
    "missing-end-tags":
       _(u"Missing end tags (%(name)s)."),
    "unexpected-start-tag-implies-end-tag":
       _(u"Unexpected start tag (%(startName)s) "
         u"implies end tag (%(endName)s)."),
    "unexpected-start-tag-treated-as":
       _(u"Unexpected start tag (%(originalName)s). Treated as %(newName)s."),
    "deprecated-tag":
       _(u"Unexpected start tag %(name)s. Don't use it!"),
    "unexpected-start-tag-ignored":
       _(u"Unexpected start tag %(name)s. Ignored."),
    "expected-one-end-tag-but-got-another":
       _(u"Unexpected end tag (%(gotName)s). "
         u"Missing end tag (%(expectedName)s)."),
    "end-tag-too-early":
       _(u"End tag (%(name)s) seen too early. Expected other end tag."),
    "end-tag-too-early-named":
       _(u"Unexpected end tag (%(gotName)s). Expected end tag (%(expectedName)s)."),
    "end-tag-too-early-ignored":
       _(u"End tag (%(name)s) seen too early. Ignored."),
    "adoption-agency-1.1":
       _(u"End tag (%(name)s) violates step 1, "
         u"paragraph 1 of the adoption agency algorithm."),
    "adoption-agency-1.2":
       _(u"End tag (%(name)s) violates step 1, "
         u"paragraph 2 of the adoption agency algorithm."),
    "adoption-agency-1.3":
       _(u"End tag (%(name)s) violates step 1, "
         u"paragraph 3 of the adoption agency algorithm."),
    "unexpected-end-tag-treated-as":
       _(u"Unexpected end tag (%(originalName)s). Treated as %(newName)s."),
    "no-end-tag":
       _(u"This element (%(name)s) has no end tag."),
    "unexpected-implied-end-tag-in-table":
       _(u"Unexpected implied end tag (%(name)s) in the table phase."),
    "unexpected-implied-end-tag-in-table-body":
       _(u"Unexpected implied end tag (%(name)s) in the table body phase."),
    "unexpected-char-implies-table-voodoo":
       _(u"Unexpected non-space characters in "
         u"table context caused voodoo mode."),
    "unexpected-hidden-input-in-table":
       _(u"Unexpected input with type hidden in table context."),
    "unexpected-form-in-table":
       _(u"Unexpected form in table context."),
    "unexpected-start-tag-implies-table-voodoo":
       _(u"Unexpected start tag (%(name)s) in "
         u"table context caused voodoo mode."),
    "unexpected-end-tag-implies-table-voodoo":
       _(u"Unexpected end tag (%(name)s) in "
         u"table context caused voodoo mode."),
    "unexpected-cell-in-table-body":
       _(u"Unexpected table cell start tag (%(name)s) "
         u"in the table body phase."),
    "unexpected-cell-end-tag":
       _(u"Got table cell end tag (%(name)s) "
         u"while required end tags are missing."),
    "unexpected-end-tag-in-table-body":
       _(u"Unexpected end tag (%(name)s) in the table body phase. Ignored."),
    "unexpected-implied-end-tag-in-table-row":
       _(u"Unexpected implied end tag (%(name)s) in the table row phase."),
    "unexpected-end-tag-in-table-row":
       _(u"Unexpected end tag (%(name)s) in the table row phase. Ignored."),
    "unexpected-select-in-select":
       _(u"Unexpected select start tag in the select phase "
         u"treated as select end tag."),
    "unexpected-input-in-select":
       _(u"Unexpected input start tag in the select phase."),
    "unexpected-start-tag-in-select":
       _(u"Unexpected start tag token (%(name)s in the select phase. "
         u"Ignored."),
    "unexpected-end-tag-in-select":
       _(u"Unexpected end tag (%(name)s) in the select phase. Ignored."),
    "unexpected-table-element-start-tag-in-select-in-table":
       _(u"Unexpected table element start tag (%(name)s) in the select in table phase."),
    "unexpected-table-element-end-tag-in-select-in-table":
       _(u"Unexpected table element end tag (%(name)s) in the select in table phase."),
    "unexpected-char-after-body":
       _(u"Unexpected non-space characters in the after body phase."),
    "unexpected-start-tag-after-body":
       _(u"Unexpected start tag token (%(name)s)"
         u" in the after body phase."),
    "unexpected-end-tag-after-body":
       _(u"Unexpected end tag token (%(name)s)"
         u" in the after body phase."),
    "unexpected-char-in-frameset":
       _(u"Unepxected characters in the frameset phase. Characters ignored."),
    "unexpected-start-tag-in-frameset":
       _(u"Unexpected start tag token (%(name)s)"
         u" in the frameset phase. Ignored."),
    "unexpected-frameset-in-frameset-innerhtml":
       _(u"Unexpected end tag token (frameset) "
         u"in the frameset phase (innerHTML)."),
    "unexpected-end-tag-in-frameset":
       _(u"Unexpected end tag token (%(name)s)"
         u" in the frameset phase. Ignored."),
    "unexpected-char-after-frameset":
       _(u"Unexpected non-space characters in the "
         u"after frameset phase. Ignored."),
    "unexpected-start-tag-after-frameset":
       _(u"Unexpected start tag (%(name)s)"
         u" in the after frameset phase. Ignored."),
    "unexpected-end-tag-after-frameset":
       _(u"Unexpected end tag (%(name)s)"
         u" in the after frameset phase. Ignored."),
    "unexpected-end-tag-after-body-innerhtml":
       _(u"Unexpected end tag after body(innerHtml)"),
    "expected-eof-but-got-char":
       _(u"Unexpected non-space characters. Expected end of file."),
    "expected-eof-but-got-start-tag":
       _(u"Unexpected start tag (%(name)s)"
         u". Expected end of file."),
    "expected-eof-but-got-end-tag":
       _(u"Unexpected end tag (%(name)s)"
         u". Expected end of file."),
    "eof-in-table":
       _(u"Unexpected end of file. Expected table content."),
    "eof-in-select":
       _(u"Unexpected end of file. Expected select content."),
    "eof-in-frameset":
       _(u"Unexpected end of file. Expected frameset content."),
    "eof-in-script-in-script":
       _(u"Unexpected end of file. Expected script content."),
    "non-void-element-with-trailing-solidus":
       _(u"Trailing solidus not allowed on element %(name)s"),
    "unexpected-html-element-in-foreign-content":
       _(u"Element %(name)s not allowed in a non-html context"),
    "unexpected-end-tag-before-html":
        _(u"Unexpected end tag (%(name)s) before html."),
    "XXX-undefined-error":
        (u"Undefined error (this sucks and should be fixed)"),
}

namespaces = {
    "html":"http://www.w3.org/1999/xhtml",
    "mathml":"http://www.w3.org/1998/Math/MathML",
    "svg":"http://www.w3.org/2000/svg",
    "xlink":"http://www.w3.org/1999/xlink",
    "xml":"http://www.w3.org/XML/1998/namespace",
    "xmlns":"http://www.w3.org/2000/xmlns/"
}

scopingElements = frozenset((
    (namespaces["html"], "applet"),
    (namespaces["html"], "button"),
    (namespaces["html"], "caption"),
    (namespaces["html"], "html"),
    (namespaces["html"], "marquee"),
    (namespaces["html"], "object"),
    (namespaces["html"], "table"),
    (namespaces["html"], "td"),
    (namespaces["html"], "th"),
    (namespaces["svg"], "foreignObject")
))

formattingElements = frozenset((
    (namespaces["html"], "a"),
    (namespaces["html"], "b"),
    (namespaces["html"], "big"),
    (namespaces["html"], "code"),
    (namespaces["html"], "em"),
    (namespaces["html"], "font"),
    (namespaces["html"], "i"),
    (namespaces["html"], "nobr"),
    (namespaces["html"], "s"),
    (namespaces["html"], "small"),
    (namespaces["html"], "strike"),
    (namespaces["html"], "strong"),
    (namespaces["html"], "tt"),
    (namespaces["html"], "u")
))

specialElements = frozenset((
    (namespaces["html"], "address"),
    (namespaces["html"], "area"),
    (namespaces["html"], "article"),
    (namespaces["html"], "aside"),
    (namespaces["html"], "base"),
    (namespaces["html"], "basefont"),
    (namespaces["html"], "bgsound"),
    (namespaces["html"], "blockquote"),
    (namespaces["html"], "body"),
    (namespaces["html"], "br"),
    (namespaces["html"], "center"),
    (namespaces["html"], "col"),
    (namespaces["html"], "colgroup"),
    (namespaces["html"], "command"),
    (namespaces["html"], "datagrid"),
    (namespaces["html"], "dd"),
    (namespaces["html"], "details"),
    (namespaces["html"], "dialog"),
    (namespaces["html"], "dir"),
    (namespaces["html"], "div"),
    (namespaces["html"], "dl"),
    (namespaces["html"], "dt"),
    (namespaces["html"], "embed"),
    (namespaces["html"], "event-source"),
    (namespaces["html"], "fieldset"),
    (namespaces["html"], "figure"),
    (namespaces["html"], "footer"),
    (namespaces["html"], "form"),
    (namespaces["html"], "frame"),
    (namespaces["html"], "frameset"),
    (namespaces["html"], "h1"),
    (namespaces["html"], "h2"),
    (namespaces["html"], "h3"),
    (namespaces["html"], "h4"),
    (namespaces["html"], "h5"),
    (namespaces["html"], "h6"),
    (namespaces["html"], "head"),
    (namespaces["html"], "header"),
    (namespaces["html"], "hr"),
    (namespaces["html"], "iframe"),
    # Note that image is commented out in the spec as "this isn't an
    # element that can end up on the stack, so it doesn't matter,"
    (namespaces["html"], "image"), 
    (namespaces["html"], "img"),
    (namespaces["html"], "input"),
    (namespaces["html"], "isindex"),
    (namespaces["html"], "li"),
    (namespaces["html"], "link"),
    (namespaces["html"], "listing"),
    (namespaces["html"], "menu"),
    (namespaces["html"], "meta"),
    (namespaces["html"], "nav"),
    (namespaces["html"], "noembed"),
    (namespaces["html"], "noframes"),
    (namespaces["html"], "noscript"),
    (namespaces["html"], "ol"),
    (namespaces["html"], "optgroup"),
    (namespaces["html"], "option"),
    (namespaces["html"], "p"),
    (namespaces["html"], "param"),
    (namespaces["html"], "plaintext"),
    (namespaces["html"], "pre"),
    (namespaces["html"], "script"),
    (namespaces["html"], "section"),
    (namespaces["html"], "select"),
    (namespaces["html"], "spacer"),
    (namespaces["html"], "style"),
    (namespaces["html"], "tbody"),
    (namespaces["html"], "textarea"),
    (namespaces["html"], "tfoot"),
    (namespaces["html"], "thead"),
    (namespaces["html"], "title"),
    (namespaces["html"], "tr"),
    (namespaces["html"], "ul"),
    (namespaces["html"], "wbr")
))

spaceCharacters = frozenset((
    u"\t",
    u"\n",
    u"\u000C",
    u" ",
    u"\r"
))

tableInsertModeElements = frozenset((
    "table",
    "tbody",
    "tfoot",
    "thead",
    "tr"
))

asciiLowercase = frozenset(string.ascii_lowercase)
asciiUppercase = frozenset(string.ascii_uppercase)
asciiLetters = frozenset(string.ascii_letters)
digits = frozenset(string.digits)
hexDigits = frozenset(string.hexdigits)

asciiUpper2Lower = dict([(ord(c),ord(c.lower()))
    for c in string.ascii_uppercase])

# Heading elements need to be ordered
headingElements = (
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6"
)

voidElements = frozenset((
    "base",
    "command",
    "event-source",
    "link",
    "meta",
    "hr",
    "br",
    "img",
    "embed",
    "param",
    "area",
    "col",
    "input",
    "source"
))

cdataElements = frozenset(('title', 'textarea'))

rcdataElements = frozenset((
    'style',
    'script',
    'xmp',
    'iframe',
    'noembed',
    'noframes',
    'noscript'
))

booleanAttributes = {
    "": frozenset(("irrelevant",)),
    "style": frozenset(("scoped",)),
    "img": frozenset(("ismap",)),
    "audio": frozenset(("autoplay","controls")),
    "video": frozenset(("autoplay","controls")),
    "script": frozenset(("defer", "async")),
    "details": frozenset(("open",)),
    "datagrid": frozenset(("multiple", "disabled")),
    "command": frozenset(("hidden", "disabled", "checked", "default")),
    "menu": frozenset(("autosubmit",)),
    "fieldset": frozenset(("disabled", "readonly")),
    "option": frozenset(("disabled", "readonly", "selected")),
    "optgroup": frozenset(("disabled", "readonly")),
    "button": frozenset(("disabled", "autofocus")),
    "input": frozenset(("disabled", "readonly", "required", "autofocus", "checked", "ismap")),
    "select": frozenset(("disabled", "readonly", "autofocus", "multiple")),
    "output": frozenset(("disabled", "readonly")),
}

# entitiesWindows1252 has to be _ordered_ and needs to have an index. It
# therefore can't be a frozenset.
entitiesWindows1252 = (
    8364,  # 0x80  0x20AC  EURO SIGN
    65533, # 0x81          UNDEFINED
    8218,  # 0x82  0x201A  SINGLE LOW-9 QUOTATION MARK
    402,   # 0x83  0x0192  LATIN SMALL LETTER F WITH HOOK
    8222,  # 0x84  0x201E  DOUBLE LOW-9 QUOTATION MARK
    8230,  # 0x85  0x2026  HORIZONTAL ELLIPSIS
    8224,  # 0x86  0x2020  DAGGER
    8225,  # 0x87  0x2021  DOUBLE DAGGER
    710,   # 0x88  0x02C6  MODIFIER LETTER CIRCUMFLEX ACCENT
    8240,  # 0x89  0x2030  PER MILLE SIGN
    352,   # 0x8A  0x0160  LATIN CAPITAL LETTER S WITH CARON
    8249,  # 0x8B  0x2039  SINGLE LEFT-POINTING ANGLE QUOTATION MARK
    338,   # 0x8C  0x0152  LATIN CAPITAL LIGATURE OE
    65533, # 0x8D          UNDEFINED
    381,   # 0x8E  0x017D  LATIN CAPITAL LETTER Z WITH CARON
    65533, # 0x8F          UNDEFINED
    65533, # 0x90          UNDEFINED
    8216,  # 0x91  0x2018  LEFT SINGLE QUOTATION MARK
    8217,  # 0x92  0x2019  RIGHT SINGLE QUOTATION MARK
    8220,  # 0x93  0x201C  LEFT DOUBLE QUOTATION MARK
    8221,  # 0x94  0x201D  RIGHT DOUBLE QUOTATION MARK
    8226,  # 0x95  0x2022  BULLET
    8211,  # 0x96  0x2013  EN DASH
    8212,  # 0x97  0x2014  EM DASH
    732,   # 0x98  0x02DC  SMALL TILDE
    8482,  # 0x99  0x2122  TRADE MARK SIGN
    353,   # 0x9A  0x0161  LATIN SMALL LETTER S WITH CARON
    8250,  # 0x9B  0x203A  SINGLE RIGHT-POINTING ANGLE QUOTATION MARK
    339,   # 0x9C  0x0153  LATIN SMALL LIGATURE OE
    65533, # 0x9D          UNDEFINED
    382,   # 0x9E  0x017E  LATIN SMALL LETTER Z WITH CARON
    376    # 0x9F  0x0178  LATIN CAPITAL LETTER Y WITH DIAERESIS
)

entities = {
    "AElig;": u"\u00C6",
    "AElig": u"\u00C6",
    "AMP;": u"\u0026",
    "AMP": u"\u0026",
    "Aacute;": u"\u00C1",
    "Aacute": u"\u00C1",
    "Acirc;": u"\u00C2",
    "Acirc": u"\u00C2",
    "Agrave;": u"\u00C0",
    "Agrave": u"\u00C0",
    "Alpha;": u"\u0391",
    "Aring;": u"\u00C5",
    "Aring": u"\u00C5",
    "Atilde;": u"\u00C3",
    "Atilde": u"\u00C3",
    "Auml;": u"\u00C4",
    "Auml": u"\u00C4",
    "Beta;": u"\u0392",
    "COPY;": u"\u00A9",
    "COPY": u"\u00A9",
    "Ccedil;": u"\u00C7",
    "Ccedil": u"\u00C7",
    "Chi;": u"\u03A7",
    "Dagger;": u"\u2021",
    "Delta;": u"\u0394",
    "ETH;": u"\u00D0",
    "ETH": u"\u00D0",
    "Eacute;": u"\u00C9",
    "Eacute": u"\u00C9",
    "Ecirc;": u"\u00CA",
    "Ecirc": u"\u00CA",
    "Egrave;": u"\u00C8",
    "Egrave": u"\u00C8",
    "Epsilon;": u"\u0395",
    "Eta;": u"\u0397",
    "Euml;": u"\u00CB",
    "Euml": u"\u00CB",
    "GT;": u"\u003E",
    "GT": u"\u003E",
    "Gamma;": u"\u0393",
    "Iacute;": u"\u00CD",
    "Iacute": u"\u00CD",
    "Icirc;": u"\u00CE",
    "Icirc": u"\u00CE",
    "Igrave;": u"\u00CC",
    "Igrave": u"\u00CC",
    "Iota;": u"\u0399",
    "Iuml;": u"\u00CF",
    "Iuml": u"\u00CF",
    "Kappa;": u"\u039A",
    "LT;": u"\u003C",
    "LT": u"\u003C",
    "Lambda;": u"\u039B",
    "Mu;": u"\u039C",
    "Ntilde;": u"\u00D1",
    "Ntilde": u"\u00D1",
    "Nu;": u"\u039D",
    "OElig;": u"\u0152",
    "Oacute;": u"\u00D3",
    "Oacute": u"\u00D3",
    "Ocirc;": u"\u00D4",
    "Ocirc": u"\u00D4",
    "Ograve;": u"\u00D2",
    "Ograve": u"\u00D2",
    "Omega;": u"\u03A9",
    "Omicron;": u"\u039F",
    "Oslash;": u"\u00D8",
    "Oslash": u"\u00D8",
    "Otilde;": u"\u00D5",
    "Otilde": u"\u00D5",
    "Ouml;": u"\u00D6",
    "Ouml": u"\u00D6",
    "Phi;": u"\u03A6",
    "Pi;": u"\u03A0",
    "Prime;": u"\u2033",
    "Psi;": u"\u03A8",
    "QUOT;": u"\u0022",
    "QUOT": u"\u0022",
    "REG;": u"\u00AE",
    "REG": u"\u00AE",
    "Rho;": u"\u03A1",
    "Scaron;": u"\u0160",
    "Sigma;": u"\u03A3",
    "THORN;": u"\u00DE",
    "THORN": u"\u00DE",
    "TRADE;": u"\u2122",
    "Tau;": u"\u03A4",
    "Theta;": u"\u0398",
    "Uacute;": u"\u00DA",
    "Uacute": u"\u00DA",
    "Ucirc;": u"\u00DB",
    "Ucirc": u"\u00DB",
    "Ugrave;": u"\u00D9",
    "Ugrave": u"\u00D9",
    "Upsilon;": u"\u03A5",
    "Uuml;": u"\u00DC",
    "Uuml": u"\u00DC",
    "Xi;": u"\u039E",
    "Yacute;": u"\u00DD",
    "Yacute": u"\u00DD",
    "Yuml;": u"\u0178",
    "Zeta;": u"\u0396",
    "aacute;": u"\u00E1",
    "aacute": u"\u00E1",
    "acirc;": u"\u00E2",
    "acirc": u"\u00E2",
    "acute;": u"\u00B4",
    "acute": u"\u00B4",
    "aelig;": u"\u00E6",
    "aelig": u"\u00E6",
    "agrave;": u"\u00E0",
    "agrave": u"\u00E0",
    "alefsym;": u"\u2135",
    "alpha;": u"\u03B1",
    "amp;": u"\u0026",
    "amp": u"\u0026",
    "and;": u"\u2227",
    "ang;": u"\u2220",
    "apos;": u"\u0027",
    "aring;": u"\u00E5",
    "aring": u"\u00E5",
    "asymp;": u"\u2248",
    "atilde;": u"\u00E3",
    "atilde": u"\u00E3",
    "auml;": u"\u00E4",
    "auml": u"\u00E4",
    "bdquo;": u"\u201E",
    "beta;": u"\u03B2",
    "brvbar;": u"\u00A6",
    "brvbar": u"\u00A6",
    "bull;": u"\u2022",
    "cap;": u"\u2229",
    "ccedil;": u"\u00E7",
    "ccedil": u"\u00E7",
    "cedil;": u"\u00B8",
    "cedil": u"\u00B8",
    "cent;": u"\u00A2",
    "cent": u"\u00A2",
    "chi;": u"\u03C7",
    "circ;": u"\u02C6",
    "clubs;": u"\u2663",
    "cong;": u"\u2245",
    "copy;": u"\u00A9",
    "copy": u"\u00A9",
    "crarr;": u"\u21B5",
    "cup;": u"\u222A",
    "curren;": u"\u00A4",
    "curren": u"\u00A4",
    "dArr;": u"\u21D3",
    "dagger;": u"\u2020",
    "darr;": u"\u2193",
    "deg;": u"\u00B0",
    "deg": u"\u00B0",
    "delta;": u"\u03B4",
    "diams;": u"\u2666",
    "divide;": u"\u00F7",
    "divide": u"\u00F7",
    "eacute;": u"\u00E9",
    "eacute": u"\u00E9",
    "ecirc;": u"\u00EA",
    "ecirc": u"\u00EA",
    "egrave;": u"\u00E8",
    "egrave": u"\u00E8",
    "empty;": u"\u2205",
    "emsp;": u"\u2003",
    "ensp;": u"\u2002",
    "epsilon;": u"\u03B5",
    "equiv;": u"\u2261",
    "eta;": u"\u03B7",
    "eth;": u"\u00F0",
    "eth": u"\u00F0",
    "euml;": u"\u00EB",
    "euml": u"\u00EB",
    "euro;": u"\u20AC",
    "exist;": u"\u2203",
    "fnof;": u"\u0192",
    "forall;": u"\u2200",
    "frac12;": u"\u00BD",
    "frac12": u"\u00BD",
    "frac14;": u"\u00BC",
    "frac14": u"\u00BC",
    "frac34;": u"\u00BE",
    "frac34": u"\u00BE",
    "frasl;": u"\u2044",
    "gamma;": u"\u03B3",
    "ge;": u"\u2265",
    "gt;": u"\u003E",
    "gt": u"\u003E",
    "hArr;": u"\u21D4",
    "harr;": u"\u2194",
    "hearts;": u"\u2665",
    "hellip;": u"\u2026",
    "iacute;": u"\u00ED",
    "iacute": u"\u00ED",
    "icirc;": u"\u00EE",
    "icirc": u"\u00EE",
    "iexcl;": u"\u00A1",
    "iexcl": u"\u00A1",
    "igrave;": u"\u00EC",
    "igrave": u"\u00EC",
    "image;": u"\u2111",
    "infin;": u"\u221E",
    "int;": u"\u222B",
    "iota;": u"\u03B9",
    "iquest;": u"\u00BF",
    "iquest": u"\u00BF",
    "isin;": u"\u2208",
    "iuml;": u"\u00EF",
    "iuml": u"\u00EF",
    "kappa;": u"\u03BA",
    "lArr;": u"\u21D0",
    "lambda;": u"\u03BB",
    "lang;": u"\u27E8",
    "laquo;": u"\u00AB",
    "laquo": u"\u00AB",
    "larr;": u"\u2190",
    "lceil;": u"\u2308",
    "ldquo;": u"\u201C",
    "le;": u"\u2264",
    "lfloor;": u"\u230A",
    "lowast;": u"\u2217",
    "loz;": u"\u25CA",
    "lrm;": u"\u200E",
    "lsaquo;": u"\u2039",
    "lsquo;": u"\u2018",
    "lt;": u"\u003C",
    "lt": u"\u003C",
    "macr;": u"\u00AF",
    "macr": u"\u00AF",
    "mdash;": u"\u2014",
    "micro;": u"\u00B5",
    "micro": u"\u00B5",
    "middot;": u"\u00B7",
    "middot": u"\u00B7",
    "minus;": u"\u2212",
    "mu;": u"\u03BC",
    "nabla;": u"\u2207",
    "nbsp;": u"\u00A0",
    "nbsp": u"\u00A0",
    "ndash;": u"\u2013",
    "ne;": u"\u2260",
    "ni;": u"\u220B",
    "not;": u"\u00AC",
    "not": u"\u00AC",
    "notin;": u"\u2209",
    "nsub;": u"\u2284",
    "ntilde;": u"\u00F1",
    "ntilde": u"\u00F1",
    "nu;": u"\u03BD",
    "oacute;": u"\u00F3",
    "oacute": u"\u00F3",
    "ocirc;": u"\u00F4",
    "ocirc": u"\u00F4",
    "oelig;": u"\u0153",
    "ograve;": u"\u00F2",
    "ograve": u"\u00F2",
    "oline;": u"\u203E",
    "omega;": u"\u03C9",
    "omicron;": u"\u03BF",
    "oplus;": u"\u2295",
    "or;": u"\u2228",
    "ordf;": u"\u00AA",
    "ordf": u"\u00AA",
    "ordm;": u"\u00BA",
    "ordm": u"\u00BA",
    "oslash;": u"\u00F8",
    "oslash": u"\u00F8",
    "otilde;": u"\u00F5",
    "otilde": u"\u00F5",
    "otimes;": u"\u2297",
    "ouml;": u"\u00F6",
    "ouml": u"\u00F6",
    "para;": u"\u00B6",
    "para": u"\u00B6",
    "part;": u"\u2202",
    "permil;": u"\u2030",
    "perp;": u"\u22A5",
    "phi;": u"\u03C6",
    "pi;": u"\u03C0",
    "piv;": u"\u03D6",
    "plusmn;": u"\u00B1",
    "plusmn": u"\u00B1",
    "pound;": u"\u00A3",
    "pound": u"\u00A3",
    "prime;": u"\u2032",
    "prod;": u"\u220F",
    "prop;": u"\u221D",
    "psi;": u"\u03C8",
    "quot;": u"\u0022",
    "quot": u"\u0022",
    "rArr;": u"\u21D2",
    "radic;": u"\u221A",
    "rang;": u"\u27E9",
    "raquo;": u"\u00BB",
    "raquo": u"\u00BB",
    "rarr;": u"\u2192",
    "rceil;": u"\u2309",
    "rdquo;": u"\u201D",
    "real;": u"\u211C",
    "reg;": u"\u00AE",
    "reg": u"\u00AE",
    "rfloor;": u"\u230B",
    "rho;": u"\u03C1",
    "rlm;": u"\u200F",
    "rsaquo;": u"\u203A",
    "rsquo;": u"\u2019",
    "sbquo;": u"\u201A",
    "scaron;": u"\u0161",
    "sdot;": u"\u22C5",
    "sect;": u"\u00A7",
    "sect": u"\u00A7",
    "shy;": u"\u00AD",
    "shy": u"\u00AD",
    "sigma;": u"\u03C3",
    "sigmaf;": u"\u03C2",
    "sim;": u"\u223C",
    "spades;": u"\u2660",
    "sub;": u"\u2282",
    "sube;": u"\u2286",
    "sum;": u"\u2211",
    "sup1;": u"\u00B9",
    "sup1": u"\u00B9",
    "sup2;": u"\u00B2",
    "sup2": u"\u00B2",
    "sup3;": u"\u00B3",
    "sup3": u"\u00B3",
    "sup;": u"\u2283",
    "supe;": u"\u2287",
    "szlig;": u"\u00DF",
    "szlig": u"\u00DF",
    "tau;": u"\u03C4",
    "there4;": u"\u2234",
    "theta;": u"\u03B8",
    "thetasym;": u"\u03D1",
    "thinsp;": u"\u2009",
    "thorn;": u"\u00FE",
    "thorn": u"\u00FE",
    "tilde;": u"\u02DC",
    "times;": u"\u00D7",
    "times": u"\u00D7",
    "trade;": u"\u2122",
    "uArr;": u"\u21D1",
    "uacute;": u"\u00FA",
    "uacute": u"\u00FA",
    "uarr;": u"\u2191",
    "ucirc;": u"\u00FB",
    "ucirc": u"\u00FB",
    "ugrave;": u"\u00F9",
    "ugrave": u"\u00F9",
    "uml;": u"\u00A8",
    "uml": u"\u00A8",
    "upsih;": u"\u03D2",
    "upsilon;": u"\u03C5",
    "uuml;": u"\u00FC",
    "uuml": u"\u00FC",
    "weierp;": u"\u2118",
    "xi;": u"\u03BE",
    "yacute;": u"\u00FD",
    "yacute": u"\u00FD",
    "yen;": u"\u00A5",
    "yen": u"\u00A5",
    "yuml;": u"\u00FF",
    "yuml": u"\u00FF",
    "zeta;": u"\u03B6",
    "zwj;": u"\u200D",
    "zwnj;": u"\u200C"
}

replacementCharacters = {
    0x0:u"\uFFFD",
    0x0d:u"\u000A",
    0x80:u"\u20AC",
    0x81:u"\u0081",
    0x81:u"\u0081",
    0x82:u"\u201A",
    0x83:u"\u0192",
    0x84:u"\u201E",
    0x85:u"\u2026",
    0x86:u"\u2020",
    0x87:u"\u2021",
    0x88:u"\u02C6",
    0x89:u"\u2030",
    0x8A:u"\u0160",
    0x8B:u"\u2039",
    0x8C:u"\u0152",
    0x8D:u"\u008D",
    0x8E:u"\u017D",
    0x8F:u"\u008F",
    0x90:u"\u0090",
    0x91:u"\u2018",
    0x92:u"\u2019",
    0x93:u"\u201C",
    0x94:u"\u201D",
    0x95:u"\u2022",
    0x96:u"\u2013",
    0x97:u"\u2014",
    0x98:u"\u02DC",
    0x99:u"\u2122",
    0x9A:u"\u0161",
    0x9B:u"\u203A",
    0x9C:u"\u0153",
    0x9D:u"\u009D",
    0x9E:u"\u017E",
    0x9F:u"\u0178",
}

encodings = {
    '437': 'cp437',
    '850': 'cp850',
    '852': 'cp852',
    '855': 'cp855',
    '857': 'cp857',
    '860': 'cp860',
    '861': 'cp861',
    '862': 'cp862',
    '863': 'cp863',
    '865': 'cp865',
    '866': 'cp866',
    '869': 'cp869',
    'ansix341968': 'ascii',
    'ansix341986': 'ascii',
    'arabic': 'iso8859-6',
    'ascii': 'ascii',
    'asmo708': 'iso8859-6',
    'big5': 'big5',
    'big5hkscs': 'big5hkscs',
    'chinese': 'gbk',
    'cp037': 'cp037',
    'cp1026': 'cp1026',
    'cp154': 'ptcp154',
    'cp367': 'ascii',
    'cp424': 'cp424',
    'cp437': 'cp437',
    'cp500': 'cp500',
    'cp775': 'cp775',
    'cp819': 'windows-1252',
    'cp850': 'cp850',
    'cp852': 'cp852',
    'cp855': 'cp855',
    'cp857': 'cp857',
    'cp860': 'cp860',
    'cp861': 'cp861',
    'cp862': 'cp862',
    'cp863': 'cp863',
    'cp864': 'cp864',
    'cp865': 'cp865',
    'cp866': 'cp866',
    'cp869': 'cp869',
    'cp936': 'gbk',
    'cpgr': 'cp869',
    'cpis': 'cp861',
    'csascii': 'ascii',
    'csbig5': 'big5',
    'cseuckr': 'cp949',
    'cseucpkdfmtjapanese': 'euc_jp',
    'csgb2312': 'gbk',
    'cshproman8': 'hp-roman8',
    'csibm037': 'cp037',
    'csibm1026': 'cp1026',
    'csibm424': 'cp424',
    'csibm500': 'cp500',
    'csibm855': 'cp855',
    'csibm857': 'cp857',
    'csibm860': 'cp860',
    'csibm861': 'cp861',
    'csibm863': 'cp863',
    'csibm864': 'cp864',
    'csibm865': 'cp865',
    'csibm866': 'cp866',
    'csibm869': 'cp869',
    'csiso2022jp': 'iso2022_jp',
    'csiso2022jp2': 'iso2022_jp_2',
    'csiso2022kr': 'iso2022_kr',
    'csiso58gb231280': 'gbk',
    'csisolatin1': 'windows-1252',
    'csisolatin2': 'iso8859-2',
    'csisolatin3': 'iso8859-3',
    'csisolatin4': 'iso8859-4',
    'csisolatin5': 'windows-1254',
    'csisolatin6': 'iso8859-10',
    'csisolatinarabic': 'iso8859-6',
    'csisolatincyrillic': 'iso8859-5',
    'csisolatingreek': 'iso8859-7',
    'csisolatinhebrew': 'iso8859-8',
    'cskoi8r': 'koi8-r',
    'csksc56011987': 'cp949',
    'cspc775baltic': 'cp775',
    'cspc850multilingual': 'cp850',
    'cspc862latinhebrew': 'cp862',
    'cspc8codepage437': 'cp437',
    'cspcp852': 'cp852',
    'csptcp154': 'ptcp154',
    'csshiftjis': 'shift_jis',
    'csunicode11utf7': 'utf-7',
    'cyrillic': 'iso8859-5',
    'cyrillicasian': 'ptcp154',
    'ebcdiccpbe': 'cp500',
    'ebcdiccpca': 'cp037',
    'ebcdiccpch': 'cp500',
    'ebcdiccphe': 'cp424',
    'ebcdiccpnl': 'cp037',
    'ebcdiccpus': 'cp037',
    'ebcdiccpwt': 'cp037',
    'ecma114': 'iso8859-6',
    'ecma118': 'iso8859-7',
    'elot928': 'iso8859-7',
    'eucjp': 'euc_jp',
    'euckr': 'cp949',
    'extendedunixcodepackedformatforjapanese': 'euc_jp',
    'gb18030': 'gb18030',
    'gb2312': 'gbk',
    'gb231280': 'gbk',
    'gbk': 'gbk',
    'greek': 'iso8859-7',
    'greek8': 'iso8859-7',
    'hebrew': 'iso8859-8',
    'hproman8': 'hp-roman8',
    'hzgb2312': 'hz',
    'ibm037': 'cp037',
    'ibm1026': 'cp1026',
    'ibm367': 'ascii',
    'ibm424': 'cp424',
    'ibm437': 'cp437',
    'ibm500': 'cp500',
    'ibm775': 'cp775',
    'ibm819': 'windows-1252',
    'ibm850': 'cp850',
    'ibm852': 'cp852',
    'ibm855': 'cp855',
    'ibm857': 'cp857',
    'ibm860': 'cp860',
    'ibm861': 'cp861',
    'ibm862': 'cp862',
    'ibm863': 'cp863',
    'ibm864': 'cp864',
    'ibm865': 'cp865',
    'ibm866': 'cp866',
    'ibm869': 'cp869',
    'iso2022jp': 'iso2022_jp',
    'iso2022jp2': 'iso2022_jp_2',
    'iso2022kr': 'iso2022_kr',
    'iso646irv1991': 'ascii',
    'iso646us': 'ascii',
    'iso88591': 'windows-1252',
    'iso885910': 'iso8859-10',
    'iso8859101992': 'iso8859-10',
    'iso885911987': 'windows-1252',
    'iso885913': 'iso8859-13',
    'iso885914': 'iso8859-14',
    'iso8859141998': 'iso8859-14',
    'iso885915': 'iso8859-15',
    'iso885916': 'iso8859-16',
    'iso8859162001': 'iso8859-16',
    'iso88592': 'iso8859-2',
    'iso885921987': 'iso8859-2',
    'iso88593': 'iso8859-3',
    'iso885931988': 'iso8859-3',
    'iso88594': 'iso8859-4',
    'iso885941988': 'iso8859-4',
    'iso88595': 'iso8859-5',
    'iso885951988': 'iso8859-5',
    'iso88596': 'iso8859-6',
    'iso885961987': 'iso8859-6',
    'iso88597': 'iso8859-7',
    'iso885971987': 'iso8859-7',
    'iso88598': 'iso8859-8',
    'iso885981988': 'iso8859-8',
    'iso88599': 'windows-1254',
    'iso885991989': 'windows-1254',
    'isoceltic': 'iso8859-14',
    'isoir100': 'windows-1252',
    'isoir101': 'iso8859-2',
    'isoir109': 'iso8859-3',
    'isoir110': 'iso8859-4',
    'isoir126': 'iso8859-7',
    'isoir127': 'iso8859-6',
    'isoir138': 'iso8859-8',
    'isoir144': 'iso8859-5',
    'isoir148': 'windows-1254',
    'isoir149': 'cp949',
    'isoir157': 'iso8859-10',
    'isoir199': 'iso8859-14',
    'isoir226': 'iso8859-16',
    'isoir58': 'gbk',
    'isoir6': 'ascii',
    'koi8r': 'koi8-r',
    'koi8u': 'koi8-u',
    'korean': 'cp949',
    'ksc5601': 'cp949',
    'ksc56011987': 'cp949',
    'ksc56011989': 'cp949',
    'l1': 'windows-1252',
    'l10': 'iso8859-16',
    'l2': 'iso8859-2',
    'l3': 'iso8859-3',
    'l4': 'iso8859-4',
    'l5': 'windows-1254',
    'l6': 'iso8859-10',
    'l8': 'iso8859-14',
    'latin1': 'windows-1252',
    'latin10': 'iso8859-16',
    'latin2': 'iso8859-2',
    'latin3': 'iso8859-3',
    'latin4': 'iso8859-4',
    'latin5': 'windows-1254',
    'latin6': 'iso8859-10',
    'latin8': 'iso8859-14',
    'latin9': 'iso8859-15',
    'ms936': 'gbk',
    'mskanji': 'shift_jis',
    'pt154': 'ptcp154',
    'ptcp154': 'ptcp154',
    'r8': 'hp-roman8',
    'roman8': 'hp-roman8',
    'shiftjis': 'shift_jis',
    'tis620': 'cp874',
    'unicode11utf7': 'utf-7',
    'us': 'ascii',
    'usascii': 'ascii',
    'utf16': 'utf-16',
    'utf16be': 'utf-16-be',
    'utf16le': 'utf-16-le',
    'utf8': 'utf-8',
    'windows1250': 'cp1250',
    'windows1251': 'cp1251',
    'windows1252': 'cp1252',
    'windows1253': 'cp1253',
    'windows1254': 'cp1254',
    'windows1255': 'cp1255',
    'windows1256': 'cp1256',
    'windows1257': 'cp1257',
    'windows1258': 'cp1258',
    'windows936': 'gbk',
    'x-x-big5': 'big5'}

tokenTypes = {
    "Doctype":0,
    "Characters":1,
    "SpaceCharacters":2,
    "StartTag":3,
    "EndTag":4,
    "EmptyTag":5,
    "Comment":6,
    "ParseError":7
}

tagTokenTypes = frozenset((tokenTypes["StartTag"], tokenTypes["EndTag"], 
                           tokenTypes["EmptyTag"]))


prefixes = dict([(v,k) for k,v in namespaces.iteritems()])
prefixes["http://www.w3.org/1998/Math/MathML"] = "math"

class DataLossWarning(UserWarning):
    pass

class ReparseException(Exception):
    pass
