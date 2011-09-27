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
import sys, os, tempfile
from calibre.ebooks.rtf2xml import copy
class Header:
    """
    Two public methods are available. The first separates all of the headers
    and footers from the body and puts them at the bottom of the text, where
    they are easier to process. The second joins those headers and footers to
    the proper places in the body.
    """
    def __init__(self,
            in_file ,
            bug_handler,
            copy = None,
            run_level = 1,
            ):
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__copy = copy
        self.__write_to = tempfile.mktemp()
        self.__found_a_header = 0
    def __in_header_func(self, line):
        """
        Handle all tokens that are part of header
        """
        if self.__cb_count == self.__header_bracket_count:
            self.__in_header = 0
            self.__write_obj.write(line)
            self.__write_to_head_obj.write(
            'mi<mk<head___clo\n')
            self.__write_to_head_obj.write(
            'mi<tg<close_____<header-or-footer\n')
            self.__write_to_head_obj.write(
            'mi<mk<header-clo\n')
        else:
            self.__write_to_head_obj.write(line)
    def __found_header(self, line):
        """
        Found a header
        """
        # but this could be header or footer
        self.__found_a_header = 1
        self.__in_header = 1
        self.__header_count += 1
        # temporarily set this to zero so I can enter loop
        self.__cb_count = 0
        self.__header_bracket_count = self.__ob_count
        self.__write_obj.write(
        'mi<mk<header-ind<%04d\n' % self.__header_count)
        self.__write_to_head_obj.write(
        'mi<mk<header-ope<%04d\n' % self.__header_count)
        info = line[6:16]
        type = self.__head_dict.get(info)
        if type:
            self.__write_to_head_obj.write(
                    'mi<tg<open-att__<header-or-footer<type>%s\n' % (type)
                    )
        else:
            sys.stderr.write('module is header\n')
            sys.stderr.write('method is __found_header\n')
            sys.stderr.write('no dict entry\n')
            sys.stderr.write('line is %s' % line)
            self.__write_to_head_obj.write(
                    'mi<tg<open-att__<header-or-footer<type>none\n'
                    )
    def __default_sep(self, line):
        """Handle all tokens that are not header tokens"""
        if self.__token_info[3:5] == 'hf':
            self.__found_header(line)
        self.__write_obj.write(line)
    def __initiate_sep_values(self):
        """
        initiate counters for separate_footnotes method.
        """
        self.__bracket_count=0
        self.__ob_count = 0
        self.__cb_count = 0
        self.__header_bracket_count = 0
        self.__in_header = 0
        self.__header_count = 0
        self.__head_dict = {
            'head-left_'        :   ('header-left'),
            'head-right'        :   ('header-right'),
            'foot-left_'        :   ('footer-left'),
            'foot-right'        :   ('footer-right'),
            'head-first'        :   ('header-first' ),
            'foot-first'        :   ('footer-first' ),
            'header____'        :   ('header' ),
            'footer____'        :   ('footer' ),
        }
    def separate_headers(self):
        """
        Separate all the footnotes in an RTF file and put them at the bottom,
        where they are easier to process.  Each time a footnote is found,
        print all of its contents to a temporary file. Close both the main and
        temporary file. Print the footnotes from the temporary file to the
        bottom of the main file.
        """
        self.__initiate_sep_values()
        read_obj = open(self.__file)
        self.__write_obj = open(self.__write_to, 'w')
        self.__header_holder = tempfile.mktemp()
        self.__write_to_head_obj = open(self.__header_holder, 'w')
        line_to_read = 1
        while line_to_read:
            line_to_read = read_obj.readline()
            line = line_to_read
            self.__token_info = line[:16]
            # keep track of opening and closing brackets
            if self.__token_info == 'ob<nu<open-brack':
                self.__ob_count = line[-5:-1]
            if self.__token_info == 'cb<nu<clos-brack':
                self.__cb_count = line[-5:-1]
            # In the middle of footnote text
            if self.__in_header:
                self.__in_header_func(line)
            # not in the middle of footnote text
            else:
                self.__default_sep(line)
        self.__write_obj.close()
        read_obj.close()
        self.__write_to_head_obj.close()
        read_obj = open(self.__header_holder, 'r')
        write_obj = open(self.__write_to, 'a')
        write_obj.write(
        'mi<mk<header-beg\n')
        line = 1
        while line:
            line = read_obj.readline()
            write_obj.write(line)
        write_obj.write(
        'mi<mk<header-end\n')
        read_obj.close()
        write_obj.close()
        os.remove(self.__header_holder)
        copy_obj = copy.Copy(bug_handler = self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "header_separate.info")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
    def update_info(self, file, copy):
        """
        Unused method
        """
        self.__file = file
        self.__copy = copy
    def __get_head_body_func(self, line):
        """
        Process lines in main body and look for beginning of headers.
        """
        # mi<mk<footnt-end
        if self.__token_info == 'mi<mk<header-beg':
            self.__state = 'head'
        else:
            self.__write_obj.write(line)
    def __get_head_head_func(self, line):
        """
        Copy headers and footers from bottom of file to a separate, temporary file.
        """
        if self.__token_info == 'mi<mk<header-end':
            self.__state = 'body'
        else:
            self.__write_to_head_obj.write(line)
    def __get_headers(self):
        """
        Private method to remove footnotes from main file.  Read one line from
        the main file at a time. If the state is 'body', call on the private
        __get_foot_foot_func. Otherwise, call on the __get_foot_body_func.
        These two functions do the work of separating the footnotes form the
        body.
        """
        read_obj = open(self.__file)
        self.__write_obj = open(self.__write_to, 'w')
            # self.__write_to = "footnote_info.data"
        self.__write_to_head_obj = open(self.__header_holder, 'w')
        line = 1
        while line:
            line = read_obj.readline()
            self.__token_info = line[:16]
            if self.__state == 'body':
                self.__get_head_body_func(line)
            elif self.__state == 'head':
                self.__get_head_head_func(line)
        read_obj.close()
        self.__write_obj.close()
        self.__write_to_head_obj.close()
    def __get_head_from_temp(self, num):
        """
        Private method for joining headers and footers to body. This method
        reads from the temporary file until the proper footnote marker is
        found. It collects all the tokens until the end of the footnote, and
        returns them as a string.
        """
        look_for = 'mi<mk<header-ope<' + num + '\n'
        found_head = 0
        string_to_return = ''
        line = 1
        while line:
            line = self.__read_from_head_obj.readline()
            if found_head:
                if line == 'mi<mk<header-clo\n':
                    return string_to_return
                string_to_return = string_to_return + line
            else:
                if line == look_for:
                    found_head = 1
    def __join_from_temp(self):
        """
        Private method for rejoining footnotes to body.  Read from the
        newly-created, temporary file that contains the body text but no
        footnotes. Each time a footnote marker is found, call the private
        method __get_foot_from_temp(). This method will return a string to
        print out to the third file.
        If no footnote marker is found, simply print out the token (line).
        """
        self.__read_from_head_obj = open(self.__header_holder, 'r')
        read_obj = open(self.__write_to, 'r')
        self.__write_obj = open(self.__write_to2, 'w')
        line = 1
        while line:
            line = read_obj.readline()
            if line[:16] == 'mi<mk<header-ind':
                line = self.__get_head_from_temp(line[17:-1])
            self.__write_obj.write(line)
        read_obj.close()
    def join_headers(self):
        """
        Join the footnotes from the bottom of the file and put them in their
        former places.  First, remove the footnotes from the bottom of the
        input file, outputting them to a temporary file. This creates two new
        files, one without footnotes, and one of just footnotes. Open both
        these files to read. When a marker is found in the main file, find the
        corresponding marker in the footnote file. Output the mix of body and
        footnotes to a third file.
        """
        if not self.__found_a_header:
            return
        self.__write_to2 = tempfile.mktemp()
        self.__state = 'body'
        self.__get_headers()
        self.__join_from_temp()
        self.__write_obj.close()
        self.__read_from_head_obj.close()
        copy_obj = copy.Copy(bug_handler = self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "header_join.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
        os.remove(self.__header_holder)
