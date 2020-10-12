
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
from polyglot.builtins import unicode_type

from . import open_for_read, open_for_write


class Sections:
    """
    =================
    Purpose
    =================
    Write section tags for a tokenized file. (This module won't be any use to use
    to you unless you use it as part of the other modules.)
    ---------------
    logic
    ---------------
    The tags for the first section breaks have already been written.
    RTF stores section breaks with the \\sect tag. Each time this tag is
    encountered, add one to the counter.
    When I encounter the \\sectd tag, I want to collect all the appropriate tokens
    that describe the section. When I reach a \\pard, I know I an stop collecting
    tokens and write the section tags.
    The exception to this method occurs when sections occur in field blocks, such
    as the index. Normally, two section break occur within the index and other
    field-blocks. (If less or more section breaks occur, this code may not work.)
    I want the sections to occur outside of the index. That is, the index
    should be nested inside one section tag. After the index is complete, a new
    section should begin.
    In order to write the sections outside of the field blocks, I have to store
    all of the field block as a string. When I ecounter the \\sect tag, add one to
    the section counter, but store this number in a list. Likewise, store the
    information describing the section in another list.
    When I reach the end of the field block, choose the first item from the
    numbered list as the section number. Choose the first item in the description
    list as the values and attributes of the section. Enclose the field string
    between the section tags.
    Start a new section outside the field-block strings. Use the second number in
    the list; use the second item in the description list.
    CHANGE (2004-04-26) No longer write sections that occurr in field-blocks.
    Instead, ingore all section information in a field-block.
    """

    def __init__(self,
            in_file,
            bug_handler,
            copy=None,
            run_level=1):
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
        self.__run_level = run_level
        self.__write_to = better_mktemp()

    def __initiate_values(self):
        """
        Initiate all values.
        """
        self.__mark_start = 'mi<mk<sect-start\n'
        self.__mark_end =   'mi<mk<sect-end__\n'
        self.__in_field = 0
        self.__section_values = {}
        self.__list_of_sec_values = []
        self.__field_num = []
        self.__section_num = 0
        self.__state = 'before_body'
        self.__found_first_sec = 0
        self.__text_string = ''
        self.__field_instruction_string = ''
        self.__state_dict = {
        'before_body'       : self.__before_body_func,
        'body'              : self.__body_func,
        'before_first_sec'  : self.__before_first_sec_func,
        'section'           : self.__section_func,
        'section_def'       : self.__section_def_func,
        'sec_in_field'      : self.__sec_in_field_func,
        }
        # cw<sc<sect-defin<nu<true
        self.__body_dict = {
        'cw<sc<section___'      : self.__found_section_func,
        'mi<mk<sec-fd-beg'      : self.__found_sec_in_field_func,
        'cw<sc<sect-defin'      : self.__found_section_def_bef_sec_func,
        }
        self.__section_def_dict = {
        'cw<pf<par-def___'      : (self.__end_sec_def_func, None),
        'mi<mk<body-open_'      : (self.__end_sec_def_func, None),
        'cw<tb<columns___'      : (self.__attribute_func, 'columns'),
        'cw<pa<margin-lef'      : (self.__attribute_func, 'margin-left'),
        'cw<pa<margin-rig'      : (self.__attribute_func, 'margin-right'),
        'mi<mk<header-ind'      : (self.__end_sec_def_func, None),
        # premature endings
        # __end_sec_premature_func
        'tx<nu<__________'      : (self.__end_sec_premature_func, None),
        'cw<ci<font-style'      : (self.__end_sec_premature_func, None),
        'cw<ci<font-size_'      : (self.__end_sec_premature_func, None),
        }
        self.__sec_in_field_dict = {
        'mi<mk<sec-fd-end'      : self.__end_sec_in_field_func,
        # changed this 2004-04-26
        # two lines
        # 'cw<sc<section___'      : self.__found_section_in_field_func,
        # 'cw<sc<sect-defin'      : self.__found_section_def_in_field_func,
        }

    def __found_section_def_func(self, line):
        """
        Required:
            line -- the line to parse
        Returns:
            nothing
        Logic:
            I have found a section definition. Change the state to
            setion_def (so subsequent lines will be processesed as part of
            the section definition), and clear the section_values dictionary.
        """
        self.__state = 'section_def'
        self.__section_values.clear()

    def __attribute_func(self, line, name):
        """
        Required:
            line -- the line to be parsed
            name -- the changed, readable name (as opposed to the
            abbreviated one)
        Returns:
            nothing
        Logic:
            I need to add the right data to the section values dictionary so I
            can retrive it later. The attribute (or key) is the name; the
            value is the last part of the text string.
            ex: cw<tb<columns___<nu<2
        """
        attribute = name
        value = line[20:-1]
        self.__section_values[attribute] = value

    def __found_section_func(self, line):
        """
        Requires:
            line -- the line to parse
        Returns:
            nothing
        Logic:
            I have found the beginning of a section, so change the state
            accordingly. Also add one to the section counter.
        """
        self.__state = 'section'
        self.__write_obj.write(line)
        self.__section_num += 1

    def __found_section_def_bef_sec_func(self, line):
        """
        Requires:
            line -- the line to parse
        Returns:
            nothing
        Logic:
            I have found the beginning of a section, so change the state
            accordingly. Also add one to the section counter.
        """
        self.__section_num += 1
        self.__found_section_def_func(line)
        self.__write_obj.write(line)

    def __section_func(self, line):
        """
        Requires:
            line --the line to parse
        Returns:
            nothing
        Logic:
        """
        if self.__token_info == 'cw<sc<sect-defin':
            self.__found_section_def_func(line)
        self.__write_obj.write(line)

    def __section_def_func(self, line):
        """
        Required:
            line --line to parse
        Returns:
            nothing
        Logic:
            I have found a section definition. Check if the line is the end of
            the defnition (a paragraph defintion), or if it contains info that
            should be added to the values dictionary. If neither of these
            cases are true, output the line to a file.
        """
        action, name = self.__section_def_dict.get(self.__token_info, (None, None))
        if action:
            action(line, name)
            if self.__in_field:
                self.__sec_in_field_string += line
            else:
                self.__write_obj.write(line)
        else:
            self.__write_obj.write(line)

    def __end_sec_def_func(self, line, name):
        """
        Requires:
            line --the line to parse
            name --changed, readable name
        Returns:
            nothing
        Logic:
            The end of the section definition has been found. Reset the state.
            Call on the write_section method.
        """
        if not self.__in_field:
            self.__state = 'body'
        else:
            self.__state = 'sec_in_field'
        self.__write_section(line)

    def __end_sec_premature_func(self, line, name):
        """
        Requires:
            line --the line to parse
            name --changed, readable name
        Returns:
            nothing
        Logic:
            Text or control words indicating text have been found
            before \\pard. This shoud indicate older RTF. Reset the state
            Write the section defintion. Insert a paragraph definition.
            Insert {} to mark the end of a paragraph defintion
        """
        if not self.__in_field:
            self.__state = 'body'
        else:
            self.__state = 'sec_in_field'
        self.__write_section(line)
        self.__write_obj.write('cw<pf<par-def___<nu<true\n')
        self.__write_obj.write('ob<nu<open-brack<0000\n')
        self.__write_obj.write('cb<nu<clos-brack<0000\n')

    def __write_section(self, line):
        """
        Requires:
            nothing
        Returns:
            nothing
        Logic:
            Form a string of attributes and values. If you are not in a field
            block, write this string to the output file. Otherwise, call on
            the handle_sec_def method to handle this string.
        """
        my_string = self.__mark_start
        if self.__found_first_sec:
            my_string += 'mi<tg<close_____<section\n'
        else:
            self.__found_first_sec = 1
        my_string += 'mi<tg<open-att__<section<num>%s' % unicode_type(self.__section_num)
        my_string += '<num-in-level>%s' % unicode_type(self.__section_num)
        my_string += '<type>rtf-native'
        my_string += '<level>0'
        keys = self.__section_values.keys()
        if len(keys) > 0:
            for key in keys:
                my_string += '<%s>%s' % (key, self.__section_values[key])
        my_string += '\n'
        my_string += self.__mark_end
        # # my_string += line
        if self.__state == 'body':
            self.__write_obj.write(my_string)
        elif self.__state == 'sec_in_field':
            self.__handle_sec_def(my_string)
        elif self.__run_level > 3:
            msg = 'missed a flag\n'
            raise self.__bug_handler(msg)

    def __handle_sec_def(self, my_string):
        """
        Requires:
            my_string -- the string of attributes and values. (Do I need this?)
        Returns:
            nothing
        Logic:
            I need to append the dictionary of attributes and values to list
            so I can use it later when I reach the end of the field-block.
        """
        values_dict = self.__section_values
        self.__list_of_sec_values.append(values_dict)

    def __body_func(self, line):
        """
        Requires:
            line --the line to parse
        Returns:
            nothing
        Logic:
            Look for the beginning of a section. Otherwise, print the line to
            the output file.
        """
        action = self.__body_dict.get(self.__token_info)
        if action:
            action(line)
        else:
            self.__write_obj.write(line)

    def __before_body_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            Look for the beginning of the body. Always print out the line.
        """
        if self.__token_info == 'mi<mk<body-open_':
            self.__state = 'before_first_sec'
        self.__write_obj.write(line)

    def __before_first_sec_func(self, line):
        """
        Requires:
            line -- line to parse
        Returns:
            nothing
        Logic:
            Look for the beginning of the first section. This can be \\sectd,
            but in older RTF it could mean the any paragraph or row definition
        """
        if self.__token_info == 'cw<sc<sect-defin':
            self.__state = 'section_def'
            self.__section_num += 1
            self.__section_values.clear()
        elif self.__token_info == 'cw<pf<par-def___':
            self.__state = 'body'
            self.__section_num += 1
            self.__write_obj.write(
                    'mi<tg<open-att__<section<num>%s'
                    '<num-in-level>%s'
                    '<type>rtf-native'
                    '<level>0\n'
                    % (unicode_type(self.__section_num), unicode_type(self.__section_num))
                    )
            self.__found_first_sec = 1
        elif self.__token_info == 'tx<nu<__________':
            self.__state = 'body'
            self.__section_num += 1
            self.__write_obj.write(
                    'mi<tg<open-att__<section<num>%s'
                    '<num-in-level>%s'
                    '<type>rtf-native'
                    '<level>0\n'
                    % (unicode_type(self.__section_num), unicode_type(self.__section_num))
                    )
            self.__write_obj.write(
                'cw<pf<par-def___<true\n'
                    )
            self.__found_first_sec = 1
        self.__write_obj.write(line)

    def __found_sec_in_field_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            I have found the beginning of a field that has a section (or
            really, two) inside of it. Change the state, and start adding to
            one long string.
        """
        self.__state = 'sec_in_field'
        self.__sec_in_field_string = line
        self.__in_field = 1

    def __sec_in_field_func(self, line):
        """
        Requires:
            line --the line to parse
        Returns:
            nothing
        Logic:
            Check for the end of the field, or the beginning of a section
            definition.
            CHANGED! Just print out each line. Ignore any sections or
            section definition info.
        """
        action = self.__sec_in_field_dict.get(self.__token_info)
        if action:
            action(line)
        else:
            # change this 2004-04-26
            # self.__sec_in_field_string += line
            self.__write_obj.write(line)

    def __end_sec_in_field_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            Add the last line to the field string. Call on the method
            print_field_sec_attributes to write the close and beginning of a
            section tag. Print out the field string. Call on the same method
            to again write the close and beginning of a section tag.
            Change the state.
        """
        # change this 2004-04-26
        # Don't do anyting
        """
        self.__sec_in_field_string += line
        self.__print_field_sec_attributes()
        self.__write_obj.write(self.__sec_in_field_string)
        self.__print_field_sec_attributes()
        """
        self.__state = 'body'
        self.__in_field = 0
        # this is changed too
        self.__write_obj.write(line)

    def __print_field_sec_attributes(self):
        """
        Requires:
            nothing
        Returns:
            nothing
        Logic:
            Get the number and dictionary of values from the lists. The number
            and dictionary will be the first item of each list. Write the
            close tag. Write the start tag. Write the attribute and values in
            the dictionary. Get rid of the first item in each list.
        keys = self.__section_values.keys()
        if len(keys) > 0:
            my_string += 'mi<tg<open-att__<section-definition'
            for key in keys:
                my_string += '<%s>%s' % (key, self.__section_values[key])
            my_string += '\n'
        else:
            my_string += 'mi<tg<open______<section-definition\n'
        """
        num = self.__field_num[0]
        self.__field_num = self.__field_num[1:]
        self.__write_obj.write(
        'mi<tg<close_____<section\n'
        'mi<tg<open-att__<section<num>%s' % unicode_type(num)
        )
        if self.__list_of_sec_values:
            keys =  self.__list_of_sec_values[0].keys()
            for key in keys:
                self.__write_obj.write(
                '<%s>%s\n' % (key, self.__list_of_sec_values[0][key]))
            self.__list_of_sec_values = self.__list_of_sec_values[1:]
        self.__write_obj.write('<level>0')
        self.__write_obj.write('<type>rtf-native')
        self.__write_obj.write('<num-in-level>%s' % unicode_type(self.__section_num))
        self.__write_obj.write('\n')
        # Look here

    def __found_section_in_field_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            I have found a section in a field block. Add one to section
            counter, and append this number to a list.
        """
        self.__section_num += 1
        self.__field_num.append(self.__section_num)
        self.__sec_in_field_string += line

    def __found_section_def_in_field_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            I have found a section definition in a filed block. Change the
            state and clear the values dictionary.
        """
        self.__state = 'section_def'
        self.__section_values.clear()

    def make_sections(self):
        """
        Requires:
            nothing
        Returns:
            nothing (changes the original file)
        Logic:
            Read one line in at a time. Determine what action to take based on
            the state. If the state is before the body, look for the
            beginning of the body.
            If the state is body, send the line to the body method.
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
            if action is None:
                sys.stderr.write('no matching state in module sections.py\n')
                sys.stderr.write(self.__state + '\n')
            action(line)
        read_obj.close()
        self.__write_obj.close()
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "sections.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
