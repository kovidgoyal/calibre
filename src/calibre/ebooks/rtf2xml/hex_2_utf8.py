
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
import sys, os, io

from calibre.ebooks.rtf2xml import get_char_map, copy
from calibre.ebooks.rtf2xml.char_set import char_set
from calibre.ptempfile import better_mktemp
from polyglot.builtins import unicode_type

from . import open_for_read, open_for_write


class Hex2Utf8:
    """
    Convert Microsoft hexidecimal numbers to utf-8
    """

    def __init__(self,
            in_file,
            area_to_convert,
            char_file,
            default_char_map,
            bug_handler,
            invalid_rtf_handler,
            copy=None,
            temp_dir=None,
            symbol=None,
            wingdings=None,
            caps=None,
            convert_caps=None,
            dingbats=None,
            run_level=1,
            ):
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
            'caps'--whether to load the caps characer map
            'convert_to_caps'--wether to convert caps to utf-8
        Returns:
            nothing
        """
        self.__file = in_file
        self.__copy = copy
        if area_to_convert not in ('preamble', 'body'):
            msg = (
            'Developer error! Wrong flag.\n'
            'in module "hex_2_utf8.py\n'
            '"area_to_convert" must be "body" or "preamble"\n'
            )
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
        self.__write_to = better_mktemp()
        self.__bug_handler = bug_handler
        self.__invalid_rtf_handler = invalid_rtf_handler

    def update_values(self,
                        file,
                        area_to_convert,
                        char_file,
                        convert_caps,
                        convert_symbol,
                        convert_wingdings,
                        convert_zapf,
                        copy=None,
                        temp_dir=None,
                        symbol=None,
                        wingdings=None,
                        caps=None,
                        dingbats=None,
                    ):
        """
        Required:
            'file'
            'area_to_convert'--the area of file to convert
            'char_file'--the file containing the character mappings
        Optional:
            'copy'-- whether to make a copy of result for debugging
            'temp_dir' --where to output temporary results (default is
            directory from which the script is run.)
            'symbol'--whether to load the symbol character map
            'winddings'--whether to load the wingdings character map
            'caps'--whether to load the caps characer map
            'convert_to_caps'--wether to convert caps to utf-8
        Returns:
            nothing
            """
        self.__file=file
        self.__copy = copy
        if area_to_convert not in ('preamble', 'body'):
            msg = (
            'in module "hex_2_utf8.py\n'
            '"area_to_convert" must be "body" or "preamble"\n'
            )
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
        # new!
        # no longer try to convert these
        # self.__convert_symbol = 0
        # self.__convert_wingdings = 0
        # self.__convert_zapf = 0

    def __initiate_values(self):
        """
        Required:
            Nothing
        Set values, including those for the dictionaries.
        The file that contains the maps is broken down into many different
        sets. For example, for the Symbol font, there is the standard part for
        hexidecimal numbers, and the part for Microsoft characters. Read
        each part in, and then combine them.
        """
        # the default encoding system, the lower map for characters 0 through
        # 128, and the encoding system for Microsoft characters.
        # New on 2004-05-8: the self.__char_map is not in directory with other
        # modules
        self.__char_file = io.StringIO(char_set)
        char_map_obj =  get_char_map.GetCharMap(
                char_file=self.__char_file,
                bug_handler=self.__bug_handler,
                )
        up_128_dict = char_map_obj.get_char_map(map=self.__default_char_map)
        bt_128_dict = char_map_obj.get_char_map(map='bottom_128')
        ms_standard_dict = char_map_obj.get_char_map(map='ms_standard')
        self.__def_dict = {}
        self.__def_dict.update(up_128_dict)
        self.__def_dict.update(bt_128_dict)
        self.__def_dict.update(ms_standard_dict)
        self.__current_dict = self.__def_dict
        self.__current_dict_name = 'default'
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
        # # print self.__caps_uni_dict
        # don't think I'll need this
        # keys = self.__caps_uni_dict.keys()
        # self.__caps_uni_replace = '|'.join(keys)
        self.__preamble_state_dict = {
            'preamble'      :       self.__preamble_func,
            'body'          :       self.__body_func,
            'mi<mk<body-open_'  :   self.__found_body_func,
            'tx<hx<__________'  :   self.__hex_text_func,
            }
        self.__body_state_dict = {
            'preamble'      :       self.__preamble_for_body_func,
            'body'          :       self.__body_for_body_func,
            }
        self.__in_body_dict = {
            'mi<mk<body-open_'  :   self.__found_body_func,
            'tx<ut<__________'  :   self.__utf_to_caps_func,
            'tx<hx<__________'  :   self.__hex_text_func,
            'tx<mc<__________'  :   self.__hex_text_func,
            'tx<nu<__________'  :   self.__text_func,
            'mi<mk<font______'  :   self.__start_font_func,
            'mi<mk<caps______'  :   self.__start_caps_func,
            'mi<mk<font-end__'  :   self.__end_font_func,
            'mi<mk<caps-end__'  :   self.__end_caps_func,
        }
        self.__caps_list = ['false']
        self.__font_list = ['not-defined']

    def __hex_text_func(self, line):
        """
        Required:
            'line' -- the line
        Logic:
            get the hex_num and look it up in the default dictionary. If the
            token is in the dictionary, then check if the value starts with a
            "&". If it does, then tag the result as utf text. Otherwise, tag it
            as normal text.
            If the hex_num is not in the dictionary, then a mistake has been
            made.
            """
        hex_num = line[17:-1]
        converted = self.__current_dict.get(hex_num)
        if converted is not None:
            # tag as utf-8
            if converted[0:1] == "&":
                font = self.__current_dict_name
                if self.__convert_caps\
                and self.__caps_list[-1] == 'true'\
                and font not in ('Symbol', 'Wingdings', 'Zapf Dingbats'):
                    converted = self.__utf_token_to_caps_func(converted)
                self.__write_obj.write(
                'tx<ut<__________<%s\n' % converted
                )
            # tag as normal text
            else:
                font = self.__current_dict_name
                if self.__convert_caps\
                and self.__caps_list[-1] == 'true'\
                and font not in ('Symbol', 'Wingdings', 'Zapf Dingbats'):
                    converted = converted.upper()
                self.__write_obj.write(
                'tx<nu<__________<%s\n' % converted
                )
        # error
        else:
            token = hex_num.replace("'", '')
            the_num = 0
            if token:
                the_num = int(token, 16)
            if the_num > 10:
                self.__write_obj.write('mi<tg<empty-att_<udef_symbol<num>%s<description>not-in-table\n' %
                    hex_num)
                if self.__run_level > 4:
                    # msg = 'no dictionary entry for %s\n'
                    # msg += 'the hexidecimal num is "%s"\n' % (hex_num)
                    # msg += 'dictionary is %s\n' % self.__current_dict_name
                    msg = 'Character "&#x%s;" does not appear to be valid (or is a control character)\n' % token
                    raise self.__bug_handler(msg)

    def __found_body_func(self, line):
        self.__state = 'body'
        self.__write_obj.write(line)

    def __body_func(self, line):
        """
        When parsing preamble
        """
        self.__write_obj.write(line)

    def __preamble_func(self, line):
        action = self.__preamble_state_dict.get(self.__token_info)
        if action is not None:
            action(line)
        else:
            self.__write_obj.write(line)

    def __convert_preamble(self):
        self.__state = 'preamble'
        with open_for_write(self.__write_to) as self.__write_obj:
            with open_for_read(self.__file) as read_obj:
                for line in read_obj:
                    self.__token_info = line[:16]
                    action = self.__preamble_state_dict.get(self.__state)
                    if action is None:
                        sys.stderr.write('error no state found in hex_2_utf8',
                        self.__state
                        )
                    action(line)
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "preamble_utf_convert.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)

    def __preamble_for_body_func(self, line):
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

    def __body_for_body_func(self, line):
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

    def __start_font_func(self, line):
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
        if face == 'Symbol' and self.__convert_symbol:
            self.__current_dict_name = 'Symbol'
            self.__current_dict = self.__symbol_dict
        elif face == 'Wingdings' and self.__convert_wingdings:
            self.__current_dict_name = 'Wingdings'
            self.__current_dict = self.__wingdings_dict
        elif face == 'Zapf Dingbats' and self.__convert_zapf:
            self.__current_dict_name = 'Zapf Dingbats'
            self.__current_dict = self.__dingbats_dict
        else:
            self.__current_dict_name = 'default'
            self.__current_dict = self.__def_dict

    def __end_font_func(self, line):
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
        if face == 'Symbol' and self.__convert_symbol:
            self.__current_dict_name = 'Symbol'
            self.__current_dict = self.__symbol_dict
        elif face == 'Wingdings' and self.__convert_wingdings:
            self.__current_dict_name = 'Wingdings'
            self.__current_dict = self.__wingdings_dict
        elif face == 'Zapf Dingbats' and self.__convert_zapf:
            self.__current_dict_name = 'Zapf Dingbats'
            self.__current_dict = self.__dingbats_dict
        else:
            self.__current_dict_name = 'default'
            self.__current_dict = self.__def_dict

    def __start_special_font_func_old(self, line):
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
            self.__current_dict.append(self.__symbol_dict)
            self.__special_fonts_found += 1
            self.__current_dict_name = 'Symbol'
        elif self.__token_info == 'mi<mk<font-wingd':
            self.__special_fonts_found += 1
            self.__current_dict.append(self.__wingdings_dict)
            self.__current_dict_name = 'Wingdings'
        elif self.__token_info == 'mi<mk<font-dingb':
            self.__current_dict.append(self.__dingbats_dict)
            self.__special_fonts_found += 1
            self.__current_dict_name = 'Zapf Dingbats'

    def __end_special_font_func(self, line):
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
            sys.stderr.write('less than two dictionaries --can\'t pop\n')
            self.__special_fonts_found -= 1
        else:
            self.__current_dict.pop()
            self.__special_fonts_found -= 1
            self.__dict_name = 'default'

    def __start_caps_func_old(self, line):
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

    def __start_caps_func(self, line):
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

    def __end_caps_func(self, line):
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
            sys.stderr.write('Module is hex_2_utf8\n'
            'method is __end_caps_func\n'
            'caps list should be more than one?\n')  # self.__in_caps not set

    def __text_func(self, line):
        """
        Required:
            line -- line to parse
        Returns:
            nothing
        Logic:
            if in caps, convert. Otherwise, print out.
        """
        text = line[17:-1]
        # print line
        if self.__current_dict_name in ('Symbol', 'Wingdings', 'Zapf Dingbats'):
            the_string = ''
            for letter in text:
                hex_num = hex(ord(letter))
                hex_num = unicode_type(hex_num)
                hex_num = hex_num.upper()
                hex_num = hex_num[2:]
                hex_num = '\'%s' % hex_num
                converted = self.__current_dict.get(hex_num)
                if converted is None:
                    sys.stderr.write('module is hex_2_ut8\nmethod is __text_func\n')
                    sys.stderr.write('no hex value for "%s"\n' % hex_num)
                else:
                    the_string += converted
            self.__write_obj.write('tx<nu<__________<%s\n' % the_string)
            # print the_string
        else:
            if self.__caps_list[-1] == 'true' \
                and self.__convert_caps\
                and self.__current_dict_name not in ('Symbol', 'Wingdings', 'Zapf Dingbats'):
                text = text.upper()
            self.__write_obj.write('tx<nu<__________<%s\n' % text)

    def __utf_to_caps_func(self, line):
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
        self.__write_obj.write('tx<ut<__________<%s\n' % utf_text)

    def __utf_token_to_caps_func(self, char_entity):
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
            hex_num = '00%s' % hex_num
        elif length == 4:
            hex_num = '0%s' % hex_num
        new_char_entity = '&#x%s' % hex_num
        converted = self.__caps_uni_dict.get(new_char_entity)
        if not converted:
            # bullets and other entities dont' have capital equivelents
            return char_entity
        else:
            return converted

    def __convert_body(self):
        self.__state = 'body'
        with open_for_read(self.__file) as read_obj:
            with open_for_write(self.__write_to) as self.__write_obj:
                for line in read_obj:
                    self.__token_info = line[:16]
                    action = self.__body_state_dict.get(self.__state)
                    if action is None:
                        sys.stderr.write('error no state found in hex_2_utf8',
                        self.__state
                        )
                    action(line)
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "body_utf_convert.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)

    def convert_hex_2_utf8(self):
        self.__initiate_values()
        if self.__area_to_convert == 'preamble':
            self.__convert_preamble()
        else:
            self.__convert_body()


"""
how to swap case for non-capitals
my_string.swapcase()
An example of how to use a hash for the caps function
(but I shouldn't need this, since utf text is separate
 from regular text?)
sub_dict = {
    "&#x0430;"   : "some other value"
    }
def my_sub_func(matchobj):
    info =  matchobj.group(0)
    value = sub_dict.get(info)
    return value
    return "f"
line = "&#x0430; more text"
reg_exp = re.compile(r'(?P<name>&#x0430;|&#x0431;)')
line2 = re.sub(reg_exp, my_sub_func, line)
print line2
"""
