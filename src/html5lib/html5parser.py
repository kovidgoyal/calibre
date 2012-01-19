try:
    frozenset
except NameError:
    # Import from the sets module for python 2.3
    from sets import Set as set
    from sets import ImmutableSet as frozenset

try:
    any
except:
    # Implement 'any' for python 2.4 and previous
    def any(iterable):
        for element in iterable:
            if element:
                return True
        return False

import sys

import inputstream
import tokenizer

import treebuilders
from treebuilders._base import Marker
from treebuilders import simpletree

import utils
from constants import spaceCharacters, asciiUpper2Lower
from constants import scopingElements, formattingElements, specialElements
from constants import headingElements, tableInsertModeElements
from constants import cdataElements, rcdataElements, voidElements
from constants import tokenTypes, ReparseException, namespaces

def parse(doc, treebuilder="simpletree", encoding=None, 
          namespaceHTMLElements=True):
    tb = treebuilders.getTreeBuilder(treebuilder)
    p = HTMLParser(tb, namespaceHTMLElements=namespaceHTMLElements)
    return p.parse(doc, encoding=encoding)

def parseFragment(doc, container="div", treebuilder="simpletree", encoding=None, 
                  namespaceHTMLElements=True):
    tb = treebuilders.getTreeBuilder(treebuilder)
    p = HTMLParser(tb, namespaceHTMLElements=namespaceHTMLElements)
    return p.parseFragment(doc, container=container, encoding=encoding)

class HTMLParser(object):
    """HTML parser. Generates a tree structure from a stream of (possibly
        malformed) HTML"""

    def __init__(self, tree = simpletree.TreeBuilder,
                 tokenizer = tokenizer.HTMLTokenizer, strict = False,
                 namespaceHTMLElements = True):
        """
        strict - raise an exception when a parse error is encountered

        tree - a treebuilder class controlling the type of tree that will be
        returned. Built in treebuilders can be accessed through
        html5lib.treebuilders.getTreeBuilder(treeType)
        
        tokenizer - a class that provides a stream of tokens to the treebuilder.
        This may be replaced for e.g. a sanitizer which converts some tags to
        text
        """

        # Raise an exception on the first error encountered
        self.strict = strict

        self.tree = tree(namespaceHTMLElements)
        self.tokenizer_class = tokenizer
        self.errors = []

        self.phases = {
            "initial": InitialPhase(self, self.tree),
            "beforeHtml": BeforeHtmlPhase(self, self.tree),
            "beforeHead": BeforeHeadPhase(self, self.tree),
            "inHead": InHeadPhase(self, self.tree),
            # XXX "inHeadNoscript": InHeadNoScriptPhase(self, self.tree),
            "afterHead": AfterHeadPhase(self, self.tree),
            "inBody": InBodyPhase(self, self.tree),
            "text": TextPhase(self, self.tree),
            "inTable": InTablePhase(self, self.tree),
            "inTableText": InTableTextPhase(self, self.tree),
            "inCaption": InCaptionPhase(self, self.tree),
            "inColumnGroup": InColumnGroupPhase(self, self.tree),
            "inTableBody": InTableBodyPhase(self, self.tree),
            "inRow": InRowPhase(self, self.tree),
            "inCell": InCellPhase(self, self.tree),
            "inSelect": InSelectPhase(self, self.tree),
            "inSelectInTable": InSelectInTablePhase(self, self.tree),
            "inForeignContent": InForeignContentPhase(self, self.tree),
            "afterBody": AfterBodyPhase(self, self.tree),
            "inFrameset": InFramesetPhase(self, self.tree),
            "afterFrameset": AfterFramesetPhase(self, self.tree),
            "afterAfterBody": AfterAfterBodyPhase(self, self.tree),
            "afterAfterFrameset": AfterAfterFramesetPhase(self, self.tree),
            # XXX after after frameset
        }

    def _parse(self, stream, innerHTML=False, container="div",
               encoding=None, parseMeta=True, useChardet=True, **kwargs):

        self.innerHTMLMode = innerHTML
        self.container = container
        self.tokenizer = self.tokenizer_class(stream, encoding=encoding,
                                              parseMeta=parseMeta,
                                              useChardet=useChardet, **kwargs)
        self.reset()

        while True:
            try:
                self.mainLoop()
                break
            except ReparseException, e:
                self.reset()

    def reset(self):
        self.tree.reset()
        self.firstStartTag = False
        self.errors = []
        # "quirks" / "limited quirks" / "no quirks"
        self.compatMode = "no quirks"

        if self.innerHTMLMode:
            self.innerHTML = self.container.lower()

            if self.innerHTML in cdataElements:
                self.tokenizer.state = self.tokenizer.rcdataState
            elif self.innerHTML in rcdataElements:
                self.tokenizer.state = self.tokenizer.rawtextState
            elif self.innerHTML == 'plaintext':
                self.tokenizer.state = self.tokenizer.plaintextState
            else:
                # state already is data state
                # self.tokenizer.state = self.tokenizer.dataState
                pass
            self.phase = self.phases["beforeHtml"]
            self.phase.insertHtmlElement()
            self.resetInsertionMode()
        else:
            self.innerHTML = False
            self.phase = self.phases["initial"]

        self.lastPhase = None
        self.secondaryPhase = None

        self.beforeRCDataPhase = None

        self.framesetOK = True
        
    def mainLoop(self):
        (CharactersToken, 
         SpaceCharactersToken, 
         StartTagToken,
         EndTagToken, 
         CommentToken,
         DoctypeToken) = (tokenTypes["Characters"],
                          tokenTypes["SpaceCharacters"],
                          tokenTypes["StartTag"],
                          tokenTypes["EndTag"],
                          tokenTypes["Comment"],
                          tokenTypes["Doctype"])

        CharactersToken = tokenTypes["Characters"]
        SpaceCharactersToken = tokenTypes["SpaceCharacters"]
        StartTagToken = tokenTypes["StartTag"]
        EndTagToken = tokenTypes["EndTag"]
        CommentToken = tokenTypes["Comment"]
        DoctypeToken = tokenTypes["Doctype"]
        
        
        for token in self.normalizedTokens():
            type = token["type"]
            if type == CharactersToken:
                self.phase.processCharacters(token)
            elif type == SpaceCharactersToken:
                self.phase.processSpaceCharacters(token)
            elif type == StartTagToken:
                self.selfClosingAcknowledged = False
                self.phase.processStartTag(token)
                if (token["selfClosing"]
                    and not self.selfClosingAcknowledged):
                    self.parseError("non-void-element-with-trailing-solidus",
                                    {"name":token["name"]})
            elif type == EndTagToken:
                self.phase.processEndTag(token)
            elif type == CommentToken:
                self.phase.processComment(token)
            elif type == DoctypeToken:
                self.phase.processDoctype(token)
            else:
                self.parseError(token["data"], token.get("datavars", {}))

        # When the loop finishes it's EOF
        self.phase.processEOF()

    def normalizedTokens(self):
        for token in self.tokenizer:
            yield self.normalizeToken(token)

    def parse(self, stream, encoding=None, parseMeta=True, useChardet=True):
        """Parse a HTML document into a well-formed tree

        stream - a filelike object or string containing the HTML to be parsed

        The optional encoding parameter must be a string that indicates
        the encoding.  If specified, that encoding will be used,
        regardless of any BOM or later declaration (such as in a meta
        element)
        """
        self._parse(stream, innerHTML=False, encoding=encoding, 
                    parseMeta=parseMeta, useChardet=useChardet)
        return self.tree.getDocument()
    
    def parseFragment(self, stream, container="div", encoding=None,
                      parseMeta=False, useChardet=True):
        """Parse a HTML fragment into a well-formed tree fragment
        
        container - name of the element we're setting the innerHTML property
        if set to None, default to 'div'

        stream - a filelike object or string containing the HTML to be parsed

        The optional encoding parameter must be a string that indicates
        the encoding.  If specified, that encoding will be used,
        regardless of any BOM or later declaration (such as in a meta
        element)
        """
        self._parse(stream, True, container=container, encoding=encoding)
        return self.tree.getFragment()

    def parseError(self, errorcode="XXX-undefined-error", datavars={}):
        # XXX The idea is to make errorcode mandatory.
        self.errors.append((self.tokenizer.stream.position(), errorcode, datavars))
        if self.strict:
            raise ParseError

    def normalizeToken(self, token):
        """ HTML5 specific normalizations to the token stream """

        if token["type"] == tokenTypes["StartTag"]:
            token["data"] = dict(token["data"][::-1])

        return token

    def adjustMathMLAttributes(self, token):
        replacements = {"definitionurl":"definitionURL"}
        for k,v in replacements.iteritems():
            if k in token["data"]:
                token["data"][v] = token["data"][k]
                del token["data"][k]

    def adjustSVGAttributes(self, token):
        replacements = {
            "attributename" : "attributeName",
            "attributetype" : "attributeType",
            "basefrequency" : "baseFrequency",
            "baseprofile" : "baseProfile",
            "calcmode" : "calcMode",
            "clippathunits" : "clipPathUnits",
            "contentscripttype" : "contentScriptType",
            "contentstyletype" : "contentStyleType",
            "diffuseconstant" : "diffuseConstant",
            "edgemode" : "edgeMode",
            "externalresourcesrequired" : "externalResourcesRequired",
            "filterres" : "filterRes",
            "filterunits" : "filterUnits",
            "glyphref" : "glyphRef",
            "gradienttransform" : "gradientTransform",
            "gradientunits" : "gradientUnits",
            "kernelmatrix" : "kernelMatrix",
            "kernelunitlength" : "kernelUnitLength",
            "keypoints" : "keyPoints",
            "keysplines" : "keySplines",
            "keytimes" : "keyTimes",
            "lengthadjust" : "lengthAdjust",
            "limitingconeangle" : "limitingConeAngle",
            "markerheight" : "markerHeight",
            "markerunits" : "markerUnits",
            "markerwidth" : "markerWidth",
            "maskcontentunits" : "maskContentUnits",
            "maskunits" : "maskUnits",
            "numoctaves" : "numOctaves",
            "pathlength" : "pathLength",
            "patterncontentunits" : "patternContentUnits",
            "patterntransform" : "patternTransform",
            "patternunits" : "patternUnits",
            "pointsatx" : "pointsAtX",
            "pointsaty" : "pointsAtY",
            "pointsatz" : "pointsAtZ",
            "preservealpha" : "preserveAlpha",
            "preserveaspectratio" : "preserveAspectRatio",
            "primitiveunits" : "primitiveUnits",
            "refx" : "refX",
            "refy" : "refY",
            "repeatcount" : "repeatCount",
            "repeatdur" : "repeatDur",
            "requiredextensions" : "requiredExtensions",
            "requiredfeatures" : "requiredFeatures",
            "specularconstant" : "specularConstant",
            "specularexponent" : "specularExponent",
            "spreadmethod" : "spreadMethod",
            "startoffset" : "startOffset",
            "stddeviation" : "stdDeviation",
            "stitchtiles" : "stitchTiles",
            "surfacescale" : "surfaceScale",
            "systemlanguage" : "systemLanguage",
            "tablevalues" : "tableValues",
            "targetx" : "targetX",
            "targety" : "targetY",
            "textlength" : "textLength",
            "viewbox" : "viewBox",
            "viewtarget" : "viewTarget",
            "xchannelselector" : "xChannelSelector",
            "ychannelselector" : "yChannelSelector",
            "zoomandpan" : "zoomAndPan"
            }
        for originalName in token["data"].keys():
            if originalName in replacements:
                svgName = replacements[originalName]
                token["data"][svgName] = token["data"][originalName]
                del token["data"][originalName]

    def adjustForeignAttributes(self, token):
        replacements = {
            "xlink:actuate":("xlink", "actuate", namespaces["xlink"]),
            "xlink:arcrole":("xlink", "arcrole", namespaces["xlink"]),
            "xlink:href":("xlink", "href", namespaces["xlink"]),
            "xlink:role":("xlink", "role", namespaces["xlink"]),
            "xlink:show":("xlink", "show", namespaces["xlink"]),
            "xlink:title":("xlink", "title", namespaces["xlink"]),
            "xlink:type":("xlink", "type", namespaces["xlink"]),
            "xml:base":("xml", "base", namespaces["xml"]),
            "xml:lang":("xml", "lang", namespaces["xml"]),
            "xml:space":("xml", "space", namespaces["xml"]),
            "xmlns":(None, "xmlns", namespaces["xmlns"]),
            "xmlns:xlink":("xmlns", "xlink", namespaces["xmlns"])
            }

        for originalName in token["data"].iterkeys():
            if originalName in replacements:
                foreignName = replacements[originalName]
                token["data"][foreignName] = token["data"][originalName]
                del token["data"][originalName]

    def resetInsertionMode(self):
        # The name of this method is mostly historical. (It's also used in the
        # specification.)
        last = False
        newModes = {
            "select":"inSelect",
            "td":"inCell",
            "th":"inCell",
            "tr":"inRow",
            "tbody":"inTableBody",
            "thead":"inTableBody",
            "tfoot":"inTableBody",
            "caption":"inCaption",
            "colgroup":"inColumnGroup",
            "table":"inTable",
            "head":"inBody",
            "body":"inBody",
            "frameset":"inFrameset"
        }
        for node in self.tree.openElements[::-1]:
            nodeName = node.name
            if node == self.tree.openElements[0]:
                last = True
                if nodeName not in ['td', 'th']:
                    # XXX
                    assert self.innerHTML
                    nodeName = self.innerHTML
            # Check for conditions that should only happen in the innerHTML
            # case
            if nodeName in ("select", "colgroup", "head", "frameset"):
                # XXX
                assert self.innerHTML
            if nodeName in newModes:
                self.phase = self.phases[newModes[nodeName]]
                break
            elif node.namespace in (namespaces["mathml"], namespaces["svg"]):
                self.phase = self.phases["inForeignContent"]
                self.secondaryPhase = self.phases["inBody"]
                break
            elif nodeName == "html":
                if self.tree.headPointer is None:
                    self.phase = self.phases["beforeHead"]
                else:
                   self.phase = self.phases["afterHead"]
                break
            elif last:
                self.phase = self.phases["inBody"]
                break

    def parseRCDataRawtext(self, token, contentType):
        """Generic RCDATA/RAWTEXT Parsing algorithm
        contentType - RCDATA or RAWTEXT
        """
        assert contentType in ("RAWTEXT", "RCDATA")
        
        element = self.tree.insertElement(token)
        
        if contentType == "RAWTEXT":
            self.tokenizer.state = self.tokenizer.rawtextState
        else:
            self.tokenizer.state = self.tokenizer.rcdataState

        self.originalPhase = self.phase

        self.phase = self.phases["text"]

