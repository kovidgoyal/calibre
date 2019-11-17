#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Gerendi Sandor Attila'
__docformat__ = 'restructuredtext en'

"""
RTF tokenizer and token parser. v.1.0 (1/17/2010)
Author: Gerendi Sandor Attila

At this point this will tokenize a RTF file then rebuild it from the tokens.
In the process the UTF8 tokens are altered to be supported by the RTF2XML and also remain RTF specification compilant.
"""


class tokenDelimitatorStart():

    def __init__(self):
        pass

    def toRTF(self):
        return '{'

    def __repr__(self):
        return '{'


class tokenDelimitatorEnd():

    def __init__(self):
        pass

    def toRTF(self):
        return '}'

    def __repr__(self):
        return '}'


class tokenControlWord():

    def __init__(self, name, separator=''):
        self.name = name
        self.separator = separator

    def toRTF(self):
        return self.name + self.separator

    def __repr__(self):
        return self.name + self.separator


class tokenControlWordWithNumericArgument():

    def __init__(self, name, argument, separator=''):
        self.name = name
        self.argument = argument
        self.separator = separator

    def toRTF(self):
        return self.name + repr(self.argument) + self.separator

    def __repr__(self):
        return self.name + repr(self.argument) + self.separator


class tokenControlSymbol():

    def __init__(self, name):
        self.name = name

    def toRTF(self):
        return self.name

    def __repr__(self):
        return self.name


class tokenData():

    def __init__(self, data):
        self.data = data

    def toRTF(self):
        return self.data

    def __repr__(self):
        return self.data


class tokenBinN():

    def __init__(self, data, separator=''):
        self.data = data
        self.separator = separator

    def toRTF(self):
        return "\\bin" + repr(len(self.data)) + self.separator + self.data

    def __repr__(self):
        return "\\bin" + repr(len(self.data)) + self.separator + self.data


class token8bitChar():

    def __init__(self, data):
        self.data = data

    def toRTF(self):
        return "\\'" + self.data

    def __repr__(self):
        return "\\'" + self.data


class tokenUnicode():

    def __init__(self, data, separator='', current_ucn=1, eqList=[]):
        self.data = data
        self.separator = separator
        self.current_ucn = current_ucn
        self.eqList = eqList

    def toRTF(self):
        result = '\\u' + repr(self.data) + ' '
        ucn = self.current_ucn
        if len(self.eqList) < ucn:
            ucn = len(self.eqList)
            result =  tokenControlWordWithNumericArgument('\\uc', ucn).toRTF() + result
        i = 0
        for eq in self.eqList:
            if i >= ucn:
                break
            result = result + eq.toRTF()
        return result

    def __repr__(self):
        return '\\u' + repr(self.data)


def isAsciiLetter(value):
    return ((value >= 'a') and (value <= 'z')) or ((value >= 'A') and (value <= 'Z'))


def isDigit(value):
    return (value >= '0') and (value <= '9')


def isChar(value, char):
    return value == char


def isString(buffer, string):
    return buffer == string


class RtfTokenParser():

    def __init__(self, tokens):
        self.tokens = tokens
        self.process()
        self.processUnicode()

    def process(self):
        i = 0
        newTokens = []
        while i < len(self.tokens):
            if isinstance(self.tokens[i], tokenControlSymbol):
                if isString(self.tokens[i].name, "\\'"):
                    i = i + 1
                    if not isinstance(self.tokens[i], tokenData):
                        raise Exception('Error: token8bitChar without data.')
                    if len(self.tokens[i].data) < 2:
                        raise Exception('Error: token8bitChar without data.')
                    newTokens.append(token8bitChar(self.tokens[i].data[0:2]))
                    if len(self.tokens[i].data) > 2:
                        newTokens.append(tokenData(self.tokens[i].data[2:]))
                    i = i + 1
                    continue

            newTokens.append(self.tokens[i])
            i = i + 1

        self.tokens = list(newTokens)

    def processUnicode(self):
        i = 0
        newTokens = []
        ucNbStack = [1]
        while i < len(self.tokens):
            if isinstance(self.tokens[i], tokenDelimitatorStart):
                ucNbStack.append(ucNbStack[len(ucNbStack) - 1])
                newTokens.append(self.tokens[i])
                i = i + 1
                continue
            if isinstance(self.tokens[i], tokenDelimitatorEnd):
                ucNbStack.pop()
                newTokens.append(self.tokens[i])
                i = i + 1
                continue
            if isinstance(self.tokens[i], tokenControlWordWithNumericArgument):
                if isString(self.tokens[i].name, '\\uc'):
                    ucNbStack[len(ucNbStack) - 1] = self.tokens[i].argument
                    newTokens.append(self.tokens[i])
                    i = i + 1
                    continue
                if isString(self.tokens[i].name, '\\u'):
                    x = i
                    j = 0
                    i = i + 1
                    replace = []
                    partialData = None
                    ucn = ucNbStack[len(ucNbStack) - 1]
                    while (i < len(self.tokens)) and (j < ucn):
                        if isinstance(self.tokens[i], tokenDelimitatorStart):
                            break
                        if isinstance(self.tokens[i], tokenDelimitatorEnd):
                            break
                        if isinstance(self.tokens[i], tokenData):
                            if len(self.tokens[i].data) >= ucn - j:
                                replace.append(tokenData(self.tokens[i].data[0 : ucn - j]))
                                if len(self.tokens[i].data) > ucn - j:
                                    partialData = tokenData(self.tokens[i].data[ucn - j:])
                                i = i + 1
                                break
                            else:
                                replace.append(self.tokens[i])
                                j = j + len(self.tokens[i].data)
                                i = i + 1
                                continue
                        if isinstance(self.tokens[i], token8bitChar) or isinstance(self.tokens[i], tokenBinN):
                            replace.append(self.tokens[i])
                            i = i + 1
                            j = j + 1
                            continue
                        raise Exception('Error: incorect utf replacement.')

                    # calibre rtf2xml does not support utfreplace
                    replace = []

                    newTokens.append(tokenUnicode(self.tokens[x].argument, self.tokens[x].separator, ucNbStack[len(ucNbStack) - 1], replace))
                    if partialData is not None:
                        newTokens.append(partialData)
                    continue

            newTokens.append(self.tokens[i])
            i = i + 1

        self.tokens = list(newTokens)

    def toRTF(self):
        result = []
        for token in self.tokens:
            result.append(token.toRTF())
        return "".join(result)


