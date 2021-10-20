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
import sys, os

from calibre.ebooks.rtf2xml import copy
from calibre.ptempfile import better_mktemp
from . import open_for_read, open_for_write


class Fonts:
    """
    Change lines with font info from font numbers to the actual font names.
    """

    def __init__(self,
            in_file,
            bug_handler,
            default_font_num,
            copy=None,
            run_level=1,
            ):
        """
        Required:
            'file'--file to parse
            'default_font_num'--the default font number
        Optional:
            'copy'-- whether to make a copy of result for debugging
            'temp_dir' --where to output temporary results (default is
            directory from which the script is run.)
        Returns:
            nothing
            """
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__copy = copy
        self.__default_font_num = default_font_num
        self.__write_to = better_mktemp()
        self.__run_level = run_level

    def __initiate_values(self):
        """
        Initiate all values.
        """
        self.__special_font_dict = {
        'Symbol'        :   0,
        'Wingdings'     :   0,
        'Zapf Dingbats'      :   0,
        }
        self.__special_font_list = [
        'Symbol', 'Wingdings', 'Zapf Dingbats'
        ]
        self.__state = 'default'
        self.__state_dict = {
        'default'           : self.__default_func,
        'font_table'        : self.__font_table_func,
        'after_font_table'  : self.__after_font_table_func,
        'font_in_table'     : self.__font_in_table_func,
        }
        self.__font_table = {}
        # individual font written
        self.__wrote_ind_font = 0

    def __default_func(self, line):
        """
        Requires:
            line
        Returns:
            nothing
        Handle all lines before the font table. Check for the beginning of the
        font table. If found, change the state. Print out all lines.
        """
        if self.__token_info == 'mi<mk<fonttb-beg':
            self.__state = 'font_table'
        self.__write_obj.write(line)

    def __font_table_func(self, line):
        """
        Requires:
            line
        Returns:
            nothing
        Logic:
            If the self.__token_info indicates that you have reached the end of
            the font table, then change the state to after the font table.
            If the self.__token_info indicates that there is a font in the
            table, change the state to font in table. Reset the number of the
            font to the default font (in case there is no number provided, in
            which case RTF assumes the number will be the default font.) Reset
            the test string (for the font name) to ''
            """
        if self.__token_info == 'mi<mk<fonttb-end':
            self.__state = 'after_font_table'
        elif self.__token_info == 'mi<mk<fontit-beg':
            self.__state = 'font_in_table'
            self.__font_num = self.__default_font_num
            self.__text_line = ''
        # self.__write_obj.write(line)

    def __font_in_table_func(self, line):
        """
        Requires:
            line
        Returns:
            nothing
        Logic:
            Check for four conditions:
                The line contains font-info. In this case, store the number in
                self.__font_num.
                The line contains text. In this case, add to the text string
                self.__text_string.
                The line marks the end of the individual font in the table. In
                this case, add a new key-> value pair to the font-table
                dictionary. Also create an empty tag with the name and number
                as attributes.
                Preamture end of font table
            """
        # cw<ci<font-style<nu<4
        # tx<nu<__________<Times;
        if self.__token_info == 'mi<mk<fontit-end':
            self.__wrote_ind_font = 1
            self.__state = 'font_table'
            self.__text_line = self.__text_line[:-1]  # get rid of last ';'
            self.__font_table[self.__font_num] = self.__text_line
            self.__write_obj.write(
            'mi<tg<empty-att_'
            '<font-in-table<name>%s<num>%s\n' % (self.__text_line, self.__font_num)
            )
        elif self.__token_info == 'cw<ci<font-style':
            self.__font_num = line[20:-1]
        elif self.__token_info == 'tx<nu<__________' or \
        self.__token_info == 'tx<ut<__________':
            self.__text_line += line[17:-1]
        elif self.__token_info == 'mi<mk<fonttb-end':
            self.__found_end_font_table_func()
            self.__state = 'after_font_table'

    def __found_end_font_table_func(self):
        """
        Required:
            nothing
        Returns:
            nothing
        Logic:
            If not individual fonts have been written, write one out
        """
        if not self.__wrote_ind_font:
            self.__write_obj.write(
            'mi<tg<empty-att_'
            '<font-in-table<name>Times<num>0\n')

    def __after_font_table_func(self, line):
        """
        Required:
            line
        Returns:
            nothing
        Logic:
            Check the self.__token_info. If this matches a token with font
            info, then extract the number from the line, and look up the font
            name in the font dictionary. If no name exists for that number,
            print out an error. Otherwise print out the same line, except with
            the name rather than the number.
            If the line does not contain font info, simply print it out to the
            file.
            """
        if self.__token_info == 'cw<ci<font-style':
            font_num = line[20:-1]
            font_name = self.__font_table.get(font_num)
            if font_name is None:
                if self.__run_level > 3:
                    msg = 'no value for %s in self.__font_table\n' % font_num
                    raise self.__bug_handler(msg)
            else:
                # self.__special_font_dict
                if font_name in self.__special_font_list:
                    self.__special_font_dict[font_name] = 1
                self.__write_obj.write(
                'cw<ci<font-style<nu<%s\n' % font_name
                )
        else:
            self.__write_obj.write(line)

    def convert_fonts(self):
        """
        Required:
            nothing
        Returns:
            a dictionary indicating with values for special fonts
        Logic:
            Read one line in at a time. Determine what action to take based on
            the state. If the state is font_table, looke for individual fonts
            and add the number and font name to a dictionary. Also create a
            tag for each individual font in the font table.
            If the state is after the font table, look for lines with font
            info. Substitute a font name for a font number.
            """
        self.__initiate_values()
        with open_for_read(self.__file) as read_obj:
            with open_for_write(self.__write_to) as self.__write_obj:
                for line in read_obj:
                    self.__token_info = line[:16]
                    action = self.__state_dict.get(self.__state)
                    if action is None:
                        sys.stderr.write('no matching state in module fonts.py\n' + self.__state + '\n')
                    action(line)
        default_font_name = self.__font_table.get(self.__default_font_num)
        if not default_font_name:
            default_font_name = 'Not Defined'
        self.__special_font_dict['default-font'] = default_font_name
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "fonts.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
        return self.__special_font_dict
