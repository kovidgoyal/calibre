
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
from polyglot.builtins import unicode_type

from . import open_for_read, open_for_write


class MakeLists:
    """
    Form lists.
    Use RTF's own formatting to determine if a paragraph definition is part of a
    list.
    Use indents to determine items and how lists are nested.
    """

    def __init__(self,
            in_file,
            bug_handler,
            headings_to_sections,
            list_of_lists,
            copy=None,
            run_level=1,
            no_headings_as_list=1,
            write_list_info=0,
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
        self.__run_level = run_level
        self.__no_headings_as_list = no_headings_as_list
        self.__headings_to_sections = headings_to_sections
        self.__copy = copy
        self.__write_to = better_mktemp()
        self.__list_of_lists = list_of_lists
        self.__write_list_info = write_list_info

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
        self.__left_indent = 0
        self.__list_type = 'not-defined'
        self.__pard_def = ""
        self.__all_lists = []
        self.__level = 0
        self.__list_chunk = ''
        self.__state_dict={
        'default'           :   self.__default_func,
        'in_pard'           :   self.__in_pard_func,
        'after_pard'        :   self.__after_pard_func,
        }
        self.__headings = [
        'heading 1', 'heading 2', 'heading 3', 'heading 4',
        'heading 5', 'heading 6', 'heading 7', 'heading 8',
        'heading 9'
        ]
        self.__allow_levels = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
        self.__style_name = ''
        self.__end_list = [
        'mi<mk<body-close',
        'mi<mk<par-in-fld',
        'cw<tb<cell______',
        'cw<tb<row-def___',
        'cw<tb<row_______',
        'mi<mk<sect-close',
        'mi<mk<sect-start',
        'mi<mk<header-beg',
        'mi<mk<header-end',
        'mi<mk<head___clo',
        'mi<mk<fldbk-end_',
        'mi<mk<close_cell',
        'mi<mk<footnt-ope',
        'mi<mk<foot___clo',
        'mi<mk<tabl-start',
        # 'mi<mk<sec-fd-beg',
        ]
        self.__end_lines = [
            'mi<tg<close_____<cell\n',
        ]
        self.__id_regex = re.compile(r'\<list-id\>(\d+)')
        self.__lv_regex = re.compile(r'\<list-level\>(\d+)')
        self.__found_appt = 0
        self.__line_num = 0

    def __in_pard_func(self, line):
        """
        Required:
            line -- the line of current text.
        Return:
            Nothing
        Logic:
            You are in a list, but in the middle of a paragraph definition.
            Don't do anything until you find the end of the paragraph definition.
        """
        if self.__token_info == 'mi<mk<pard-end__':
            self.__state = 'after_pard'
        self.__write_obj.write(line)

    def __after_pard_func(self, line):
        """
        Required:
            line -- the line of current text.
        Return:
            Nothing
        Logic:
            You are in a list, but after a paragraph definition. You have to
            determine if the last pargraph definition ends a list, continues
            the old one, or starts a new one.
            Otherwise, look for a paragraph definition. If one is found, determine if
            the paragraph definition contains a list-id. If it does, use the method
            self.__list_after_par_def to determine the action.
            If the paragraph definition does not contain a list-id, use the method
            close_lists to close out items and lists for a paragraph that is not
            If a bigger block is found (such as a section or a cell), end all lists.
            indented.
            If no special line is found, add each line to a buffer.
        """
        if self.__token_info == 'mi<tg<open-att__' and line[17:37] == 'paragraph-definition':
            is_heading = self.__is_a_heading()
            # found paragraph definition and not heading 1
            search_obj = re.search(self.__id_regex, line)
            if search_obj and not is_heading:  # found list-id
                search_obj_lv = re.search(self.__lv_regex, line)
                if search_obj_lv:
                    self.__level = search_obj_lv.group(1)
                num = search_obj.group(1)
                self.__list_after_par_def_func(line, num)
                self.__write_obj.write(line)
                self.__state = 'in_pard'
            # heading 1
            elif is_heading:
                self.__left_indent = -1000
                self.__close_lists()
                self.__write_obj.write(self.__list_chunk)
                self.__list_chunk = ''
                self.__state = 'default'
                self.__write_obj.write(line)
            # Normal with no list id
            else:
                self.__close_lists()
                self.__write_obj.write(self.__list_chunk)
                self.__list_chunk = ''
                self.__write_obj.write(line)
                if len(self.__all_lists) == 0:
                    self.__state= 'default'
                else:
                    self.__state = 'in_pard'
        # section to end lists
        elif self.__token_info in self.__end_list :
            self.__left_indent = -1000
            self.__close_lists()
            self.__write_obj.write(self.__list_chunk)
            self.__list_chunk = ''
            self.__state = 'default'
            self.__write_obj.write(line)
        else:
            self.__list_chunk += line

    def __list_after_par_def_func(self, line, id):
        """
        Required:
            line -- the line of current text.
            id -- the id of the current list
        Return:
            Nothing
        Logic:
            You have found the end of a paragraph definition, and have found
            another paragraph definition with a list id.
            If the list-id is different from the last paragraph definition,
            write the string in the buffer. Close out the lists with another
            method and start a new list.
            If the list id is the same as the last one, check the indent on the
            current paragraph definition. If it is greater than the previous one,
            do not end the current list or item. Start a new list.
        """
        last_list_id = self.__all_lists[-1]['id']
        if id != last_list_id:
            self.__close_lists()
            self.__write_obj.write(self.__list_chunk)
            self.__write_start_list(id)
            self.__list_chunk = ''
        else:
            last_list_indent = self.__all_lists[-1]['left-indent']
            if self.__left_indent > last_list_indent:
                self.__write_obj.write(self.__list_chunk)
                self.__write_start_list(id)
            else:
                self.__write_end_item()
                self.__write_obj.write(self.__list_chunk)
                self.__write_start_item()
            self.__list_chunk = ''

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
        if self.__line_num < 25 and self.__found_appt:
            sys.stderr.write('in closing out lists\n')
            sys.stderr.write('current_indent is "%s"\n' % self.__left_indent)
        current_indent = self.__left_indent
        self.__all_lists.reverse()
        num_levels_closed = 0
        for the_dict in self.__all_lists:
            list_indent = the_dict.get('left-indent')
            if self.__line_num < 25 and self.__found_appt:
                sys.stderr.write('last indent is "%s"' % list_indent)
            if current_indent <= list_indent:
                self.__write_end_item()
                self.__write_end_list()
                num_levels_closed += 1
        self.__all_lists = self.__all_lists[num_levels_closed:]
        self.__all_lists.reverse()

    def __write_end_list(self):
        """
        Required:
            Nothing
        Return:
            Nothing
        Logic:
            Write the end of a list.
        """
        self.__write_obj.write('mi<tg<close_____<list\n')
        self.__write_obj.write('mi<mk<list_close\n')

    def __write_start_list(self, id):
        """
        Required:
            id -- the id of the current list.
        Return:
            Nothing
        Logic:
            Write the start of a list and add the id and left-indent to the
            self.__all_lists list.
            Write cues of when a list starts for later processing.
            In order to determine the type of list, you have to iterate through
            the self.__list_of lists. This list looks like:
                [[{list-id: [1, 2], [{}], [{}]] [{list-id: [3, 4], [{}]]]
            I need to get the inside lists of the main lists. Then I need to get
            the first item of what I just got. This is a dictionary. Get the list-id.
            This is  a list. Check to see if the current id is in this list. If
            so, then get the list-type from the dictionary.
        """
        the_dict = {}
        the_dict['left-indent'] = self.__left_indent
        the_dict['id'] = id
        self.__all_lists.append(the_dict)
        self.__write_obj.write(
            'mi<mk<list_start\n'
                )
        # bogus levels are sometimes written for empty paragraphs
        if unicode_type(self.__level) not in self.__allow_levels:
            lev_num = '0'
        else:
            lev_num = self.__level
        self.__write_obj.write(
            'mi<tg<open-att__<list<list-id>%s<level>%s'
            % (id, lev_num)
                )
        list_dict = {}
        if self.__list_of_lists:  # older RTF won't generate a list_of_lists
            index_of_list = self.__get_index_of_list(id)
            if index_of_list is not None:  # found a matching id
                curlist = self.__list_of_lists[index_of_list]
                list_dict = curlist[0]
                level = int(self.__level) + 1
                if level >= len(curlist):
                    level = len(curlist) - 1
                level_dict = curlist[level][0]
                list_type = level_dict.get('numbering-type')
                if list_type == 'bullet':
                    list_type = 'unordered'
                else:
                    list_type = 'ordered'
                self.__write_obj.write(
                    '<list-type>%s' % (list_type))
            else:  # no matching id
                self.__write_obj.write(
                    '<list-type>%s' % (self.__list_type))
        else:  # older RTF
            self.__write_obj.write(
                '<list-type>%s' % (self.__list_type))
        # if you want to dump all the info to the list, rather than
        # keeping it in the table above, change self.__write_list_info
        # to true.
        if self.__list_of_lists and self.__write_list_info and list_dict:
            not_allow = ['list-id',]
            the_keys_list = list_dict.keys()
            for the_key in the_keys_list:
                if the_key in not_allow:
                    continue
                self.__write_obj.write('<%s>%s' % (the_key, list_dict[the_key]))
            the_keys_level = level_dict.keys()
            for the_key in the_keys_level:
                self.__write_obj.write('<%s>%s' % (the_key, level_dict[the_key]))
        self.__write_obj.write('\n')
        self.__write_obj.write(
            'mi<mk<liststart_\n'
                )
        self.__write_start_item()

    def __get_index_of_list(self, id):
        """
        Requires:
            id -- id of current paragraph-definition
        Returns:
            an index of where the id occurs in list_of_lists, the
            dictionary passed to this module.
        Logic:
            Iterate through the big lists, the one passed to this module and
            get the first item, the dictionary. Use a counter to keep
            track of how many times you iterate with the counter.
            Once you find a match, return the counter.
            If no match is found, print out an error message.
        """
        # some RTF use 0 indexed list. Don't know what to do?
        if id == '0':
            return
        the_index = 0
        for list in self.__list_of_lists:
            the_dict = list[0]
            id_in_list = the_dict.get('list-id')
            if id in id_in_list:
                return the_index
            the_index += 1
        if self.__run_level > 0:
            sys.stderr.write('Module is make_lists.py\n'
                'Method is __get_index_of_list\n'
                'The main list does not appear to have a matching id for %s \n'
                % (id)
                )
            # sys.stderr.write(repr(self.__list_of_lists))
#        if self.__run_level > 3:
#            msg = 'level is "%s"\n' % self.__run_level
#            self.__bug_handler

    def __write_start_item(self):
        self.__write_obj.write('mi<mk<item_start\n')
        self.__write_obj.write('mi<tg<open______<item\n')
        self.__write_obj.write('mi<mk<itemstart_\n')

    def __write_end_item(self):
        self.__write_obj.write('mi<tg<item_end__\n')
        self.__write_obj.write('mi<tg<close_____<item\n')
        self.__write_obj.write('mi<tg<item__end_\n')

    def __default_func(self, line):
        """
        Required:
            self, line
        Returns:
            Nothing
        Logic
            Look for the start of a paragraph defintion. If one is found, check if
            it contains a list-id. If it does, start a list. Change the state to
            in_pard.
            """
        if self.__token_info == 'mi<tg<open-att__' and line[17:37] == 'paragraph-definition':
            is_a_heading = self.__is_a_heading()
            if not is_a_heading:
                search_obj = re.search(self.__id_regex, line)
                if search_obj:
                    num = search_obj.group(1)
                    self.__state = 'in_pard'
                    search_obj_lv = re.search(self.__lv_regex, line)
                    if search_obj_lv:
                        self.__level = search_obj_lv.group(1)
                    self.__write_start_list(num)
        self.__write_obj.write(line)

    def __is_a_heading(self):
        if self.__style_name in self.__headings:
            if self.__headings_to_sections:
                return 1
            else:
                if self.__no_headings_as_list:
                    return 1
                else:
                    return 0
        else:
            return 0

    def __get_indent(self, line):
        if self.__token_info == 'mi<mk<left_inden':
            self.__left_indent = float(line[17:-1])

    def __get_list_type(self, line):
        if self.__token_info == 'mi<mk<list-type_':  # <ordered
            self.__list_type = line[17:-1]
            if self.__list_type == 'item':
                self.__list_type = "unordered"

    def __get_style_name(self, line):
        if self.__token_info == 'mi<mk<style-name':
            self.__style_name = line[17:-1]

    def make_lists(self):
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
            self.__get_indent(line)
            self.__get_list_type(line)
            self.__get_style_name(line)
            action = self.__state_dict.get(self.__state)
            action(line)
        read_obj.close()
        self.__write_obj.close()
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "make_lists.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
