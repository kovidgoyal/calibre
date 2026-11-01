#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Gerendi Sandor Attila

"""
RTF tokenizer and token parser. v.1.0 (1/17/2010)
Author: Gerendi Sandor Attila

At this point this will tokenize a RTF file then rebuild it from the tokens.
In the process the UTF8 tokens are altered to be supported by the RTF2XML and also remain RTF specification compliant.
"""


class tokenDelimitatorStart:
    def __init__(self) -> None:
        pass

    def toRTF(self) -> str:
        return '{'

    def __repr__(self) -> str:
        return '{'


class tokenDelimitatorEnd:
    def __init__(self) -> None:
        pass

    def toRTF(self) -> str:
        return '}'

    def __repr__(self) -> str:
        return '}'


class tokenControlWord:
    def __init__(self, name: str, separator: str = '') -> None:
        self.name = name
        self.separator = separator

    def toRTF(self) -> str:
        return self.name + self.separator

    def __repr__(self) -> str:
        return self.name + self.separator


class tokenControlWordWithNumericArgument:
    def __init__(self, name: str, argument: int, separator: str = '') -> None:
        self.name = name
        self.argument = argument
        self.separator = separator

    def toRTF(self) -> str:
        return self.name + repr(self.argument) + self.separator

    def __repr__(self) -> str:
        return self.name + repr(self.argument) + self.separator


