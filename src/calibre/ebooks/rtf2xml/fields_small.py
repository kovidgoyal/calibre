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

from calibre.ebooks.rtf2xml import field_strings, copy
from calibre.ptempfile import better_mktemp
from . import open_for_read, open_for_write


class FieldsSmall:
    """
=================
Purpose
=================
Write tags for bookmarks, index and toc entry fields in a tokenized file.
This module does not handle toc or index tables.  (This module won't be any
use to you unless you use it as part of the other modules.)
-----------
Method
-----------
Look for the beginning of a bookmark, index, or toc entry. When such a token
is found, store the opening bracket count in a variable. Collect all the text
until the closing bracket entry is found. Send the string to the module
field_strings to process it. Write the processed string to the output
file.
    """

    def __init__(self,
            in_file,
            bug_handler,
            copy=None,
            run_level=1,
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
        self.__bug_handler = bug_handler
        self.__copy = copy
        self.__write_to = better_mktemp()
        self.__run_level = run_level

    def __initiate_values(self):
        """
        Initiate all values.
        """
        self.__string_obj = field_strings.FieldStrings(bug_handler=self.__bug_handler)
        self.__state = 'before_body'
        self.__text_string = ''
        self.__marker = 'mi<mk<inline-fld\n'
        self.__state_dict = {
        'before_body'   : self.__before_body_func,
        'body'  : self.__body_func,
        'bookmark'  : self.__bookmark_func,
        'toc_index'       : self.__toc_index_func,
        }
        self.__body_dict = {
        'cw<an<book-mk-st'      : (self.__found_bookmark_func, 'start'),
        'cw<an<book-mk-en'      : (self.__found_bookmark_func, 'end'),
        'cw<an<toc_______'      : (self.__found_toc_index_func, 'toc'),
        'cw<an<index-mark'      : (self.__found_toc_index_func, 'index'),
        }
        ob = 'ob<nu<open-brack.....'
        cb = 'cb<nu<clos-brack'
        bk_st = 'cw<an<book-mk-st<nu<true'
        tx = 'tx<nu<__________<(.*?)'
        reg_st = ob + bk_st + tx + cb
        self.__book_start = re.compile(r'%s' % reg_st)

    def __before_body_func(self, line):
        """
        Requires:
            line --the line to parse
        Returns:
            nothing
        Logic:
            Look for the beginning of the body. When found, change the state
            to body. Always print out the line.
        """
        if self.__token_info == 'mi<mk<body-open_':
            self.__state = 'body'
        self.__write_obj.write(line)

    def __body_func(self, line):
        """
        Requires:
            line --the line to parse
        Returns:
            nothing
        Logic:
            This function handles all the lines in the body of the documents.
            Look for a bookmark, index or toc entry and take the appropriate action.
        """
        action, tag = \
           self.__body_dict.get(self.__token_info, (None, None))
        if action:
            action(line, tag)
        else:
            self.__write_obj.write(line)

    def __found_bookmark_func(self, line, tag):
        """
        Requires:
            line --the line to parse
        Returns:
            nothing
        Logic:
            This function is called when a bookmark is found. The opening
            bracket count is stored int eh beginning bracket count. The state
            is changed to 'bookmark.'
        """
        self.__beg_bracket_count = self.__ob_count
        self.__cb_count = 0
        self.__state = 'bookmark'
        self.__type_of_bookmark = tag

    def __bookmark_func(self, line):
        """
        Requires:
            line --the line to parse
        Returns:
            nothing
        Logic:
            This function handles all lines within a bookmark. It adds each
            line to a string until the end of the bookmark is found. It
            processes the string with the fields_string module, and
            prints out the result.
        """
        if self.__beg_bracket_count == self.__cb_count:
            self.__state = 'body'
            type = 'bookmark-%s'  % self.__type_of_bookmark
            # change here
            """
            my_string = self.__string_obj.process_string(
                self.__text_string, type)
            """
            my_string = self.__parse_bookmark_func(
                self.__text_string, type)
            self.__write_obj.write(self.__marker)
            self.__write_obj.write(my_string)
            self.__text_string = ''
            self.__write_obj.write(line)
        elif line[0:2] == 'tx':
            self.__text_string += line[17:-1]

    def __parse_index_func(self, my_string):
        """
        Requires:
            my_string --string to parse
            type --type of string
        Returns:
            A string for a toc instruction field.
        Logic:
            This method is meant for *both* index and toc entries.
            I want to eliminate paragraph endings, and I want to divide the
            entry into a main entry and (if it exists) a sub entry.
            Split the string by newlines. Read on token at a time. If the
            token is a special colon, end the main entry element and start the
            sub entry element.
            If the token is a pargrah ending, ignore it, since I don't won't
            paragraphs within toc or index entries.
        """
        my_string, see_string = self.__index_see_func(my_string)
        my_string, bookmark_string = self.__index_bookmark_func(my_string)
        italics, bold = self.__index__format_func(my_string)
        found_sub = 0
        my_changed_string = 'mi<tg<empty-att_<field<type>index-entry'
        my_changed_string += '<update>static'
        if see_string:
            my_changed_string += '<additional-text>%s' % see_string
        if bookmark_string:
            my_changed_string += '<bookmark>%s' % bookmark_string
        if italics:
            my_changed_string += '<italics>true'
        if bold:
            my_changed_string += '<bold>true'
        main_entry = ''
        sub_entry = ''
        lines = my_string.split('\n')
        for line in lines:
            token_info = line[:16]
            if token_info == 'cw<ml<colon_____':
                found_sub = 1
            elif token_info[0:2] == 'tx':
                if found_sub:
                    sub_entry += line[17:]
                else:
                    main_entry += line[17:]
        my_changed_string += '<main-entry>%s' % main_entry
        if found_sub:
            my_changed_string += '<sub-entry>%s' % sub_entry
        my_changed_string += '\n'
        return my_changed_string

    def __index_see_func(self, my_string):
        in_see = 0
        bracket_count = 0
        see_string = ''
        changed_string = ''
        lines = my_string.split('\n')
        end_bracket_count = sys.maxsize
        for line in lines:
            token_info = line[:16]
            if token_info == 'ob<nu<open-brack':
                bracket_count += 1
            if token_info == 'cb<nu<clos-brack':
                bracket_count -= 1
            if in_see:
                if bracket_count == end_bracket_count and token_info == 'cb<nu<clos-brack':
                    in_see = 0
                else:
                    if token_info == 'tx<nu<__________':
                        see_string += line[17:]
            else:
                if token_info == 'cw<in<index-see_':
                    end_bracket_count = bracket_count - 1
                    in_see = 1
                changed_string += '%s\n' % line
        return changed_string, see_string

    def __index_bookmark_func(self, my_string):
        """
        Requires:
            my_string -- string in all the index
        Returns:
            bookmark_string -- the text string of the book mark
            index_string -- string minus the bookmark_string
        """
        # cw<an<place_____<nu<true
        in_bookmark = 0
        bracket_count = 0
        bookmark_string = ''
        index_string = ''
        lines = my_string.split('\n')
        end_bracket_count = sys.maxsize
        for line in lines:
            token_info = line[:16]
            if token_info == 'ob<nu<open-brack':
                bracket_count += 1
            if token_info == 'cb<nu<clos-brack':
                bracket_count -= 1
            if in_bookmark:
                if bracket_count == end_bracket_count and token_info == 'cb<nu<clos-brack':
                    in_bookmark = 0
                    index_string += '%s\n' % line
                else:
                    if token_info == 'tx<nu<__________':
                        bookmark_string += line[17:]
                    else:
                        index_string += '%s\n' % line
            else:
                if token_info == 'cw<an<place_____':
                    end_bracket_count = bracket_count - 1
                    in_bookmark = 1
                index_string += '%s\n' % line
        return index_string, bookmark_string

    def __index__format_func(self, my_string):
        italics = 0
        bold =0
        lines = my_string.split('\n')
        for line in lines:
            token_info = line[:16]
            if token_info == 'cw<in<index-bold':
                bold = 1
            if token_info == 'cw<in<index-ital':
                italics = 1
        return italics, bold

    def __parse_toc_func(self, my_string):
        """
        Requires:
            my_string -- all the string in the toc
        Returns:
            modidified string
        Logic:
        """
        toc_level = 0
        toc_suppress = 0
        my_string, book_start_string, book_end_string =\
        self.__parse_bookmark_for_toc(my_string)
        main_entry = ''
        my_changed_string = 'mi<tg<empty-att_<field<type>toc-entry'
        my_changed_string += '<update>static'
        if book_start_string:
            my_changed_string += '<bookmark-start>%s' % book_start_string
        if book_end_string:
            my_changed_string += '<bookmark-end>%s' % book_end_string
        lines = my_string.split('\n')
        for line in lines:
            token_info = line[:16]
            if token_info[0:2] == 'tx':
                main_entry += line[17:]
            if token_info == 'cw<tc<toc-level_':
                toc_level = line[20:]
            if token_info == 'cw<tc<toc-sup-nu':
                toc_suppress = 1
        if toc_level:
            my_changed_string += '<toc-level>%s' % toc_level
        if toc_suppress:
            my_changed_string += '<toc-suppress-number>true'
        my_changed_string += '<main-entry>%s' % main_entry
        my_changed_string += '\n'
        return my_changed_string

    def __parse_bookmark_for_toc(self, my_string):
        """
        Requires:
            the_string --string of toc, with new lines
        Returns:
            the_string -- string minus bookmarks
            bookmark_string -- bookmarks
        Logic:
        """
        in_bookmark = 0
        bracket_count = 0
        book_start_string = ''
        book_end_string = ''
        book_type = 0
        toc_string = ''
        lines = my_string.split('\n')
        end_bracket_count = sys.maxsize
        for line in lines:
            token_info = line[:16]
            if token_info == 'ob<nu<open-brack':
                bracket_count += 1
            if token_info == 'cb<nu<clos-brack':
                bracket_count -= 1
            if in_bookmark:
                if bracket_count == end_bracket_count and token_info == 'cb<nu<clos-brack':
                    in_bookmark = 0
                    toc_string += '%s\n' % line
                else:
                    if token_info == 'tx<nu<__________':
                        if book_type == 'start':
                            book_start_string += line[17:]
                        elif book_type == 'end':
                            book_end_string += line[17:]
                    else:
                        toc_string += '%s\n' % line
            else:
                if token_info == 'cw<an<book-mk-st' or token_info =='cw<an<book-mk-en':
                    if token_info == 'cw<an<book-mk-st':
                        book_type = 'start'
                    if token_info == 'cw<an<book-mk-en':
                        book_type = 'end'
                    end_bracket_count = bracket_count - 1
                    in_bookmark = 1
                toc_string += '%s\n' % line
        return toc_string, book_start_string, book_end_string

    def __parse_bookmark_func(self, my_string, type):
        """
        Requires:
            my_string --string to parse
            type --type of string
        Returns:
            A string formatted for a field instruction.
        Logic:
            The type is the name (either bookmark-end or bookmark-start). The
            id is the complete text string.
        """
        my_changed_string = ('mi<tg<empty-att_<field<type>%s'
        '<number>%s<update>none\n' % (type, my_string))
        return my_changed_string

    def __found_toc_index_func(self, line, tag):
        """
        Requires:
            line --the line to parse
        Returns:
            nothing
        Logic:
            This function is called when a toc or index entry is found. The opening
            bracket count is stored in the beginning bracket count. The state
            is changed to 'toc_index.'
        """
        self.__beg_bracket_count = self.__ob_count
        self.__cb_count = 0
        self.__state = 'toc_index'
        self.__tag = tag

    def __toc_index_func(self, line):
        """
        Requires:
            line --the line to parse
        Returns:
            nothing
        Logic:
            This function handles all lines within a toc or index entry. It
            adds each line to a string until the end of the entry is found. It
            processes the string with the fields_string module, and
            prints out the result.
        """
        if self.__beg_bracket_count == self.__cb_count:
            self.__state = 'body'
            type = self.__tag
            if type == 'index':
                my_string = self.__parse_index_func(
                self.__text_string)
            elif type == 'toc':
                my_string = self.__parse_toc_func(
                self.__text_string)
            self.__write_obj.write(self.__marker)
            self.__write_obj.write(my_string)
            self.__text_string = ''
            self.__write_obj.write(line)
        else:
            self.__text_string += line

    def fix_fields(self):
        """
        Requires:
            nothing
        Returns:
            nothing (changes the original file)
        Logic:
            Read one line in at a time. Determine what action to take based on
            the state. If the state is before the body, look for the
            beginning of the body.
           The other two states are toc_index (for toc and index entries) and
           bookmark.
        """
        self.__initiate_values()
        with open_for_read(self.__file) as read_obj:
            with open_for_write(self.__write_to) as self.__write_obj:
                for line in read_obj:
                    self.__token_info = line[:16]
                    if self.__token_info == 'ob<nu<open-brack':
                        self.__ob_count = line[-5:-1]
                    if self.__token_info == 'cb<nu<clos-brack':
                        self.__cb_count = line[-5:-1]
                    action = self.__state_dict.get(self.__state)
                    if action is None:
                        sys.stderr.write('No matching state in module fields_small.py\n')
                        sys.stderr.write(self.__state + '\n')
                    action(line)
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "fields_small.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
