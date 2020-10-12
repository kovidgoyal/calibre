
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
from polyglot.builtins import unicode_type

from . import open_for_read, open_for_write


class ParagraphDef:
    """
=================
Purpose
=================
Write paragraph definition tags.
States:
1. before_1st_para_def.
Before any para_def token is found. This means all the text in the preamble.
Look for the token 'cw<pf<par-def___'. This will changet the state to collect_tokens.
2. collect_tokens.
Found a paragraph_def. Need to get all tokens.
Change with start of a paragrph ('mi<mk<para-start'). State then becomes
in_paragraphs
If another paragraph definition is found, the state does not change.
But the dictionary is reset.
3. in_paragraphs
State changes when 'mi<mk<para-end__', or end of paragraph is found.
State then becomes 'self.__state = 'after_para_end'
4. after_para_end
If 'mi<mk<para-start' (the start of a paragraph) or 'mi<mk<para-end__' (the end of a paragraph--must be empty paragraph?) are found:
    state changes to 'in_paragraphs'
If 'cw<pf<par-def___' (paragraph_definition) is found:
    state changes to collect_tokens
if 'mi<mk<body-close', 'mi<mk<par-in-fld',
'cw<tb<cell______','cw<tb<row-def___','cw<tb<row_______',
'mi<mk<sect-close',   'mi<mk<header-beg',  'mi<mk<header-end'
are found. (All these tokens mark the start of a bigger element. para_def must
be closed:
    state changes to  'after_para_def'
5. after_para_def
'mi<mk<para-start'  changes state to in_paragraphs
if another paragraph_def is found, the state changes to collect_tokens.
    """

    def __init__(self,
        in_file,
        bug_handler,
        default_font,
        copy=None,
        run_level=1,):
        """
        Required:
            'file'--file to parse
            'default_font' --document default font
        Optional:
            'copy'-- whether to make a copy of result for debugging
            'temp_dir' --where to output temporary results (default is
            directory from which the script is run.)
        Returns:
            nothing
            """
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__default_font = default_font
        self.__copy = copy
        self.__run_level = run_level
        self.__write_to = better_mktemp()

    def __initiate_values(self):
        """
        Initiate all values.
        """
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
        # stylesheet = > ss
        'style-shet'    : 'stylesheet',
        'based-on__'    : 'based-on-style',
        'next-style'    : 'next-style',
        'char-style'    : 'character-style',
        # this is changed to get a nice attribute
        'para-style'    : 'name',
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
        # this line must be wrong because it duplicates an earlier one
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
        'caps______'   :       'caps',
        'dbl-strike'   : 'double-strike-through',
        'emboss____'    : 'emboss',
        'engrave___'    : 'engrave',
        'subscript_'    : 'subscript',
        'superscrip'    : 'superscipt',
        'font-style'    : 'font-style',
        'font-color'    : 'font-color',
        'font-size_'    : 'font-size',
        'font-up___'    : 'superscript',
        'font-down_'    : 'subscript',
        'red_______'    : 'red',
        'blue______'    : 'blue',
        'green_____'    : 'green',
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
        self.__border_obj = border_parse.BorderParse()
        self.__style_num_strings = []
        self.__body_style_strings = []
        self.__state = 'before_1st_para_def'
        self.__att_val_dict = {}
        self.__start_marker =  'mi<mk<pard-start\n'  # outside para tags
        self.__start2_marker = 'mi<mk<pardstart_\n'  # inside para tags
        self.__end2_marker =   'mi<mk<pardend___\n'  # inside para tags
        self.__end_marker =    'mi<mk<pard-end__\n'  # outside para tags
        self.__text_string = ''
        self.__state_dict = {
        'before_1st_para_def'   : self.__before_1st_para_def_func,
        'collect_tokens'        : self.__collect_tokens_func,
        'after_para_def'        : self.__after_para_def_func,
        'in_paragraphs'         : self.__in_paragraphs_func,
        'after_para_end'        : self.__after_para_end_func,
        }
        self.__collect_tokens_dict = {
        'mi<mk<para-start'  :  self.__end_para_def_func,
        'cw<pf<par-def___'  :  self.__para_def_in_para_def_func,
        'cw<tb<cell______'  : self.__empty_table_element_func,
        'cw<tb<row_______'  : self.__empty_table_element_func,
        }
        self.__after_para_def_dict = {
        'mi<mk<para-start'  :   self.__start_para_after_def_func,
        'cw<pf<par-def___'  :   self.__found_para_def_func,
        'cw<tb<cell______'  :   self.__empty_table_element_func,
        'cw<tb<row_______'  :   self.__empty_table_element_func,
        }
        self.__in_paragraphs_dict = {
        'mi<mk<para-end__'      : self.__found_para_end_func,
        }
        self.__after_para_end_dict = {
        'mi<mk<para-start'      : self.__continue_block_func,
        'mi<mk<para-end__'      : self.__continue_block_func,
        'cw<pf<par-def___'      : self.__new_para_def_func,
        'mi<mk<body-close'      : self.__stop_block_func,
        'mi<mk<par-in-fld'      : self.__stop_block_func,
        'cw<tb<cell______'      : self.__stop_block_func,
        'cw<tb<row-def___'      : self.__stop_block_func,
        'cw<tb<row_______'      : self.__stop_block_func,
        'mi<mk<sect-close'      : self.__stop_block_func,
        'mi<mk<sect-start'      : self.__stop_block_func,
        'mi<mk<header-beg'      : self.__stop_block_func,
        'mi<mk<header-end'      : self.__stop_block_func,
        'mi<mk<head___clo'      : self.__stop_block_func,
        'mi<mk<fldbk-end_'      : self.__stop_block_func,
        'mi<mk<lst-txbeg_'      : self.__stop_block_func,
        }

    def __before_1st_para_def_func(self, line):
        """
        Required:
            line -- line to parse
        Returns:
            nothing
        Logic:
            Look for the beginning of a paragaraph definition
        """
        # cw<pf<par-def___<nu<true
        if self.__token_info == 'cw<pf<par-def___':
            self.__found_para_def_func()
        else:
            self.__write_obj.write(line)

    def __found_para_def_func(self):
        self.__state = 'collect_tokens'
        # not exactly right--have to reset the dictionary--give it default
        # values
        self.__reset_dict()

    def __collect_tokens_func(self, line):
        """
        Required:
            line --line to parse
        Returns:
            nothing
        Logic:
            Check the collect_tokens_dict for either the beginning of a
            paragraph or a new paragraph definition. Take the actions
            according to the value in the dict.
            Otherwise, check if the token is not a control word. If it is not,
            change the state to after_para_def.
            Otherwise, check if the token is a paragraph definition word; if
            so, add it to the attributes and values dictionary.
        """
        action = self.__collect_tokens_dict.get(self.__token_info)
        if action:
            action(line)
        elif line[0:2] != 'cw':
            self.__write_obj.write(line)
            self.__state = 'after_para_def'
        elif line[0:5] == 'cw<bd':
            self.__parse_border(line)
        else:
            action = self.__tabs_dict.get(self.__token_info)
            if action:
                action(line)
            else:
                token = self.__token_dict.get(line[6:16])
                if token:
                    self.__att_val_dict[token] = line[20:-1]

    def __tab_stop_func(self, line):
        """
        """
        self.__att_val_dict['tabs'] += '%s:' % self.__tab_type
        self.__att_val_dict['tabs'] += '%s;' % line[20:-1]
        self.__tab_type = 'left'

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
        """
        leader = self.__tab_type_dict.get(self.__token_info)
        if leader is not None:
            self.__att_val_dict['tabs'] += '%s^' % leader
        else:
            if self.__run_level > 3:
                msg = 'no entry for %s\n' % self.__token_info
                raise self.__bug_handler(msg)

    def __tab_bar_func(self, line):
        """
        """
        # self.__att_val_dict['tabs-bar'] += '%s:' % line[20:-1]
        self.__att_val_dict['tabs'] += 'bar:%s;' % (line[20:-1])
        self.__tab_type = 'left'

    def __parse_border(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing (updates dictionary)
        Logic:
            Uses the border_parse module to return a dictionary of attribute
            value pairs for a border line.
        """
        border_dict = self.__border_obj.parse_border(line)
        self.__att_val_dict.update(border_dict)

    def __para_def_in_para_def_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            I have found a \\pard while I am collecting tokens. I want to reset
            the dectionary and do nothing else.
        """
        # Change this
        self.__state = 'collect_tokens'
        self.__reset_dict()

    def __end_para_def_func(self, line):
        """
        Requires:
            Nothing
        Returns:
            Nothing
        Logic:
            The previous state was collect tokens, and I have found the start
            of a paragraph. I want to outut the defintion tag; output the line
            itself (telling me of the beginning of a paragraph);change the
            state to 'in_paragraphs';
        """
        self.__write_para_def_beg()
        self.__write_obj.write(line)
        self.__state = 'in_paragraphs'

    def __start_para_after_def_func(self, line):
        """
        Requires:
            Nothing
        Returns:
            Nothing
        Logic:
            The state was is after_para_def. and I have found the start of a
            paragraph. I want to outut the defintion tag; output the line
            itself (telling me of the beginning of a paragraph);change the
            state to 'in_paragraphs'.
            (I now realize that this is absolutely identical to the function above!)
        """
        self.__write_para_def_beg()
        self.__write_obj.write(line)
        self.__state = 'in_paragraphs'

    def __after_para_def_func(self, line):
        """
        Requires:
            line -- line to parse
        Returns:
            nothing
        Logic:
            Check if the token info is the start of a paragraph. If so, call
            on the function found in the value of the dictionary.
        """
        action = self.__after_para_def_dict.get(self.__token_info)
        if self.__token_info == 'cw<pf<par-def___':
            self.__found_para_def_func()
        elif action:
            action(line)
        else:
            self.__write_obj.write(line)

    def __in_paragraphs_func(self, line):
        """
        Requires:
            line --current line
        Returns:
            nothing
        Logic:
            Look for the end of a paragraph, the start of a cell or row.
        """
        action = self.__in_paragraphs_dict.get(self.__token_info)
        if action:
            action(line)
        else:
            self.__write_obj.write(line)

    def __found_para_end_func(self,line):
        """
        Requires:
            line -- line to print out
        Returns:
            Nothing
        Logic:
            State is in paragraphs. You have found the end of a paragraph. You
            need to print out the line and change the state to after
            paragraphs.
        """
        self.__state = 'after_para_end'
        self.__write_obj.write(line)

    def __after_para_end_func(self, line):
        """
        Requires:
            line -- line to output
        Returns:
            nothing
        Logic:
            The state is after the end of a paragraph. You are collecting all
            the lines in a string and waiting to see if you need to write
            out the paragraph definition. If you find another paragraph
            definition, then you write out the old paragraph dictionary and
            print out the string. You change the state to collect tokens.
            If you find any larger block elemens, such as cell, row,
            field-block, or section, you write out the paragraph defintion and
            then the text string.
            If you find the beginning of a paragraph, then you don't need to
            write out the paragraph definition. Write out the string, and
            change the state to in paragraphs.
        """
        self.__text_string += line
        action = self.__after_para_end_dict.get(self.__token_info)
        if action:
            action(line)

    def __continue_block_func(self, line):
        """
        Requires:
            line --line to print out
        Returns:
            Nothing
        Logic:
            The state is after the end of a paragraph. You have found the
            start of a paragaph, so you don't need to print out the paragaph
            definition. Print out the string, the line, and change the state
            to in paragraphs.
        """
        self.__state = 'in_paragraphs'
        self.__write_obj.write(self.__text_string)
        self.__text_string = ''
    # found a new paragraph definition after an end of a paragraph

    def __new_para_def_func(self, line):
        """
        Requires:
            line -- line to output
        Returns:
            Nothing
        Logic:
            You have found a new paragraph defintion at the end of a
            paragraph. Output the end of the old paragraph defintion. Output
            the text string. Output the line. Change the state to collect
            tokens. (And don't forget to set the text string to ''!)
        """
        self.__write_para_def_end_func()
        self.__found_para_def_func()
    # after a paragraph and found reason to stop this block

    def __stop_block_func(self, line):
        """
        Requires:
            line --(shouldn't be here?)
        Returns:
            nothing
        Logic:
            The state is after a paragraph, and you have found a larger block
            than paragraph-definition. You want to write the end tag of the
            old defintion and reset the text string (handled by other
            methods).
        """
        self.__write_para_def_end_func()
        self.__state = 'after_para_def'

    def __write_para_def_end_func(self):
        """
        Requires:
            nothing
        Returns:
            nothing
        Logic:
            Print out the end of the pargraph definition tag, and the markers
            that let me know when I have reached this tag. (These markers are
            used for later parsing.)
        """
        self.__write_obj.write(self.__end2_marker)
        self.__write_obj.write('mi<tg<close_____<paragraph-definition\n')
        self.__write_obj.write(self.__end_marker)
        self.__write_obj.write(self.__text_string)
        self.__text_string = ''
        keys = self.__att_val_dict.keys()
        if 'font-style' in keys:
            self.__write_obj.write('mi<mk<font-end__\n')
        if 'caps' in keys:
            self.__write_obj.write('mi<mk<caps-end__\n')

    def __get_num_of_style(self):
        """
        Requires:
            nothing
        Returns:
            nothing
        Logic:
            Get a unique value for each style.
        """
        my_string = ''
        new_style = 0
        # when determining uniqueness for a style, ingorne these values, since
        # they don't tell us if the style is unique
        ignore_values = ['style-num', 'nest-level', 'in-table']
        for k in sorted(self.__att_val_dict):
            if k not in ignore_values:
                my_string += '%s:%s' % (k, self.__att_val_dict[k])
        if my_string in self.__style_num_strings:
            num = self.__style_num_strings.index(my_string)
            num += 1  # since indexing starts at zero, rather than 1
        else:
            self.__style_num_strings.append(my_string)
            num = len(self.__style_num_strings)
            new_style = 1
        num = '%04d' % num
        self.__att_val_dict['style-num'] = 's' + unicode_type(num)
        if new_style:
            self.__write_body_styles()

    def __write_body_styles(self):
        style_string = ''
        style_string += 'mi<tg<empty-att_<paragraph-style-in-body'
        style_string += '<name>%s' % self.__att_val_dict['name']
        style_string += '<style-number>%s' % self.__att_val_dict['style-num']
        tabs_list = ['tabs-left', 'tabs-right', 'tabs-decimal', 'tabs-center',
            'tabs-bar', 'tabs']
        if self.__att_val_dict['tabs'] != '':
            the_value = self.__att_val_dict['tabs']
            # the_value = the_value[:-1]
            style_string += ('<%s>%s' % ('tabs', the_value))
        exclude = frozenset(['name', 'style-num', 'in-table'] + tabs_list)
        for k in sorted(self.__att_val_dict):
            if k not in exclude:
                style_string += ('<%s>%s' % (k, self.__att_val_dict[k]))
        style_string += '\n'
        self.__body_style_strings.append(style_string)

    def __write_para_def_beg(self):
        """
        Requires:
            nothing
        Returns:
            nothing
        Logic:
            Print out the beginning of the pargraph definition tag, and the markers
            that let me know when I have reached this tag. (These markers are
            used for later parsing.)
        """
        self.__get_num_of_style()
        table = self.__att_val_dict.get('in-table')
        if table:
            # del self.__att_val_dict['in-table']
            self.__write_obj.write('mi<mk<in-table__\n')
        else:
            self.__write_obj.write('mi<mk<not-in-tbl\n')
        left_indent = self.__att_val_dict.get('left-indent')
        if left_indent:
            self.__write_obj.write('mi<mk<left_inden<%s\n' % left_indent)
        is_list =  self.__att_val_dict.get('list-id')
        if is_list:
            self.__write_obj.write('mi<mk<list-id___<%s\n' % is_list)
        else:
            self.__write_obj.write('mi<mk<no-list___\n')
        self.__write_obj.write('mi<mk<style-name<%s\n' % self.__att_val_dict['name'])
        self.__write_obj.write(self.__start_marker)
        self.__write_obj.write('mi<tg<open-att__<paragraph-definition')
        self.__write_obj.write('<name>%s' % self.__att_val_dict['name'])
        self.__write_obj.write('<style-number>%s' % self.__att_val_dict['style-num'])
        tabs_list = ['tabs-left', 'tabs-right', 'tabs-decimal', 'tabs-center',
            'tabs-bar', 'tabs']
        """
        for tab_item in tabs_list:
            if self.__att_val_dict[tab_item] != '':
                the_value = self.__att_val_dict[tab_item]
                the_value = the_value[:-1]
                self.__write_obj.write('<%s>%s' % (tab_item, the_value))
        """
        if self.__att_val_dict['tabs'] != '':
            the_value = self.__att_val_dict['tabs']
            # the_value = the_value[:-1]
            self.__write_obj.write('<%s>%s' % ('tabs', the_value))
        keys = sorted(self.__att_val_dict)
        exclude = frozenset(['name', 'style-num', 'in-table'] + tabs_list)
        for key in keys:
            if key not in exclude:
                self.__write_obj.write('<%s>%s' % (key, self.__att_val_dict[key]))
        self.__write_obj.write('\n')
        self.__write_obj.write(self.__start2_marker)
        if 'font-style' in keys:
            face = self.__att_val_dict['font-style']
            self.__write_obj.write('mi<mk<font______<%s\n' % face)
        if 'caps' in keys:
            value = self.__att_val_dict['caps']
            self.__write_obj.write('mi<mk<caps______<%s\n' % value)

    def __empty_table_element_func(self, line):
        self.__write_obj.write('mi<mk<in-table__\n')
        self.__write_obj.write(line)
        self.__state = 'after_para_def'

    def __reset_dict(self):
        """
        Requires:
            nothing
        Returns:
            nothing
        Logic:
            The dictionary containing values and attributes must be reset each
            time a new paragraphs definition is found.
        """
        self.__att_val_dict.clear()
        self.__att_val_dict['name'] = 'Normal'
        self.__att_val_dict['font-style'] = self.__default_font
        self.__tab_type = 'left'
        self.__att_val_dict['tabs-left'] = ''
        self.__att_val_dict['tabs-right'] = ''
        self.__att_val_dict['tabs-center'] = ''
        self.__att_val_dict['tabs-decimal'] = ''
        self.__att_val_dict['tabs-bar'] = ''
        self.__att_val_dict['tabs'] = ''

    def make_paragraph_def(self):
        """
        Requires:
            nothing
        Returns:
            nothing (changes the original file)
        Logic:
            Read one line in at a time. Determine what action to take based on
            the state.
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
                sys.stderr.write('no no matching state in module sections.py\n')
                sys.stderr.write(self.__state + '\n')
            action(line)
        read_obj.close()
        self.__write_obj.close()
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "paragraphs_def.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
        return self.__body_style_strings
