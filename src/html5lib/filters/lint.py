from gettext import gettext
_ = gettext

import _base
from html5lib.constants import cdataElements, rcdataElements, voidElements

from html5lib.constants import spaceCharacters
spaceCharacters = u"".join(spaceCharacters)

class LintError(Exception): pass

class Filter(_base.Filter):
    def __iter__(self):
        open_elements = []
        contentModelFlag = "PCDATA"
        for token in _base.Filter.__iter__(self):
            type = token["type"]
            if type in ("StartTag", "EmptyTag"):
                name = token["name"]
                if contentModelFlag != "PCDATA":
                    raise LintError(_("StartTag not in PCDATA content model flag: %s") % name)
                if not isinstance(name, unicode):
                    raise LintError(_(u"Tag name is not a string: %r") % name)
                if not name:
                    raise LintError(_(u"Empty tag name"))
                if type == "StartTag" and name in voidElements:
                    raise LintError(_(u"Void element reported as StartTag token: %s") % name)
                elif type == "EmptyTag" and name not in voidElements:
                    raise LintError(_(u"Non-void element reported as EmptyTag token: %s") % token["name"])
                if type == "StartTag":
                    open_elements.append(name)
                for name, value in token["data"]:
                    if not isinstance(name, unicode):
                        raise LintError(_("Attribute name is not a string: %r") % name)
                    if not name:
                        raise LintError(_(u"Empty attribute name"))
                    if not isinstance(value, unicode):
                        raise LintError(_("Attribute value is not a string: %r") % value)
                if name in cdataElements:
                    contentModelFlag = "CDATA"
                elif name in rcdataElements:
                    contentModelFlag = "RCDATA"
                elif name == "plaintext":
                    contentModelFlag = "PLAINTEXT"

            elif type == "EndTag":
                name = token["name"]
                if not isinstance(name, unicode):
                    raise LintError(_(u"Tag name is not a string: %r") % name)
                if not name:
                    raise LintError(_(u"Empty tag name"))
                if name in voidElements:
                    raise LintError(_(u"Void element reported as EndTag token: %s") % name)
                start_name = open_elements.pop()
                if start_name != name:
                    raise LintError(_(u"EndTag (%s) does not match StartTag (%s)") % (name, start_name))
                contentModelFlag = "PCDATA"

            elif type == "Comment":
                if contentModelFlag != "PCDATA":
                    raise LintError(_("Comment not in PCDATA content model flag"))

            elif type in ("Characters", "SpaceCharacters"):
                data = token["data"]
                if not isinstance(data, unicode):
                    raise LintError(_("Attribute name is not a string: %r") % data)
                if not data:
                    raise LintError(_(u"%s token with empty data") % type)
                if type == "SpaceCharacters":
                    data = data.strip(spaceCharacters)
                    if data:
                        raise LintError(_(u"Non-space character(s) found in SpaceCharacters token: ") % data)

            elif type == "Doctype":
                name = token["name"]
                if contentModelFlag != "PCDATA":
                    raise LintError(_("Doctype not in PCDATA content model flag: %s") % name)
                if not isinstance(name, unicode):
                    raise LintError(_(u"Tag name is not a string: %r") % name)
                # XXX: what to do with token["data"] ?

            elif type in ("ParseError", "SerializeError"):
                pass

            else:
                raise LintError(_(u"Unknown token type: %s") % type)

            yield token
