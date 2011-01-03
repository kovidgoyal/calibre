# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

class TCRCompressor(object):
    '''
    TCR compression takes the form header+code_dict+coded_text.
    The header is always "!!8-Bit!!". The code dict is a list of 256 strings.
    The list takes the form 1 byte length and then a string. Each position in
    The list corresponds to a code found in the file. The coded text is
    string of characters values. for instance the character Q represents the
    value 81 which corresponds to the string in the code list at position 81.
    '''
    
    def _reset(self):
        # List of indexes in the codes list that are empty and can hold new codes
        self.unused_codes = set()
        self.coded_txt = ''
        # Generate initial codes from text.
        # The index of the list will be the code that represents the characters at that location
        # in the list
        self.codes = []
        
    def _combine_codes(self):
        '''
        Combine two codes that always appear in pair into a single code.
        The intent is to create more unused codes.
        '''
        possible_codes = []
        a_code = set(re.findall('(?msu).', self.coded_txt))
        
        for code in a_code:
            single_code = set(re.findall('(?msu)%s.' % re.escape(code), self.coded_txt))
            if len(single_code) == 1:
                possible_codes.append(single_code.pop())
                
        for code in possible_codes:
            self.coded_txt = self.coded_txt.replace(code, code[0])
            self.codes[ord(code[0])] = '%s%s' % (self.codes[ord(code[0])], self.codes[ord(code[1])])
        
    def _free_unused_codes(self):
        '''
        Look for codes that do no not appear in the coded text and add them to
        the list of free codes.
        '''
        for i in xrange(256):
            if i not in self.unused_codes:
                if chr(i) not in self.coded_txt:
                    self.unused_codes.add(i)
    
    def _new_codes(self):
        '''
        Create new codes from codes that occur in pairs often.
        '''
        possible_new_codes = list(set(re.findall('(?msu)..', self.coded_txt)))
        new_codes_count = []
        
        for c in possible_new_codes:
            count = self.coded_txt.count(c)
            # Less than 3 occurrences will not produce any size reduction.
            if count > 2:
                new_codes_count.append((c, count))
        
        # Arrange the codes in order of least to most occurring. 
        possible_new_codes = [x[0] for x in sorted(new_codes_count, key=lambda c: c[1])]
        
        return possible_new_codes
        
    def compress(self, txt):
        self._reset()
        
        self.codes = list(set(re.findall('(?msu).', txt)))
        
        # Replace the text with their corresponding code
        for c in txt:
            self.coded_txt += chr(self.codes.index(c))
        
        # Zero the unused codes and record which are unused.
        for i in range(len(self.codes), 256):
            self.codes.append('')
            self.unused_codes.add(i)
            
        self._combine_codes()
        possible_codes = self._new_codes()

        while possible_codes and self.unused_codes:
            while possible_codes and self.unused_codes:
                unused_code = self.unused_codes.pop()
                # Take the last possible codes and split it into individual
                # codes. The last possible code is the most often occurring.
                code1, code2 = possible_codes.pop()
                self.codes[unused_code] = '%s%s' % (self.codes[ord(code1)], self.codes[ord(code2)])
                self.coded_txt = self.coded_txt.replace('%s%s' % (code1, code2), chr(unused_code))
            self._combine_codes()
            self._free_unused_codes()
            possible_codes = self._new_codes()

        self._free_unused_codes()

        # Generate the code dictionary.
        code_dict = []
        for i in xrange(0, 256):
            if i in self.unused_codes:
                code_dict.append(chr(0))
            else:
                code_dict.append(chr(len(self.codes[i])) + self.codes[i])
    
        # Join the identifier with the dictionary and coded text.
        return '!!8-Bit!!'+''.join(code_dict)+self.coded_txt


def decompress(stream):
        txt = []
        stream.seek(0)
        if stream.read(9) != '!!8-Bit!!':
            raise ValueError('File %s contains an invalid TCR header.' % stream.name)

        # Codes that the file contents are broken down into.
        entries = []
        for i in xrange(256):
            entry_len = ord(stream.read(1))
            entries.append(stream.read(entry_len))

        # Map the values in the file to locations in the string list.
        entry_loc = stream.read(1)
        while entry_loc != '': # EOF
            txt.append(entries[ord(entry_loc)])
            entry_loc = stream.read(1)

        return ''.join(txt)

def compress(txt):
    t = TCRCompressor()
    return t.compress(txt)
