## Copyright (C) 2003-2006 Rubens Ramos <rubensr@users.sourceforge.net>

## Based on code by:
## Copyright (C) 2003  Razvan Cojocaru <razvanco@gmx.net>

## pychm is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License as
## published by the Free Software Foundation; either version 2 of the
## License, or (at your option) any later version.

## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.

## $Id: chm.py,v 1.12 2006/08/07 12:31:51 rubensr Exp $

'''
   chm - A high-level front end for the chmlib python module.

   The chm module provides high level access to the functionality
   included in chmlib. It encapsulates functions in the CHMFile class, and
   provides some additional features, such as the ability to obtain
   the contents tree of a CHM archive.

'''

import array
import string
import sys
import codecs

import calibre.utils.chm.chmlib as chmlib
from calibre.constants import plugins

extra, extra_err = plugins['chm_extra']
if extra_err:
    raise RuntimeError('Failed to load chm.extra: '+extra_err)

charset_table = {
    0   : 'iso8859_1',  # ANSI_CHARSET
    238 : 'iso8859_2',  # EASTEUROPE_CHARSET
    178 : 'iso8859_6',  # ARABIC_CHARSET
    161 : 'iso8859_7',  # GREEK_CHARSET
    177 : 'iso8859_8',  # HEBREW_CHARSET
    162 : 'iso8859_9',  # TURKISH_CHARSET
    222 : 'iso8859_11', # THAI_CHARSET - hmm not in python 2.2...
    186 : 'iso8859_13', # BALTIC_CHARSET
    204 : 'cp1251',     # RUSSIAN_CHARSET
    255 : 'cp437',      # OEM_CHARSET
    128 : 'cp932',      # SHIFTJIS_CHARSET
    134 : 'cp936',      # GB2312_CHARSET
    129 : 'cp949',      # HANGUL_CHARSET
    136 : 'cp950',      # CHINESEBIG5_CHARSET
    1   : None,         # DEFAULT_CHARSET
    2   : None,         # SYMBOL_CHARSET
    130 : None,         # JOHAB_CHARSET
    163 : None,         # VIETNAMESE_CHARSET
    77  : None,         # MAC_CHARSET
}

