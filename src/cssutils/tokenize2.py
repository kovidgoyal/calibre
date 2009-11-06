#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""New CSS Tokenizer (a generator)
"""
__all__ = ['Tokenizer', 'CSSProductions']
__docformat__ = 'restructuredtext'
__version__ = '$Id: tokenize2.py 1865 2009-10-11 15:23:11Z cthedot $'

from cssproductions import *
from helper import normalize
import itertools
import re

class Tokenizer(object):
    """
    generates a list of Token tuples:
        (Tokenname, value, startline, startcolumn)
    """
    _atkeywords = {
        u'@font-face': CSSProductions.FONT_FACE_SYM,
        u'@import': CSSProductions.IMPORT_SYM,
        u'@media': CSSProductions.MEDIA_SYM,        
        u'@namespace': CSSProductions.NAMESPACE_SYM,
        u'@page': CSSProductions.PAGE_SYM,
        u'@variables': CSSProductions.VARIABLES_SYM
        }
    _linesep = u'\n'
    unicodesub = re.compile(r'\\[0-9a-fA-F]{1,6}(?:\r\n|[\t|\r|\n|\f|\x20])?').sub
    cleanstring = re.compile(r'\\((\r\n)|[\n|\r|\f])').sub
    
    def __init__(self, macros=None, productions=None):
        """
        inits tokenizer with given macros and productions which default to
        cssutils own macros and productions
        """
        if not macros:
            macros = MACROS
        if not productions:
            productions = PRODUCTIONS
        self.tokenmatches = self._compile_productions(
                self._expand_macros(macros, 
                                    productions))
        self.commentmatcher = [x[1] for x in self.tokenmatches if x[0] == 'COMMENT'][0]
        self.urimatcher = [x[1] for x in self.tokenmatches if x[0] == 'URI'][0]
        
        self._pushed = []

    def _expand_macros(self, macros, productions):
        """returns macro expanded productions, order of productions is kept"""
        def macro_value(m):
            return '(?:%s)' % macros[m.groupdict()['macro']]
        expanded = []
        for key, value in productions:
            while re.search(r'{[a-zA-Z][a-zA-Z0-9-]*}', value):
                value = re.sub(r'{(?P<macro>[a-zA-Z][a-zA-Z0-9-]*)}',
                               macro_value, value)
            expanded.append((key, value))
        return expanded

    def _compile_productions(self, expanded_productions):
        """compile productions into callable match objects, order is kept"""
        compiled = []
        for key, value in expanded_productions:
            compiled.append((key, re.compile('^(?:%s)' % value, re.U).match))
        return compiled

    def push(self, *tokens):
        """Push back tokens which have been pulled but not processed."""
        self._pushed = itertools.chain(tokens, self._pushed)

    def clear(self):
        self._pushed = []

    def tokenize(self, text, fullsheet=False):
        """Generator: Tokenize text and yield tokens, each token is a tuple 
        of::
        
            (nname, value, line, col)
        
        The token value will contain a normal string, meaning CSS unicode 
        escapes have been resolved to normal characters. The serializer
        escapes needed characters back to unicode escapes depending on
        the stylesheet target encoding.

        text
            to be tokenized
        fullsheet
            if ``True`` appends EOF token as last one and completes incomplete
            COMMENT or INVALID (to STRING) tokens
        """
        def _repl(m):
            "used by unicodesub"
            num = int(m.group(0)[1:], 16)
            if num < 0x10000:
                return unichr(num)
            else:
                return m.group(0)

        def _normalize(value):
            "normalize and do unicodesub"
            return normalize(self.unicodesub(_repl, value))

        line = col = 1
        
        # check for BOM first as it should only be max one at the start
        (BOM, matcher), productions = self.tokenmatches[0], self.tokenmatches[1:]
        match = matcher(text)
        if match:
            found = match.group(0)
            yield (BOM, found, line, col)
            text = text[len(found):]

        # check for @charset which is valid only at start of CSS
        if text.startswith('@charset '):
            found = '@charset ' # production has trailing S!
            yield (CSSProductions.CHARSET_SYM, found, line, col)
            text = text[len(found):]
            col += len(found)
        
        while text:
            
            for pushed in self._pushed:
                # do pushed tokens before new ones 
                yield pushed

            # speed test for most used CHARs
            c = text[0]
            if c in '{}:;,':
                yield ('CHAR', c, line, col)
                col += 1
                text = text[1:]
                
            else:
                # check all other productions, at least CHAR must match
                for name, matcher in productions:
                    if fullsheet and name == 'CHAR' and text.startswith(u'/*'):
                        # before CHAR production test for incomplete comment
                        possiblecomment = u'%s*/' % text
                        match = self.commentmatcher(possiblecomment)
                        if match:
                            yield ('COMMENT', possiblecomment, line, col)
                            text = None # eats all remaining text 
                            break 
    
                    match = matcher(text) # if no match try next production
                    if match:
                        found = match.group(0) # needed later for line/col
                        if fullsheet:                        
                            # check if found may be completed into a full token
                            if 'INVALID' == name and text == found:
                                # complete INVALID to STRING with start char " or '
                                name, found = 'STRING', '%s%s' % (found, found[0])
                            
                            elif 'FUNCTION' == name and\
                                 u'url(' == _normalize(found):
                                # FUNCTION url( is fixed to URI if fullsheet
                                # FUNCTION production MUST BE after URI production!
                                for end in (u"')", u'")', u')'):
                                    possibleuri = '%s%s' % (text, end)
                                    match = self.urimatcher(possibleuri)
                                    if match:
                                        name, found = 'URI', match.group(0)
                                        break
    
                        if name in ('DIMENSION', 'IDENT', 'STRING', 'URI', 
                                    'HASH', 'COMMENT', 'FUNCTION', 'INVALID',
                                    'UNICODE-RANGE'):
                            # may contain unicode escape, replace with normal char
                            # but do not _normalize (?)
                            value = self.unicodesub(_repl, found)
                            if name in ('STRING', 'INVALID'): #'URI'?
                                # remove \ followed by nl (so escaped) from string
                                value = self.cleanstring('', found)
    
                        else:
                            if 'ATKEYWORD' == name:
                                # get actual ATKEYWORD SYM
                                if '@charset' == found and ' ' == text[len(found):len(found)+1]:
                                    # only this syntax!
                                    name = CSSProductions.CHARSET_SYM
                                    found += ' '
                                else:
                                    name = self._atkeywords.get(_normalize(found), 'ATKEYWORD')
                                    
                            value = found # should not contain unicode escape (?)
                        yield (name, value, line, col)
                        text = text[len(found):]
                        nls = found.count(self._linesep)
                        line += nls
                        if nls:
                            col = len(found[found.rfind(self._linesep):])
                        else:
                            col += len(found)
                        break

        if fullsheet:
            yield ('EOF', u'', line, col)
