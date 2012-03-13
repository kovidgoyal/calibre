try:
    frozenset
except NameError:
    # Import from the sets module for python 2.3
    from sets import Set as set
    from sets import ImmutableSet as frozenset
try:
    from collections import deque
except ImportError:
    from utils import deque
    
from constants import spaceCharacters
from constants import entitiesWindows1252, entities
from constants import asciiLowercase, asciiLetters, asciiUpper2Lower
from constants import digits, hexDigits, EOF
from constants import tokenTypes, tagTokenTypes
from constants import replacementCharacters

from inputstream import HTMLInputStream

# Group entities by their first character, for faster lookups
entitiesByFirstChar = {}
for e in entities:
    entitiesByFirstChar.setdefault(e[0], []).append(e)

class HTMLTokenizer:
    """ This class takes care of tokenizing HTML.

    * self.currentToken
      Holds the token that is currently being processed.

    * self.state
      Holds a reference to the method to be invoked... XXX

    * self.stream
      Points to HTMLInputStream object.
    """

    # XXX need to fix documentation

    def __init__(self, stream, encoding=None, parseMeta=True, useChardet=True,
                 lowercaseElementName=True, lowercaseAttrName=True):

        self.stream = HTMLInputStream(stream, encoding, parseMeta, useChardet)
        
        #Perform case conversions?
        self.lowercaseElementName = lowercaseElementName
        self.lowercaseAttrName = lowercaseAttrName
        
        # Setup the initial tokenizer state
        self.escapeFlag = False
        self.lastFourChars = []
        self.state = self.dataState
        self.escape = False

        # The current token being created
        self.currentToken = None

    def __iter__(self):
        """ This is where the magic happens.

        We do our usually processing through the states and when we have a token
        to return we yield the token which pauses processing until the next token
        is requested.
        """
        self.tokenQueue = deque([])
        # Start processing. When EOF is reached self.state will return False
        # instead of True and the loop will terminate.
        while self.state():
            while self.stream.errors:
                yield {"type": tokenTypes["ParseError"], "data": self.stream.errors.pop(0)}
            while self.tokenQueue:
                yield self.tokenQueue.popleft()

    def consumeNumberEntity(self, isHex):
        """This function returns either U+FFFD or the character based on the
        decimal or hexadecimal representation. It also discards ";" if present.
        If not present self.tokenQueue.append({"type": tokenTypes["ParseError"]}) is invoked.
        """

        allowed = digits
        radix = 10
        if isHex:
            allowed = hexDigits
            radix = 16

        charStack = []

        # Consume all the characters that are in range while making sure we
        # don't hit an EOF.
        c = self.stream.char()
        while c in allowed and c is not EOF:
            charStack.append(c)
            c = self.stream.char()

        # Convert the set of characters consumed to an int.
        charAsInt = int("".join(charStack), radix)

        # Certain characters get replaced with others
        if charAsInt in replacementCharacters:
            char = replacementCharacters[charAsInt]
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "illegal-codepoint-for-numeric-entity",
              "datavars": {"charAsInt": charAsInt}})
        elif ((0xD800 <= charAsInt <= 0xDFFF) or 
              (charAsInt > 0x10FFFF)):
            char = u"\uFFFD"
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "illegal-codepoint-for-numeric-entity",
              "datavars": {"charAsInt": charAsInt}})
        else:
            #Should speed up this check somehow (e.g. move the set to a constant)
            if ((0x0001 <= charAsInt <= 0x0008) or 
                (0x000E <= charAsInt <= 0x001F) or 
                (0x007F  <= charAsInt <= 0x009F) or
                (0xFDD0  <= charAsInt <= 0xFDEF) or 
                charAsInt in frozenset([0x000B, 0xFFFE, 0xFFFF, 0x1FFFE, 
                                        0x1FFFF, 0x2FFFE, 0x2FFFF, 0x3FFFE,
                                        0x3FFFF, 0x4FFFE, 0x4FFFF, 0x5FFFE, 
                                        0x5FFFF, 0x6FFFE, 0x6FFFF, 0x7FFFE,
                                        0x7FFFF, 0x8FFFE, 0x8FFFF, 0x9FFFE,
                                        0x9FFFF, 0xAFFFE, 0xAFFFF, 0xBFFFE, 
                                        0xBFFFF, 0xCFFFE, 0xCFFFF, 0xDFFFE, 
                                        0xDFFFF, 0xEFFFE, 0xEFFFF, 0xFFFFE, 
                                        0xFFFFF, 0x10FFFE, 0x10FFFF])):
                self.tokenQueue.append({"type": tokenTypes["ParseError"], 
                                        "data":
                                            "illegal-codepoint-for-numeric-entity",
                                        "datavars": {"charAsInt": charAsInt}})
            try:
                # Try/except needed as UCS-2 Python builds' unichar only works
                # within the BMP.
                char = unichr(charAsInt)
            except ValueError:
                char = eval("u'\\U%08x'" % charAsInt)

        # Discard the ; if present. Otherwise, put it back on the queue and
        # invoke parseError on parser.
        if c != u";":
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "numeric-entity-without-semicolon"})
            self.stream.unget(c)

        return char

    def consumeEntity(self, allowedChar=None, fromAttribute=False):
        # Initialise to the default output for when no entity is matched
        output = u"&"

        charStack = [self.stream.char()]
        if (charStack[0] in spaceCharacters or charStack[0] in (EOF, u"<", u"&") 
            or (allowedChar is not None and allowedChar == charStack[0])):
            self.stream.unget(charStack[0])

        elif charStack[0] == u"#":
            # Read the next character to see if it's hex or decimal
            hex = False
            charStack.append(self.stream.char())
            if charStack[-1] in (u"x", u"X"):
                hex = True
                charStack.append(self.stream.char())

            # charStack[-1] should be the first digit
            if (hex and charStack[-1] in hexDigits) \
             or (not hex and charStack[-1] in digits):
                # At least one digit found, so consume the whole number
                self.stream.unget(charStack[-1])
                output = self.consumeNumberEntity(hex)
            else:
                # No digits found
                self.tokenQueue.append({"type": tokenTypes["ParseError"],
                    "data": "expected-numeric-entity"})
                self.stream.unget(charStack.pop())
                output = u"&" + u"".join(charStack)

        else:
            # At this point in the process might have named entity. Entities
            # are stored in the global variable "entities".
            #
            # Consume characters and compare to these to a substring of the
            # entity names in the list until the substring no longer matches.
            filteredEntityList = entitiesByFirstChar.get(charStack[0], [])

            def entitiesStartingWith(name):
                return [e for e in filteredEntityList if e.startswith(name)]

            while charStack[-1] is not EOF and\
              entitiesStartingWith("".join(charStack)):
                charStack.append(self.stream.char())

            # At this point we have a string that starts with some characters
            # that may match an entity
            entityName = None

            # Try to find the longest entity the string will match to take care
            # of &noti for instance.
            for entityLength in xrange(len(charStack)-1, 1, -1):
                possibleEntityName = "".join(charStack[:entityLength])
                if possibleEntityName in entities:
                    entityName = possibleEntityName
                    break

            if entityName is not None:
                if entityName[-1] != ";":
                    self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
                      "named-entity-without-semicolon"})
                if entityName[-1] != ";" and fromAttribute and \
                  (charStack[entityLength] in asciiLetters
                  or charStack[entityLength] in digits):
                    self.stream.unget(charStack.pop())
                    output = u"&" + u"".join(charStack)
                else:
                    output = entities[entityName]
                    self.stream.unget(charStack.pop())
                    output += u"".join(charStack[entityLength:])
            else:
                self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
                  "expected-named-entity"})
                self.stream.unget(charStack.pop())
                output = u"&" + u"".join(charStack)

        if fromAttribute:
            self.currentToken["data"][-1][1] += output
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": output})

    def processEntityInAttribute(self, allowedChar):
        """This method replaces the need for "entityInAttributeValueState".
        """
        self.consumeEntity(allowedChar=allowedChar, fromAttribute=True)

    def emitCurrentToken(self):
        """This method is a generic handler for emitting the tags. It also sets
        the state to "data" because that's what's needed after a token has been
        emitted.
        """
        token = self.currentToken
        # Add token to the queue to be yielded
        if (token["type"] in tagTokenTypes):
            if self.lowercaseElementName:
                token["name"] = token["name"].translate(asciiUpper2Lower)
            if token["type"] == tokenTypes["EndTag"]:
                if token["data"]:
                    self.tokenQueue.append({"type":tokenTypes["ParseError"],
                                            "data":"attributes-in-end-tag"})
                if token["selfClosing"]:
                    self.tokenQueue.append({"type":tokenTypes["ParseError"],
                                            "data":"self-closing-flag-on-end-tag"})
        self.tokenQueue.append(token)
        self.state = self.dataState


    # Below are the various tokenizer states worked out.

    def dataState(self):
        data = self.stream.char()
        if data == "&":
            self.state = self.entityDataState
        elif data == "<":
            self.state = self.tagOpenState
        elif data is EOF:
            # Tokenization ends.
            return False
        elif data in spaceCharacters:
            # Directly after emitting a token you switch back to the "data
            # state". At that point spaceCharacters are important so they are
            # emitted separately.
            self.tokenQueue.append({"type": tokenTypes["SpaceCharacters"], "data":
              data + self.stream.charsUntil(spaceCharacters, True)})
            # No need to update lastFourChars here, since the first space will
            # have already been appended to lastFourChars and will have broken
            # any <!-- or --> sequences
        else:
            chars = self.stream.charsUntil((u"&", u"<"))
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": 
              data + chars})
        return True

    def entityDataState(self):
        self.consumeEntity()
        self.state = self.dataState
        return True
    
    def rcdataState(self):
        data = self.stream.char()
        if data == "&":
            self.state = self.characterReferenceInRcdata
        elif data == "<":
            self.state = self.rcdataLessThanSignState
        elif data == EOF:
            # Tokenization ends.
            return False
        elif data in spaceCharacters:
            # Directly after emitting a token you switch back to the "data
            # state". At that point spaceCharacters are important so they are
            # emitted separately.
            self.tokenQueue.append({"type": tokenTypes["SpaceCharacters"], "data":
              data + self.stream.charsUntil(spaceCharacters, True)})
            # No need to update lastFourChars here, since the first space will
            # have already been appended to lastFourChars and will have broken
            # any <!-- or --> sequences
        else:
            chars = self.stream.charsUntil((u"&", u"<"))
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": 
              data + chars})
        return True

    def characterReferenceInRcdata(self):
        self.consumeEntity()
        self.state = self.rcdataState
        return True
    
    def rawtextState(self):
        data = self.stream.char()
        if data == "<":
            self.state = self.rawtextLessThanSignState
        elif data == EOF:
            # Tokenization ends.
            return False
        else:
            chars = self.stream.charsUntil((u"<"))
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": 
              data + chars})
        return True
    
    def scriptDataState(self):
        data = self.stream.char()
        if data == "<":
            self.state = self.scriptDataLessThanSignState
        elif data == EOF:
            # Tokenization ends.
            return False
        else:
            chars = self.stream.charsUntil((u"<"))
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": 
              data + chars})
        return True
    
    def plaintextState(self):
        data = self.stream.char()
        if data == EOF:
            # Tokenization ends.
            return False
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": 
              data + self.stream.charsUntilEOF()})
            return True

    def tagOpenState(self):
        data = self.stream.char()
        if data == u"!":
            self.state = self.markupDeclarationOpenState
        elif data == u"/":
            self.state = self.closeTagOpenState
        elif data in asciiLetters:
            self.currentToken = {"type": tokenTypes["StartTag"], 
                                 "name": data, "data": [],
                                 "selfClosing": False,
                                 "selfClosingAcknowledged": False}
            self.state = self.tagNameState
        elif data == u">":
            # XXX In theory it could be something besides a tag name. But
            # do we really care?
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "expected-tag-name-but-got-right-bracket"})
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"<>"})
            self.state = self.dataState
        elif data == u"?":
            # XXX In theory it could be something besides a tag name. But
            # do we really care?
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "expected-tag-name-but-got-question-mark"})
            self.stream.unget(data)
            self.state = self.bogusCommentState
        else:
            # XXX
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "expected-tag-name"})
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"<"})
            self.stream.unget(data)
            self.state = self.dataState
        return True

    def closeTagOpenState(self):
        data = self.stream.char()
        if data in asciiLetters:
            self.currentToken = {"type": tokenTypes["EndTag"], "name": data,
                                 "data": [], "selfClosing":False}
            self.state = self.tagNameState
        elif data == u">":
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "expected-closing-tag-but-got-right-bracket"})
            self.state = self.dataState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "expected-closing-tag-but-got-eof"})
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"</"})
            self.state = self.dataState
        else:
            # XXX data can be _'_...
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "expected-closing-tag-but-got-char",
              "datavars": {"data": data}})
            self.stream.unget(data)
            self.state = self.bogusCommentState
        return True

    def tagNameState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            self.state = self.beforeAttributeNameState
        elif data == u">":
            self.emitCurrentToken()
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-tag-name"})
            self.state = self.dataState
        elif data == u"/":
            self.state = self.selfClosingStartTagState
        else:
            self.currentToken["name"] += data
            # (Don't use charsUntil here, because tag names are
            # very short and it's faster to not do anything fancy)
        return True
    
    def rcdataLessThanSignState(self):
        data = self.stream.char()
        if data == "/":
            self.temporaryBuffer = ""
            self.state = self.rcdataEndTagOpenState
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"<"})
            self.stream.unget(data)
            self.state = self.rcdataState
        return True
    
    def rcdataEndTagOpenState(self):
        data = self.stream.char()
        if data in asciiLetters:
            self.temporaryBuffer += data
            self.state = self.rcdataEndTagNameState
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"</"})
            self.stream.unget(data)
            self.state = self.rcdataState
        return True
    
    def rcdataEndTagNameState(self):
        appropriate = self.currentToken and self.currentToken["name"].lower() == self.temporaryBuffer.lower()
        data = self.stream.char()
        if data in spaceCharacters and appropriate:
            self.currentToken = {"type": tokenTypes["EndTag"],
                                 "name": self.temporaryBuffer,
                                 "data": [], "selfClosing":False}
            self.state = self.beforeAttributeNameState
        elif data == "/" and appropriate:
            self.currentToken = {"type": tokenTypes["EndTag"],
                                 "name": self.temporaryBuffer,
                                 "data": [], "selfClosing":False}
            self.state = self.selfClosingStartTagState
        elif data == ">" and appropriate:
            self.currentToken = {"type": tokenTypes["EndTag"],
                                 "name": self.temporaryBuffer,
                                 "data": [], "selfClosing":False}
            self.emitCurrentToken()
            self.state = self.dataState
        elif data in asciiLetters:
            self.temporaryBuffer += data
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"],
                                    "data": u"</" + self.temporaryBuffer})
            self.stream.unget(data)
            self.state = self.rcdataState
        return True
    
    def rawtextLessThanSignState(self):
        data = self.stream.char()
        if data == "/":
            self.temporaryBuffer = ""
            self.state = self.rawtextEndTagOpenState
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"<"})
            self.stream.unget(data)
            self.state = self.rawtextState
        return True
    
    def rawtextEndTagOpenState(self):
        data = self.stream.char()
        if data in asciiLetters:
            self.temporaryBuffer += data
            self.state = self.rawtextEndTagNameState
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"</"})
            self.stream.unget(data)
            self.state = self.rawtextState
        return True
    
    def rawtextEndTagNameState(self):
        appropriate = self.currentToken and self.currentToken["name"].lower() == self.temporaryBuffer.lower()
        data = self.stream.char()
        if data in spaceCharacters and appropriate:
            self.currentToken = {"type": tokenTypes["EndTag"],
                                 "name": self.temporaryBuffer,
                                 "data": [], "selfClosing":False}
            self.state = self.beforeAttributeNameState
        elif data == "/" and appropriate:
            self.currentToken = {"type": tokenTypes["EndTag"],
                                 "name": self.temporaryBuffer,
                                 "data": [], "selfClosing":False}
            self.state = self.selfClosingStartTagState
        elif data == ">" and appropriate:
            self.currentToken = {"type": tokenTypes["EndTag"],
                                 "name": self.temporaryBuffer,
                                 "data": [], "selfClosing":False}
            self.emitCurrentToken()
            self.state = self.dataState
        elif data in asciiLetters:
            self.temporaryBuffer += data
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"],
                                    "data": u"</" + self.temporaryBuffer})
            self.stream.unget(data)
            self.state = self.rawtextState
        return True
    
    def scriptDataLessThanSignState(self):
        data = self.stream.char()
        if data == "/":
            self.temporaryBuffer = ""
            self.state = self.scriptDataEndTagOpenState
        elif data == "!":
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"<!"})
            self.state = self.scriptDataEscapeStartState
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"<"})
            self.stream.unget(data)
            self.state = self.scriptDataState
        return True
    
    def scriptDataEndTagOpenState(self):
        data = self.stream.char()
        if data in asciiLetters:
            self.temporaryBuffer += data
            self.state = self.scriptDataEndTagNameState
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"</"})
            self.stream.unget(data)
            self.state = self.scriptDataState
        return True
    
    def scriptDataEndTagNameState(self):
        appropriate = self.currentToken and self.currentToken["name"].lower() == self.temporaryBuffer.lower()
        data = self.stream.char()
        if data in spaceCharacters and appropriate:
            self.currentToken = {"type": tokenTypes["EndTag"],
                                 "name": self.temporaryBuffer,
                                 "data": [], "selfClosing":False}
            self.state = self.beforeAttributeNameState
        elif data == "/" and appropriate:
            self.currentToken = {"type": tokenTypes["EndTag"],
                                 "name": self.temporaryBuffer,
                                 "data": [], "selfClosing":False}
            self.state = self.selfClosingStartTagState
        elif data == ">" and appropriate:
            self.currentToken = {"type": tokenTypes["EndTag"],
                                 "name": self.temporaryBuffer,
                                 "data": [], "selfClosing":False}
            self.emitCurrentToken()
            self.state = self.dataState
        elif data in asciiLetters:
            self.temporaryBuffer += data
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"],
                                    "data": u"</" + self.temporaryBuffer})
            self.stream.unget(data)
            self.state = self.scriptDataState
        return True
    
    def scriptDataEscapeStartState(self):
        data = self.stream.char()
        if data == "-":
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"-"})
            self.state = self.scriptDataEscapeStartDashState
        else:
            self.stream.unget(data)
            self.state = self.scriptDataState
        return True
    
    def scriptDataEscapeStartDashState(self):
        data = self.stream.char()
        if data == "-":
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"-"})
            self.state = self.scriptDataEscapedDashDashState
        else:
            self.stream.unget(data)
            self.state = self.scriptDataState
        return True
    
    def scriptDataEscapedState(self):
        data = self.stream.char()
        if data == "-":
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"-"})
            self.state = self.scriptDataEscapedDashState
        elif data == "<":
            self.state = self.scriptDataEscapedLessThanSignState
        elif data == EOF:
            self.state = self.dataState
        else:
            chars = self.stream.charsUntil((u"<-"))
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": 
              data + chars})
        return True
    
    def scriptDataEscapedDashState(self):
        data = self.stream.char()
        if data == "-":
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"-"})
            self.state = self.scriptDataEscapedDashDashState
        elif data == "<":
            self.state = self.scriptDataEscapedLessThanSignState
        elif data == EOF:
            self.state = self.dataState
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": data})
            self.state = self.scriptDataEscapedState
        return True
    
    def scriptDataEscapedDashDashState(self):
        data = self.stream.char()
        if data == "-":
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"-"})
        elif data == "<":
            self.state = self.scriptDataEscapedLessThanSignState
        elif data == ">":
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u">"})
            self.state = self.scriptDataState
        elif data == EOF:
            self.state = self.dataState
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": data})
            self.state = self.scriptDataEscapedState
        return True
    
    def scriptDataEscapedLessThanSignState(self):
        data = self.stream.char()
        if data == "/":
            self.temporaryBuffer = ""
            self.state = self.scriptDataEscapedEndTagOpenState
        elif data in asciiLetters:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"<" + data})
            self.temporaryBuffer = data
            self.state = self.scriptDataDoubleEscapeStartState
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"<"})
            self.stream.unget(data)
            self.state = self.scriptDataEscapedState
        return True
    
    def scriptDataEscapedEndTagOpenState(self):
        data = self.stream.char()
        if data in asciiLetters:
            self.temporaryBuffer = data
            self.state = self.scriptDataEscapedEndTagNameState
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"</"})
            self.stream.unget(data)
            self.state = self.scriptDataEscapedState
        return True
    
    def scriptDataEscapedEndTagNameState(self):
        appropriate = self.currentToken and self.currentToken["name"].lower() == self.temporaryBuffer.lower()
        data = self.stream.char()
        if data in spaceCharacters and appropriate:
            self.currentToken = {"type": tokenTypes["EndTag"],
                                 "name": self.temporaryBuffer,
                                 "data": [], "selfClosing":False}
            self.state = self.beforeAttributeNameState
        elif data == "/" and appropriate:
            self.currentToken = {"type": tokenTypes["EndTag"],
                                 "name": self.temporaryBuffer,
                                 "data": [], "selfClosing":False}
            self.state = self.selfClosingStartTagState
        elif data == ">" and appropriate:
            self.currentToken = {"type": tokenTypes["EndTag"],
                                 "name": self.temporaryBuffer,
                                 "data": [], "selfClosing":False}
            self.emitCurrentToken()
            self.state = self.dataState
        elif data in asciiLetters:
            self.temporaryBuffer += data
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"],
                                    "data": u"</" + self.temporaryBuffer})
            self.stream.unget(data)
            self.state = self.scriptDataEscapedState
        return True
    
    def scriptDataDoubleEscapeStartState(self):
        data = self.stream.char()
        if data in (spaceCharacters | frozenset(("/", ">"))):
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": data})
            if self.temporaryBuffer.lower() == "script":
                self.state = self.scriptDataDoubleEscapedState
            else:
                self.state = self.scriptDataEscapedState
        elif data in asciiLetters:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": data})
            self.temporaryBuffer += data
        else:
            self.stream.unget(data)
            self.state = self.scriptDataEscapedState
        return True
    
    def scriptDataDoubleEscapedState(self):
        data = self.stream.char()
        if data == "-":
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"-"})
            self.state = self.scriptDataDoubleEscapedDashState
        elif data == "<":
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"<"})
            self.state = self.scriptDataDoubleEscapedLessThanSignState
        elif data == EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-script-in-script"})
            self.state = self.dataState
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": data})
        return True
    
    def scriptDataDoubleEscapedDashState(self):
        data = self.stream.char()
        if data == "-":
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"-"})
            self.state = self.scriptDataDoubleEscapedDashDashState
        elif data == "<":
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"<"})
            self.state = self.scriptDataDoubleEscapedLessThanSignState
        elif data == EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-script-in-script"})
            self.state = self.dataState
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": data})
            self.state = self.scriptDataDoubleEscapedState
        return True
    
    def scriptDataDoubleEscapedDashState(self):
        data = self.stream.char()
        if data == "-":
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"-"})
        elif data == "<":
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"<"})
            self.state = self.scriptDataDoubleEscapedLessThanSignState
        elif data == ">":
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u">"})
            self.state = self.scriptDataState
        elif data == EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-script-in-script"})
            self.state = self.dataState
        else:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": data})
            self.state = self.scriptDataDoubleEscapedState
        return True
    
    def scriptDataDoubleEscapedLessThanSignState(self):
        data = self.stream.char()
        if data == "/":
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": u"/"})
            self.temporaryBuffer = ""
            self.state = self.scriptDataDoubleEscapeEndState
        else:
            self.stream.unget(data)
            self.state = self.scriptDataDoubleEscapedState
        return True
    
    def scriptDataDoubleEscapeEndState(self):
        data = self.stream.char()
        if data in (spaceCharacters | frozenset(("/", ">"))):
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": data})
            if self.temporaryBuffer.lower() == "script":
                self.state = self.scriptDataEscapedState
            else:
                self.state = self.scriptDataDoubleEscapedState
        elif data in asciiLetters:
            self.tokenQueue.append({"type": tokenTypes["Characters"], "data": data})
            self.temporaryBuffer += data
        else:
            self.stream.unget(data)
            self.state = self.scriptDataDoubleEscapedState
        return True

    def beforeAttributeNameState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            self.stream.charsUntil(spaceCharacters, True)
        elif data in asciiLetters:
            self.currentToken["data"].append([data, ""])
            self.state = self.attributeNameState
        elif data == u">":
            self.emitCurrentToken()
        elif data == u"/":
            self.state = self.selfClosingStartTagState
        elif data in (u"'", u'"', u"=", u"<"):
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "invalid-character-in-attribute-name"})
            self.currentToken["data"].append([data, ""])
            self.state = self.attributeNameState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "expected-attribute-name-but-got-eof"})
            self.state = self.dataState
        else:
            self.currentToken["data"].append([data, ""])
            self.state = self.attributeNameState
        return True

    def attributeNameState(self):
        data = self.stream.char()
        leavingThisState = True
        emitToken = False
        if data == u"=":
            self.state = self.beforeAttributeValueState
        elif data in asciiLetters:
            self.currentToken["data"][-1][0] += data +\
              self.stream.charsUntil(asciiLetters, True)
            leavingThisState = False
        elif data == u">":
            # XXX If we emit here the attributes are converted to a dict
            # without being checked and when the code below runs we error
            # because data is a dict not a list
            emitToken = True
        elif data in spaceCharacters:
            self.state = self.afterAttributeNameState
        elif data == u"/":
            self.state = self.selfClosingStartTagState
        elif data in (u"'", u'"', u"<"):
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "invalid-character-in-attribute-name"})
            self.currentToken["data"][-1][0] += data
            leavingThisState = False
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-attribute-name"})
            self.state = self.dataState
            emitToken = True
        else:
            self.currentToken["data"][-1][0] += data
            leavingThisState = False

        if leavingThisState:
            # Attributes are not dropped at this stage. That happens when the
            # start tag token is emitted so values can still be safely appended
            # to attributes, but we do want to report the parse error in time.
            if self.lowercaseAttrName:
                self.currentToken["data"][-1][0] = (
                    self.currentToken["data"][-1][0].translate(asciiUpper2Lower))
            for name, value in self.currentToken["data"][:-1]:
                if self.currentToken["data"][-1][0] == name:
                    self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
                      "duplicate-attribute"})
                    break
            # XXX Fix for above XXX
            if emitToken:
                self.emitCurrentToken()
        return True

    def afterAttributeNameState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            self.stream.charsUntil(spaceCharacters, True)
        elif data == u"=":
            self.state = self.beforeAttributeValueState
        elif data == u">":
            self.emitCurrentToken()
        elif data in asciiLetters:
            self.currentToken["data"].append([data, ""])
            self.state = self.attributeNameState
        elif data == u"/":
            self.state = self.selfClosingStartTagState
        elif data in (u"'", u'"', u"<"):
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "invalid-character-after-attribute-name"})
            self.currentToken["data"].append([data, ""])
            self.state = self.attributeNameState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "expected-end-of-tag-but-got-eof"})
            self.emitCurrentToken()
        else:
            self.currentToken["data"].append([data, ""])
            self.state = self.attributeNameState
        return True

    def beforeAttributeValueState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            self.stream.charsUntil(spaceCharacters, True)
        elif data == u"\"":
            self.state = self.attributeValueDoubleQuotedState
        elif data == u"&":
            self.state = self.attributeValueUnQuotedState
            self.stream.unget(data);
        elif data == u"'":
            self.state = self.attributeValueSingleQuotedState
        elif data == u">":
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "expected-attribute-value-but-got-right-bracket"})
            self.emitCurrentToken()
        elif data in (u"=", u"<", u"`"):
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "equals-in-unquoted-attribute-value"})
            self.currentToken["data"][-1][1] += data
            self.state = self.attributeValueUnQuotedState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "expected-attribute-value-but-got-eof"})
            self.emitCurrentToken()
        else:
            self.currentToken["data"][-1][1] += data
            self.state = self.attributeValueUnQuotedState
        return True

    def attributeValueDoubleQuotedState(self):
        data = self.stream.char()
        if data == "\"":
            self.state = self.afterAttributeValueState
        elif data == u"&":
            self.processEntityInAttribute(u'"')
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-attribute-value-double-quote"})
            self.emitCurrentToken()
        else:
            self.currentToken["data"][-1][1] += data +\
              self.stream.charsUntil(("\"", u"&"))
        return True

    def attributeValueSingleQuotedState(self):
        data = self.stream.char()
        if data == "'":
            self.state = self.afterAttributeValueState
        elif data == u"&":
            self.processEntityInAttribute(u"'")
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-attribute-value-single-quote"})
            self.emitCurrentToken()
        else:
            self.currentToken["data"][-1][1] += data +\
              self.stream.charsUntil(("'", u"&"))
        return True

    def attributeValueUnQuotedState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            self.state = self.beforeAttributeNameState
        elif data == u"&":
            self.processEntityInAttribute(">")
        elif data == u">":
            self.emitCurrentToken()
        elif data in (u'"', u"'", u"=", u"<", u"`"):
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-character-in-unquoted-attribute-value"})
            self.currentToken["data"][-1][1] += data
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-attribute-value-no-quotes"})
            self.emitCurrentToken()
        else:
            self.currentToken["data"][-1][1] += data + self.stream.charsUntil(
              frozenset((u"&", u">", u'"', u"'", u"=", u"<", u"`")) | spaceCharacters)
        return True

    def afterAttributeValueState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            self.state = self.beforeAttributeNameState
        elif data == u">":
            self.emitCurrentToken()
        elif data == u"/":
            self.state = self.selfClosingStartTagState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-EOF-after-attribute-value"})
            self.emitCurrentToken()
            self.stream.unget(data)
            self.state = self.dataState
        else:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-character-after-attribute-value"})
            self.stream.unget(data)
            self.state = self.beforeAttributeNameState
        return True

    def selfClosingStartTagState(self):
        data = self.stream.char()
        if data == ">":
            self.currentToken["selfClosing"] = True
            self.emitCurrentToken()
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], 
                                    "data":
                                        "unexpected-EOF-after-solidus-in-tag"})
            self.stream.unget(data)
            self.state = self.dataState
        else:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-character-after-soldius-in-tag"})
            self.stream.unget(data)
            self.state = self.beforeAttributeNameState
        return True

    def bogusCommentState(self):
        # Make a new comment token and give it as value all the characters
        # until the first > or EOF (charsUntil checks for EOF automatically)
        # and emit it.
        self.tokenQueue.append(
          {"type": tokenTypes["Comment"], "data": self.stream.charsUntil(u">")})

        # Eat the character directly after the bogus comment which is either a
        # ">" or an EOF.
        self.stream.char()
        self.state = self.dataState
        return True

    def bogusCommentContinuationState(self):
        # Like bogusCommentState, but the caller must create the comment token
        # and this state just adds more characters to it
        self.currentToken["data"] += self.stream.charsUntil(u">")
        self.tokenQueue.append(self.currentToken)

        # Eat the character directly after the bogus comment which is either a
        # ">" or an EOF.
        self.stream.char()
        self.state = self.dataState
        return True

    def markupDeclarationOpenState(self):
        charStack = [self.stream.char()]
        if charStack[-1] == u"-":
            charStack.append(self.stream.char())
            if charStack[-1] == u"-":
                self.currentToken = {"type": tokenTypes["Comment"], "data": u""}
                self.state = self.commentStartState
                return True
        elif charStack[-1] in (u'd', u'D'):
            matched = True
            for expected in ((u'o', u'O'), (u'c', u'C'), (u't', u'T'),
                             (u'y', u'Y'), (u'p', u'P'), (u'e', u'E')):
                charStack.append(self.stream.char())
                if charStack[-1] not in expected:
                    matched = False
                    break
            if matched:
                self.currentToken = {"type": tokenTypes["Doctype"],
                                     "name": u"",
                                     "publicId": None, "systemId": None, 
                                     "correct": True}
                self.state = self.doctypeState
                return True

        self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
          "expected-dashes-or-doctype"})
        # charStack[:-2] consists of 'safe' characters ('-', 'd', 'o', etc)
        # so they can be copied directly into the bogus comment data, and only
        # the last character might be '>' or EOF and needs to be ungetted
        self.stream.unget(charStack.pop())
        self.currentToken = {"type": tokenTypes["Comment"], 
                             "data": u"".join(charStack)}
        self.state = self.bogusCommentContinuationState
        return True

    def commentStartState(self):
        data = self.stream.char()
        if data == "-":
            self.state = self.commentStartDashState
        elif data == ">":
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "incorrect-comment"})
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-comment"})
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.currentToken["data"] += data + self.stream.charsUntil(u"-")
            self.state = self.commentState
        return True
    
    def commentStartDashState(self):
        data = self.stream.char()
        if data == "-":
            self.state = self.commentEndState
        elif data == ">":
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "incorrect-comment"})
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-comment"})
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.currentToken["data"] += "-" + data + self.stream.charsUntil(u"-")
            self.state = self.commentState
        return True

    
    def commentState(self):
        data = self.stream.char()
        if data == u"-":
            self.state = self.commentEndDashState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-comment"})
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.currentToken["data"] += data + self.stream.charsUntil(u"-")
        return True

    def commentEndDashState(self):
        data = self.stream.char()
        if data == u"-":
            self.state = self.commentEndState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-comment-end-dash"})
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.currentToken["data"] += u"-" + data +\
              self.stream.charsUntil(u"-")
            # Consume the next character which is either a "-" or an EOF as
            # well so if there's a "-" directly after the "-" we go nicely to
            # the "comment end state" without emitting a ParseError() there.
            self.stream.char()
        return True

    def commentEndState(self):
        data = self.stream.char()
        if data == u">":
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data == u"-":
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
             "unexpected-dash-after-double-dash-in-comment"})
            self.currentToken["data"] += data
        elif data in spaceCharacters:
            self.currentToken["data"] += "--" + data
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-space-after-double-dash-in-comment"})
            self.state = self.commentEndSpaceState
        elif data == "!":
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-bang-after-double-dash-in-comment"})
            self.state = self.commentEndBangState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-comment-double-dash"})
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            # XXX
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-char-in-comment"})
            self.currentToken["data"] += u"--" + data
            self.state = self.commentState
        return True

    def commentEndBangState(self):
        data = self.stream.char()
        if data == u">":
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data == u"-":
            self.currentToken["data"] += "--!"
            self.state = self.commentEndDashState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-comment-end-bang-state"})
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.currentToken["data"] += u"--!" + data
            self.state = self.commentState
        return True

    def commentEndSpaceState(self):
        data = self.stream.char()
        if data == u">":
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data == u"-":
            self.state = self.commentEndDashState
        elif data in spaceCharacters:
            self.currentToken["data"] += data
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-comment-end-space-state"})
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.currentToken["data"] += data
            self.state = self.commentState
        return True

    def doctypeState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            self.state = self.beforeDoctypeNameState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "expected-doctype-name-but-got-eof"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "need-space-after-doctype"})
            self.stream.unget(data)
            self.state = self.beforeDoctypeNameState
        return True

    def beforeDoctypeNameState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            pass
        elif data == u">":
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "expected-doctype-name-but-got-right-bracket"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "expected-doctype-name-but-got-eof"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.currentToken["name"] = data
            self.state = self.doctypeNameState
        return True

    def doctypeNameState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            self.currentToken["name"] = self.currentToken["name"].translate(asciiUpper2Lower)
            self.state = self.afterDoctypeNameState
        elif data == u">":
            self.currentToken["name"] = self.currentToken["name"].translate(asciiUpper2Lower)
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-doctype-name"})
            self.currentToken["correct"] = False
            self.currentToken["name"] = self.currentToken["name"].translate(asciiUpper2Lower)
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.currentToken["name"] += data
        return True

    def afterDoctypeNameState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            pass
        elif data == u">":
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data is EOF:
            self.currentToken["correct"] = False
            self.stream.unget(data)
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-doctype"})
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            if data in (u"p", u"P"):
                matched = True
                for expected in ((u"u", u"U"), (u"b", u"B"), (u"l", u"L"),
                                 (u"i", u"I"), (u"c", u"C")):
                    data = self.stream.char()
                    if data not in expected:
                        matched = False
                        break
                if matched:
                    self.state = self.afterDoctypePublicKeywordState
                    return True
            elif data in (u"s", u"S"):
                matched = True
                for expected in ((u"y", u"Y"), (u"s", u"S"), (u"t", u"T"),
                                 (u"e", u"E"), (u"m", u"M")):
                    data = self.stream.char()
                    if data not in expected:
                        matched = False
                        break
                if matched:
                    self.state = self.afterDoctypeSystemKeywordState
                    return True

            # All the characters read before the current 'data' will be
            # [a-zA-Z], so they're garbage in the bogus doctype and can be
            # discarded; only the latest character might be '>' or EOF
            # and needs to be ungetted
            self.stream.unget(data)
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
                "expected-space-or-right-bracket-in-doctype", "datavars":
                {"data": data}})
            self.currentToken["correct"] = False
            self.state = self.bogusDoctypeState

        return True
    
    def afterDoctypePublicKeywordState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            self.state = self.beforeDoctypePublicIdentifierState
        elif data in ("'", '"'):
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-char-in-doctype"})
            self.stream.unget(data)
            self.state = self.beforeDoctypePublicIdentifierState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.stream.unget(data)
            self.state = self.beforeDoctypePublicIdentifierState
        return True

    def beforeDoctypePublicIdentifierState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            pass
        elif data == "\"":
            self.currentToken["publicId"] = u""
            self.state = self.doctypePublicIdentifierDoubleQuotedState
        elif data == "'":
            self.currentToken["publicId"] = u""
            self.state = self.doctypePublicIdentifierSingleQuotedState
        elif data == ">":
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-end-of-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-char-in-doctype"})
            self.currentToken["correct"] = False
            self.state = self.bogusDoctypeState
        return True

    def doctypePublicIdentifierDoubleQuotedState(self):
        data = self.stream.char()
        if data == "\"":
            self.state = self.afterDoctypePublicIdentifierState
        elif data == ">":
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-end-of-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.currentToken["publicId"] += data
        return True

    def doctypePublicIdentifierSingleQuotedState(self):
        data = self.stream.char()
        if data == "'":
            self.state = self.afterDoctypePublicIdentifierState
        elif data == ">":
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-end-of-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.currentToken["publicId"] += data
        return True

    def afterDoctypePublicIdentifierState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            self.state = self.betweenDoctypePublicAndSystemIdentifiersState
        elif data == ">":
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data == '"':
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-char-in-doctype"})
            self.currentToken["systemId"] = u""
            self.state = self.doctypeSystemIdentifierDoubleQuotedState
        elif data == "'":
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-char-in-doctype"})
            self.currentToken["systemId"] = u""
            self.state = self.doctypeSystemIdentifierSingleQuotedState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-char-in-doctype"})
            self.currentToken["correct"] = False
            self.state = self.bogusDoctypeState
        return True
    
    def betweenDoctypePublicAndSystemIdentifiersState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            pass
        elif data == ">":
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data == '"':
            self.currentToken["systemId"] = u""
            self.state = self.doctypeSystemIdentifierDoubleQuotedState
        elif data == "'":
            self.currentToken["systemId"] = u""
            self.state = self.doctypeSystemIdentifierSingleQuotedState
        elif data == EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-char-in-doctype"})
            self.currentToken["correct"] = False
            self.state = self.bogusDoctypeState
        return True
    
    def afterDoctypeSystemKeywordState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            self.state = self.beforeDoctypeSystemIdentifierState
        elif data in ("'", '"'):
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-char-in-doctype"})
            self.stream.unget(data)
            self.state = self.beforeDoctypeSystemIdentifierState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.stream.unget(data)
            self.state = self.beforeDoctypeSystemIdentifierState
        return True
    
    def beforeDoctypeSystemIdentifierState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            pass
        elif data == "\"":
            self.currentToken["systemId"] = u""
            self.state = self.doctypeSystemIdentifierDoubleQuotedState
        elif data == "'":
            self.currentToken["systemId"] = u""
            self.state = self.doctypeSystemIdentifierSingleQuotedState
        elif data == ">":
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-char-in-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-char-in-doctype"})
            self.currentToken["correct"] = False
            self.state = self.bogusDoctypeState
        return True

    def doctypeSystemIdentifierDoubleQuotedState(self):
        data = self.stream.char()
        if data == "\"":
            self.state = self.afterDoctypeSystemIdentifierState
        elif data == ">":
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-end-of-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.currentToken["systemId"] += data
        return True

    def doctypeSystemIdentifierSingleQuotedState(self):
        data = self.stream.char()
        if data == "'":
            self.state = self.afterDoctypeSystemIdentifierState
        elif data == ">":
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-end-of-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.currentToken["systemId"] += data
        return True

    def afterDoctypeSystemIdentifierState(self):
        data = self.stream.char()
        if data in spaceCharacters:
            pass
        elif data == ">":
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data is EOF:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "eof-in-doctype"})
            self.currentToken["correct"] = False
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            self.tokenQueue.append({"type": tokenTypes["ParseError"], "data":
              "unexpected-char-in-doctype"})
            self.state = self.bogusDoctypeState
        return True

    def bogusDoctypeState(self):
        data = self.stream.char()
        if data == u">":
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        elif data is EOF:
            # XXX EMIT
            self.stream.unget(data)
            self.tokenQueue.append(self.currentToken)
            self.state = self.dataState
        else:
            pass
        return True
