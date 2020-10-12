
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
from polyglot.builtins import unicode_type

from . import open_for_read, open_for_write


class Footnote:
    """
    Two public methods are available. The first separates all of the
    footnotes from the body and puts them at the bottom of the text, where
    they are easier to process. The second joins those footnotes to the
    proper places in the body.
    """

    def __init__(self,
            in_file ,
            bug_handler,
            copy=None,
            run_level=1,
            ):
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__copy = copy
        self.__write_to = better_mktemp()
        self.__found_a_footnote = 0

    def __first_line_func(self, line):
        """
        Print the tag info for footnotes.  Check whether footnote is an
        endnote and make the tag according to that.
        """
        if self.__token_info == 'cw<nt<type______':
            self.__write_to_foot_obj.write(
            'mi<tg<open-att__<footnote<type>endnote<num>%s\n' % self.__footnote_count)
        else:
            self.__write_to_foot_obj.write(
            'mi<tg<open-att__<footnote<num>%s\n' % self.__footnote_count)
        self.__first_line = 0

    def __in_footnote_func(self, line):
        """Handle all tokens that are part of footnote"""
        if self.__first_line:
            self.__first_line_func(line)
        if self.__token_info == 'cw<ci<footnot-mk':
            num = unicode_type(self.__footnote_count)
            self.__write_to_foot_obj.write(line)
            self.__write_to_foot_obj.write(
                'tx<nu<__________<%s\n' % num
            )
        if self.__cb_count == self.__footnote_bracket_count:
            self.__in_footnote = 0
            self.__write_obj.write(line)
            self.__write_to_foot_obj.write(
            'mi<mk<foot___clo\n')
            self.__write_to_foot_obj.write(
            'mi<tg<close_____<footnote\n')
            self.__write_to_foot_obj.write(
            'mi<mk<footnt-clo\n')
        else:
            self.__write_to_foot_obj.write(line)

    def __found_footnote(self, line):
        """ Found a footnote"""
        self.__found_a_footnote = 1
        self.__in_footnote = 1
        self.__first_line = 1
        self.__footnote_count += 1
        # temporarily set this to zero so I can enter loop
        self.__cb_count = 0
        self.__footnote_bracket_count = self.__ob_count
        self.__write_obj.write(
        'mi<mk<footnt-ind<%04d\n' % self.__footnote_count)
        self.__write_to_foot_obj.write(
        'mi<mk<footnt-ope<%04d\n' % self.__footnote_count)

    def __default_sep(self, line):
        """Handle all tokens that are not footnote tokens"""
        if self.__token_info == 'cw<nt<footnote__':
            self.__found_footnote(line)
        self.__write_obj.write(line)
        if self.__token_info == 'cw<ci<footnot-mk':
            num = unicode_type(self.__footnote_count + 1)
            self.__write_obj.write(
                'tx<nu<__________<%s\n' % num
            )

    def __initiate_sep_values(self):
        """
        initiate counters for separate_footnotes method.
        """
        self.__bracket_count=0
        self.__ob_count = 0
        self.__cb_count = 0
        self.__footnote_bracket_count = 0
        self.__in_footnote = 0
        self.__first_line = 0  # have not processed the first line of footnote
        self.__footnote_count = 0

    def separate_footnotes(self):
        """
        Separate all the footnotes in an RTF file and put them at the bottom,
        where they are easier to process.  Each time a footnote is found,
        print all of its contents to a temporary file. Close both the main and
        temporary file. Print the footnotes from the temporary file to the
        bottom of the main file.
        """
        self.__initiate_sep_values()
        self.__footnote_holder = better_mktemp()
        with open_for_read(self.__file) as read_obj:
            with open_for_write(self.__write_to) as self.__write_obj:
                with open_for_write(self.__footnote_holder) as self.__write_to_foot_obj:
                    for line in read_obj:
                        self.__token_info = line[:16]
                        # keep track of opening and closing brackets
                        if self.__token_info == 'ob<nu<open-brack':
                            self.__ob_count = line[-5:-1]
                        if self.__token_info == 'cb<nu<clos-brack':
                            self.__cb_count = line[-5:-1]
                        # In the middle of footnote text
                        if self.__in_footnote:
                            self.__in_footnote_func(line)
                        # not in the middle of footnote text
                        else:
                            self.__default_sep(line)
        with open_for_read(self.__footnote_holder) as read_obj:
            with open_for_write(self.__write_to, append=True) as write_obj:
                write_obj.write(
                    'mi<mk<sect-close\n'
                    'mi<mk<body-close\n'
                    'mi<tg<close_____<section\n'
                    'mi<tg<close_____<body\n'
                    'mi<tg<close_____<doc\n'
                    'mi<mk<footnt-beg\n')
                for line in read_obj:
                    write_obj.write(line)
                write_obj.write(
                'mi<mk<footnt-end\n')
        os.remove(self.__footnote_holder)
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "footnote_separate.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)

    def update_info(self, file, copy):
        """
        Unused method
        """
        self.__file = file
        self.__copy = copy

    def __get_foot_body_func(self, line):
        """
        Process lines in main body and look for beginning of footnotes.
        """
        # mi<mk<footnt-end
        if self.__token_info == 'mi<mk<footnt-beg':
            self.__state = 'foot'
        else:
            self.__write_obj.write(line)

    def __get_foot_foot_func(self, line):
        """
        Copy footnotes from bottom of file to a separate, temporary file.
        """
        if self.__token_info == 'mi<mk<footnt-end':
            self.__state = 'body'
        else:
            self.__write_to_foot_obj.write(line)

    def __get_footnotes(self):
        """
        Private method to remove footnotes from main file.  Read one line from
        the main file at a time. If the state is 'body', call on the private
        __get_foot_foot_func. Otherwise, call on the __get_foot_body_func.
        These two functions do the work of separating the footnotes form the
        body.
        """
        with open_for_read(self.__file) as read_obj:
            with open_for_write(self.__write_to) as self.__write_obj:
                with open_for_write(self.__footnote_holder) as self.__write_to_foot_obj:
                    for line in read_obj:
                        self.__token_info = line[:16]
                        if self.__state == 'body':
                            self.__get_foot_body_func(line)
                        elif self.__state == 'foot':
                            self.__get_foot_foot_func(line)

    def __get_foot_from_temp(self, num):
        """
        Private method for joining footnotes to body. This method reads from
        the temporary file until the proper footnote marker is found. It
        collects all the tokens until the end of the footnote, and returns
        them as a string.
        """
        look_for = 'mi<mk<footnt-ope<' + num + '\n'
        found_foot = 0
        string_to_return = ''
        for line in self.__read_from_foot_obj:
            if found_foot:
                if line == 'mi<mk<footnt-clo\n':
                    return string_to_return
                string_to_return = string_to_return + line
            else:
                if line == look_for:
                    found_foot = 1

    def __join_from_temp(self):
        """
        Private method for rejoining footnotes to body.  Read from the
        newly-created, temporary file that contains the body text but no
        footnotes. Each time a footnote marker is found, call the private
        method __get_foot_from_temp(). This method will return a string to
        print out to the third file.
        If no footnote marker is found, simply print out the token (line).
        """
        with open_for_read(self.__footnote_holder) as self.__read_from_foot_obj:
            with open_for_read(self.__write_to) as read_obj:
                with open_for_write(self.__write_to2) as self.__write_obj:
                    for line in read_obj:
                        if line[:16] == 'mi<mk<footnt-ind':
                            line = self.__get_foot_from_temp(line[17:-1])
                        self.__write_obj.write(line)

    def join_footnotes(self):
        """
        Join the footnotes from the bottom of the file and put them in their
        former places.  First, remove the footnotes from the bottom of the
        input file, outputting them to a temporary file. This creates two new
        files, one without footnotes, and one of just footnotes. Open both
        these files to read. When a marker is found in the main file, find the
        corresponding marker in the footnote file. Output the mix of body and
        footnotes to a third file.
        """
        if not self.__found_a_footnote:
            return
        self.__write_to2 = better_mktemp()
        self.__state = 'body'
        self.__get_footnotes()
        self.__join_from_temp()
        # self.__write_obj.close()
        # self.__read_from_foot_obj.close()
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to2, "footnote_joined.data")
        copy_obj.rename(self.__write_to2, self.__file)
        os.remove(self.__write_to2)
        os.remove(self.__footnote_holder)
