
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
import sys, os,  re
from calibre.ebooks.rtf2xml import copy
from calibre.ptempfile import better_mktemp
from . import open_for_read, open_for_write


class GroupStyles:
    """
    Form lists.
    Use RTF's own formatting to determine if a paragraph definition is part of a
    list.
    Use indents to determine items and how lists are nested.
    """

    def __init__(self,
            in_file,
            bug_handler,
            copy=None,
            run_level=1,
            wrap=0,
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
        self.__run_level = run_level
        self.__write_to =  better_mktemp()
        self.__wrap = wrap

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
        self.__list_chunk = ''
        self.__state_dict={
        'default'           :   self.__default_func,
        'in_pard'           :   self.__in_pard_func,
        'after_pard'        :   self.__after_pard_func,
        }
        # section end
        self.__end_list = [
        # section end
        'mi<mk<sect-close',
        'mi<mk<sect-start',
        # table begin
        'mi<mk<tabl-start',
        # field block begin
        'mi<mk<fldbk-end_',
        'mi<mk<fldbkstart',
        # cell end
        'mi<mk<close_cell',
        # item end
        'mi<tg<item_end__',
        # footnote end
        'mi<mk<foot___clo',
        'mi<mk<footnt-ope',
        # heading end
        'mi<mk<header-beg',
        'mi<mk<header-end',
        'mi<mk<head___clo',
        # lists
        'mi<tg<item_end__',
        'mi<tg<item_end__',
        'mi<mk<list_start'
        # body close
        # don't use
        # 'mi<mk<body-close',
        # 'mi<mk<par-in-fld',
        # 'cw<tb<cell______',
        # 'cw<tb<row-def___',
        # 'cw<tb<row_______',
        # 'mi<mk<sec-fd-beg',
        ]
        self.__name_regex = re.compile(r'<name>')
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
        if self.__token_info == 'mi<tg<close_____' \
            and line[17:-1] == 'paragraph-definition':
            self.__state = 'after_pard'
        else:
            self.__write_obj.write(line)

    def __after_pard_func(self, line):
        """
        Required:
            line -- the line of current text.
        Return:
            Nothing
        Logic:
        """
        if self.__token_info == 'mi<tg<open-att__' \
            and line[17:37] == 'paragraph-definition':
            # found paragraph definition
            self.__pard_after_par_def_func(line)
        elif self.__token_info == 'mi<tg<close_____' \
            and line[17:-1] == 'paragraph-definition':
            sys.stderr.write('Wrong flag in __after_pard_func\n')
            if self.__run_level > 2:
                msg =  'wrong flag'
                raise self.__bug_handler(msg)
        elif self.__token_info in self.__end_list:
            self.__write_obj.write('mi<tg<close_____<paragraph-definition\n')
            self.__write_end_wrap()
            self.__write_obj.write(self.__list_chunk)
            self.__list_chunk = ''
            self.__state = 'default'
            self.__write_obj.write(line)
        else:
            self.__list_chunk += line

    def __close_pard_(self, line):
        self.__write_obj.write(self.__list_chunk)
        self.__write_obj.write('mi<tg<close_____<paragraph-definition\n')
        self.__write_end_wrap()
        self.__list_chunk = ''
        self.__state = 'default'

    def __write_start_wrap(self, name):
        if self.__wrap:
            self.__write_obj.write('mi<mk<style-grp_<%s\n' % name)
            self.__write_obj.write('mi<tg<open-att__<style-group<name>%s\n' % name)
            self.__write_obj.write('mi<mk<style_grp_<%s\n' % name)

    def __write_end_wrap(self):
        if self.__wrap:
            self.__write_obj.write('mi<mk<style_gend\n')
            self.__write_obj.write('mi<tg<close_____<style-group\n')
            self.__write_obj.write('mi<mk<stylegend_\n')

    def __pard_after_par_def_func(self, line):
        """
        Required:
            line -- the line of current text.
            id -- the id of the current list
        Return:
            Nothing
        Logic:
        """
        if self.__last_style_name == self.__style_name:
            # just keep going
            if self.__wrap:
                self.__write_obj.write('mi<tg<close_____<paragraph-definition\n')
            self.__write_obj.write(self.__list_chunk)
            self.__list_chunk = ''
            self.__state = 'in_pard'
            if self.__wrap:
                self.__write_obj.write(line)
        else:
            # different name for the paragraph definition
            self.__write_obj.write('mi<tg<close_____<paragraph-definition\n')
            self.__write_end_wrap()
            self.__write_obj.write(self.__list_chunk)
            self.__write_start_wrap(self.__style_name)
            self.__write_obj.write(line)
            self.__state = 'in_pard'
            self.__last_style_name = self.__style_name
            self.__list_chunk = ''

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
        if self.__token_info == 'mi<tg<open-att__' \
            and line[17:37] == 'paragraph-definition':
            self.__state = 'in_pard'
            self.__last_style_name = self.__style_name
            self.__write_start_wrap(self.__last_style_name)
            self.__write_obj.write(line)
        else:
            self.__write_obj.write(line)

    def __get_style_name(self, line):
        if self.__token_info == 'mi<mk<style-name':
            self.__style_name = line[17:-1]

    def group_styles(self):
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
            self.__get_style_name(line)
            action = self.__state_dict.get(self.__state)
            action(line)
        read_obj.close()
        self.__write_obj.close()
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "group_styles.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
