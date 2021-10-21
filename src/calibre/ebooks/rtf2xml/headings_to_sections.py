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
import os, re
from calibre.ebooks.rtf2xml import copy
from calibre.ptempfile import better_mktemp
from . import open_for_read, open_for_write


class HeadingsToSections:
    """
    """

    def __init__(self,
            in_file,
            bug_handler,
            copy=None,
            run_level=1,
            ):
        """
        Required:
            'file'
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
        self.__write_to = better_mktemp()

    def __initiate_values(self):
        """
        Required:
            Nothing
        Return:
            Nothing
        Logic:
            The self.__end_list is a list of tokens that will force a list to end.
            Likewise, the self.__end_lines is a list of lines that forces a list to end.
        """
        self.__state = "default"
        self.__all_sections = []
        self.__chunk = ''
        self.__state_dict={
        'default'           :   self.__default_func,
        'in_table'          :   self.__in_table_func,
        'in_list'           :   self.__in_list_func,
        'after_body'        :   self.__after_body_func,
        }
        self.__list_depth = 0
        self.__end_list = [
        'mi<mk<body-close',
        # changed 2004-04-26
        # 'mi<mk<par-in-fld',
        'mi<mk<sect-close',  # right before close of section
        'mi<mk<sect-start',  # right before section start
                            # this should be sect-close!
        # 'mi<mk<header-beg',
        # 'mi<mk<header-end',
        # 'mi<mk<head___clo',
        #
        # changed 2004-04-26
        # 'mi<mk<fldbk-end_',
        # 'mi<mk<sec-fd-beg',
        ]
        self.__headings = [
        'heading 1', 'heading 2', 'heading 3', 'heading 4',
        'heading 5', 'heading 6', 'heading 7', 'heading 8',
        'heading 9'
        ]
        self.__section_num = [0]
        self.__id_regex = re.compile(r'\<list-id\>(\d+)')

    def __close_lists(self):
        """
        Required:
            Nothing
        Return:
            Nothing
        Logic:
            Reverse the list of dictionaries. Iterate through the list and
            get the indent for each list. If the current indent is less than
            or equal to the indent in the dictionary, close that level.
            Keep track of how many levels you close. Reduce the list by that
            many levels.
            Reverse the list again.
        """
        current_indent = self.__left_indent
        self.__all_lists.reverse()
        num_levels_closed = 0
        for the_dict in self.__all_lists:
            list_indent = the_dict.get('left-indent')
            if current_indent <= list_indent:
                self.__write_end_item()
                self.__write_end_list()
                num_levels_closed += 1
        self.__all_lists = self.__all_lists[num_levels_closed:]
        self.__all_lists.reverse()

    def __close_sections(self, current_level):
        self.__all_sections.reverse()
        num_levels_closed = 0
        for level in self.__all_sections:
            if current_level <= level:
                self.__write_end_section()
                num_levels_closed += 1
        self.__all_sections = self.__all_sections[num_levels_closed:]
        self.__all_sections.reverse()

    def __write_start_section(self, current_level, name):
        section_num = ''
        for the_num in self.__section_num:
            section_num += '%s.' % the_num
        section_num = section_num[:-1]
        num_in_level = len(self.__all_sections)
        num_in_level = self.__section_num[num_in_level]
        level = len(self.__all_sections)
        self.__write_obj.write(
            'mi<mk<sect-start\n'
                )
        self.__write_obj.write(
                'mi<tg<open-att__<section<num>%s<num-in-level>%s<level>%s'
                '<type>%s\n'
                % (section_num, num_in_level, level, name)
                )

    def __write_end_section(self):
        self.__write_obj.write('mi<mk<sect-close\n')
        self.__write_obj.write('mi<tg<close_____<section\n')

    def __default_func(self, line):
        """
        Required:
            self, line
        Returns:
            Nothing
        Logic
            Look for the start of a paragraph definition. If one is found, check if
            it contains a list-id. If it does, start a list. Change the state to
            in_pard.
            """
        if self.__token_info == 'mi<mk<sect-start':
            self.__section_num[0] += 1
            self.__section_num = self.__section_num[0:1]
        if self.__token_info == 'mi<mk<tabl-start':
            self.__state = 'in_table'
        elif self.__token_info == 'mi<mk<list_start':
            self.__state = 'in_list'
            self.__list_depth += 1
        elif self.__token_info in self.__end_list:
            self.__close_sections(0)
        elif self.__token_info == 'mi<mk<style-name':
            name = line[17:-1]
            if name in self.__headings:
                self.__handle_heading(name)
        if self.__token_info == 'mi<mk<body-close':
            self.__state = 'after_body'
        self.__write_obj.write(line)

    def __handle_heading(self, name):
        num = self.__headings.index(name) + 1
        self.__close_sections(num)
        self.__all_sections.append(num)
        level_depth = len(self.__all_sections) + 1
        self.__section_num = self.__section_num[:level_depth]
        if len(self.__section_num) < level_depth:
            self.__section_num.append(1)
        else:
            self.__section_num[-1] += 1
        self.__write_start_section(num, name)

    def __in_table_func(self, line):
        if self.__token_info == 'mi<mk<table-end_':
            self.__state = 'default'
        self.__write_obj.write(line)

    def __in_list_func(self, line):
        if self.__token_info == 'mi<mk<list_close':
            self.__list_depth -= 1
        elif self.__token_info == 'mi<mk<list_start':
            self.__list_depth += 1
        if self.__list_depth == 0:
            self.__state = 'default'
        self.__write_obj.write(line)

    def __after_body_func(self, line):
        self.__write_obj.write(line)

    def make_sections(self):
        """
        Required:
            nothing
        Returns:
            original file will be changed
        Logic:
        """
        self.__initiate_values()
        read_obj = open_for_read(self.__file)
        self.__write_obj = open_for_write(self.__write_to)
        line_to_read = 1
        while line_to_read:
            line_to_read = read_obj.readline()
            line = line_to_read
            self.__token_info = line[:16]
            action = self.__state_dict.get(self.__state)
            action(line)
        read_obj.close()
        self.__write_obj.close()
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "sections_to_headings.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