locale_table = {
    0x0436 : ('iso8859_1', "Afrikaans", "Western Europe & US"),
    0x041c : ('iso8859_2', "Albanian", "Central Europe"),
    0x0401 : ('iso8859_6', "Arabic_Saudi_Arabia", "Arabic"),
    0x0801 : ('iso8859_6', "Arabic_Iraq", "Arabic"),
    0x0c01 : ('iso8859_6', "Arabic_Egypt", "Arabic"),
    0x1001 : ('iso8859_6', "Arabic_Libya", "Arabic"),
    0x1401 : ('iso8859_6', "Arabic_Algeria", "Arabic"),
    0x1801 : ('iso8859_6', "Arabic_Morocco", "Arabic"),
    0x1c01 : ('iso8859_6', "Arabic_Tunisia", "Arabic"),
    0x2001 : ('iso8859_6', "Arabic_Oman", "Arabic"),
    0x2401 : ('iso8859_6', "Arabic_Yemen", "Arabic"),
    0x2801 : ('iso8859_6', "Arabic_Syria", "Arabic"),
    0x2c01 : ('iso8859_6', "Arabic_Jordan", "Arabic"),
    0x3001 : ('iso8859_6', "Arabic_Lebanon", "Arabic"),
    0x3401 : ('iso8859_6', "Arabic_Kuwait", "Arabic"),
    0x3801 : ('iso8859_6', "Arabic_UAE", "Arabic"),
    0x3c01 : ('iso8859_6', "Arabic_Bahrain", "Arabic"),
    0x4001 : ('iso8859_6', "Arabic_Qatar", "Arabic"),
    0x042b : (None,        "Armenian","Armenian"),
    0x042c : ('iso8859_9', "Azeri_Latin", "Turkish"),
    0x082c : ('cp1251',    "Azeri_Cyrillic", "Cyrillic"),
    0x042d : ('iso8859_1', "Basque", "Western Europe & US"),
    0x0423 : ('cp1251',    "Belarusian", "Cyrillic"),
    0x0402 : ('cp1251',    "Bulgarian", "Cyrillic"),
    0x0403 : ('iso8859_1', "Catalan", "Western Europe & US"),
    0x0404 : ('cp950',     "Chinese_Taiwan", "Traditional Chinese"),
    0x0804 : ('cp936',     "Chinese_PRC", "Simplified Chinese"),
    0x0c04 : ('cp950',     "Chinese_Hong_Kong", "Traditional Chinese"),
    0x1004 : ('cp936',     "Chinese_Singapore", "Simplified Chinese"),
    0x1404 : ('cp950',     "Chinese_Macau", "Traditional Chinese"),
    0x041a : ('iso8859_2', "Croatian", "Central Europe"),
    0x0405 : ('iso8859_2', "Czech", "Central Europe"),
    0x0406 : ('iso8859_1', "Danish", "Western Europe & US"),
    0x0413 : ('iso8859_1', "Dutch_Standard", "Western Europe & US"),
    0x0813 : ('iso8859_1', "Dutch_Belgian", "Western Europe & US"),
    0x0409 : ('iso8859_1', "English_United_States", "Western Europe & US"),
    0x0809 : ('iso8859_1', "English_United_Kingdom", "Western Europe & US"),
    0x0c09 : ('iso8859_1', "English_Australian", "Western Europe & US"),
    0x1009 : ('iso8859_1', "English_Canadian", "Western Europe & US"),
    0x1409 : ('iso8859_1', "English_New_Zealand", "Western Europe & US"),
    0x1809 : ('iso8859_1', "English_Irish", "Western Europe & US"),
    0x1c09 : ('iso8859_1', "English_South_Africa", "Western Europe & US"),
    0x2009 : ('iso8859_1', "English_Jamaica", "Western Europe & US"),
    0x2409 : ('iso8859_1', "English_Caribbean", "Western Europe & US"),
    0x2809 : ('iso8859_1', "English_Belize", "Western Europe & US"),
    0x2c09 : ('iso8859_1', "English_Trinidad", "Western Europe & US"),
    0x3009 : ('iso8859_1', "English_Zimbabwe", "Western Europe & US"),
    0x3409 : ('iso8859_1', "English_Philippines", "Western Europe & US"),
    0x0425 : ('iso8859_13',"Estonian", "Baltic",),
    0x0438 : ('iso8859_1', "Faeroese", "Western Europe & US"),
    0x0429 : ('iso8859_6', "Farsi", "Arabic"),
    0x040b : ('iso8859_1', "Finnish", "Western Europe & US"),
    0x040c : ('iso8859_1', "French_Standard", "Western Europe & US"),
    0x080c : ('iso8859_1', "French_Belgian", "Western Europe & US"),
    0x0c0c : ('iso8859_1', "French_Canadian", "Western Europe & US"),
    0x100c : ('iso8859_1', "French_Swiss", "Western Europe & US"),
    0x140c : ('iso8859_1', "French_Luxembourg", "Western Europe & US"),
    0x180c : ('iso8859_1', "French_Monaco", "Western Europe & US"),
    0x0437 : (None,        "Georgian", "Georgian"),
    0x0407 : ('iso8859_1', "German_Standard", "Western Europe & US"),
    0x0807 : ('iso8859_1', "German_Swiss", "Western Europe & US"),
    0x0c07 : ('iso8859_1', "German_Austrian", "Western Europe & US"),
    0x1007 : ('iso8859_1', "German_Luxembourg", "Western Europe & US"),
    0x1407 : ('iso8859_1', "German_Liechtenstein", "Western Europe & US"),
    0x0408 : ('iso8859_7', "Greek", "Greek"),
    0x040d : ('iso8859_8', "Hebrew", "Hebrew"),
    0x0439 : (None,        "Hindi", "Indic"),
    0x040e : ('iso8859_2', "Hungarian", "Central Europe"),
    0x040f : ('iso8859_1', "Icelandic", "Western Europe & US"),
    0x0421 : ('iso8859_1', "Indonesian", "Western Europe & US"),
    0x0410 : ('iso8859_1', "Italian_Standard", "Western Europe & US"),
    0x0810 : ('iso8859_1', "Italian_Swiss", "Western Europe & US"),
    0x0411 : ('cp932',     "Japanese", "Japanese"),
    0x043f : ('cp1251',    "Kazakh", "Cyrillic"),
    0x0457 : (None,        "Konkani", "Indic"),
    0x0412 : ('cp949',     "Korean", "Korean"),
    0x0426 : ('iso8859_13',"Latvian", "Baltic",),
    0x0427 : ('iso8859_13',"Lithuanian", "Baltic",),
    0x042f : ('cp1251',    "Macedonian", "Cyrillic"),
    0x043e : ('iso8859_1', "Malay_Malaysia", "Western Europe & US"),
    0x083e : ('iso8859_1', "Malay_Brunei_Darussalam", "Western Europe & US"),
    0x044e : (None,        "Marathi", "Indic"),
    0x0414 : ('iso8859_1', "Norwegian_Bokmal", "Western Europe & US"),
    0x0814 : ('iso8859_1', "Norwegian_Nynorsk", "Western Europe & US"),
    0x0415 : ('iso8859_2', "Polish", "Central Europe"),
    0x0416 : ('iso8859_1', "Portuguese_Brazilian", "Western Europe & US"),
    0x0816 : ('iso8859_1', "Portuguese_Standard", "Western Europe & US"),
    0x0418 : ('iso8859_2', "Romanian", "Central Europe"),
    0x0419 : ('cp1251',    "Russian", "Cyrillic"),
    0x044f : (None,        "Sanskrit", "Indic"),
    0x081a : ('iso8859_2', "Serbian_Latin", "Central Europe"),
    0x0c1a : ('cp1251',    "Serbian_Cyrillic", "Cyrillic"),
    0x041b : ('iso8859_2', "Slovak", "Central Europe"),
    0x0424 : ('iso8859_2', "Slovenian", "Central Europe"),
    0x040a : ('iso8859_1', "Spanish_Trad_Sort", "Western Europe & US"),
    0x080a : ('iso8859_1', "Spanish_Mexican", "Western Europe & US"),
    0x0c0a : ('iso8859_1', "Spanish_Modern_Sort", "Western Europe & US"),
    0x100a : ('iso8859_1', "Spanish_Guatemala", "Western Europe & US"),
    0x140a : ('iso8859_1', "Spanish_Costa_Rica", "Western Europe & US"),
    0x180a : ('iso8859_1', "Spanish_Panama", "Western Europe & US"),
    0x1c0a : ('iso8859_1', "Spanish_Dominican_Repub", "Western Europe & US"),
    0x200a : ('iso8859_1', "Spanish_Venezuela", "Western Europe & US"),
    0x240a : ('iso8859_1', "Spanish_Colombia", "Western Europe & US"),
    0x280a : ('iso8859_1', "Spanish_Peru", "Western Europe & US"),
    0x2c0a : ('iso8859_1', "Spanish_Argentina", "Western Europe & US"),
    0x300a : ('iso8859_1', "Spanish_Ecuador", "Western Europe & US"),
    0x340a : ('iso8859_1', "Spanish_Chile", "Western Europe & US"),
    0x380a : ('iso8859_1', "Spanish_Uruguay", "Western Europe & US"),
    0x3c0a : ('iso8859_1', "Spanish_Paraguay", "Western Europe & US"),
    0x400a : ('iso8859_1', "Spanish_Bolivia", "Western Europe & US"),
    0x440a : ('iso8859_1', "Spanish_El_Salvador", "Western Europe & US"),
    0x480a : ('iso8859_1', "Spanish_Honduras", "Western Europe & US"),
    0x4c0a : ('iso8859_1', "Spanish_Nicaragua", "Western Europe & US"),
    0x500a : ('iso8859_1', "Spanish_Puerto_Rico", "Western Europe & US"),
    0x0441 : ('iso8859_1', "Swahili", "Western Europe & US"),
    0x041d : ('iso8859_1', "Swedish", "Western Europe & US"),
    0x081d : ('iso8859_1', "Swedish_Finland", "Western Europe & US"),
    0x0449 : (None,        "Tamil", "Indic"),
    0x0444 : ('cp1251',    "Tatar", "Cyrillic"),
    0x041e : ('iso8859_11',"Thai", "Thai"),
    0x041f : ('iso8859_9', "Turkish", "Turkish"),
    0x0422 : ('cp1251',    "Ukrainian", "Cyrillic"),
    0x0420 : ('iso8859_6', "Urdu", "Arabic"),
    0x0443 : ('iso8859_9', "Uzbek_Latin", "Turkish"),
    0x0843 : ('cp1251',    "Uzbek_Cyrillic", "Cyrillic"),
    0x042a : ('cp1258',        "Vietnamese", "Vietnamese")
}