class tokenControlSymbol:
    def __init__(self, name: str) -> None:
        self.name = name

    def toRTF(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name


class tokenData:
    def __init__(self, data: str) -> None:
        self.data = data

    def toRTF(self) -> str:
        return self.data

    def __repr__(self) -> str:
        return self.data


class tokenBinN:
    def __init__(self, data: str, separator: str = '') -> None:
        self.data = data
        self.separator = separator

    def toRTF(self) -> str:
        return '\\bin' + repr(len(self.data)) + self.separator + self.data

    def __repr__(self) -> str:
        return '\\bin' + repr(len(self.data)) + self.separator + self.data


class token8bitChar:
    def __init__(self, data: str) -> None:
        self.data = data

    def toRTF(self) -> str:
        return "\\'" + self.data

    def __repr__(self) -> str:
        return "\\'" + self.data


class tokenUnicode:
    def __init__(self, data: int, separator: str = '', current_ucn: int = 1, eqList: list[Token] | None = None) -> None:
        if eqList is None:
            eqList = []
        self.data = data
        self.separator = separator
        self.current_ucn = current_ucn
        self.eqList = eqList

    def toRTF(self) -> str:
        result = '\\u' + repr(self.data) + ' '
        ucn = self.current_ucn
        if len(self.eqList) < ucn:
            ucn = len(self.eqList)
            result = tokenControlWordWithNumericArgument('\\uc', ucn).toRTF() + result
        i = 0
        for eq in self.eqList:
            if i >= ucn:
                break
            result = result + eq.toRTF()
        return result

    def __repr__(self) -> str:
        return '\\u' + repr(self.data)


type Token = (
    tokenDelimitatorStart
    | tokenDelimitatorEnd
    | tokenControlWord
    | tokenControlWordWithNumericArgument
    | tokenControlSymbol
    | tokenData
    | tokenBinN
    | token8bitChar
    | tokenUnicode
)


def isAsciiLetter(value: str) -> bool:
    return ((value >= 'a') and (value <= 'z')) or ((value >= 'A') and (value <= 'Z'))


def isDigit(value: str) -> bool:
    return (value >= '0') and (value <= '9')


def isChar(value: str, char: str) -> bool:
    return value == char


def isString(buffer: str, string: str) -> bool:
    return buffer == string


class RtfTokenParser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.process()
        self.processUnicode()

    def process(self) -> None:
        i = 0
        newTokens = []
        while i < len(self.tokens):
            token = self.tokens[i]
            if isinstance(token, tokenControlSymbol):
                if isString(token.name, "\\'"):
                    i = i + 1
                    dataToken = self.tokens[i]
                    if not isinstance(dataToken, tokenData):
                        raise Exception('Error: token8bitChar without data.')
                    if len(dataToken.data) < 2:
                        raise Exception('Error: token8bitChar without data.')
                    newTokens.append(token8bitChar(dataToken.data[0:2]))
                    if len(dataToken.data) > 2:
                        newTokens.append(tokenData(dataToken.data[2:]))
                    i = i + 1
                    continue

            newTokens.append(token)
            i = i + 1

        self.tokens = list(newTokens)

    def processUnicode(self) -> None:
        i = 0
        newTokens: list[Token] = []
        ucNbStack = [1]
        while i < len(self.tokens):
            token = self.tokens[i]
            if isinstance(token, tokenDelimitatorStart):
                ucNbStack.append(ucNbStack[len(ucNbStack) - 1])
                newTokens.append(token)
                i = i + 1
                continue
            if isinstance(token, tokenDelimitatorEnd):
                ucNbStack.pop()
                newTokens.append(token)
                i = i + 1
                continue
            if isinstance(token, tokenControlWordWithNumericArgument):
                if isString(token.name, '\\uc'):
                    ucNbStack[len(ucNbStack) - 1] = token.argument
                    newTokens.append(token)
                    i = i + 1
                    continue
                if isString(token.name, '\\u'):
                    j = 0
                    i = i + 1
                    replace: list[Token] = []
                    partialData = None
                    ucn = ucNbStack[len(ucNbStack) - 1]
                    while (i < len(self.tokens)) and (j < ucn):
                        replToken = self.tokens[i]
                        if isinstance(replToken, tokenDelimitatorStart):
                            break
                        if isinstance(replToken, tokenDelimitatorEnd):
                            break
                        if isinstance(replToken, tokenData):
                            if len(replToken.data) >= ucn - j:
                                replace.append(tokenData(replToken.data[0 : ucn - j]))
                                if len(replToken.data) > ucn - j:
                                    partialData = tokenData(replToken.data[ucn - j :])
                                i = i + 1
                                break
                            else:
                                replace.append(replToken)
                                j = j + len(replToken.data)
                                i = i + 1
                                continue
                        if isinstance(replToken, (token8bitChar, tokenBinN)):
                            replace.append(replToken)
                            i = i + 1
                            j = j + 1
                            continue
                        raise Exception('Error: incorrect utf replacement.')

                    # calibre rtf2xml does not support utfreplace
                    replace = []

                    newTokens.append(tokenUnicode(token.argument, token.separator, ucNbStack[len(ucNbStack) - 1], replace))
                    if partialData is not None:
                        newTokens.append(partialData)
                    continue

            newTokens.append(token)
            i = i + 1

        self.tokens = list(newTokens)

    def toRTF(self) -> str:
        result = []
        for token in self.tokens:
            result.append(token.toRTF())
        return ''.join(result)


class RtfTokenizer:
    def __init__(self, rtfData: str) -> None:
        self.rtfData = rtfData
        self.tokens: list[Token] = []
        self.tokenize()

    def tokenize(self) -> None:
        i = 0
        lastDataStart = -1
        while i < len(self.rtfData):
            if isChar(self.rtfData[i], '{'):
                if lastDataStart > -1:
                    self.tokens.append(tokenData(self.rtfData[lastDataStart:i]))
                    lastDataStart = -1
                self.tokens.append(tokenDelimitatorStart())
                i = i + 1
                continue

            if isChar(self.rtfData[i], '}'):
                if lastDataStart > -1:
                    self.tokens.append(tokenData(self.rtfData[lastDataStart:i]))
                    lastDataStart = -1
                self.tokens.append(tokenDelimitatorEnd())
                i = i + 1
                continue

            if isChar(self.rtfData[i], '\\'):
                if i + 1 >= len(self.rtfData):
                    raise Exception('Error: Control character found at the end of the document.')

                if lastDataStart > -1:
                    self.tokens.append(tokenData(self.rtfData[lastDataStart:i]))
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
                        raise Exception(f'Error (at:{tokenStart}): Control Word without end.')

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
                            if l > 10:
                                raise Exception(f'Error (at:{tokenStart}): Too many digits in control word numeric argument.')

                        if not consumed:
                            raise Exception(f'Error (at:{tokenStart}): Control Word without numeric argument end.')

                    separator = ''
                    if isChar(self.rtfData[i], ' '):
                        separator = ' '

                    controlWord = self.rtfData[tokenStart:tokenEnd]
                    if tokenEnd < i:
                        value = int(self.rtfData[tokenEnd:i])
                        if isString(controlWord, '\\bin'):
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

    def toRTF(self) -> str:
        result = []
        for token in self.tokens:
            result.append(token.toRTF())
        return ''.join(result)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print('Usage %prog rtfFileToConvert')
        sys.exit()
    # RTF is a 7-bit format, latin-1 round trips any stray 8-bit bytes unchanged
    with open(sys.argv[1], encoding='latin-1') as f:
        data = f.read()

    tokenizer = RtfTokenizer(data)
    parsedTokens = RtfTokenParser(tokenizer.tokens)

    data = parsedTokens.toRTF()

    with open(sys.argv[1], 'w', encoding='latin-1') as f:
        f.write(data)
