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
import sys, os, re

from calibre.ebooks.rtf2xml import copy
from calibre.ptempfile import better_mktemp
from . import open_for_read, open_for_write


class Colors:
    """
    Change lines with color info from color numbers to the actual color names.
    """

    def __init__(self,
            in_file,
            bug_handler,
            copy=None,
            run_level=1
            ):
        """
        Required:
            'file'--file to parse
        Optional:
            'copy'-- whether to make a copy of result for debugging
            'temp_dir' --where to output temporary results (default is
            directory from which the script is run.)
        Returns:
            nothing
            """
        self.__file = in_file
        self.__copy = copy
        self.__bug_handler = bug_handler
        self.__line = 0
        self.__write_to = better_mktemp()
        self.__run_level = run_level

    def __initiate_values(self):
        """
        Initiate all values.
        """
        self.__color_dict = {}
        self.__state = 'before_color_table'
        self.__state_dict = {
        'before_color_table': self.__before_color_func,
        'in_color_table'    : self.__in_color_func,
        'after_color_table'  : self.__after_color_func,
        'cw<ci<red_______'  : self.__default_color_func,
        'cw<ci<green_____'  : self.__default_color_func,
        'cw<ci<blue______'  : self.__blue_func,
        'tx<nu<__________'  : self.__do_nothing_func,
        }
        self.__color_string = '#'
        self.__color_num = 1
        self.__line_color_exp = re.compile(r'bdr-color_:(\d+)')
        # cw<bd<bor-par-to<nu<bdr-hair__|bdr-li-wid:0.50|bdr-sp-wid:1.00|bdr-color_:2

    def __before_color_func(self, line):
        """
        Requires:
            line
        Returns:
            nothing
        Logic:
            Check to see if the line marks the beginning of the color table.
            If so, change states.
            Always print out the line.
        """
        # mi<mk<clrtbl-beg
        if self.__token_info == 'mi<mk<clrtbl-beg':
            self.__state = 'in_color_table'
        self.__write_obj.write(line)

    def __default_color_func(self, line):
        """
        Requires:
            line
        Returns:
            nothing
        Logic:
            get the hex number from the line and add it to the color string.
            """
        hex_num = line[-3:-1]
        self.__color_string += hex_num

    def __blue_func(self, line):
        """
        Requires:
            line
        Returns:
            nothing
        Logic:
            Get the hex number from the line and add it to the color string.
            Add a key -> value pair to the color dictionary, with the number
            as the key, and the hex number as the value. Write an empty tag
            with the hex number and number as attributes. Add one to the color
            number. Reset the color string to '#'
            """
        hex_num = line[-3:-1]
        self.__color_string +=  hex_num
        self.__color_dict[self.__color_num] = self.__color_string
        self.__write_obj.write(
        'mi<tg<empty-att_'
        '<color-in-table<num>%s<value>%s\n' % (self.__color_num, self.__color_string)
        )
        self.__color_num += 1
        self.__color_string = '#'

    def __in_color_func(self, line):
        """
        Requires:
            line
        Returns:
            nothing
        Logic:
            Check if the end of the color table has been reached. If so,
            change the state to after the color table.
            Otherwise, get a function by passing the self.__token_info to the
            state dictionary.
            """
        # mi<mk<clrtbl-beg
        # cw<ci<red_______<nu<00
        if self.__token_info == 'mi<mk<clrtbl-end':
            self.__state = 'after_color_table'
        else:
            action = self.__state_dict.get(self.__token_info)
            if action is None:
                sys.stderr.write('in module colors.py\n'
                'function is self.__in_color_func\n'
                'no action for %s' % self.__token_info
                )
            action(line)

    def __after_color_func(self, line):
        """
        Check the to see if it contains color info. If it does, extract the
        number and look up the hex value in the color dictionary. If the color
        dictionary has no key for the number, print out an error message.
        Otherwise, print out the line.
        Added Oct 10, 2003
        If the number is 0, that indicates no color
        """
        # cw<ci<font-color<nu<2
        if self.__token_info == 'cw<ci<font-color':
            hex_num = int(line[20:-1])
            hex_num = self.__figure_num(hex_num)
            if hex_num:
                self.__write_obj.write(
                'cw<ci<font-color<nu<%s\n' % hex_num
                )
        elif line[0:5] == 'cw<bd':
            the_index = line.find('bdr-color_')
            if the_index > -1:
                line = re.sub(self.__line_color_exp, self.__sub_from_line_color, line)
            self.__write_obj.write(line)
            """
            if num == 0:
                hex_num = 'false'
            else:
                hex_num = self.__color_dict.get(num)
            if hex_num == None:
                if self.__run_level > 0:
                    sys.stderr.write(
                    'module is colors.py\n'
                    'function is self.__after_color_func\n'
                    'no value in self.__color_dict for key %s\n' % num
                    )
                if self.__run_level > 3:
                    sys.stderr.write(
                        'run level is %s\n'
                        'Script will now quit\n'
                        % self.__run_level)
            else:
                self.__write_obj.write(
                'cw<ci<font-color<nu<%s\n' % hex_num
                )
            """
        else:
            self.__write_obj.write(line)
        # cw<bd<bor-par-to<nu<bdr-hair__|bdr-li-wid:0.50|bdr-sp-wid:1.00|bdr-color_:2

    def __sub_from_line_color(self, match_obj):
        num = match_obj.group(1)
        try:
            num = int(num)
        except ValueError:
            if self.__run_level > 3:
                msg = 'can\'t make integer from string\n'
                raise self.__bug_handler(msg)
            else:
                return 'bdr-color_:no-value'
        hex_num = self.__figure_num(num)
        return 'bdr-color_:%s' % hex_num

    def __figure_num(self, num):
        if num == 0:
            hex_num = 'false'
        else:
            hex_num = self.__color_dict.get(num)
        if hex_num is None:
            hex_num = '0'
            if self.__run_level > 3:
                msg = 'no value in self.__color_dict' \
                'for key %s at line %d\n' % (num, self.__line)
                raise self.__bug_handler(msg)
        return hex_num

    def __do_nothing_func(self, line):
        """
        Bad RTF will have text in the color table
        """
        pass

    def convert_colors(self):
        """
        Requires:
            nothing
        Returns:
            nothing (changes the original file)
        Logic:
            Read one line in at a time. Determine what action to take based on
            the state. If the state is before the color table, look for the
            beginning of the color table.
            If the state is in the color table, create the color dictionary
            and print out the tags.
            If the state if after the color table, look for lines with color
            info, and substitute the number with the hex number.
        """
        self.__initiate_values()
        with open_for_read(self.__file) as read_obj:
            with open_for_write(self.__write_to) as self.__write_obj:
                for line in read_obj:
                    self.__line+=1
                    self.__token_info = line[:16]
                    action = self.__state_dict.get(self.__state)
                    if action is None:
                        try:
                            sys.stderr.write('no matching state in module fonts.py\n')
                            sys.stderr.write(self.__state + '\n')
                        except:
                            pass
                    action(line)
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "color.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