class CHMFile:
    "A class to manage access to CHM files."
    filename = ""
    file = None
    title = ""
    home = "/"
    index = None
    topics = None
    encoding = None
    lcid = None
    binaryindex = None

    def __init__(self):
        self.searchable = 0

    def LoadCHM(self, archiveName):
        '''Loads a CHM archive.
        This function will also call GetArchiveInfo to obtain information
        such as the index file name and the topics file. It returns 1 on
        success, and 0 if it fails.
        '''
        if (self.filename != None):
            self.CloseCHM()

        self.file = chmlib.chm_open(archiveName)
        if (self.file == None):
            return 0

        self.filename = archiveName
        self.GetArchiveInfo()

        return 1

    def CloseCHM(self):
        '''Closes the CHM archive.
        This function will close the CHM file, if it is open. All variables
        are also reset.
        '''
        if (self.filename != None):
            chmlib.chm_close(self.file)
            self.file = None
            self.filename = ''
            self.title = ""
            self.home = "/"
            self.index = None
            self.topics = None
            self.encoding = None

    def GetArchiveInfo(self):
        '''Obtains information on CHM archive.
        This function checks the /#SYSTEM file inside the CHM archive to
        obtain the index, home page, topics, encoding and title. It is called
        from LoadCHM.
        '''

        #extra.is_searchable crashed...
        #self.searchable = extra.is_searchable (self.file)
        self.searchable = False
        self.lcid = None

        result, ui = chmlib.chm_resolve_object(self.file, '/#SYSTEM')
        if (result != chmlib.CHM_RESOLVE_SUCCESS):
            sys.stderr.write('GetArchiveInfo: #SYSTEM does not exist\n')
            return 0

        size, text = chmlib.chm_retrieve_object(self.file, ui, 4l, ui.length)
        if (size == 0):
            sys.stderr.write('GetArchiveInfo: file size = 0\n')
            return 0

        buff = array.array('B', text)

        index = 0
        while (index < size):
            cursor = buff[index] + (buff[index+1] * 256)

            if (cursor == 0):
                index += 2
                cursor = buff[index] + (buff[index+1] * 256)
                index += 2
                self.topics = '/' + text[index:index+cursor-1]
            elif (cursor == 1):
                index += 2
                cursor = buff[index] + (buff[index+1] * 256)
                index += 2
                self.index = '/' + text[index:index+cursor-1]
            elif (cursor == 2):
                index += 2
                cursor = buff[index] + (buff[index+1] * 256)
                index += 2
                self.home = '/' + text[index:index+cursor-1]
            elif (cursor == 3):
                index += 2
                cursor = buff[index] + (buff[index+1] * 256)
                index += 2
                self.title = text[index:index+cursor-1]
            elif (cursor == 4):
                index += 2
                cursor = buff[index] + (buff[index+1] * 256)
                index += 2
                self.lcid = buff[index] + (buff[index+1] * 256)
            elif (cursor == 6):
                index += 2
                cursor = buff[index] + (buff[index+1] * 256)
                index += 2
                tmp = text[index:index+cursor-1]
                if not self.topics:
                    tmp1 = '/' + tmp + '.hhc'
                    tmp2 = '/' + tmp + '.hhk'
                    res1, ui1 = chmlib.chm_resolve_object(self.file, tmp1)
                    res2, ui2 = chmlib.chm_resolve_object(self.file, tmp2)
                    if (not self.topics) and \
                           (res1 == chmlib.CHM_RESOLVE_SUCCESS):
                        self.topics = '/' + tmp + '.hhc'
                    if (not self.index) and \
                           (res2 == chmlib.CHM_RESOLVE_SUCCESS):
                        self.index = '/' + tmp + '.hhk'
            elif (cursor == 16):
                index += 2
                cursor = buff[index] + (buff[index+1] * 256)
                index += 2
                self.encoding = text[index:index+cursor-1]
            else:
                index += 2
                cursor = buff[index] + (buff[index+1] * 256)
                index += 2
            index += cursor

        self.GetWindowsInfo()

        if not self.lcid:
            self.lcid = extra.get_lcid (self.file)

        return 1

    def GetTopicsTree(self):
        '''Reads and returns the topics tree.
        This auxiliary function reads and returns the topics tree file
        contents for the CHM archive.
        '''
        if (self.topics == None):
            return None

        if self.topics:
            res, ui = chmlib.chm_resolve_object(self.file, self.topics)
            if (res != chmlib.CHM_RESOLVE_SUCCESS):
                return None

        size, text = chmlib.chm_retrieve_object(self.file, ui, 0l, ui.length)
        if (size == 0):
            sys.stderr.write('GetTopicsTree: file size = 0\n')
            return None
        return text

    def GetIndex(self):
        '''Reads and returns the index tree.
        This auxiliary function reads and returns the index tree file
        contents for the CHM archive.
        '''
        if (self.index == None):
            return None

        if self.index:
            res, ui = chmlib.chm_resolve_object(self.file, self.index)
            if (res != chmlib.CHM_RESOLVE_SUCCESS):
                return None

        size, text = chmlib.chm_retrieve_object(self.file, ui, 0l, ui.length)
        if (size == 0):
            sys.stderr.write('GetIndex: file size = 0\n')
            return None
        return text

    def ResolveObject(self, document):
        '''Tries to locate a document in the archive.
        This function tries to locate the document inside the archive. It
        returns a tuple where the first element is zero if the function
        was successful, and the second is the UnitInfo for that document.
        The UnitInfo is used to retrieve the document contents
        '''
        if self.file:
            #path = os.path.abspath(document)
            path = document
            return chmlib.chm_resolve_object(self.file, path)
        else:
            return (1, None)

    def RetrieveObject(self, ui, start = -1, length = -1):
        '''Retrieves the contents of a document.
        This function takes a UnitInfo and two optional arguments, the first
        being the start address and the second is the length. These define
        the amount of data to be read from the archive.
        '''
        if self.file and ui:
            if length == -1:
                len = ui.length
            else:
                len = length
            if start == -1:
                st = 0l
            else:
                st = long(start)
            return chmlib.chm_retrieve_object(self.file, ui, st, len)
        else:
            return (0, '')

    def Search(self, text, wholewords=0, titleonly=0):
        '''Performs full-text search on the archive.
        The first parameter is the word to look for, the second
        indicates if the search should be for whole words only, and
        the third parameter indicates if the search should be
        restricted to page titles.
        This method will return a tuple, the first item
        indicating if the search results were partial, and the second
        item being a dictionary containing the results.'''
        if text and text != '' and self.file:
            return extra.search (self.file, text, wholewords,
                                 titleonly)
        else:
            return None

    def IsSearchable(self):
        '''Indicates if the full-text search is available for this
        archive - this flag is updated when GetArchiveInfo is called'''
        return self.searchable

    def GetEncoding(self):
        '''Returns a string that can be used with the codecs python package
        to encode or decode the files in the chm archive. If an error is
        found, or if it is not possible to find the encoding, None is
        returned.'''
        if self.encoding:
            vals = string.split(self.encoding, ',')
            if len(vals) > 2:
                try:
                    return charset_table[int(vals[2])]
                except KeyError:
                    pass
        return None

    def GetLCID(self):
        '''Returns the archive Locale ID'''
        if self.lcid in locale_table:
            return locale_table[self.lcid]
        else:
            return None

    def get_encoding(self):
        ans = self.GetEncoding()
        if ans is None:
            lcid = self.GetLCID()
            if lcid is not None:
                ans = lcid[0]
        if ans:
            try:
                codecs.lookup(ans)
            except:
                ans = None
        return ans

    def GetDWORD(self, buff, idx=0):
        '''Internal method.
        Reads a double word (4 bytes) from a buffer.
        '''
        result = buff[idx] + (buff[idx+1]<<8) + (buff[idx+2]<<16) + \
                 (buff[idx+3]<<24)

        if result == 0xFFFFFFFF:
            result = 0

        return result

    def GetString(self, text, idx):
        '''Internal method.
        Retrieves a string from the #STRINGS buffer.
        '''
        next = string.find(text, '\x00', idx)
        chunk = text[idx:next]
        return chunk

    def GetWindowsInfo(self):
        '''Gets information from the #WINDOWS file.
        Checks the #WINDOWS file to see if it has any info that was
        not found in #SYSTEM (topics, index or default page.
        '''
        result, ui = chmlib.chm_resolve_object(self.file, '/#WINDOWS')
        if (result != chmlib.CHM_RESOLVE_SUCCESS):
            return -1

        size, text = chmlib.chm_retrieve_object(self.file, ui, 0l, 8)
        if (size < 8):
            return -2

        buff = array.array('B', text)
        num_entries = self.GetDWORD(buff, 0)
        entry_size = self.GetDWORD(buff, 4)

        if num_entries < 1:
            return -3

        size, text = chmlib.chm_retrieve_object(self.file, ui, 8l, entry_size)
        if (size < entry_size):
            return -4

        buff = array.array('B', text)
        toc_index = self.GetDWORD(buff, 0x60)
        idx_index = self.GetDWORD(buff, 0x64)
        dft_index = self.GetDWORD(buff, 0x68)

        result, ui = chmlib.chm_resolve_object(self.file, '/#STRINGS')
        if (result != chmlib.CHM_RESOLVE_SUCCESS):
            return -5

        size, text = chmlib.chm_retrieve_object(self.file, ui, 0l, ui.length)
        if (size == 0):
            return -6

        if (not self.topics):
            self.topics = self.GetString(text, toc_index)
            if not self.topics.startswith("/"):
                self.topics = "/" + self.topics

        if (not self.index):
            self.index = self.GetString(text, idx_index)
            if not self.index.startswith("/"):
                self.index = "/" + self.index

        if (dft_index != 0):
            self.home = self.GetString(text, dft_index)
            if not self.home.startswith("/"):
                self.home = "/" + self.home