class RtfTokenizer():

    def __init__(self, rtfData):
        self.rtfData = []
        self.tokens = []
        self.rtfData = rtfData
        self.tokenize()

    def tokenize(self):
        i = 0
        lastDataStart = -1
        while i < len(self.rtfData):

            if isChar(self.rtfData[i], '{'):
                if lastDataStart > -1:
                    self.tokens.append(tokenData(self.rtfData[lastDataStart : i]))
                    lastDataStart = -1
                self.tokens.append(tokenDelimitatorStart())
                i = i + 1
                continue

            if isChar(self.rtfData[i], '}'):
                if lastDataStart > -1:
                    self.tokens.append(tokenData(self.rtfData[lastDataStart : i]))
                    lastDataStart = -1
                self.tokens.append(tokenDelimitatorEnd())
                i = i + 1
                continue

            if isChar(self.rtfData[i], '\\'):
                if i + 1 >= len(self.rtfData):
                    raise Exception('Error: Control character found at the end of the document.')

                if lastDataStart > -1:
                    self.tokens.append(tokenData(self.rtfData[lastDataStart : i]))
                    lastDataStart = -1

                tokenStart = i
                i = i + 1

                # Control Words
                if isAsciiLetter(self.rtfData[i]):
                    # consume <ASCII Letter Sequence>
                    consumed = False
                    while i < len(self.rtfData):
                        if not isAsciiLetter(self.rtfData[i]):
                            tokenEnd = i
                            consumed = True
                            break
                        i = i + 1

                    if not consumed:
                        raise Exception('Error (at:%d): Control Word without end.'%(tokenStart))

                    # we have numeric argument before delimiter
                    if isChar(self.rtfData[i], '-') or isDigit(self.rtfData[i]):
                        # consume the numeric argument
                        consumed = False
                        l = 0
                        while i < len(self.rtfData):
                            if not isDigit(self.rtfData[i]):
                                consumed = True
                                break
                            l = l + 1
                            i = i + 1
                            if l > 10 :
                                raise Exception('Error (at:%d): Too many digits in control word numeric argument.'%[tokenStart])

                        if not consumed:
                            raise Exception('Error (at:%d): Control Word without numeric argument end.'%[tokenStart])

                    separator = ''
                    if isChar(self.rtfData[i], ' '):
                        separator = ' '

                    controlWord = self.rtfData[tokenStart: tokenEnd]
                    if tokenEnd < i:
                        value = int(self.rtfData[tokenEnd: i])
                        if isString(controlWord, "\\bin"):
                            i = i + value
                            self.tokens.append(tokenBinN(self.rtfData[tokenStart:i], separator))
                        else:
                            self.tokens.append(tokenControlWordWithNumericArgument(controlWord, value, separator))
                    else:
                        self.tokens.append(tokenControlWord(controlWord, separator))
                    # space delimiter, we should discard it
                    if self.rtfData[i] == ' ':
                        i = i + 1

                # Control Symbol
                else:
                    self.tokens.append(tokenControlSymbol(self.rtfData[tokenStart : i + 1]))
                    i = i + 1
                continue

            if lastDataStart < 0:
                lastDataStart = i
            i = i + 1

    def toRTF(self):
        result = []
        for token in self.tokens:
            result.append(token.toRTF())
        return "".join(result)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage %prog rtfFileToConvert")
        sys.exit()
    with open(sys.argv[1], 'rb') as f:
        data = f.read()

    tokenizer = RtfTokenizer(data)
    parsedTokens = RtfTokenParser(tokenizer.tokens)

    data = parsedTokens.toRTF()

    with open(sys.argv[1], 'w') as f:
        f.write(data)
