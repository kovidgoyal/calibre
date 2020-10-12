
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
from calibre.ebooks.rtf2xml import copy, border_parse
from calibre.ptempfile import better_mktemp
from . import open_for_read, open_for_write


class Styles:
    """
    Change lines with style numbers to actual style names.
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
        self.__border_obj = border_parse.BorderParse()
        self.__styles_dict =  {'par':{}, 'char':{}}
        self.__styles_num = '0'
        self.__type_of_style = 'par'
        self.__text_string = ''
        self.__state = 'before_styles_table'
        self.__state_dict = {
        'before_styles_table': self.__before_styles_func,
        'in_styles_table'    : self.__in_styles_func,
        'in_individual_style' : self.__in_individual_style_func,
        'after_styles_table'  : self.__after_styles_func,
        'mi<mk<styles-beg'  : self.__found_styles_table_func,
        'mi<mk<styles-end'  : self.__found_end_styles_table_func,
        'mi<mk<stylei-beg'  : self.__found_beg_ind_style_func,
        'mi<mk<stylei-end'  : self.__found_end_ind_style_func,
        'cw<ss<para-style'  : self.__para_style_func,
        'cw<ss<char-style'  : self.__char_style_func,
        }
        # A separate dictionary for parsing the body text
        self.__body_dict = {
        'cw<ss<para-style'  : (self.__para_style_in_body_func, 'par'),
        'cw<ss<char-style'  : (self.__para_style_in_body_func, 'char'),
        }
        # Dictionary needed to convert shortened style names to readable names
        self.__token_dict={
        # paragraph formatting => pf
        'par-end___'    : 'para',
        'par-def___'    : 'paragraph-definition',
        'keep-w-nex'    : 'keep-with-next',
        'widow-cntl'    : 'widow-control',
        'adjust-rgt'    : 'adjust-right',
        'language__'    : 'language',
        'right-inde'    : 'right-indent',
        'fir-ln-ind'    : 'first-line-indent',
        'left-inden'    : 'left-indent',
        'space-befo'    : 'space-before',
        'space-afte'    : 'space-after',
        'line-space'    : 'line-spacing',
        'default-ta'    : 'default-tab',
        'align_____'    : 'align',
        'widow-cntr'    : 'widow-control',
        # page fomratting mixed in! (Just in older RTF?)
        'margin-lef'    :       'left-indent',
        'margin-rig'    :       'right-indent',
        'margin-bot'    :       'space-after',
        'margin-top'    :       'space-before',
        # stylesheet = > ss
        'style-shet'    : 'stylesheet',
        'based-on__'    : 'based-on-style',
        'next-style'    : 'next-style',
        'char-style'    : 'character-style',
        'para-style'    : 'paragraph-style',
        # graphics => gr
        'picture___'    : 'pict',
        'obj-class_'    : 'obj_class',
        'mac-pic___'    : 'mac-pict',
        # section => sc
        'section___'    : 'section-new',
        'sect-defin'    : 'section-reset',
        'sect-note_'    : 'endnotes-in-section',
        # list=> ls
        'list-text_'    : 'list-text',
        'list______'    : 'list',
        'list-lev-d'    : 'list-level-definition',
        'list-cardi'    : 'list-cardinal-numbering',
        'list-decim'    : 'list-decimal-numbering',
        'list-up-al'    : 'list-uppercase-alphabetic-numbering',
        'list-up-ro'    : 'list-uppercae-roman-numbering',
        'list-ord__'    : 'list-ordinal-numbering',
        'list-ordte'    : 'list-ordinal-text-numbering',
        'list-bulli'    : 'list-bullet',
        'list-simpi'    : 'list-simple',
        'list-conti'    : 'list-continue',
        'list-hang_'    : 'list-hang',
        # 'list-tebef'    :	'list-text-before',
        # 'list-level'    : 'level',
        'list-id___'    : 'list-id',
        'list-start'    : 'list-start',
        'nest-level'    : 'nest-level',
        # duplicate
        'list-level'    : 'list-level',
        # notes => nt
        'footnote__'    : 'footnote',
        'type______'    : 'type',
        # anchor => an
        'toc_______'    : 'anchor-toc',
        'book-mk-st'    : 'bookmark-start',
        'book-mk-en'    : 'bookmark-end',
        'index-mark'    : 'anchor-index',
        'place_____'    : 'place',
        # field => fd
        'field_____'    : 'field',
        'field-inst'    : 'field-instruction',
        'field-rslt'    : 'field-result',
        'datafield_'    : 'data-field',
        # info-tables => it
        'font-table'    : 'font-table',
        'colr-table'    : 'color-table',
        'lovr-table'    : 'list-override-table',
        'listtable_'    : 'list-table',
        'revi-table'    : 'revision-table',
        # character info => ci
        'hidden____'    : 'hidden',
        'italics___'    : 'italics',
        'bold______'    : 'bold',
        'strike-thr'   : 'strike-through',
        'shadow____'   : 'shadow',
        'outline___'   : 'outline',
        'small-caps'   : 'small-caps',
        'dbl-strike'   : 'double-strike-through',
        'emboss____'    : 'emboss',
        'engrave___'    : 'engrave',
        'subscript_'    : 'subscript',
        'superscrip'    : 'superscript',
        'plain_____'    : 'plain',
        'font-style'    : 'font-style',
        'font-color'    : 'font-color',
        'font-size_'    : 'font-size',
        'font-up___'    : 'superscript',
        'font-down_'    : 'subscript',
        'red_______'    : 'red',
        'blue______'    : 'blue',
        'green_____'    : 'green',
        'caps______'    :       'caps',
        # table => tb
        'row-def___'    : 'row-definition',
        'cell______'    : 'cell',
        'row_______'    : 'row',
        'in-table__'    : 'in-table',
        'columns___'    : 'columns',
        'row-pos-le'    : 'row-position-left',
        'cell-posit'    : 'cell-position',
        # preamble => pr
        # underline
        'underlined'    : 'underlined',
        # border => bd
        'bor-t-r-hi'    : 'border-table-row-horizontal-inside',
        'bor-t-r-vi'    : 'border-table-row-vertical-inside',
        'bor-t-r-to'    : 'border-table-row-top',
        'bor-t-r-le'    : 'border-table-row-left',
        'bor-t-r-bo'    : 'border-table-row-bottom',
        'bor-t-r-ri'    : 'border-table-row-right',
        'bor-cel-bo'    : 'border-cell-bottom',
        'bor-cel-to'    : 'border-cell-top',
        'bor-cel-le'    : 'border-cell-left',
        'bor-cel-ri'    : 'border-cell-right',
        # 'bor-par-bo'    : 'border-paragraph-bottom',
        'bor-par-to'    : 'border-paragraph-top',
        'bor-par-le'    : 'border-paragraph-left',
        'bor-par-ri'    : 'border-paragraph-right',
        'bor-par-bo'    : 'border-paragraph-box',
        'bor-for-ev'    : 'border-for-every-paragraph',
        'bor-outsid'    : 'border-outisde',
        'bor-none__'    : 'border',
        # border type => bt
        'bdr-single'    : 'single',
        'bdr-doubtb'    : 'double-thickness-border',
        'bdr-shadow'    : 'shadowed-border',
        'bdr-double'    : 'double-border',
        'bdr-dotted'    : 'dotted-border',
        'bdr-dashed'    : 'dashed',
        'bdr-hair__'    : 'hairline',
        'bdr-inset_'    : 'inset',
        'bdr-das-sm'    : 'dash-small',
        'bdr-dot-sm'    : 'dot-dash',
        'bdr-dot-do'    : 'dot-dot-dash',
        'bdr-outset'    : 'outset',
        'bdr-trippl'    : 'tripple',
        'bdr-thsm__'    : 'thick-thin-small',
        'bdr-htsm__'    : 'thin-thick-small',
        'bdr-hthsm_'    : 'thin-thick-thin-small',
        'bdr-thm__'     : 'thick-thin-medium',
        'bdr-htm__'     : 'thin-thick-medium',
        'bdr-hthm_'     : 'thin-thick-thin-medium',
        'bdr-thl__'     : 'thick-thin-large',
        'bdr-hthl_'     : 'think-thick-think-large',
        'bdr-wavy_'     : 'wavy',
        'bdr-d-wav'     : 'double-wavy',
        'bdr-strip'     : 'striped',
        'bdr-embos'     : 'emboss',
        'bdr-engra'     : 'engrave',
        'bdr-frame'     : 'frame',
        'bdr-li-wid'    : 'line-width',
        # tabs
        'tab-center'  :   'center',
        'tab-right_'  :   'right',
        'tab-dec___'  :   'decimal',
        'leader-dot'  :   'leader-dot',
        'leader-hyp'  :   'leader-hyphen',
        'leader-und'  :   'leader-underline',
        }
        self.__tabs_dict = {
        'cw<pf<tab-stop__'  :   self.__tab_stop_func,
        'cw<pf<tab-center'  :   self.__tab_type_func,
        'cw<pf<tab-right_'  :   self.__tab_type_func,
        'cw<pf<tab-dec___'  :   self.__tab_type_func,
        'cw<pf<leader-dot'  :   self.__tab_leader_func,
        'cw<pf<leader-hyp'  :   self.__tab_leader_func,
        'cw<pf<leader-und'  :   self.__tab_leader_func,
        'cw<pf<tab-bar-st'  :   self.__tab_bar_func,
        }
        self.__tab_type_dict = {
        'cw<pf<tab-center'  :   'center',
        'cw<pf<tab-right_'  :   'right',
        'cw<pf<tab-dec___'  :   'decimal',
        'cw<pf<leader-dot'  :   'leader-dot',
        'cw<pf<leader-hyp'  :   'leader-hyphen',
        'cw<pf<leader-und'  :   'leader-underline',
        }
        self.__ignore_list = [
        'list-tebef',
            ]
        self.__tabs_list = self.__tabs_dict.keys()
        self.__tab_type = 'left'
        self.__leader_found = 0

    def __in_individual_style_func(self, line):
        """
        Required:
            line
        Returns:
            nothing
        Logic:
            Check if the token marks the end of the individual style. (Action
            is the value of the state dictionary, and the only key that will
            match in this function is the end of the individual style.)
            If the end of the individual style is not found, check if the line
            is a control word. If it is, extract the relelvant info and look
            up this info in the tokens dictionary. I want to change
            abbreviated names for longer, more readable ones.
            Write an error message if no key is found for the info.
            If the line is text, add the text to a text string. The text
            string will be the name of the style.
            """
        action = self.__state_dict.get(self.__token_info)
        if action:
            action(line)
        # have to parse border lines with external module
        elif line[0:5] == 'cw<bd':
            border_dict = self.__border_obj.parse_border(line)
            keys = border_dict.keys()
            for key in keys:
                self.__enter_dict_entry(key, border_dict[key])
        elif self.__token_info in self.__tabs_list:
            action = self.__tabs_dict.get(self.__token_info)
            if action is not None:
                action(line)
        elif line[0:2] == 'cw':
            # cw<pf<widow-cntl<nu<true
            info = line[6:16]
            att = self.__token_dict.get(info)
            if att is None :
                if info not in self.__ignore_list:
                    if self.__run_level > 3:
                        msg = 'no value for key %s\n' % info
                        raise self.__bug_handler(msg)
            else:
                value = line[20:-1]
                self.__enter_dict_entry(att, value)
        elif line[0:2] == 'tx':
            self.__text_string += line[17:-1]

    def __tab_stop_func(self, line):
        """
        Requires:
            line -- line to parse
        Returns:
            nothing
        Logic:
            Try to add the number to dictionary entry tabs-left, or tabs-right, etc.
            If the dictionary entry doesn't exist, create one.
        """
        try:
            if self.__leader_found:
                self.__styles_dict['par'][self.__styles_num]['tabs']\
                += '%s:' % self.__tab_type
                self.__styles_dict['par'][self.__styles_num]['tabs']\
                += '%s;' % line[20:-1]
            else:
                self.__styles_dict['par'][self.__styles_num]['tabs']\
                += '%s:' % self.__tab_type
                self.__styles_dict['par'][self.__styles_num]['tabs']\
                += '%s;' % line[20:-1]
        except KeyError:
            self.__enter_dict_entry('tabs', '')
            self.__styles_dict['par'][self.__styles_num]['tabs']\
                += '%s:' % self.__tab_type
            self.__styles_dict['par'][self.__styles_num]['tabs'] += '%s;' % line[20:-1]
        self.__tab_type = 'left'
        self.__leader_found = 0

    def __tab_type_func(self, line):
        """
        """
        type = self.__tab_type_dict.get(self.__token_info)
        if type is not None:
            self.__tab_type = type
        else:
            if self.__run_level > 3:
                msg = 'no entry for %s\n' % self.__token_info
                raise self.__bug_handler(msg)

    def __tab_leader_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            Try to add the string of the tab leader to dictionary entry
            tabs-left, or tabs-right, etc.  If the dictionary entry doesn't
            exist, create one.
        """
        self.__leader_found = 1
        leader = self.__tab_type_dict.get(self.__token_info)
        if leader is not None:
            leader += '^'
            try:
                self.__styles_dict['par'][self.__styles_num]['tabs'] += ':%s;' % leader
            except KeyError:
                self.__enter_dict_entry('tabs', '')
                self.__styles_dict['par'][self.__styles_num]['tabs'] += '%s;' % leader
        else:
            if self.__run_level > 3:
                msg = 'no entry for %s\n' % self.__token_info
                raise self.__bug_handler(msg)

    def __tab_bar_func(self, line):
        """
        Requires:
            line -- line to parse
        Returns:
            nothing
        Logic:
            Try to add the string of the tab bar to dictionary entry tabs-bar.
            If the dictionary entry doesn't exist, create one.
        """
        # self.__add_dict_entry('tabs-bar', line[20:-1])
        try:
            self.__styles_dict['par'][self.__styles_num]['tabs']\
            += '%s:' % 'bar'
            self.__styles_dict['par'][self.__styles_num]['tabs']\
            += '%s;' % line[20:-1]
        except KeyError:
            self.__enter_dict_entry('tabs', '')
            self.__styles_dict['par'][self.__styles_num]['tabs']\
            += '%s:' % 'bar'
            self.__styles_dict['par'][self.__styles_num]['tabs']\
            += '%s;' % line[20:-1]
        self.__tab_type = 'left'

    def __enter_dict_entry(self, att, value):
        """
        Required:
            att -- the attribute
            value -- the value
        Returns:
            nothing
        Logic:
            Try to add the attribute value directly to the styles dictionary.
            If a keyerror is found, that means I have to build the "branches"
            of the dictionary before I can add the key value pair.
        """
        try:
            self.__styles_dict[self.__type_of_style][self.__styles_num][att] = value
        except KeyError:
            self.__add_dict_entry(att, value)

    def __add_dict_entry(self, att, value):
        """
        Required:
            att --the attribute
            value --the value
        Returns:
            nothing
        Logic:
            I have to build the branches of the dictionary before I can add
            the leaves. (I am comparing a dictionary to a tree.) To achieve
            this, I first make a temporary dictionary by extracting either the
            inside dictionary of the keyword par or char. This temporary
            dictionary is called type_dict.
            Next, create a second, smaller dictionary with just the attribute and value.
            Add the small dictionary to the type dictionary.
            Add this type dictionary to the main styles dictionary.
        """
        if self.__type_of_style == 'par':
            type_dict =self.__styles_dict['par']
        elif self.__type_of_style == 'char':
            type_dict = self.__styles_dict['char']
        else:
            if self.__run_level > 3:
                msg = self.__type_of_style + 'error\n'
                raise self.__bug_handler(msg)
        smallest_dict = {}
        smallest_dict[att] = value
        type_dict[self.__styles_num] = smallest_dict
        self.__styles_dict[self.__type_of_style] = type_dict

    def __para_style_func(self, line):
        """
        Required:
            line
        Returns:
            nothing
        Logic:
            Set the type of style to paragraph.
            Extract the number for a line such as "cw<ss<para-style<nu<15".
        """
        self.__type_of_style = 'par'
        self.__styles_num = line[20:-1]
        """
        self.__enter_dict_entry('tabs-left', '')
        self.__enter_dict_entry('tabs-right', '')
        self.__enter_dict_entry('tabs-center', '')
        self.__enter_dict_entry('tabs-decimal', '')
        self.__enter_dict_entry('tabs-bar', '')
        """

    def __char_style_func(self, line):
        """
        Required:
            line
        Returns:
            nothing
        Logic:
            Set the type of style to character.
            Extract the number for a line such as "cw<ss<char-style<nu<15".
        """
        self.__type_of_style = 'char'
        self.__styles_num = line[20:-1]

    def __found_beg_ind_style_func(self, line):
        """
        Required:
            line
        Returns:
            nothing
        Logic:
            Get rid of the last semicolon in the text string. Add the text
            string as the value with 'name' as the key in the style
            dictionary.
        """
        self.__state = 'in_individual_style'

    def __found_end_ind_style_func(self, line):
        name = self.__text_string[:-1]  # get rid of semicolon
        # add 2005-04-29
        # get rid of space before or after
        name = name.strip()
        self.__enter_dict_entry('name', name)
        self.__text_string = ''

    def __found_end_styles_table_func(self, line):
        """
        Required:
            line
        Returns:
            nothing
        Logic:
            Set the state to after the styles table.
            Fix the styles. (I explain this below.)
            Print out the style table.
        """
        self.__state = 'after_styles_table'
        self.__fix_based_on()
        self.__print_style_table()

    def __fix_based_on(self):
        """
        Requires:
            nothing
        Returns:
            nothing
        Logic:
            The styles dictionary may contain a pair of key values such as
            'next-style' => '15'. I want to change the 15 to the name of the
            style. I accomplish this by simply looking up the value of 15 in
            the styles table.
            Use two loops. First, check all the paragraph styles. Then check
            all the characer styles.
            The inner loop: first check 'next-style', then check 'based-on-style'.
            Make sure values exist for the keys to avoid the nasty keyerror message.
        """
        types = ['par', 'char']
        for type in types:
            keys = self.__styles_dict[type].keys()
            for key in keys:
                styles = ['next-style', 'based-on-style']
                for style in styles:
                    value = self.__styles_dict[type][key].get(style)
                    if value is not None:
                        temp_dict = self.__styles_dict[type].get(value)
                        if temp_dict:
                            changed_value = self.__styles_dict[type][value].get('name')
                            if changed_value:
                                self.__styles_dict[type][key][style] = \
                                changed_value
                        else:
                            if value == 0 or value == '0':
                                pass
                            else:
                                if self.__run_level > 4:
                                    msg = '%s %s is based on %s\n' % (type, key, value)
                                    msg = 'There is no style with %s\n' % value
                                    raise self.__bug_handler(msg)
                            del self.__styles_dict[type][key][style]

    def __print_style_table(self):
        """
        Required:
            nothing
        Returns:
            nothing
        Logic:
            This function prints out the style table.
            I use three nested for loops. The outer loop prints out the
            paragraphs styles, then the character styles.
            The next loop iterates through the style numbers.
            The most inside loop iterates over the pairs of attributes and
            values, and prints them out.
        """
        types = ['par', 'char']
        for type in types:
            if type == 'par':
                prefix = 'paragraph'
            else:
                prefix = 'character'
            self.__write_obj.write(
            'mi<tg<open______<%s-styles\n' % prefix
            )
            style_numbers = self.__styles_dict[type].keys()
            for num in style_numbers:
                self.__write_obj.write(
                'mi<tg<empty-att_<%s-style-in-table<num>%s' % (prefix, num)
                )
                attributes = self.__styles_dict[type][num].keys()
                for att in attributes:
                    this_value = self.__styles_dict[type][num][att]
                    self.__write_obj.write(
                        '<%s>%s' % (att, this_value)
                        )
                self.__write_obj.write('\n')
            self.__write_obj.write(
            'mi<tg<close_____<%s-styles\n' % prefix
            )

    def __found_styles_table_func(self, line):
        """
        Required:
            line
        Returns:
            nothing
        Logic:
            Change the state to in the style table when the marker has been found.
        """
        self.__state = 'in_styles_table'

    def __before_styles_func(self, line):
        """
        Required:
            line
        Returns:
            nothing.
        Logic:
            Check the line info in the state dictionary. When the beginning of
            the styles table is found, change the state to in the styles
            table.
        """
        action = self.__state_dict.get(self.__token_info)
        if not action:
            self.__write_obj.write(line)
        else:
            action(line)

    def __in_styles_func(self, line):
        """
        Required:
            line
        Returns:
            nothing
        Logic:
            Check the line for the beginning of an individaul style. If it is
            not found, simply print out the line.
        """
        action = self.__state_dict.get(self.__token_info)
        if action is None:
            self.__write_obj.write(line)
        else:
            action(line)

    def __para_style_in_body_func(self, line, type):
        """
        Required:
            line-- the line
            type -- whether a character or paragraph
        Returns:
            nothing
        Logic:
            Determine the prefix by whether the type is "par" or "char".
            Extract the number from a line such as "cw<ss<para-style<nu<15".
            Look up that number in the styles dictionary and put a name for a number
        """
        if type == 'par':
            prefix = 'para'
        else:
            prefix = 'char'
        num = line[20:-1]
        # may be invalid RTF--a style down below not defined above!
        try:
            value = self.__styles_dict[type][num]['name']
        except KeyError:
            value = None
        if value:
            self.__write_obj.write(
            'cw<ss<%s-style<nu<%s\n' % (prefix, value)
            )
        else:
            self.__write_obj.write(
            'cw<ss<%s_style<nu<not-defined\n' % prefix
            )

    def __after_styles_func(self, line):
        """
        Required:
            line
        Returns:
            nothing
        Logic:
            Determine if a line with either character of paragraph style info
            has been found. If so, then use the appropriate method to parse
            the line. Otherwise, write the line to a file.
        """
        action, type = self.__body_dict.get(self.__token_info, (None, None))
        if action:
            action(line, type)
        else:
            self.__write_obj.write(line)

    def convert_styles(self):
        """
        Requires:
            nothing
        Returns:
            nothing (changes the original file)
        Logic:
            Read one line in at a time. Determine what action to take based on
            the state. If the state is before the style table, look for the
            beginning of the style table.
            If the state is in the style table, create the style dictionary
            and print out the tags.
            If the state if afer the style table, look for lines with style
            info, and substitute the number with the name of the style.
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
                sys.stderr.write('no matching state in module styles.py\n')
                sys.stderr.write(self.__state + '\n')
            action(line)
        read_obj.close()
        self.__write_obj.close()
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "styles.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