class Phase(object):
    """Base class for helper object that implements each phase of processing
    """
    # Order should be (they can be omitted):
    # * EOF
    # * Comment
    # * Doctype
    # * SpaceCharacters
    # * Characters
    # * StartTag
    #   - startTag* methods
    # * EndTag
    #   - endTag* methods

    def __init__(self, parser, tree):
        self.parser = parser
        self.tree = tree

    def processEOF(self):
        raise NotImplementedError

    def processComment(self, token):
        # For most phases the following is correct. Where it's not it will be
        # overridden.
        self.tree.insertComment(token, self.tree.openElements[-1])

    def processDoctype(self, token):
        self.parser.parseError("unexpected-doctype")

    def processCharacters(self, token):
        self.tree.insertText(token["data"])

    def processSpaceCharacters(self, token):
        self.tree.insertText(token["data"])

    def processStartTag(self, token):
        self.startTagHandler[token["name"]](token)

    def startTagHtml(self, token):
        if self.parser.firstStartTag == False and token["name"] == "html":
           self.parser.parseError("non-html-root")
        # XXX Need a check here to see if the first start tag token emitted is
        # this token... If it's not, invoke self.parser.parseError().
        for attr, value in token["data"].iteritems():
            if attr not in self.tree.openElements[0].attributes:
                self.tree.openElements[0].attributes[attr] = value
        self.parser.firstStartTag = False

    def processEndTag(self, token):
        self.endTagHandler[token["name"]](token)

class InitialPhase(Phase):
    def processSpaceCharacters(self, token):
        pass
    
    def processComment(self, token):
        self.tree.insertComment(token, self.tree.document)

    def processDoctype(self, token):
        name = token["name"]
        publicId = token["publicId"]
        systemId = token["systemId"]
        correct = token["correct"]

        if (name != "html" or publicId != None or
            systemId != None and systemId != "about:legacy-compat"):
            self.parser.parseError("unknown-doctype")
        
        if publicId is None:
            publicId = ""
            
        self.tree.insertDoctype(token)

        if publicId != "":
            publicId = publicId.translate(asciiUpper2Lower)

        if (not correct or token["name"] != "html"
            or publicId.startswith( 
            ("+//silmaril//dtd html pro v0r11 19970101//",
             "-//advasoft ltd//dtd html 3.0 aswedit + extensions//",
             "-//as//dtd html 3.0 aswedit + extensions//",
             "-//ietf//dtd html 2.0 level 1//",
             "-//ietf//dtd html 2.0 level 2//",
             "-//ietf//dtd html 2.0 strict level 1//",
             "-//ietf//dtd html 2.0 strict level 2//",
             "-//ietf//dtd html 2.0 strict//",
             "-//ietf//dtd html 2.0//",
             "-//ietf//dtd html 2.1e//",
             "-//ietf//dtd html 3.0//",
             "-//ietf//dtd html 3.2 final//",
             "-//ietf//dtd html 3.2//",
             "-//ietf//dtd html 3//",
             "-//ietf//dtd html level 0//",
             "-//ietf//dtd html level 1//",
             "-//ietf//dtd html level 2//",
             "-//ietf//dtd html level 3//",
             "-//ietf//dtd html strict level 0//",
             "-//ietf//dtd html strict level 1//",
             "-//ietf//dtd html strict level 2//",
             "-//ietf//dtd html strict level 3//",
             "-//ietf//dtd html strict//",
             "-//ietf//dtd html//",
             "-//metrius//dtd metrius presentational//",
             "-//microsoft//dtd internet explorer 2.0 html strict//",
             "-//microsoft//dtd internet explorer 2.0 html//",
             "-//microsoft//dtd internet explorer 2.0 tables//",
             "-//microsoft//dtd internet explorer 3.0 html strict//",
             "-//microsoft//dtd internet explorer 3.0 html//",
             "-//microsoft//dtd internet explorer 3.0 tables//",
             "-//netscape comm. corp.//dtd html//",
             "-//netscape comm. corp.//dtd strict html//",
             "-//o'reilly and associates//dtd html 2.0//",
             "-//o'reilly and associates//dtd html extended 1.0//",
             "-//o'reilly and associates//dtd html extended relaxed 1.0//",
             "-//softquad software//dtd hotmetal pro 6.0::19990601::extensions to html 4.0//",
             "-//softquad//dtd hotmetal pro 4.0::19971010::extensions to html 4.0//",
             "-//spyglass//dtd html 2.0 extended//",
             "-//sq//dtd html 2.0 hotmetal + extensions//",
             "-//sun microsystems corp.//dtd hotjava html//",
             "-//sun microsystems corp.//dtd hotjava strict html//",
             "-//w3c//dtd html 3 1995-03-24//",
             "-//w3c//dtd html 3.2 draft//",
             "-//w3c//dtd html 3.2 final//",
             "-//w3c//dtd html 3.2//",
             "-//w3c//dtd html 3.2s draft//",
             "-//w3c//dtd html 4.0 frameset//",
             "-//w3c//dtd html 4.0 transitional//",
             "-//w3c//dtd html experimental 19960712//",
             "-//w3c//dtd html experimental 970421//",
             "-//w3c//dtd w3 html//",
             "-//w3o//dtd w3 html 3.0//",
             "-//webtechs//dtd mozilla html 2.0//",
             "-//webtechs//dtd mozilla html//"))
            or publicId in
                ("-//w3o//dtd w3 html strict 3.0//en//",
                 "-/w3c/dtd html 4.0 transitional/en",
                 "html")
            or publicId.startswith(
                ("-//w3c//dtd html 4.01 frameset//",
                 "-//w3c//dtd html 4.01 transitional//")) and 
                systemId == None
            or systemId and systemId.lower() == "http://www.ibm.com/data/dtd/v11/ibmxhtml1-transitional.dtd"):
            self.parser.compatMode = "quirks"
        elif (publicId.startswith(
                ("-//w3c//dtd xhtml 1.0 frameset//",
                 "-//w3c//dtd xhtml 1.0 transitional//"))
              or publicId.startswith(
                  ("-//w3c//dtd html 4.01 frameset//",
                   "-//w3c//dtd html 4.01 transitional//")) and 
                  systemId != None):
            self.parser.compatMode = "limited quirks"

        self.parser.phase = self.parser.phases["beforeHtml"]
    
    def anythingElse(self):
        self.parser.compatMode = "quirks"
        self.parser.phase = self.parser.phases["beforeHtml"]

    def processCharacters(self, token):
        self.parser.parseError("expected-doctype-but-got-chars")
        self.anythingElse()
        self.parser.phase.processCharacters(token)

    def processStartTag(self, token):
        self.parser.parseError("expected-doctype-but-got-start-tag",
          {"name": token["name"]})
        self.anythingElse()
        self.parser.phase.processStartTag(token)

    def processEndTag(self, token):
        self.parser.parseError("expected-doctype-but-got-end-tag",
          {"name": token["name"]})
        self.anythingElse()
        self.parser.phase.processEndTag(token)
        
    def processEOF(self):
        self.parser.parseError("expected-doctype-but-got-eof")
        self.anythingElse()
        self.parser.phase.processEOF()


