
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
import os
from calibre.ebooks.rtf2xml import copy
from calibre.ptempfile import better_mktemp
from . import open_for_read, open_for_write


class ListNumbers:
    """
        RTF puts list numbers outside of the paragraph. The public method
        in this class put the list numbers inside the paragraphs.
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
        initiate values for fix_list_numbers.
        Required:
            Nothing
        Return:
            Nothing
        """
        self.__state = "default"
        self.__list_chunk = ''
        self.__previous_line = ''
        self.__list_text_ob_count = ''
        self.__state_dict={
        'default'           :   self.__default_func,
        'after_ob'          :   self.__after_ob_func,
        'list_text'         :   self.__list_text_func,
        'after_list_text'   :   self.__after_list_text_func
        }

    def __after_ob_func(self, line):
        """
        Handle the line immediately after an open bracket.
        Required:
            self, line
        Returns:
            Nothing
            """
        if self.__token_info == 'cw<ls<list-text_':
            self.__state = 'list_text'
            self.__list_chunk = self.__list_chunk + \
            self.__previous_line + line
            self.__list_text_ob = self.__ob_count
            self.__cb_count = 0
        else:
            self.__write_obj.write(self.__previous_line)
            self.__write_obj.write(line)
            self.__state = 'default'

    def __after_list_text_func(self, line):
        """
        Look for an open bracket or a line of text, and then print out the
        self.__list_chunk. Print out the line.
        """
        if line[0:2] == 'ob' or line[0:2] == 'tx':
            self.__state = 'default'
            self.__write_obj.write('mi<mk<lst-txbeg_\n')
            self.__write_obj.write('mi<mk<para-beg__\n')
            self.__write_obj.write('mi<mk<lst-tx-beg\n')
            self.__write_obj.write(
                # 'mi<tg<open-att__<list-text<type>%s\n' % self.__list_type)
                'mi<tg<open-att__<list-text\n')
            self.__write_obj.write(self.__list_chunk)
            self.__write_obj.write('mi<tg<close_____<list-text\n')
            self.__write_obj.write('mi<mk<lst-tx-end\n')
            self.__list_chunk = ''
        self.__write_obj.write(line)

    def __determine_list_type(self, chunk):
        """
        Determine if the list is ordered or itemized
        """
        lines = chunk.split('\n')
        text_string = ''
        for line in lines:
            if line[0:5] == 'tx<hx':
                if line[17:] == '\'B7':
                    return "unordered"
            elif line[0:5] == 'tx<nu':
                text_string += line[17:]
        text_string = text_string.replace('.', '')
        text_string = text_string.replace('(', '')
        text_string = text_string.replace(')', '')
        if text_string.isdigit():
            return 'ordered'
        """
        sys.stderr.write('module is list_numbers\n')
        sys.stderr.write('method is __determine type\n')
        sys.stderr.write('Couldn\'t get type of list\n')
        """
        # must be some type of ordered list -- just a guess!
        return 'unordered'

    def __list_text_func(self, line):
        """
        Handle lines that are part of the list text. If the end of the list
        text is found (the closing bracket matches the self.__list_text_ob),
        then change  the state. Always add the line to the self.__list_chunk
        Required:
            self, line
        Returns:
            Nothing
            """
        if self.__list_text_ob == self.__cb_count:
            self.__state = 'after_list_text'
            self.__right_after_list_text = 1
            self.__list_type = self.__determine_list_type(self.__list_chunk)
            self.__write_obj.write('mi<mk<list-type_<%s\n' % self.__list_type)
        if self.__token_info != 'cw<pf<par-def___':
            self.__list_chunk = self.__list_chunk + line

    def __default_func(self, line):
        """
        Handle the lines that are not part of any special state. Look for an
        opening bracket. If an open bracket is found, add this line to a
        temporary self.__previous line, which other methods need. Otherwise,
        print out the line.
        Required:
            self, line
        Returns:
            Nothing
            """
        if self.__token_info == 'ob<nu<open-brack':
            self.__state = 'after_ob'
            self.__previous_line = line
        else:
            self.__write_obj.write(line)

    def fix_list_numbers(self):
        """
        Required:
            nothing
        Returns:
            original file will be changed
        Logic:
            Read in one line a time from the file. Keep track of opening and
            closing brackets. Determine the method ('action') by passing the
            state to the self.__state_dict.
            Simply print out the line to a temp file until an open bracket
            is found. Check the next line. If it is list-text, then start
            adding to the self.__list_chunk until the closing bracket is
            found.
            Next, look for an open bracket or text. When either is found,
            print out self.__list_chunk and the line.
        """
        self.__initiate_values()
        read_obj = open_for_read(self.__file)
        self.__write_obj = open_for_write(self.__write_to)
        line_to_read = 1
        while line_to_read:
            line_to_read = read_obj.readline()
            line = line_to_read
            self.__token_info = line[:16]
            if self.__token_info == 'ob<nu<open-brack':
                self.__ob_count = line[-5:-1]
            if self.__token_info == 'cb<nu<clos-brack':
                self.__cb_count = line[-5:-1]
            action = self.__state_dict.get(self.__state)
            action(line)
        read_obj.close()
        self.__write_obj.close()
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "list_numbers.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
