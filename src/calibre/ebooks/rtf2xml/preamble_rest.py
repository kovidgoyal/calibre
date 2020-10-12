
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
import sys,os

from calibre.ebooks.rtf2xml import copy
from . import open_for_read, open_for_write


class Preamble:
    """
    Fix the reamaing parts of the preamble. This module does very little. It
    makes sure that no text gets put in the revision of list table. In the
    future, when I understand how to interpret the revision table and list
    table, I will make these methods more functional.
    """

    def __init__(self, file,
                bug_handler,
                platform,
                default_font,
                code_page,
                copy=None,
                temp_dir=None,
                ):
        """
        Required:
            file--file to parse
            platform --Windows or Macintosh
            default_font -- the default font
            code_page --the code page (ansi1252, for example)
        Optional:
            'copy'-- whether to make a copy of result for debugging
            'temp_dir' --where to output temporary results (default is
            directory from which the script is run.)
        Returns:
            nothing
            """
        self.__file=file
        self.__bug_handler = bug_handler
        self.__copy = copy
        self.__default_font = default_font
        self.__code_page = code_page
        self.__platform = platform
        if temp_dir:
            self.__write_to = os.path.join(temp_dir,"info_table_info.data")
        else:
            self.__write_to = "info_table_info.data"

    def __initiate_values(self):
        """
        Initiate all values.
        """
        self.__state = 'default'
        self.__text_string = ''
        self.__state_dict = {
        'default'   : self.__default_func,
        'revision'  : self.__revision_table_func,
        'list_table'  : self.__list_table_func,
        'body'        : self.__body_func,
        }
        self.__default_dict = {
        'mi<mk<rtfhed-beg'      : self.__found_rtf_head_func,
        'mi<mk<listabbeg_'      : self.__found_list_table_func,
        'mi<mk<revtbl-beg'      : self.__found_revision_table_func,
        'mi<mk<body-open_'      : self.__found_body_func,
        }

    def __default_func(self, line):
        action = self.__default_dict.get(self.__token_info)
        if action:
            action(line)
        else:
            self.__write_obj.write(line)

    def __found_rtf_head_func(self, line):
        """
        Requires:
            line -- the line to parse
        Returns:
            nothing.
        Logic:
            Write to the output file the default font info, the code page
            info, and the platform info.
        """
        self.__write_obj.write(
            'mi<tg<empty-att_<rtf-definition'
            '<default-font>%s<code-page>%s'
            '<platform>%s\n' % (self.__default_font, self.__code_page,
            self.__platform)
        )

    def __found_list_table_func(self, line):
        self.__state = 'list_table'

    def __list_table_func(self, line):
        if self.__token_info == 'mi<mk<listabend_':
            self.__state = 'default'
        elif line[0:2] == 'tx':
            pass
        else:
            self.__write_obj.write(line)

    def __found_revision_table_func(self, line):
        self.__state = 'revision'

    def __revision_table_func(self, line):
        if self.__token_info == 'mi<mk<revtbl-end':
            self.__state = 'default'
        elif line[0:2] == 'tx':
            pass
        else:
            self.__write_obj.write(line)

    def __found_body_func(self, line):
        self.__state = 'body'
        self.__write_obj.write(line)

    def __body_func(self, line):
        self.__write_obj.write(line)

    def fix_preamble(self):
        """
        Requires:
            nothing
        Returns:
            nothing (changes the original file)
        Logic:
            Read one line in at a time. Determine what action to take based on
            the state. The state can either be defaut, the revision table, or
            the list table.
        """
        self.__initiate_values()
        with open_for_read(self.__file) as read_obj:
            with open_for_write(self.__write_to) as self.__write_obj:
                for line in read_obj:
                    self.__token_info = line[:16]
                    action = self.__state_dict.get(self.__state)
                    if action is None:
                        sys.stderr.write(
                        'no matching state in module preamble_rest.py\n' + self.__state + '\n')
                    action(line)
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "preamble_div.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