class BeforeHtmlPhase(Phase):
    # helper methods
    def insertHtmlElement(self):
        self.tree.insertRoot(impliedTagToken("html", "StartTag"))
        self.parser.phase = self.parser.phases["beforeHead"]

    # other
    def processEOF(self):
        self.insertHtmlElement()
        self.parser.phase.processEOF()

    def processComment(self, token):
        self.tree.insertComment(token, self.tree.document)

    def processSpaceCharacters(self, token):
        pass

    def processCharacters(self, token):
        self.insertHtmlElement()
        self.parser.phase.processCharacters(token)

    def processStartTag(self, token):
        if token["name"] == "html":
            self.parser.firstStartTag = True
        self.insertHtmlElement()
        self.parser.phase.processStartTag(token)

    def processEndTag(self, token):
        if token["name"] not in ("head", "body", "html", "br"):
            self.parser.parseError("unexpected-end-tag-before-html",
              {"name": token["name"]})
        else:
            self.insertHtmlElement()
            self.parser.phase.processEndTag(token)


class BeforeHeadPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("head", self.startTagHead)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            (("head", "body", "html", "br"), self.endTagImplyHead)
        ])
        self.endTagHandler.default = self.endTagOther

    def processEOF(self):
        self.startTagHead(impliedTagToken("head", "StartTag"))
        self.parser.phase.processEOF()

    def processSpaceCharacters(self, token):
        pass

    def processCharacters(self, token):
        self.startTagHead(impliedTagToken("head", "StartTag"))
        self.parser.phase.processCharacters(token)

    def startTagHtml(self, token):
        self.parser.phases["inBody"].processStartTag(token)

    def startTagHead(self, token):
        self.tree.insertElement(token)
        self.tree.headPointer = self.tree.openElements[-1]
        self.parser.phase = self.parser.phases["inHead"]

    def startTagOther(self, token):
        self.startTagHead(impliedTagToken("head", "StartTag"))
        self.parser.phase.processStartTag(token)

    def endTagImplyHead(self, token):
        self.startTagHead(impliedTagToken("head", "StartTag"))
        self.parser.phase.processEndTag(token)

    def endTagOther(self, token):
        self.parser.parseError("end-tag-after-implied-root",
          {"name": token["name"]})

class InHeadPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler =  utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("title", self.startTagTitle),
            (("noscript", "noframes", "style"), self.startTagNoScriptNoFramesStyle),
            ("script", self.startTagScript),
            (("base", "link", "command"), 
             self.startTagBaseLinkCommand),
            ("meta", self.startTagMeta),
            ("head", self.startTagHead)
        ])
        self.startTagHandler.default = self.startTagOther

        self. endTagHandler = utils.MethodDispatcher([
            ("head", self.endTagHead),
            (("br", "html", "body"), self.endTagHtmlBodyBr)
        ])
        self.endTagHandler.default = self.endTagOther

    # helper
    def appendToHead(self, element):
        if self.tree.headPointer is not None:
            self.tree.headPointer.appendChild(element)
        else:
            assert self.parser.innerHTML
            self.tree.openElementsw[-1].appendChild(element)

    # the real thing
    def processEOF (self):
        self.anythingElse()
        self.parser.phase.processEOF()

    def processCharacters(self, token):
        self.anythingElse()
        self.parser.phase.processCharacters(token)

    def startTagHtml(self, token):
        self.parser.phases["inBody"].processStartTag(token)

    def startTagHead(self, token):
        self.parser.parseError("two-heads-are-not-better-than-one")

    def startTagBaseLinkCommand(self, token):
        self.tree.insertElement(token)
        self.tree.openElements.pop()
        token["selfClosingAcknowledged"] = True

    def startTagMeta(self, token):
        self.tree.insertElement(token)
        self.tree.openElements.pop()
        token["selfClosingAcknowledged"] = True

        attributes = token["data"]
        if self.parser.tokenizer.stream.charEncoding[1] == "tentative":
            if "charset" in attributes:
                self.parser.tokenizer.stream.changeEncoding(attributes["charset"])
            elif "content" in attributes:
                # Encoding it as UTF-8 here is a hack, as really we should pass
                # the abstract Unicode string, and just use the
                # ContentAttrParser on that, but using UTF-8 allows all chars
                # to be encoded and as a ASCII-superset works.
                data = inputstream.EncodingBytes(attributes["content"].encode("utf-8"))
                parser = inputstream.ContentAttrParser(data)
                codec = parser.parse()
                self.parser.tokenizer.stream.changeEncoding(codec)

    def startTagTitle(self, token):
        self.parser.parseRCDataRawtext(token, "RCDATA")

    def startTagNoScriptNoFramesStyle(self, token):
        #Need to decide whether to implement the scripting-disabled case
        self.parser.parseRCDataRawtext(token, "RAWTEXT")

    def startTagScript(self, token):
        self.tree.insertElement(token)
        self.parser.tokenizer.state = self.parser.tokenizer.scriptDataState
        self.parser.originalPhase = self.parser.phase
        self.parser.phase = self.parser.phases["text"]

    def startTagOther(self, token):
        self.anythingElse()
        self.parser.phase.processStartTag(token)

    def endTagHead(self, token):
        node = self.parser.tree.openElements.pop()
        assert node.name == "head", "Expected head got %s"%node.name
        self.parser.phase = self.parser.phases["afterHead"]

    def endTagHtmlBodyBr(self, token):
        self.anythingElse()
        self.parser.phase.processEndTag(token)

    def endTagOther(self, token):
        self.parser.parseError("unexpected-end-tag", {"name": token["name"]})

    def anythingElse(self):
        self.endTagHead(impliedTagToken("head"))
        

# XXX If we implement a parser for which scripting is disabled we need to
# implement this phase.
#
# class InHeadNoScriptPhase(Phase):

class AfterHeadPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("body", self.startTagBody),
            ("frameset", self.startTagFrameset),
            (("base", "link", "meta", "noframes", "script", "style", "title"),
              self.startTagFromHead),
            ("head", self.startTagHead)
        ])
        self.startTagHandler.default = self.startTagOther
        self.endTagHandler = utils.MethodDispatcher([(("body", "html", "br"), 
                                                      self.endTagHtmlBodyBr)])
        self.endTagHandler.default = self.endTagOther

    def processEOF(self):
        self.anythingElse()
        self.parser.phase.processEOF()

    def processCharacters(self, token):
        self.anythingElse()
        self.parser.phase.processCharacters(token)

    def startTagBody(self, token):
        self.parser.framesetOK = False
        self.tree.insertElement(token)
        self.parser.phase = self.parser.phases["inBody"]

    def startTagFrameset(self, token):
        self.tree.insertElement(token)
        self.parser.phase = self.parser.phases["inFrameset"]

    def startTagFromHead(self, token):
        self.parser.parseError("unexpected-start-tag-out-of-my-head",
          {"name": token["name"]})
        self.tree.openElements.append(self.tree.headPointer)
        self.parser.phases["inHead"].processStartTag(token)
        for node in self.tree.openElements[::-1]:
            if node.name == "head":
                self.tree.openElements.remove(node)
                break

    def startTagHead(self, token):
        self.parser.parseError("unexpected-start-tag", {"name":token["name"]})

    def startTagOther(self, token):
        self.anythingElse()
        self.parser.phase.processStartTag(token)

    def endTagHtmlBodyBr(self, token):
        self.anythingElse()
        self.parser.phase.processEndTag(token)

    def endTagOther(self, token):
        self.parser.parseError("unexpected-end-tag", {"name":token["name"]})

    def anythingElse(self):
        self.tree.insertElement(impliedTagToken("body", "StartTag"))
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.framesetOK = True


class InBodyPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#parsing-main-inbody
    # the really-really-really-very crazy mode
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        #Keep a ref to this for special handling of whitespace in <pre>
        self.processSpaceCharactersNonPre = self.processSpaceCharacters

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            (("base", "command", "link", "meta", "noframes", "script", "style", 
              "title"), self.startTagProcessInHead),
            ("body", self.startTagBody),
            ("frameset", self.startTagFrameset),
            (("address", "article", "aside", "blockquote", "center", "datagrid",
              "details", "dir", "div", "dl", "fieldset", "figure",
              "footer", "header", "hgroup", "menu", "nav", "ol", "p",
              "section", "ul"),
              self.startTagCloseP),
            (("pre", "listing"), self.startTagPreListing),
            ("form", self.startTagForm),
            (("li", "dd", "dt"), self.startTagListItem),
            ("plaintext",self.startTagPlaintext),
            (headingElements, self.startTagHeading),
            ("a", self.startTagA),
            (("b", "big", "code", "em", "font", "i", "s", "small", "strike", 
              "strong", "tt", "u"),self.startTagFormatting),
            ("nobr", self.startTagNobr),
            ("button", self.startTagButton),
            (("applet", "marquee", "object"), self.startTagAppletMarqueeObject),
            ("xmp", self.startTagXmp),
            ("table", self.startTagTable),
            (("area", "basefont", "bgsound", "br", "embed", "img", "input",
              "keygen", "spacer", "wbr"), self.startTagVoidFormatting),
            (("param", "source"), self.startTagParamSource),
            ("hr", self.startTagHr),
            ("image", self.startTagImage),
            ("isindex", self.startTagIsIndex),
            ("textarea", self.startTagTextarea),
            ("iframe", self.startTagIFrame),
            (("noembed", "noframes", "noscript"), self.startTagRawtext),
            ("select", self.startTagSelect),
            (("rp", "rt"), self.startTagRpRt),
            (("option", "optgroup"), self.startTagOpt),
            (("math"), self.startTagMath),
            (("svg"), self.startTagSvg),
            (("caption", "col", "colgroup", "frame", "head",
              "tbody", "td", "tfoot", "th", "thead",
              "tr"), self.startTagMisplaced)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("body",self.endTagBody),
            ("html",self.endTagHtml),
            (("address", "article", "aside", "blockquote", "center", "datagrid",
              "details", "dir", "div", "dl", "fieldset", "figure",
              "footer", "header", "hgroup", "listing", "menu", "nav", "ol", "pre", 
              "section", "ul"), self.endTagBlock),
            ("form", self.endTagForm),
            ("p",self.endTagP),
            (("dd", "dt", "li"), self.endTagListItem),
            (headingElements, self.endTagHeading),
            (("a", "b", "big", "code", "em", "font", "i", "nobr", "s", "small",
              "strike", "strong", "tt", "u"), self.endTagFormatting),
            (("applet", "button", "marquee", "object"), self.endTagAppletButtonMarqueeObject),
            ("br", self.endTagBr),
            ])
        self.endTagHandler.default = self.endTagOther

    # helper
    def addFormattingElement(self, token):
        self.tree.insertElement(token)
        self.tree.activeFormattingElements.append(
            self.tree.openElements[-1])

    # the real deal
    def processEOF(self):
        allowed_elements = frozenset(("dd", "dt", "li", "p", "tbody", "td",
                                      "tfoot", "th", "thead", "tr", "body",
                                      "html"))
        for node in self.tree.openElements[::-1]:
            if node.name not in allowed_elements:
                self.parser.parseError("expected-closing-tag-but-got-eof")
                break
        #Stop parsing
    
    def processSpaceCharactersDropNewline(self, token):
        # Sometimes (start of <pre>, <listing>, and <textarea> blocks) we
        # want to drop leading newlines
        data = token["data"]
        self.processSpaceCharacters = self.processSpaceCharactersNonPre
        if (data.startswith("\n") and
            self.tree.openElements[-1].name in ("pre", "listing", "textarea")
            and not self.tree.openElements[-1].hasContent()):
            data = data[1:]
        if data:
            self.tree.reconstructActiveFormattingElements()
            self.tree.insertText(data)

    def processCharacters(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.tree.insertText(token["data"])
        self.parser.framesetOK = False

    def processSpaceCharacters(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.tree.insertText(token["data"])

    def startTagProcessInHead(self, token):
        self.parser.phases["inHead"].processStartTag(token)

    def startTagBody(self, token):
        self.parser.parseError("unexpected-start-tag", {"name": "body"})
        if (len(self.tree.openElements) == 1
            or self.tree.openElements[1].name != "body"):
            assert self.parser.innerHTML
        else:
            for attr, value in token["data"].iteritems():
                if attr not in self.tree.openElements[1].attributes:
                    self.tree.openElements[1].attributes[attr] = value

    def startTagFrameset(self, token):
        self.parser.parseError("unexpected-start-tag", {"name": "frameset"})
        if (len(self.tree.openElements) == 1 or self.tree.openElements[1].name != "body"):
            assert self.parser.innerHTML
        elif not self.parser.framesetOK:
            pass
        else:
            if self.tree.openElements[1].parent:
                self.tree.openElements[1].parent.removeChild(self.tree.openElements[1])
            while self.tree.openElements[-1].name != "html":
                self.tree.openElements.pop()
            self.tree.insertElement(token)
            self.parser.phase = self.parser.phases["inFrameset"]

    def startTagCloseP(self, token):
        if self.tree.elementInScope("p"):
            self.endTagP(impliedTagToken("p"))
        self.tree.insertElement(token)
    
    def startTagPreListing(self, token):
        if self.tree.elementInScope("p"):
            self.endTagP(impliedTagToken("p"))
        self.tree.insertElement(token)
        self.parser.framesetOK = False
        self.processSpaceCharacters = self.processSpaceCharactersDropNewline

    def startTagForm(self, token):
        if self.tree.formPointer:
            self.parser.parseError(u"unexpected-start-tag", {"name": "form"})
        else:
            if self.tree.elementInScope("p"):
                self.endTagP("p")
            self.tree.insertElement(token)
            self.tree.formPointer = self.tree.openElements[-1]

    def startTagListItem(self, token):
        self.parser.framesetOK = False

        stopNamesMap = {"li":["li"],
                        "dt":["dt", "dd"],
                        "dd":["dt", "dd"]}
        stopNames = stopNamesMap[token["name"]]
        for node in reversed(self.tree.openElements):
            if node.name in stopNames:
                self.parser.phase.processEndTag(
                    impliedTagToken(node.name, "EndTag"))
                break
            if (node.nameTuple in (scopingElements | specialElements) and
                node.name not in ("address", "div", "p")):
                break
            
        if self.tree.elementInScope("p"):
            self.parser.phase.processEndTag(
                impliedTagToken("p", "EndTag"))

        self.tree.insertElement(token)

    def startTagPlaintext(self, token):
        if self.tree.elementInScope("p"):
            self.endTagP(impliedTagToken("p"))
        self.tree.insertElement(token)
        self.parser.tokenizer.state = self.parser.tokenizer.plaintextState

    def startTagHeading(self, token):
        if self.tree.elementInScope("p"):
            self.endTagP(impliedTagToken("p"))
        if self.tree.openElements[-1].name in headingElements:
            self.parser.parseError("unexpected-start-tag", {"name": token["name"]})
            self.tree.openElements.pop()
        self.tree.insertElement(token)

    def startTagA(self, token):
        afeAElement = self.tree.elementInActiveFormattingElements("a")
        if afeAElement:
            self.parser.parseError("unexpected-start-tag-implies-end-tag",
              {"startName": "a", "endName": "a"})
            self.endTagFormatting(impliedTagToken("a"))
            if afeAElement in self.tree.openElements:
                self.tree.openElements.remove(afeAElement)
            if afeAElement in self.tree.activeFormattingElements:
                self.tree.activeFormattingElements.remove(afeAElement)
        self.tree.reconstructActiveFormattingElements()
        self.addFormattingElement(token)

    def startTagFormatting(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.addFormattingElement(token)

    def startTagNobr(self, token):
        self.tree.reconstructActiveFormattingElements()
        if self.tree.elementInScope("nobr"):
            self.parser.parseError("unexpected-start-tag-implies-end-tag",
              {"startName": "nobr", "endName": "nobr"})
            self.processEndTag(impliedTagToken("nobr"))
            # XXX Need tests that trigger the following
            self.tree.reconstructActiveFormattingElements()
        self.addFormattingElement(token)

    def startTagButton(self, token):
        if self.tree.elementInScope("button"):
            self.parser.parseError("unexpected-start-tag-implies-end-tag",
              {"startName": "button", "endName": "button"})
            self.processEndTag(impliedTagToken("button"))
            self.parser.phase.processStartTag(token)
        else:
            self.tree.reconstructActiveFormattingElements()
            self.tree.insertElement(token)
            self.tree.activeFormattingElements.append(Marker)
            self.parser.framesetOK = False

    def startTagAppletMarqueeObject(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.tree.insertElement(token)
        self.tree.activeFormattingElements.append(Marker)
        self.parser.framesetOK = False

    def startTagXmp(self, token):
        if self.tree.elementInScope("p"):
            self.endTagP(impliedTagToken("p"))
        self.tree.reconstructActiveFormattingElements()
        self.parser.framesetOK = False
        self.parser.parseRCDataRawtext(token, "RAWTEXT")

    def startTagTable(self, token):
        if self.parser.compatMode != "quirks":
            if self.tree.elementInScope("p"):
                self.processEndTag(impliedTagToken("p"))
        self.tree.insertElement(token)
        self.parser.framesetOK = False
        self.parser.phase = self.parser.phases["inTable"]

    def startTagVoidFormatting(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.tree.insertElement(token)
        self.tree.openElements.pop()
        token["selfClosingAcknowledged"] = True
        self.parser.framesetOK = False

    def startTagParamSource(self, token):
        self.tree.insertElement(token)
        self.tree.openElements.pop()
        token["selfClosingAcknowledged"] = True

    def startTagHr(self, token):
        if self.tree.elementInScope("p"):
            self.endTagP(impliedTagToken("p"))
        self.tree.insertElement(token)
        self.tree.openElements.pop()
        token["selfClosingAcknowledged"] = True
        self.parser.framesetOK = False

    def startTagImage(self, token):
        # No really...
        self.parser.parseError("unexpected-start-tag-treated-as",
          {"originalName": "image", "newName": "img"})
        self.processStartTag(impliedTagToken("img", "StartTag",
                                             attributes=token["data"],
                                             selfClosing=token["selfClosing"]))

    def startTagIsIndex(self, token):
        self.parser.parseError("deprecated-tag", {"name": "isindex"})
        if self.tree.formPointer:
            return
        form_attrs = {}
        if "action" in token["data"]:
            form_attrs["action"] = token["data"]["action"]
        self.processStartTag(impliedTagToken("form", "StartTag",
                                             attributes=form_attrs))
        self.processStartTag(impliedTagToken("hr", "StartTag"))
        self.processStartTag(impliedTagToken("label", "StartTag"))
        # XXX Localization ...
        if "prompt" in token["data"]:
            prompt = token["data"]["prompt"]
        else:
            prompt = "This is a searchable index. Insert your search keywords here: "
        self.processCharacters(
            {"type":tokenTypes["Characters"], "data":prompt})
        attributes = token["data"].copy()
        if "action" in attributes:
            del attributes["action"]
        if "prompt" in attributes:
            del attributes["prompt"]
        attributes["name"] = "isindex"
        self.processStartTag(impliedTagToken("input", "StartTag", 
                                             attributes = attributes,
                                             selfClosing = 
                                             token["selfClosing"]))
        self.processEndTag(impliedTagToken("label"))
        self.processStartTag(impliedTagToken("hr", "StartTag"))
        self.processEndTag(impliedTagToken("form"))

    def startTagTextarea(self, token):
        self.tree.insertElement(token)
        self.parser.tokenizer.state = self.parser.tokenizer.rcdataState
        self.processSpaceCharacters = self.processSpaceCharactersDropNewline
        self.parser.framesetOK = False

    def startTagIFrame(self, token):
        self.parser.framesetOK = False
        self.startTagRawtext(token)

    def startTagRawtext(self, token):
        """iframe, noembed noframes, noscript(if scripting enabled)"""
        self.parser.parseRCDataRawtext(token, "RAWTEXT")

    def startTagOpt(self, token):
        if self.tree.elementInScope("option"):
            self.parser.phase.processEndTag(impliedTagToken("option"))
        self.tree.reconstructActiveFormattingElements()
        self.parser.tree.insertElement(token)

    def startTagSelect(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.tree.insertElement(token)
        self.parser.framesetOK = False
        if self.parser.phase in (self.parser.phases["inTable"],
                                 self.parser.phases["inCaption"],
                                 self.parser.phases["inColumnGroup"],
                                 self.parser.phases["inTableBody"], 
                                 self.parser.phases["inRow"],
                                 self.parser.phases["inCell"]):
            self.parser.phase = self.parser.phases["inSelectInTable"]
        else:
            self.parser.phase = self.parser.phases["inSelect"]

    def startTagRpRt(self, token):
        if self.tree.elementInScope("ruby"):
            self.tree.generateImpliedEndTags()
            if self.tree.openElements[-1].name != "ruby":
                self.parser.parseError()
                while self.tree.openElements[-1].name != "ruby":
                    self.tree.openElements.pop()
        self.tree.insertElement(token)

    def startTagMath(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.parser.adjustMathMLAttributes(token)
        self.parser.adjustForeignAttributes(token)
        token["namespace"] = namespaces["mathml"]
        self.tree.insertElement(token)
        #Need to get the parse error right for the case where the token 
        #has a namespace not equal to the xmlns attribute
        if self.parser.phase != self.parser.phases["inForeignContent"]:
            self.parser.secondaryPhase = self.parser.phase
        self.parser.phase = self.parser.phases["inForeignContent"]
        if token["selfClosing"]:
            self.tree.openElements.pop()
            token["selfClosingAcknowledged"] = True

    def startTagSvg(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.parser.adjustSVGAttributes(token)
        self.parser.adjustForeignAttributes(token)
        token["namespace"] = namespaces["svg"]
        self.tree.insertElement(token)
        #Need to get the parse error right for the case where the token 
        #has a namespace not equal to the xmlns attribute
        if self.parser.phase != self.parser.phases["inForeignContent"]:
            self.parser.secondaryPhase = self.parser.phase
        self.parser.phase = self.parser.phases["inForeignContent"]
        if token["selfClosing"]:
            self.tree.openElements.pop()
            token["selfClosingAcknowledged"] = True

    def startTagMisplaced(self, token):
        """ Elements that should be children of other elements that have a
        different insertion mode; here they are ignored
        "caption", "col", "colgroup", "frame", "frameset", "head",
        "option", "optgroup", "tbody", "td", "tfoot", "th", "thead",
        "tr", "noscript"
        """
        self.parser.parseError("unexpected-start-tag-ignored", {"name": token["name"]})

    def startTagOther(self, token):
        self.tree.reconstructActiveFormattingElements()
        self.tree.insertElement(token)

    def endTagP(self, token):
        if not self.tree.elementInScope("p"):
            self.startTagCloseP(impliedTagToken("p", "StartTag"))
            self.parser.parseError("unexpected-end-tag", {"name": "p"})
            self.endTagP(impliedTagToken("p", "EndTag"))
        else:
            self.tree.generateImpliedEndTags("p")
            if self.tree.openElements[-1].name != "p":
                self.parser.parseError("unexpected-end-tag", {"name": "p"})
            node = self.tree.openElements.pop()
            while node.name != "p":
                node = self.tree.openElements.pop()

    def endTagBody(self, token):
        if not self.tree.elementInScope("body"):
            self.parser.parseError()
            return
        elif self.tree.openElements[-1].name != "body":
            for node in self.tree.openElements[2:]:
                if node.name not in frozenset(("dd", "dt", "li", "optgroup",
                                               "option", "p", "rp", "rt",
                                               "tbody", "td", "tfoot",
                                               "th", "thead", "tr", "body",
                                               "html")):
                    #Not sure this is the correct name for the parse error
                    self.parser.parseError(
                        "expected-one-end-tag-but-got-another",
                        {"expectedName": "body", "gotName": node.name})
                    break
        self.parser.phase = self.parser.phases["afterBody"]

    def endTagHtml(self, token):
        #We repeat the test for the body end tag token being ignored here
        if self.tree.elementInScope("body"):
            self.endTagBody(impliedTagToken("body"))
            self.parser.phase.processEndTag(token)

    def endTagBlock(self, token):
        #Put us back in the right whitespace handling mode
        if token["name"] == "pre":
            self.processSpaceCharacters = self.processSpaceCharactersNonPre
        inScope = self.tree.elementInScope(token["name"])
        if inScope:
            self.tree.generateImpliedEndTags()
        if self.tree.openElements[-1].name != token["name"]:
             self.parser.parseError("end-tag-too-early", {"name": token["name"]})
        if inScope:
            node = self.tree.openElements.pop()
            while node.name != token["name"]:
                node = self.tree.openElements.pop()

    def endTagForm(self, token):
        node = self.tree.formPointer
        self.tree.formPointer = None
        if node is None or not self.tree.elementInScope(node):
            self.parser.parseError("unexpected-end-tag",
                                   {"name":"form"})
        else:
            self.tree.generateImpliedEndTags()
            if self.tree.openElements[-1].name != node:
                self.parser.parseError("end-tag-too-early-ignored",
                                       {"name": "form"})
                self.tree.openElements.remove(node)

    def endTagListItem(self, token):
        if token["name"] == "li":
            variant = "list"
        else:
            variant = None
        if not self.tree.elementInScope(token["name"], variant=variant):
            self.parser.parseError("unexpected-end-tag", {"name": token["name"]})
        else:
            self.tree.generateImpliedEndTags(exclude = token["name"])
            if self.tree.openElements[-1].name != token["name"]:
                self.parser.parseError(
                    "end-tag-too-early",
                    {"name": token["name"]})
            node = self.tree.openElements.pop()
            while node.name != token["name"]:
                node = self.tree.openElements.pop()

    def endTagHeading(self, token):
        for item in headingElements:
            if self.tree.elementInScope(item):
                self.tree.generateImpliedEndTags()
                break
        if self.tree.openElements[-1].name != token["name"]:
            self.parser.parseError("end-tag-too-early", {"name": token["name"]})

        for item in headingElements:
            if self.tree.elementInScope(item):
                item = self.tree.openElements.pop()
                while item.name not in headingElements:
                    item = self.tree.openElements.pop()
                break

    def endTagFormatting(self, token):
        """The much-feared adoption agency algorithm"""
        # http://www.whatwg.org/specs/web-apps/current-work/#adoptionAgency
        # XXX Better parseError messages appreciated.
        name = token["name"]
        while True:
            # Step 1 paragraph 1
            formattingElement = self.tree.elementInActiveFormattingElements(
                token["name"])
            if not formattingElement or (formattingElement in 
                                        self.tree.openElements and
                                        not self.tree.elementInScope(
                    formattingElement.name)):
                self.parser.parseError("adoption-agency-1.1", {"name": token["name"]})
                return

            # Step 1 paragraph 2
            elif formattingElement not in self.tree.openElements:
                self.parser.parseError("adoption-agency-1.2", {"name": token["name"]})
                self.tree.activeFormattingElements.remove(formattingElement)
                return

            # Step 1 paragraph 3
            if formattingElement != self.tree.openElements[-1]:
                self.parser.parseError("adoption-agency-1.3", {"name": token["name"]})

            # Step 2
            # Start of the adoption agency algorithm proper
            afeIndex = self.tree.openElements.index(formattingElement)
            furthestBlock = None
            for element in self.tree.openElements[afeIndex:]:
                if (element.nameTuple in
                    specialElements | scopingElements):
                    furthestBlock = element
                    break

            # Step 3
            if furthestBlock is None:
                element = self.tree.openElements.pop()
                while element != formattingElement:
                    element = self.tree.openElements.pop()
                self.tree.activeFormattingElements.remove(element)
                return
            commonAncestor = self.tree.openElements[afeIndex-1]

            # Step 5
            #if furthestBlock.parent:
            #    furthestBlock.parent.removeChild(furthestBlock)

            # Step 5
            # The bookmark is supposed to help us identify where to reinsert
            # nodes in step 12. We have to ensure that we reinsert nodes after
            # the node before the active formatting element. Note the bookmark
            # can move in step 7.4
            bookmark = self.tree.activeFormattingElements.index(formattingElement)

            # Step 6
            lastNode = node = furthestBlock
            while True:
                # AT replace this with a function and recursion?
                # Node is element before node in open elements
                node = self.tree.openElements[
                    self.tree.openElements.index(node)-1]
                while node not in self.tree.activeFormattingElements:
                    tmpNode = node
                    node = self.tree.openElements[
                        self.tree.openElements.index(node)-1]
                    self.tree.openElements.remove(tmpNode)
                # Step 6.3
                if node == formattingElement:
                    break
                # Step 6.4
                if lastNode == furthestBlock:
                    bookmark = (self.tree.activeFormattingElements.index(node)
                                + 1)
                # Step 6.5
                #cite = node.parent
                #if node.hasContent():
                clone = node.cloneNode()
                # Replace node with clone
                self.tree.activeFormattingElements[
                    self.tree.activeFormattingElements.index(node)] = clone
                self.tree.openElements[
                    self.tree.openElements.index(node)] = clone
                node = clone
                
                # Step 6.6
                # Remove lastNode from its parents, if any
                if lastNode.parent:
                    lastNode.parent.removeChild(lastNode)
                node.appendChild(lastNode)
                # Step 7.7
                lastNode = node
                # End of inner loop 

            # Step 7
            # Foster parent lastNode if commonAncestor is a
            # table, tbody, tfoot, thead, or tr we need to foster parent the 
            # lastNode
            if lastNode.parent:
                lastNode.parent.removeChild(lastNode)
            commonAncestor.appendChild(lastNode)

            # Step 8
            clone = formattingElement.cloneNode()

            # Step 9
            furthestBlock.reparentChildren(clone)

            # Step 10
            furthestBlock.appendChild(clone)

            # Step 11
            self.tree.activeFormattingElements.remove(formattingElement)
            self.tree.activeFormattingElements.insert(bookmark, clone)

            # Step 12
            self.tree.openElements.remove(formattingElement)
            self.tree.openElements.insert(
              self.tree.openElements.index(furthestBlock) + 1, clone)

    def endTagAppletButtonMarqueeObject(self, token):
        if self.tree.elementInScope(token["name"]):
            self.tree.generateImpliedEndTags()
        if self.tree.openElements[-1].name != token["name"]:
            self.parser.parseError("end-tag-too-early", {"name": token["name"]})

        if self.tree.elementInScope(token["name"]):
            element = self.tree.openElements.pop()
            while element.name != token["name"]:
                element = self.tree.openElements.pop()
            self.tree.clearActiveFormattingElements()

    def endTagBr(self, token):
        self.parser.parseError("unexpected-end-tag-treated-as",
          {"originalName": "br", "newName": "br element"})
        self.tree.reconstructActiveFormattingElements()
        self.tree.insertElement(impliedTagToken("br", "StartTag"))
        self.tree.openElements.pop()

    def endTagOther(self, token):
        for node in self.tree.openElements[::-1]:
            if node.name == token["name"]:
                self.tree.generateImpliedEndTags()
                if self.tree.openElements[-1].name != token["name"]:
                    self.parser.parseError("unexpected-end-tag", {"name": token["name"]})
                while self.tree.openElements.pop() != node:
                    pass
                break
            else:
                if (node.nameTuple in
                    specialElements | scopingElements):
                    self.parser.parseError("unexpected-end-tag", {"name": token["name"]})
                    break

class TextPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)
        self.startTagHandler = utils.MethodDispatcher([])
        self.startTagHandler.default = self.startTagOther
        self.endTagHandler = utils.MethodDispatcher([
                ("script", self.endTagScript)])
        self.endTagHandler.default = self.endTagOther

    def processCharacters(self, token):
        self.tree.insertText(token["data"])
    
    def processEOF(self):
        self.parser.parseError("expected-named-closing-tag-but-got-eof", 
                               self.tree.openElements[-1].name)
        self.tree.openElements.pop()
        self.parser.phase = self.parser.originalPhase
        self.parser.phase.processEOF()

    def startTagOther(self, token):
        assert False, "Tried to process start tag %s in RCDATA/RAWTEXT mode"%name

    def endTagScript(self, token):
        node = self.tree.openElements.pop()
        assert node.name == "script"
        self.parser.phase = self.parser.originalPhase
        #The rest of this method is all stuff that only happens if
        #document.write works
    
    def endTagOther(self, token):
        node = self.tree.openElements.pop()
        self.parser.phase = self.parser.originalPhase

class InTablePhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#in-table
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)
        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("caption", self.startTagCaption),
            ("colgroup", self.startTagColgroup),
            ("col", self.startTagCol),
            (("tbody", "tfoot", "thead"), self.startTagRowGroup),
            (("td", "th", "tr"), self.startTagImplyTbody),
            ("table", self.startTagTable),
            (("style", "script"), self.startTagStyleScript),
            ("input", self.startTagInput),
            ("form", self.startTagForm)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("table", self.endTagTable),
            (("body", "caption", "col", "colgroup", "html", "tbody", "td",
              "tfoot", "th", "thead", "tr"), self.endTagIgnore)
        ])
        self.endTagHandler.default = self.endTagOther

    # helper methods
    def clearStackToTableContext(self):
        # "clear the stack back to a table context"
        while self.tree.openElements[-1].name not in ("table", "html"):
            #self.parser.parseError("unexpected-implied-end-tag-in-table",
            #  {"name":  self.tree.openElements[-1].name})
            self.tree.openElements.pop()
        # When the current node is <html> it's an innerHTML case

    def getCurrentTable(self):
        i = -1
        while -i <= len(self.tree.openElements) and self.tree.openElements[i].name != "table":
             i -= 1
        if -i > len(self.tree.openElements):
            return self.tree.openElements[0]
        else:
            return self.tree.openElements[i]

    # processing methods
    def processEOF(self):
        if self.tree.openElements[-1].name != "html":
            self.parser.parseError("eof-in-table")
        else:
            assert self.parser.innerHTML
        #Stop parsing

    def processSpaceCharacters(self, token):
        originalPhase = self.parser.phase
        self.parser.phase = self.parser.phases["inTableText"]
        self.parser.phase.originalPhase = originalPhase
        self.parser.phase.characterTokens.append(token)

    def processCharacters(self, token):
        #If we get here there must be at least one non-whitespace character
        # Do the table magic!
        self.tree.insertFromTable = True
        self.parser.phases["inBody"].processCharacters(token)
        self.tree.insertFromTable = False

    def startTagCaption(self, token):
        self.clearStackToTableContext()
        self.tree.activeFormattingElements.append(Marker)
        self.tree.insertElement(token)
        self.parser.phase = self.parser.phases["inCaption"]

    def startTagColgroup(self, token):
        self.clearStackToTableContext()
        self.tree.insertElement(token)
        self.parser.phase = self.parser.phases["inColumnGroup"]

    def startTagCol(self, token):
        self.startTagColgroup(impliedTagToken("colgroup", "StartTag"))
        self.parser.phase.processStartTag(token)

    def startTagRowGroup(self, token):
        self.clearStackToTableContext()
        self.tree.insertElement(token)
        self.parser.phase = self.parser.phases["inTableBody"]

    def startTagImplyTbody(self, token):
        self.startTagRowGroup(impliedTagToken("tbody", "StartTag"))
        self.parser.phase.processStartTag(token)

    def startTagTable(self, token):
        self.parser.parseError("unexpected-start-tag-implies-end-tag",
          {"startName": "table", "endName": "table"})
        self.parser.phase.processEndTag(impliedTagToken("table"))
        if not self.parser.innerHTML:
            self.parser.phase.processStartTag(token)

    def startTagStyleScript(self, token):
        self.parser.phases["inHead"].processStartTag(token)

    def startTagInput(self, token):
        if ("type" in token["data"] and 
            token["data"]["type"].translate(asciiUpper2Lower) == "hidden"):
            self.parser.parseError("unexpected-hidden-input-in-table")
            self.tree.insertElement(token)
            # XXX associate with form
            self.tree.openElements.pop()
        else:
            self.startTagOther(token)

    def startTagForm(self, token):
        self.parser.parseError("unexpected-form-in-table")
        self.tree.insertElement(token)
        self.tree.openElements.pop()

    def startTagOther(self, token):
        self.parser.parseError("unexpected-start-tag-implies-table-voodoo", {"name": token["name"]})
        if "tainted" not in self.getCurrentTable()._flags:
            self.getCurrentTable()._flags.append("tainted")
        # Do the table magic!
        self.tree.insertFromTable = True
        self.parser.phases["inBody"].processStartTag(token)
        self.tree.insertFromTable = False

    def endTagTable(self, token):
        if self.tree.elementInScope("table", variant="table"):
            self.tree.generateImpliedEndTags()
            if self.tree.openElements[-1].name != "table":
                self.parser.parseError("end-tag-too-early-named",
                  {"gotName": "table",
                   "expectedName": self.tree.openElements[-1].name})
            while self.tree.openElements[-1].name != "table":
                self.tree.openElements.pop()
            self.tree.openElements.pop()
            self.parser.resetInsertionMode()
        else:
            # innerHTML case
            assert self.parser.innerHTML
            self.parser.parseError()

    def endTagIgnore(self, token):
        self.parser.parseError("unexpected-end-tag", {"name": token["name"]})

    def endTagOther(self, token):
        self.parser.parseError("unexpected-end-tag-implies-table-voodoo", {"name": token["name"]})
        if "tainted" not in self.getCurrentTable()._flags:
            self.getCurrentTable()._flags.append("tainted")
        # Do the table magic!
        self.tree.insertFromTable = True
        self.parser.phases["inBody"].processEndTag(token)
        self.tree.insertFromTable = False

class InTableTextPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)
        self.originalPhase = None
        self.characterTokens = []

    def flushCharacters(self):
        data = "".join([item["data"] for item in self.characterTokens])
        if any([item not in spaceCharacters for item in data]):
            token = {"type":tokenTypes["Characters"], "data":data}
            self.originalPhase.processCharacters(token)
        elif data:
            self.tree.insertText(data)
        self.characterTokens = []

    def processComment(self, token):
        self.flushCharacters()
        self.phase = self.originalPhase
        self.phase.processComment(token)

    def processEOF(self):
        self.flushCharacters()
        self.phase = self.originalPhase
        self.phase.processEOF()

    def processCharacters(self, token):
        self.characterTokens.append(token)

    def processSpaceCharacters(self, token):
        #pretty sure we should never reach here
        self.characterTokens.append(token)
#        assert False

    def processStartTag(self, token):        
        self.flushCharacters()
        self.phase = self.originalPhase
        self.phase.processStartTag(token)

    def processEndTag(self, token):
        self.flushCharacters()
        self.phase = self.originalPhase
        self.phase.processEndTag(token)
    

class InCaptionPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#in-caption
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            (("caption", "col", "colgroup", "tbody", "td", "tfoot", "th",
              "thead", "tr"), self.startTagTableElement)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("caption", self.endTagCaption),
            ("table", self.endTagTable),
            (("body", "col", "colgroup", "html", "tbody", "td", "tfoot", "th",
              "thead", "tr"), self.endTagIgnore)
        ])
        self.endTagHandler.default = self.endTagOther

    def ignoreEndTagCaption(self):
        return not self.tree.elementInScope("caption", variant="table")

    def processEOF(self):
        self.parser.phases["inBody"].processEOF()

    def processCharacters(self, token):
        self.parser.phases["inBody"].processCharacters(token)

    def startTagTableElement(self, token):
        self.parser.parseError()
        #XXX Have to duplicate logic here to find out if the tag is ignored
        ignoreEndTag = self.ignoreEndTagCaption()
        self.parser.phase.processEndTag(impliedTagToken("caption"))
        if not ignoreEndTag:
            self.parser.phase.processStartTag(token)

    def startTagOther(self, token):
        self.parser.phases["inBody"].processStartTag(token)

    def endTagCaption(self, token):
        if not self.ignoreEndTagCaption():
            # AT this code is quite similar to endTagTable in "InTable"
            self.tree.generateImpliedEndTags()
            if self.tree.openElements[-1].name != "caption":
                self.parser.parseError("expected-one-end-tag-but-got-another",
                  {"gotName": "caption",
                   "expectedName": self.tree.openElements[-1].name})
            while self.tree.openElements[-1].name != "caption":
                self.tree.openElements.pop()
            self.tree.openElements.pop()
            self.tree.clearActiveFormattingElements()
            self.parser.phase = self.parser.phases["inTable"]
        else:
            # innerHTML case
            assert self.parser.innerHTML
            self.parser.parseError()

    def endTagTable(self, token):
        self.parser.parseError()
        ignoreEndTag = self.ignoreEndTagCaption()
        self.parser.phase.processEndTag(impliedTagToken("caption"))
        if not ignoreEndTag:
            self.parser.phase.processEndTag(token)

    def endTagIgnore(self, token):
        self.parser.parseError("unexpected-end-tag", {"name": token["name"]})

    def endTagOther(self, token):
        self.parser.phases["inBody"].processEndTag(token)


class InColumnGroupPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#in-column

    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("col", self.startTagCol)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("colgroup", self.endTagColgroup),
            ("col", self.endTagCol)
        ])
        self.endTagHandler.default = self.endTagOther

    def ignoreEndTagColgroup(self):
        return self.tree.openElements[-1].name == "html"

    def processEOF(self):
        if self.tree.openElements[-1].name == "html":
            assert self.parser.innerHTML
            return
        else:
            ignoreEndTag = self.ignoreEndTagColgroup()
            self.endTagColgroup("colgroup")
            if not ignoreEndTag:
                self.parser.phase.processEOF()

    def processCharacters(self, token):
        ignoreEndTag = self.ignoreEndTagColgroup()
        self.endTagColgroup(impliedTagToken("colgroup"))
        if not ignoreEndTag:
            self.parser.phase.processCharacters(token)

    def startTagCol(self, token):
        self.tree.insertElement(token)
        self.tree.openElements.pop()

    def startTagOther(self, token):
        ignoreEndTag = self.ignoreEndTagColgroup()
        self.endTagColgroup("colgroup")
        if not ignoreEndTag:
            self.parser.phase.processStartTag(token)

    def endTagColgroup(self, token):
        if self.ignoreEndTagColgroup():
            # innerHTML case
            assert self.parser.innerHTML
            self.parser.parseError()
        else:
            self.tree.openElements.pop()
            self.parser.phase = self.parser.phases["inTable"]

    def endTagCol(self, token):
        self.parser.parseError("no-end-tag", {"name": "col"})

    def endTagOther(self, token):
        ignoreEndTag = self.ignoreEndTagColgroup()
        self.endTagColgroup("colgroup")
        if not ignoreEndTag:
            self.parser.phase.processEndTag(token)


class InTableBodyPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#in-table0
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)
        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("tr", self.startTagTr),
            (("td", "th"), self.startTagTableCell),
            (("caption", "col", "colgroup", "tbody", "tfoot", "thead"),
             self.startTagTableOther)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            (("tbody", "tfoot", "thead"), self.endTagTableRowGroup),
            ("table", self.endTagTable),
            (("body", "caption", "col", "colgroup", "html", "td", "th",
              "tr"), self.endTagIgnore)
        ])
        self.endTagHandler.default = self.endTagOther

    # helper methods
    def clearStackToTableBodyContext(self):
        while self.tree.openElements[-1].name not in ("tbody", "tfoot",
          "thead", "html"):
            #self.parser.parseError("unexpected-implied-end-tag-in-table",
            #  {"name": self.tree.openElements[-1].name})
            self.tree.openElements.pop()
        if self.tree.openElements[-1].name == "html":
            assert self.parser.innerHTML

    # the rest
    def processEOF(self):
        self.parser.phases["inTable"].processEOF()
    
    def processSpaceCharacters(self, token):
        self.parser.phases["inTable"].processSpaceCharacters(token)

    def processCharacters(self, token):
        self.parser.phases["inTable"].processCharacters(token)

    def startTagTr(self, token):
        self.clearStackToTableBodyContext()
        self.tree.insertElement(token)
        self.parser.phase = self.parser.phases["inRow"]

    def startTagTableCell(self, token):
        self.parser.parseError("unexpected-cell-in-table-body", 
                               {"name": token["name"]})
        self.startTagTr(impliedTagToken("tr", "StartTag"))
        self.parser.phase.processStartTag(token)

    def startTagTableOther(self, token):
        # XXX AT Any ideas on how to share this with endTagTable?
        if (self.tree.elementInScope("tbody", variant="table") or
            self.tree.elementInScope("thead", variant="table") or
            self.tree.elementInScope("tfoot", variant="table")):
            self.clearStackToTableBodyContext()
            self.endTagTableRowGroup(
                impliedTagToken(self.tree.openElements[-1].name))
            self.parser.phase.processStartTag(token)
        else:
            # innerHTML case
            self.parser.parseError()

    def startTagOther(self, token):
        self.parser.phases["inTable"].processStartTag(token)

    def endTagTableRowGroup(self, token):
        if self.tree.elementInScope(token["name"], variant="table"):
            self.clearStackToTableBodyContext()
            self.tree.openElements.pop()
            self.parser.phase = self.parser.phases["inTable"]
        else:
            self.parser.parseError("unexpected-end-tag-in-table-body",
              {"name": token["name"]})

    def endTagTable(self, token):
        if (self.tree.elementInScope("tbody", variant="table") or
            self.tree.elementInScope("thead", variant="table") or
            self.tree.elementInScope("tfoot", variant="table")):
            self.clearStackToTableBodyContext()
            self.endTagTableRowGroup(
                impliedTagToken(self.tree.openElements[-1].name))
            self.parser.phase.processEndTag(token)
        else:
            # innerHTML case
            self.parser.parseError()

    def endTagIgnore(self, token):
        self.parser.parseError("unexpected-end-tag-in-table-body",
          {"name": token["name"]})

    def endTagOther(self, token):
        self.parser.phases["inTable"].processEndTag(token)


class InRowPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#in-row
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)
        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            (("td", "th"), self.startTagTableCell),
            (("caption", "col", "colgroup", "tbody", "tfoot", "thead",
              "tr"), self.startTagTableOther)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("tr", self.endTagTr),
            ("table", self.endTagTable),
            (("tbody", "tfoot", "thead"), self.endTagTableRowGroup),
            (("body", "caption", "col", "colgroup", "html", "td", "th"),
              self.endTagIgnore)
        ])
        self.endTagHandler.default = self.endTagOther

    # helper methods (XXX unify this with other table helper methods)
    def clearStackToTableRowContext(self):
        while self.tree.openElements[-1].name not in ("tr", "html"):
            self.parser.parseError("unexpected-implied-end-tag-in-table-row",
              {"name": self.tree.openElements[-1].name})
            self.tree.openElements.pop()

    def ignoreEndTagTr(self):
        return not self.tree.elementInScope("tr", variant="table")

    # the rest
    def processEOF(self):
        self.parser.phases["inTable"].processEOF()
    
    def processSpaceCharacters(self, token):
        self.parser.phases["inTable"].processSpaceCharacters(token)        

    def processCharacters(self, token):
        self.parser.phases["inTable"].processCharacters(token)

    def startTagTableCell(self, token):
        self.clearStackToTableRowContext()
        self.tree.insertElement(token)
        self.parser.phase = self.parser.phases["inCell"]
        self.tree.activeFormattingElements.append(Marker)

    def startTagTableOther(self, token):
        ignoreEndTag = self.ignoreEndTagTr()
        self.endTagTr("tr")
        # XXX how are we sure it's always ignored in the innerHTML case?
        if not ignoreEndTag:
            self.parser.phase.processStartTag(token)

    def startTagOther(self, token):
        self.parser.phases["inTable"].processStartTag(token)

    def endTagTr(self, token):
        if not self.ignoreEndTagTr():
            self.clearStackToTableRowContext()
            self.tree.openElements.pop()
            self.parser.phase = self.parser.phases["inTableBody"]
        else:
            # innerHTML case
            assert self.parser.innerHTML
            self.parser.parseError()

    def endTagTable(self, token):
        ignoreEndTag = self.ignoreEndTagTr()
        self.endTagTr("tr")
        # Reprocess the current tag if the tr end tag was not ignored
        # XXX how are we sure it's always ignored in the innerHTML case?
        if not ignoreEndTag:
            self.parser.phase.processEndTag(token)

    def endTagTableRowGroup(self, token):
        if self.tree.elementInScope(token["name"], variant="table"):
            self.endTagTr("tr")
            self.parser.phase.processEndTag(token)
        else:
            # innerHTML case
            self.parser.parseError()

    def endTagIgnore(self, token):
        self.parser.parseError("unexpected-end-tag-in-table-row",
            {"name": token["name"]})

    def endTagOther(self, token):
        self.parser.phases["inTable"].processEndTag(token)

class InCellPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#in-cell
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)
        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            (("caption", "col", "colgroup", "tbody", "td", "tfoot", "th",
              "thead", "tr"), self.startTagTableOther)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            (("td", "th"), self.endTagTableCell),
            (("body", "caption", "col", "colgroup", "html"), self.endTagIgnore),
            (("table", "tbody", "tfoot", "thead", "tr"), self.endTagImply)
        ])
        self.endTagHandler.default = self.endTagOther

    # helper
    def closeCell(self):
        if self.tree.elementInScope("td", variant="table"):
            self.endTagTableCell(impliedTagToken("td"))
        elif self.tree.elementInScope("th", variant="table"):
            self.endTagTableCell(impliedTagToken("th"))

    # the rest
    def processEOF(self):
        self.parser.phases["inBody"].processEOF()
        
    def processCharacters(self, token):
        self.parser.phases["inBody"].processCharacters(token)

    def startTagTableOther(self, token):
        if (self.tree.elementInScope("td", variant="table") or
            self.tree.elementInScope("th", variant="table")):
            self.closeCell()
            self.parser.phase.processStartTag(token)
        else:
            # innerHTML case
            self.parser.parseError()

    def startTagOther(self, token):
        self.parser.phases["inBody"].processStartTag(token)
        # Optimize this for subsequent invocations. Can't do this initially
        # because self.phases doesn't really exist at that point.
        self.startTagHandler.default =\
          self.parser.phases["inBody"].processStartTag

    def endTagTableCell(self, token):
        if self.tree.elementInScope(token["name"], variant="table"):
            self.tree.generateImpliedEndTags(token["name"])
            if self.tree.openElements[-1].name != token["name"]:
                self.parser.parseError("unexpected-cell-end-tag",
                  {"name": token["name"]})
                while True:
                    node = self.tree.openElements.pop()
                    if node.name == token["name"]:
                        break
            else:
                self.tree.openElements.pop()
            self.tree.clearActiveFormattingElements()
            self.parser.phase = self.parser.phases["inRow"]
        else:
            self.parser.parseError("unexpected-end-tag", {"name": token["name"]})

    def endTagIgnore(self, token):
        self.parser.parseError("unexpected-end-tag", {"name": token["name"]})

    def endTagImply(self, token):
        if self.tree.elementInScope(token["name"], variant="table"):
            self.closeCell()
            self.parser.phase.processEndTag(token)
        else:
            # sometimes innerHTML case
            self.parser.parseError()

    def endTagOther(self, token):
        self.parser.phases["inBody"].processEndTag(token)
        # Optimize this for subsequent invocations. Can't do this initially
        # because self.phases doesn't really exist at that point.
        self.endTagHandler.default = self.parser.phases["inBody"].processEndTag


class InSelectPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("option", self.startTagOption),
            ("optgroup", self.startTagOptgroup),
            ("select", self.startTagSelect),
            (("input", "keygen", "textarea"), self.startTagInput)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("option", self.endTagOption),
            ("optgroup", self.endTagOptgroup),
            ("select", self.endTagSelect),
            (("caption", "table", "tbody", "tfoot", "thead", "tr", "td",
              "th"), self.endTagTableElements)
        ])
        self.endTagHandler.default = self.endTagOther

    # http://www.whatwg.org/specs/web-apps/current-work/#in-select
    def processEOF(self):
        if self.tree.openElements[-1].name != "html":
            self.parser.parseError("eof-in-select")
        else:
            assert self.parser.innerHTML

    def processCharacters(self, token):
        self.tree.insertText(token["data"])

    def startTagOption(self, token):
        # We need to imply </option> if <option> is the current node.
        if self.tree.openElements[-1].name == "option":
            self.tree.openElements.pop()
        self.tree.insertElement(token)

    def startTagOptgroup(self, token):
        if self.tree.openElements[-1].name == "option":
            self.tree.openElements.pop()
        if self.tree.openElements[-1].name == "optgroup":
            self.tree.openElements.pop()
        self.tree.insertElement(token)

    def startTagSelect(self, token):
        self.parser.parseError("unexpected-select-in-select")
        self.endTagSelect("select")

    def startTagInput(self, token):
        self.parser.parseError("unexpected-input-in-select")
        if self.tree.elementInScope("select", variant="table"):
            self.endTagSelect("select")
            self.parser.phase.processStartTag(token)

    def startTagOther(self, token):
        self.parser.parseError("unexpected-start-tag-in-select",
          {"name": token["name"]})

    def endTagOption(self, token):
        if self.tree.openElements[-1].name == "option":
            self.tree.openElements.pop()
        else:
            self.parser.parseError("unexpected-end-tag-in-select",
              {"name": "option"})

    def endTagOptgroup(self, token):
        # </optgroup> implicitly closes <option>
        if (self.tree.openElements[-1].name == "option" and
            self.tree.openElements[-2].name == "optgroup"):
            self.tree.openElements.pop()
        # It also closes </optgroup>
        if self.tree.openElements[-1].name == "optgroup":
            self.tree.openElements.pop()
        # But nothing else
        else:
            self.parser.parseError("unexpected-end-tag-in-select",
              {"name": "optgroup"})

    def endTagSelect(self, token):
        if self.tree.elementInScope("select", variant="table"):
            node = self.tree.openElements.pop()
            while node.name != "select":
                node = self.tree.openElements.pop()
            self.parser.resetInsertionMode()
        else:
            # innerHTML case
            self.parser.parseError()

    def endTagTableElements(self, token):
        self.parser.parseError("unexpected-end-tag-in-select",
          {"name": token["name"]})
        if self.tree.elementInScope(token["name"], variant="table"):
            self.endTagSelect("select")
            self.parser.phase.processEndTag(token)

    def endTagOther(self, token):
        self.parser.parseError("unexpected-end-tag-in-select",
          {"name": token["name"]})


class InSelectInTablePhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            (("caption", "table", "tbody", "tfoot", "thead", "tr", "td", "th"),
             self.startTagTable)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            (("caption", "table", "tbody", "tfoot", "thead", "tr", "td", "th"),
             self.endTagTable)
        ])
        self.endTagHandler.default = self.endTagOther

    def processEOF(self):
        self.parser.phases["inSelect"].processEOF()

    def processCharacters(self, token):
        self.parser.phases["inSelect"].processCharacters(token)
    
    def startTagTable(self, token):
        self.parser.parseError("unexpected-table-element-start-tag-in-select-in-table", {"name": token["name"]})
        self.endTagOther(impliedTagToken("select"))
        self.parser.phase.processStartTag(token)

    def startTagOther(self, token):
        self.parser.phases["inSelect"].processStartTag(token)

    def endTagTable(self, token):
        self.parser.parseError("unexpected-table-element-end-tag-in-select-in-table", {"name": token["name"]})
        if self.tree.elementInScope(token["name"], variant="table"):
            self.endTagOther(impliedTagToken("select"))
            self.parser.phase.processEndTag(token)

    def endTagOther(self, token):
        self.parser.phases["inSelect"].processEndTag(token)


