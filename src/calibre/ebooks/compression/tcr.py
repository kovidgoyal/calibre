# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

def decompress(stream):
        txt = []
        stream.seek(0)
        if stream.read(9) != '!!8-Bit!!':
            raise ValueError('File %s contaions an invalid TCR header.' % stream.name)

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


def compress(txt, level=5):
    '''
    TCR compression takes the form header+code_list+coded_text.
    The header is always "!!8-Bit!!". The code list is a list of 256 strings.
    The list takes the form 1 byte length and then a string. Each position in
    The list corresponds to a code found in the file. The coded text is
    string of characters vaules. for instance the character Q represents the
    value 81 which corresponds to the string in the code list at position 81.
    '''
    # Turn each unique character into a coded value.
    # The code of the string at a given position are represented by the position
    # they occupy in the list.
    codes = list(set(re.findall('(?msu).', txt)))
    for i in range(len(codes), 256):
        codes.append('')
    # Set the compression level.
    if level <= 1:
        new_length = 256
    if level >= 10:
        new_length = 1
    else:
        new_length = int(256 * (10 - level) * .1)
    new_length = 1 if new_length < 1 else new_length
    # Replace txt with codes.
    coded_txt = ''
    for c in txt:
        coded_txt += chr(codes.index(c))
    txt = coded_txt
    # Start compressing the text.
    new = True
    merged = True
    while new or merged:
        # Merge codes that always follow another code
        merge = []
        merged = False
        for i in xrange(256):
            if codes[i] != '':
                # Find all codes that are next to i.
                fall = list(set(re.findall('(?msu)%s.' % re.escape(chr(i)), txt)))
                # 1 if only one code comes after i.
                if len(fall) == 1:
                    # We are searching codes and each code is always 1 character.
                    j = ord(fall[0][1:2])
                    # Only merge if the total length of the string represented by
                    # code is less than 256.
                    if len(codes[i]) + len(codes[j]) < 256:
                        merge.append((i, j))
        if merge:
            merged = True
            for i, j in merge:
                # Merge the string for j into the string for i.
                if i == j:
                    # Don't use += here just in case something goes wrong. This
                    # will prevent out of control memory consumption. This is
                    # unecessary but when creating this routine it happened due
                    # to an error.
                    codes[i] = codes[i] + codes[i]
                else:
                    codes[i] = codes[i] + codes[j]
                txt = txt.replace(chr(i)+chr(j), chr(i))
                if chr(j) not in txt:
                    codes[j] = ''
        new = False
        if '' in codes:
            # Create a list of codes based on combinations of codes that are next
            # to each other. The amount of savings for the new code is calculated.
            new_codes = []
            for c in list(set(re.findall('(?msu)..', txt))):
                i = ord(c[0:1])
                j = ord(c[1:2])
                if codes[i]+codes[j] in codes:
                    continue
                savings = txt.count(chr(i)+chr(j)) - len(codes[i]) - len(codes[j])
                if savings > 2 and len(codes[i]) + len(codes[j]) < 256:
                    new_codes.append((savings, i, j, codes[i], codes[j]))
            if new_codes:
                new = True
                # Sort the codes from highest savings to lowest.
                new_codes.sort(lambda x, y: -1 if x[0] > y[0] else 1 if x[0] < y[0] else 0)
                # The shorter new_length the more chances time merging will happen
                # giving more changes for better codes to be created. However,
                # the shorter new_lengh the longer it will take to compress.
                new_codes = new_codes[:new_length]
                for code in new_codes:
                    if '' not in codes:
                        break
                    c = codes.index('')
                    codes[c] = code[3]+code[4]
                    txt = txt.replace(chr(code[1])+chr(code[2]), chr(c))
    # Generate the code dictionary.
    header = []
    for code in codes:
        header.append(chr(len(code))+code)
    for i in xrange(len(header), 256):
        header.append(chr(0))
    # Join the identifier with the dictionary and coded text.
    return '!!8-Bit!!'+''.join(header)+txt
