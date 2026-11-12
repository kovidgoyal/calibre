#########################################################################
#                                                                       #
#                                                                       #
#   copyright 2002 Paul Henry Tremblay                                  #
#                                                                       #
#   This program is distributed in the hope that it will be useful,     #
#   but WITHOUT ANY WARRANTY; without even the implied warranty of      #
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU    #
#   General Public License for more details.                            #
#                                                                       #
#                                                                       #
#########################################################################
import codecs
import io
import os
import sys

from calibre.ebooks.rtf2xml import copy, get_char_map
from calibre.ebooks.rtf2xml.char_set import char_set
from calibre.ebooks.rtf2xml.default_encoding import FONT_CHARSET_CODE_PAGES, codec_for_code_page, lead_bytes
from calibre.ptempfile import better_mktemp

from . import open_for_read, open_for_write

SPECIAL_FONTS = ('Symbol', 'Wingdings', 'Zapf Dingbats')
# the longest character in the code pages with multibyte characters, in UTF-8
MAX_CHAR_LENGTH = 4


class Hex2Utf8:
    """
    Convert Microsoft hexadecimal numbers to utf-8
    """

    def __init__(
        self,
        in_file: str,
        area_to_convert: str,
        char_file: str,
        default_char_map: str,
        bug_handler: type[Exception],
        invalid_rtf_handler: type[Exception],
        copy: int | None = None,
        temp_dir: str | None = None,
        symbol: int | None = None,
        wingdings: int | None = None,
        caps: int | None = None,
        convert_caps: int | None = None,
        dingbats: int | None = None,
        run_level: int = 1,
    ) -> None:
        """
        Required:
            'file'
            'area_to_convert'--the area of file to convert
            'char_file'--the file containing the character mappings
            'default_char_map'--name of default character map
        Optional:
            'copy'-- whether to make a copy of result for debugging
            'temp_dir' --where to output temporary results (default is
            directory from which the script is run.)
            'symbol'--whether to load the symbol character map
            'winddings'--whether to load the wingdings character map
            'caps'--whether to load the caps character map
            'convert_to_caps'--wether to convert caps to utf-8
        Returns:
            nothing
        """
        self.__file = in_file
        self.__copy = copy
        if area_to_convert not in ('preamble', 'body'):
            msg = 'Developer error! Wrong flag.\nin module "hex_2_utf8.py\n"area_to_convert" must be "body" or "preamble"\n'
            raise self.__bug_handler(msg)
        self.__char_file = char_file
        self.__area_to_convert = area_to_convert
        self.__default_char_map = default_char_map
        self.__symbol = symbol
        self.__wingdings = wingdings
        self.__dingbats = dingbats
        self.__caps = caps
        self.__convert_caps = 0
        self.__convert_symbol = 0
        self.__convert_wingdings = 0
        self.__convert_zapf = 0
        self.__run_level = run_level
        self.__font_code_pages: dict[str, str] = {}
        self.__default_font: str | None = None
        self.__write_to = better_mktemp()
        self.__bug_handler = bug_handler
        self.__invalid_rtf_handler = invalid_rtf_handler

    def update_values(
        self,
        file: str,
        area_to_convert: str,
        char_file: str,
        convert_caps: int | None,
        convert_symbol: int | None,
        convert_wingdings: int | None,
        convert_zapf: int | None,
        copy: int | None = None,
        temp_dir: str | None = None,
        symbol: int | None = None,
        wingdings: int | None = None,
        caps: int | None = None,
        dingbats: int | None = None,
        font_code_pages: dict[str, str] | None = None,
        default_font: str | None = None,
    ) -> None:
        """
        Required:
            'file'
            'area_to_convert'--the area of file to convert
            'char_file'--the file containing the character mappings
        Optional:
            'font_code_pages'--the code page of each font name, from \\fcharset
            'default_font'--the name of the default font
            'copy'-- whether to make a copy of result for debugging
            'temp_dir' --where to output temporary results (default is
            directory from which the script is run.)
            'symbol'--whether to load the symbol character map
            'winddings'--whether to load the wingdings character map
            'caps'--whether to load the caps character map
            'convert_to_caps'--wether to convert caps to utf-8
        Returns:
            nothing
        """
        self.__file = file
        self.__copy = copy
        if area_to_convert not in ('preamble', 'body'):
            msg = 'in module "hex_2_utf8.py\n"area_to_convert" must be "body" or "preamble"\n'
            raise self.__bug_handler(msg)
        self.__area_to_convert = area_to_convert
        self.__symbol = symbol
        self.__wingdings = wingdings
        self.__dingbats = dingbats
        self.__caps = caps
        self.__convert_caps = convert_caps
        self.__convert_symbol = convert_symbol
        self.__convert_wingdings = convert_wingdings
        self.__convert_zapf = convert_zapf
        self.__font_code_pages = font_code_pages or {}
        self.__default_font = default_font
        # new!
        # no longer try to convert these
        # self.__convert_symbol = 0
        # self.__convert_wingdings = 0
        # self.__convert_zapf = 0

    def __initiate_values(self) -> None:
        """
        Required:
            Nothing
        Set values, including those for the dictionaries.
        The file that contains the maps is broken down into many different
        sets. For example, for the Symbol font, there is the standard part for
        hexadecimal numbers, and the part for Microsoft characters. Read
        each part in, and then combine them.
        """
        # the default encoding system, the lower map for characters 0 through
        # 128, and the encoding system for Microsoft characters.
        # New on 2004-05-8: the self.__char_map is not in directory with other
        # modules
        self.__char_file = io.StringIO(char_set)
        char_map_obj = get_char_map.GetCharMap(
            char_file=self.__char_file,
            bug_handler=self.__bug_handler,
        )
        self.__char_map_obj = char_map_obj
        self.__bt_128_dict = char_map_obj.get_char_map(map='bottom_128')
        self.__ms_standard_dict = char_map_obj.get_char_map(map='ms_standard')
        self.__doc_code_page = self.__default_char_map.removeprefix('ansicpg')
        # the default dictionary of each code page, the code page of the text
        # depends on its font
        self.__def_dicts: dict[str, dict[str, str]] = {}
        # In the code pages with multibyte characters, such as the East Asian
        # ones, a character is a lead byte followed by trail bytes. The trail
        # bytes are written as hex escapes or, when below 0x80, as plain text.
        self.__pending_bytes = b''
        self.__in_caps = 0
        self.__special_fonts_found = 0
        if self.__symbol:
            symbol_base_dict = char_map_obj.get_char_map(map='SYMBOL')
            ms_symbol_dict = char_map_obj.get_char_map(map='ms_symbol')
            self.__symbol_dict = {}
            self.__symbol_dict.update(symbol_base_dict)
            self.__symbol_dict.update(ms_symbol_dict)
        if self.__wingdings:
            wingdings_base_dict = char_map_obj.get_char_map(map='wingdings')
            ms_wingdings_dict = char_map_obj.get_char_map(map='ms_wingdings')
            self.__wingdings_dict = {}
            self.__wingdings_dict.update(wingdings_base_dict)
            self.__wingdings_dict.update(ms_wingdings_dict)
        if self.__dingbats:
            dingbats_base_dict = char_map_obj.get_char_map(map='dingbats')
            ms_dingbats_dict = char_map_obj.get_char_map(map='ms_dingbats')
            self.__dingbats_dict = {}
            self.__dingbats_dict.update(dingbats_base_dict)
            self.__dingbats_dict.update(ms_dingbats_dict)
        # load dictionary for caps, and make a string for the replacement
        self.__caps_uni_dict = char_map_obj.get_char_map(map='caps_uni')
        # print(self.__caps_uni_dict)
        # don't think I'll need this
        # keys = self.__caps_uni_dict.keys()
        # self.__caps_uni_replace = '|'.join(keys)
        self.__preamble_state_dict = {
            'preamble': self.__preamble_func,
            'body': self.__body_func,
            'mi<mk<body-open_': self.__found_body_func,
            'tx<hx<__________': self.__hex_text_func,
            'mi<mk<fontit-beg': self.__font_in_table_func,
            'cw<ci<font-chset': self.__font_in_table_func,
            'mi<mk<fontit-end': self.__font_in_table_func,
        }
        self.__body_state_dict = {
            'preamble': self.__preamble_for_body_func,
            'body': self.__body_for_body_func,
        }
        self.__in_body_dict = {
            'mi<mk<body-open_': self.__found_body_func,
            'tx<ut<__________': self.__utf_to_caps_func,
            'tx<hx<__________': self.__hex_text_func,
            'tx<mc<__________': self.__hex_text_func,
            'tx<nu<__________': self.__text_func,
            'mi<mk<font______': self.__start_font_func,
            'mi<mk<caps______': self.__start_caps_func,
            'mi<mk<font-end__': self.__end_font_func,
            'mi<mk<caps-end__': self.__end_caps_func,
        }
        self.__caps_list = ['false']
        self.__font_list = ['not-defined']
        # sets self.__def_dict, self.__current_dict, self.__lead_bytes,
        # self.__codec and self.__text_trail_bytes
        self.__select_font(self.__font_list[-1])

    def __hex_text_func(self, line: str) -> None:
        '''
        Required:
            'line' -- the line
        Logic:
            get the hex_num and look it up in the default dictionary. If the
            token is in the dictionary, then check if the value starts with a
            "&". If it does, then tag the result as utf text. Otherwise, tag it
            as normal text.
            If the hex_num is not in the dictionary, then a mistake has been
            made.
        '''
        hex_num = line[17:-1]
        if self.__token_info == 'tx<hx<__________' and self.__lead_bytes and self.__current_dict_name == 'default':
            byte = int(hex_num[1:], 16)
            if self.__pending_bytes and self.__add_trail_byte(byte):
                return
            if byte in self.__lead_bytes:
                self.__pending_bytes = bytes((byte,))
                return
        self.__convert_hex(hex_num)

    def __convert_hex(self, hex_num: str) -> None:
        converted = self.__current_dict.get(hex_num)
        if converted is not None:
            # tag as utf-8
            if converted[0:1] == '&':
                self.__write_utf(converted)
            # tag as normal text
            else:
                if self.__in_caps_text():
                    converted = converted.upper()
                self.__write_obj.write(f'tx<nu<__________<{converted}\n')
        # error
        else:
            token = hex_num.replace("'", '')
            the_num = 0
            if token:
                the_num = int(token, 16)
            if the_num > 10:
                self.__write_obj.write(f'mi<tg<empty-att_<udef_symbol<num>{hex_num}<description>not-in-table\n')
                if self.__run_level > 4:
                    # msg = 'no dictionary entry for %s\n'
                    # msg += 'the hexadecimal num is "%s"\n' % (hex_num)
                    # msg += 'dictionary is %s\n' % self.__current_dict_name
                    msg = f'Character "&#x{token};" does not appear to be valid (or is a control character)\n'
                    raise self.__bug_handler(msg)

    def __in_caps_text(self) -> bool:
        return bool(self.__convert_caps) and self.__caps_list[-1] == 'true' and self.__current_dict_name not in SPECIAL_FONTS

    def __write_utf(self, converted: str) -> None:
        if self.__in_caps_text():
            converted = self.__utf_token_to_caps_func(converted)
        self.__write_obj.write(f'tx<ut<__________<{converted}\n')

    def __add_trail_byte(self, byte: int) -> bool:
        """
        Add byte to the multibyte character started by the pending bytes and
        write the character once it is complete. Return False, after writing a
        replacement character for the pending bytes, if byte cannot continue
        the character.
        """
        assert self.__codec is not None
        data = self.__pending_bytes + bytes((byte,))
        try:
            text = codecs.getincrementaldecoder(self.__codec)().decode(data, final=False)
        except UnicodeDecodeError:
            self.__flush_pending_bytes()
            return False
        if not text:
            if len(data) >= MAX_CHAR_LENGTH:
                self.__flush_pending_bytes()
                return False
            self.__pending_bytes = data
            return True
        self.__pending_bytes = b''
        for ch in text:
            self.__write_utf(f'&#x{ord(ch):04X};')
        return True

    def __flush_pending_bytes(self) -> None:
        # the lead byte of a character whose trail bytes are missing or invalid
        pending, self.__pending_bytes = self.__pending_bytes, b''
        if not pending:
            return
        if self.__text_trail_bytes:
            self.__write_utf('&#xFFFD;')
        else:
            # the font and the document disagree on the code page, the bytes
            # are single byte characters
            for byte in pending:
                self.__convert_hex(f"'{byte:02X}")

    def __complete_pending_char(self, line: str) -> str:
        """
        Called with a line that follows the start of a multibyte character.
        Complete the character with the trail bytes written as plain text at
        the start of line and return what is left of line, or flush the
        pending bytes and return line unchanged if line is not text.
        """
        if self.__token_info != 'tx<nu<__________':
            if self.__token_info != 'tx<hx<__________':
                self.__flush_pending_bytes()
            return line
        text = line[17:-1]
        if not self.__text_trail_bytes:
            self.__flush_pending_bytes()
            return line
        while self.__pending_bytes and text and ord(text[0]) < 0x80 and self.__add_trail_byte(ord(text[0])):
            text = text[1:]
        if self.__pending_bytes and text:
            self.__flush_pending_bytes()
        return f'tx<nu<__________<{text}\n' if text else ''

    def __select_code_page(self, code_page: str | None) -> None:
        """
        Use the code page of a font, if it has one, for its text.

        Writers do not agree on whether the code page of the document or of
        the font applies when only one of them has multibyte characters: Word
        writes the double byte characters of the document code page in runs of
        a \\fcharset0 font and UTF-8 writers use \\fcharset0 fonts. So in that
        case a lead byte starts a multibyte character only when the trail
        bytes are hex escapes too, otherwise the bytes are single byte
        characters of the single byte code page. This also keeps the text of
        single byte documents with East Asian fonts converted as before.
        """
        doc = self.__doc_code_page
        if code_page is None or code_page == doc or not (lead_bytes(code_page) or lead_bytes(doc)):
            code_page = doc
        if bool(lead_bytes(code_page)) == bool(lead_bytes(doc)):
            multibyte, single_byte, self.__text_trail_bytes = code_page, code_page, True
        elif lead_bytes(code_page):
            multibyte, single_byte, self.__text_trail_bytes = code_page, doc, False
        else:
            multibyte, single_byte, self.__text_trail_bytes = doc, code_page, False
        self.__def_dict = self.__default_dict(single_byte)
        self.__lead_bytes = lead_bytes(multibyte)
        self.__codec = codec_for_code_page(multibyte)

    def __default_dict(self, code_page: str) -> dict[str, str]:
        ans = self.__def_dicts.get(code_page)
        if ans is None:
            ans = {}
            ans.update(self.__char_map_obj.get_char_map(map=f'ansicpg{code_page}'))
            ans.update(self.__bt_128_dict)
            ans.update(self.__ms_standard_dict)
            self.__def_dicts[code_page] = ans
        return ans

    def __font_in_table_func(self, line: str) -> None:
        """
        The font names in the font table are in the code page of their font
        """
        code_page = FONT_CHARSET_CODE_PAGES.get(line[20:-1]) if self.__token_info == 'cw<ci<font-chset' else None
        self.__select_code_page(code_page)
        self.__current_dict = self.__def_dict.copy()
        self.__write_obj.write(line)

    def __found_body_func(self, line: str) -> None:
        self.__state = 'body'
        self.__write_obj.write(line)

    def __body_func(self, line: str) -> None:
        """
        When parsing preamble
        """
        self.__write_obj.write(line)

    def __preamble_func(self, line: str) -> None:
        action = self.__preamble_state_dict.get(self.__token_info)
        if action is not None:
            action(line)
        else:
            self.__write_obj.write(line)

    def __convert_preamble(self) -> None:
        self.__state = 'preamble'
        with open_for_write(self.__write_to) as self.__write_obj:
            with open_for_read(self.__file) as read_obj:
                for line in read_obj:
                    self.__token_info = line[:16]
                    if self.__pending_bytes and not (line := self.__complete_pending_char(line)):
                        continue
                    action = self.__preamble_state_dict.get(self.__state)
                    if action is None:
                        sys.stderr.write(f'error no state found in hex_2_utf8: {self.__state}\n')
                    assert action is not None
                    action(line)
                self.__flush_pending_bytes()
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, 'preamble_utf_convert.data')
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)

    def __preamble_for_body_func(self, line: str) -> None:
        """
        Required:
            line -- line to parse
        Returns:
            nothing
        Logic:
            Used when parsing the body.
        """
        if self.__token_info == 'mi<mk<body-open_':
            self.__found_body_func(line)
        self.__write_obj.write(line)

    def __body_for_body_func(self, line: str) -> None:
        """
        Required:
            line -- line to parse
        Returns:
            nothing
        Logic:
            Used when parsing the body.
        """
        action = self.__in_body_dict.get(self.__token_info)
        if action is not None:
            action(line)
        else:
            self.__write_obj.write(line)

    def __start_font_func(self, line: str) -> None:
        """
        Required:
            line -- line to parse
        Returns:
            nothing
        Logic:
            add font face to font_list
        """
        face = line[17:-1]
        self.__font_list.append(face)
        self.__select_font(face)

    def __select_font(self, face: str) -> None:
        if face == 'Symbol' and self.__convert_symbol:
            self.__current_dict_name = 'Symbol'
            self.__current_dict = self.__symbol_dict.copy()
        elif face == 'Wingdings' and self.__convert_wingdings:
            self.__current_dict_name = 'Wingdings'
            self.__current_dict = self.__wingdings_dict.copy()
        elif face == 'Zapf Dingbats' and self.__convert_zapf:
            self.__current_dict_name = 'Zapf Dingbats'
            self.__current_dict = self.__dingbats_dict.copy()
        else:
            if face == 'not-defined' and self.__default_font is not None:
                face = self.__default_font
            self.__select_code_page(self.__font_code_pages.get(face))
            self.__current_dict_name = 'default'
            self.__current_dict = self.__def_dict.copy()

    def __end_font_func(self, line: str) -> None:
        """
        Required:
            line -- line to parse
        Returns:
            nothing
        Logic:
            pop font_list
        """
        if len(self.__font_list) > 1:
            self.__font_list.pop()
        else:
            sys.stderr.write('module is hex_2_utf8\n')
            sys.stderr.write('method is end_font_func\n')
            sys.stderr.write('self.__font_list should be greater than one?\n')
        face = self.__font_list[-1]
        self.__select_font(face)

    def __start_special_font_func_old(self, line: str) -> None:
        """
        Required:
            line -- line
        Returns;
            nothing
        Logic:
            change the dictionary to use in conversion
        """
        # for error checking
        if self.__token_info == 'mi<mk<font-symbo':
            self.__current_dict.update(self.__symbol_dict)
            self.__special_fonts_found += 1
            self.__current_dict_name = 'Symbol'
        elif self.__token_info == 'mi<mk<font-wingd':
            self.__special_fonts_found += 1
            self.__current_dict.update(self.__wingdings_dict)
            self.__current_dict_name = 'Wingdings'
        elif self.__token_info == 'mi<mk<font-dingb':
            self.__current_dict.update(self.__dingbats_dict)
            self.__special_fonts_found += 1
            self.__current_dict_name = 'Zapf Dingbats'

    def __end_special_font_func(self, line: str) -> None:
        """
        Required:
            line --line to parse
        Returns:
            nothing
        Logic:
            pop the last dictionary, which should be a special font
        """
        if len(self.__current_dict) < 2:
            sys.stderr.write('module is hex_2_utf 8\n')
            sys.stderr.write('method is __end_special_font_func\n')
            sys.stderr.write("less than two dictionaries --can't pop\n")
            self.__special_fonts_found -= 1
        else:
            self.__current_dict = self.__def_dict.copy()
            self.__special_fonts_found -= 1
            self.__dict_name = 'default'

    def __start_caps_func_old(self, line: str) -> None:
        """
        Required:
            line -- line to parse
        Returns:
            nothing
        Logic:
            A marker that marks the start of caps has been found. Set
            self.__in_caps to 1
        """
        self.__in_caps = 1

    def __start_caps_func(self, line: str) -> None:
        """
        Required:
            line -- line to parse
        Returns:
            nothing
        Logic:
            A marker that marks the start of caps has been found. Set
            self.__in_caps to 1
        """
        self.__in_caps = 1
        value = line[17:-1]
        self.__caps_list.append(value)

    def __end_caps_func(self, line: str) -> None:
        """
        Required:
            line -- line to parse
        Returns:
            nothing
        Logic:
            A marker that marks the end of caps has been found.
            set self.__in_caps to 0
        """
        if len(self.__caps_list) > 1:
            self.__caps_list.pop()
        else:
            sys.stderr.write('Module is hex_2_utf8\nmethod is __end_caps_func\ncaps list should be more than one?\n')  # self.__in_caps not set

    def __text_func(self, line: str) -> None:
        """
        Required:
            line -- line to parse
        Returns:
            nothing
        Logic:
            if in caps, convert. Otherwise, print out.
        """
        text = line[17:-1]
        # print(line)
        if self.__current_dict_name in ('Symbol', 'Wingdings', 'Zapf Dingbats'):
            the_string = ''
            for letter in text:
                hex_num = hex(ord(letter))
                hex_num = str(hex_num)
                hex_num = hex_num.upper()
                hex_num = hex_num[2:]
                hex_num = f"'{hex_num}"
                converted = self.__current_dict.get(hex_num)
                if converted is None:
                    sys.stderr.write('module is hex_2_ut8\nmethod is __text_func\n')
                    sys.stderr.write(f'no hex value for "{hex_num}"\n')
                else:
                    the_string += converted
            self.__write_obj.write(f'tx<nu<__________<{the_string}\n')
            # print(the_string)
        else:
            if self.__caps_list[-1] == 'true' and self.__convert_caps and self.__current_dict_name not in ('Symbol', 'Wingdings', 'Zapf Dingbats'):
                text = text.upper()
            self.__write_obj.write(f'tx<nu<__________<{text}\n')

    def __utf_to_caps_func(self, line: str) -> None:
        """
        Required:
            line -- line to parse
        returns
            nothing
        Logic
            Get the text, and use another method to convert
        """
        utf_text = line[17:-1]
        if self.__caps_list[-1] == 'true' and self.__convert_caps:
            # utf_text = utf_text.upper()
            utf_text = self.__utf_token_to_caps_func(utf_text)
        self.__write_obj.write(f'tx<ut<__________<{utf_text}\n')

    def __utf_token_to_caps_func(self, char_entity: str) -> str:
        """
        Required:
            utf_text -- such as &xxx;
        Returns:
            token converted to the capital equivalent
        Logic:
            RTF often stores text in the improper values. For example, a
            capital umlaut o (?), is stores as ?. This function swaps the
            case by looking up the value in a dictionary.
        """
        hex_num = char_entity[3:]
        length = len(hex_num)
        if length == 3:
            hex_num = f'00{hex_num}'
        elif length == 4:
            hex_num = f'0{hex_num}'
        new_char_entity = f'&#x{hex_num}'
        converted = self.__caps_uni_dict.get(new_char_entity)
        if not converted:
            # bullets and other entities don't have capital equivalents
            return char_entity
        else:
            return converted

    def __convert_body(self) -> None:
        self.__state = 'body'
        with open_for_read(self.__file) as read_obj:
            with open_for_write(self.__write_to) as self.__write_obj:
                for line in read_obj:
                    self.__token_info = line[:16]
                    if self.__pending_bytes and not (line := self.__complete_pending_char(line)):
                        continue
                    action = self.__body_state_dict.get(self.__state)
                    if action is None:
                        sys.stderr.write(f'error no state found in hex_2_utf8: {self.__state}\n')
                    assert action is not None
                    action(line)
                self.__flush_pending_bytes()
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, 'body_utf_convert.data')
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)

    def convert_hex_2_utf8(self) -> None:
        self.__initiate_values()
        if self.__area_to_convert == 'preamble':
            self.__convert_preamble()
        else:
            self.__convert_body()


# how to swap case for non-capitals
# my_string.swapcase()
# An example of how to use a hash for the caps function
# (but I shouldn't need this, since utf text is separate
#  from regular text?)
# sub_dict = {
#     "&#x0430;"   : "some other value"
#     }
# def my_sub_func(matchobj):
#     info =  matchobj.group(0)
#     value = sub_dict.get(info)
#     return value
#     return "f"
# line = "&#x0430; more text"
# reg_exp = re.compile(r'(?P<name>&#x0430;|&#x0431;)')
# line2 = re.sub(reg_exp, my_sub_func, line)
# print line2