class InForeignContentPhase(Phase):
    breakoutElements = frozenset(["b", "big", "blockquote", "body", "br", 
                                  "center", "code", "dd", "div", "dl", "dt",
                                  "em", "embed", "font", "h1", "h2", "h3", 
                                  "h4", "h5", "h6", "head", "hr", "i", "img",
                                  "li", "listing", "menu", "meta", "nobr", 
                                  "ol", "p", "pre", "ruby", "s",  "small", 
                                  "span", "strong", "strike",  "sub", "sup", 
                                  "table", "tt", "u", "ul", "var"])
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

    def nonHTMLElementInScope(self):
        for element in self.tree.openElements[::-1]:
            if element.namespace == self.tree.defaultNamespace:
                return self.tree.elementInScope(element)
        assert False
        for item in self.tree.openElements[::-1]:
            if item.namespace == self.tree.defaultNamespace:
                return True
            elif item.nameTuple in scopingElements:
                return False
        return False

    def adjustSVGTagNames(self, token):
        replacements = {"altglyph":"altGlyph",
                        "altglyphdef":"altGlyphDef",
                        "altglyphitem":"altGlyphItem",
                        "animatecolor":"animateColor",
                        "animatemotion":"animateMotion",
                        "animatetransform":"animateTransform",
                        "clippath":"clipPath",
                        "feblend":"feBlend",
                        "fecolormatrix":"feColorMatrix",
                        "fecomponenttransfer":"feComponentTransfer",
                        "fecomposite":"feComposite",
                        "feconvolvematrix":"feConvolveMatrix",
                        "fediffuselighting":"feDiffuseLighting",
                        "fedisplacementmap":"feDisplacementMap",
                        "fedistantlight":"feDistantLight",
                        "feflood":"feFlood",
                        "fefunca":"feFuncA",
                        "fefuncb":"feFuncB",
                        "fefuncg":"feFuncG",
                        "fefuncr":"feFuncR",
                        "fegaussianblur":"feGaussianBlur",
                        "feimage":"feImage",
                        "femerge":"feMerge",
                        "femergenode":"feMergeNode",
                        "femorphology":"feMorphology",
                        "feoffset":"feOffset",
                        "fepointlight":"fePointLight",
                        "fespecularlighting":"feSpecularLighting",
                        "fespotlight":"feSpotLight",
                        "fetile":"feTile",
                        "feturbulence":"feTurbulence",
                        "foreignobject":"foreignObject",
                        "glyphref":"glyphRef",
                        "lineargradient":"linearGradient",
                        "radialgradient":"radialGradient",
                        "textpath":"textPath"}

        if token["name"] in replacements:
            token["name"] = replacements[token["name"]]

    def processCharacters(self, token):
        self.parser.framesetOK = False
        Phase.processCharacters(self, token)

    def processEOF(self):
        pass

    def processStartTag(self, token):
        currentNode = self.tree.openElements[-1]
        if (currentNode.namespace == self.tree.defaultNamespace or
            (currentNode.namespace == namespaces["mathml"] and 
             token["name"] not in frozenset(["mglyph", "malignmark"]) and
             currentNode.name in frozenset(["mi", "mo", "mn", 
                                            "ms", "mtext"])) or
            (currentNode.namespace == namespaces["mathml"] and
             currentNode.name == "annotation-xml" and
             token["name"] == "svg") or
            (currentNode.namespace == namespaces["svg"] and 
             currentNode.name in frozenset(["foreignObject", 
                                            "desc", "title"])
             )):
            assert self.parser.secondaryPhase != self
            self.parser.secondaryPhase.processStartTag(token)
            if self.parser.phase == self and self.nonHTMLElementInScope():
                self.parser.phase = self.parser.secondaryPhase
        elif token["name"] in self.breakoutElements:
            self.parser.parseError("unexpected-html-element-in-foreign-content",
                                   token["name"])
            while (self.tree.openElements[-1].namespace !=
                   self.tree.defaultNamespace):
                self.tree.openElements.pop()
            self.parser.phase = self.parser.secondaryPhase
            self.parser.phase.processStartTag(token)
        else:
            if currentNode.namespace == namespaces["mathml"]:
                self.parser.adjustMathMLAttributes(token)
            elif currentNode.namespace == namespaces["svg"]:
                self.adjustSVGTagNames(token)
                self.parser.adjustSVGAttributes(token)
            self.parser.adjustForeignAttributes(token)
            token["namespace"] = currentNode.namespace
            self.tree.insertElement(token)
            if token["selfClosing"]:
                self.tree.openElements.pop()
                token["selfClosingAcknowledged"] = True

    def processEndTag(self, token):
        self.adjustSVGTagNames(token)
        self.parser.secondaryPhase.processEndTag(token)
        if self.parser.phase == self and self.nonHTMLElementInScope():
            self.parser.phase = self.parser.secondaryPhase

class AfterBodyPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
                ("html", self.startTagHtml)
                ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([("html", self.endTagHtml)])
        self.endTagHandler.default = self.endTagOther

    def processEOF(self):
        #Stop parsing
        pass
    
    def processComment(self, token):
        # This is needed because data is to be appended to the <html> element
        # here and not to whatever is currently open.
        self.tree.insertComment(token, self.tree.openElements[0])

    def processCharacters(self, token):
        self.parser.parseError("unexpected-char-after-body")
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processCharacters(token)

    def startTagHtml(self, token):
        self.parser.phases["inBody"].processStartTag(token)

    def startTagOther(self, token):
        self.parser.parseError("unexpected-start-tag-after-body",
          {"name": token["name"]})
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processStartTag(token)

    def endTagHtml(self,name):
        if self.parser.innerHTML:
            self.parser.parseError("unexpected-end-tag-after-body-innerhtml")
        else:
            self.parser.phase = self.parser.phases["afterAfterBody"]

    def endTagOther(self, token):
        self.parser.parseError("unexpected-end-tag-after-body",
          {"name": token["name"]})
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processEndTag(token)

class InFramesetPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#in-frameset
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("frameset", self.startTagFrameset),
            ("frame", self.startTagFrame),
            ("noframes", self.startTagNoframes)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("frameset", self.endTagFrameset),
            ("noframes", self.endTagNoframes)
        ])
        self.endTagHandler.default = self.endTagOther

    def processEOF(self):
        if self.tree.openElements[-1].name != "html":
            self.parser.parseError("eof-in-frameset")
        else:
            assert self.parser.innerHTML

    def processCharacters(self, token):
        self.parser.parseError("unexpected-char-in-frameset")

    def startTagFrameset(self, token):
        self.tree.insertElement(token)

    def startTagFrame(self, token):
        self.tree.insertElement(token)
        self.tree.openElements.pop()

    def startTagNoframes(self, token):
        self.parser.phases["inBody"].processStartTag(token)

    def startTagOther(self, token):
        self.parser.parseError("unexpected-start-tag-in-frameset",
          {"name": token["name"]})

    def endTagFrameset(self, token):
        if self.tree.openElements[-1].name == "html":
            # innerHTML case
            self.parser.parseError("unexpected-frameset-in-frameset-innerhtml")
        else:
            self.tree.openElements.pop()
        if (not self.parser.innerHTML and
            self.tree.openElements[-1].name != "frameset"):
            # If we're not in innerHTML mode and the the current node is not a
            # "frameset" element (anymore) then switch.
            self.parser.phase = self.parser.phases["afterFrameset"]

    def endTagNoframes(self, token):
        self.parser.phases["inBody"].processEndTag(token)

    def endTagOther(self, token):
        self.parser.parseError("unexpected-end-tag-in-frameset",
          {"name": token["name"]})


class AfterFramesetPhase(Phase):
    # http://www.whatwg.org/specs/web-apps/current-work/#after3
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("noframes", self.startTagNoframes)
        ])
        self.startTagHandler.default = self.startTagOther

        self.endTagHandler = utils.MethodDispatcher([
            ("html", self.endTagHtml)
        ])
        self.endTagHandler.default = self.endTagOther

    def processEOF(self):
        #Stop parsing
        pass

    def processCharacters(self, token):
        self.parser.parseError("unexpected-char-after-frameset")

    def startTagNoframes(self, token):
        self.parser.phases["inHead"].processStartTag(token)

    def startTagOther(self, token):
        self.parser.parseError("unexpected-start-tag-after-frameset",
          {"name": token["name"]})

    def endTagHtml(self, token):
        self.parser.phase = self.parser.phases["afterAfterFrameset"]

    def endTagOther(self, token):
        self.parser.parseError("unexpected-end-tag-after-frameset",
          {"name": token["name"]})


class AfterAfterBodyPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml)
        ])
        self.startTagHandler.default = self.startTagOther

    def processEOF(self):
        pass

    def processComment(self, token):
        self.tree.insertComment(token, self.tree.document)

    def processSpaceCharacters(self, token):
        self.parser.phases["inBody"].processSpaceCharacters(token)

    def processCharacters(self, token):
        self.parser.parseError("expected-eof-but-got-char")
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processCharacters(token)

    def startTagHtml(self, token):
        self.parser.phases["inBody"].processStartTag(token)

    def startTagOther(self, token):
        self.parser.parseError("expected-eof-but-got-start-tag",
          {"name": token["name"]})
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processStartTag(token)

    def processEndTag(self, token):
        self.parser.parseError("expected-eof-but-got-end-tag",
          {"name": token["name"]})
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processEndTag(token)

class AfterAfterFramesetPhase(Phase):
    def __init__(self, parser, tree):
        Phase.__init__(self, parser, tree)

        self.startTagHandler = utils.MethodDispatcher([
            ("html", self.startTagHtml),
            ("noframes", self.startTagNoFrames)
        ])
        self.startTagHandler.default = self.startTagOther

    def processEOF(self):
        pass

    def processComment(self, token):
        self.tree.insertComment(token, self.tree.document)

    def processSpaceCharacters(self, token):
        self.parser.phases["inBody"].processSpaceCharacters(token)

    def processCharacters(self, token):
        self.parser.parseError("expected-eof-but-got-char")
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processCharacters(token)

    def startTagHtml(self, token):
        self.parser.phases["inBody"].processStartTag(token)

    def startTagNoFrames(self, token):
        self.parser.phases["inHead"].processStartTag(token)

    def startTagOther(self, token):
        self.parser.parseError("expected-eof-but-got-start-tag",
          {"name": token["name"]})
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processStartTag(token)

    def processEndTag(self, token):
        self.parser.parseError("expected-eof-but-got-end-tag",
          {"name": token["name"]})
        self.parser.phase = self.parser.phases["inBody"]
        self.parser.phase.processEndTag(token)

def impliedTagToken(name, type="EndTag", attributes = None, 
                    selfClosing = False):
    if attributes is None:
        attributes = {}
    return {"type":tokenTypes[type], "name":name, "data":attributes,
            "selfClosing":selfClosing}

class ParseError(Exception):
    """Error in parsed document"""
    pass
