import sys, os

from calibre.ebooks.rtf2xml import copy
from calibre.ptempfile import better_mktemp
from . import open_for_read, open_for_write

"""
States.
1. default
    1. an open bracket ends this state.
    2. Text print out text. Print out any groups_in_waiting.
    3. closed bracket. Close groups
2. after an open bracket
    1. The lack of a control word ends this state.
    2. paragraph end -- close out all tags
    3. footnote beg -- close out all tags
"""


class Inline:
    """
    Make inline tags within lists.
    Logic:
    """

    def __init__(self,
            in_file,
            bug_handler,
            copy=None,
            run_level=1,):
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
        self.__state_dict = {
            'default':              self.__default_func,
            'after_open_bracket':   self.__after_open_bracket_func,
        }
        self.__default_dict = {
            'ob<nu<open-brack':         self.__found_open_bracket_func,
            'tx<nu<__________'  :       self.__found_text_func,
            'tx<hx<__________'  :       self.__found_text_func,
            'tx<ut<__________'  :       self.__found_text_func,
            'mi<mk<inline-fld'  :       self.__found_text_func,
            'text'              :       self.__found_text_func,
            'cb<nu<clos-brack'  :       self.__close_bracket_func,
            'mi<mk<par-end___'  :       self.__end_para_func,
            'mi<mk<footnt-ope'  :       self.__end_para_func,
            'mi<mk<footnt-ind'  :       self.__end_para_func,
        }
        self.__after_open_bracket_dict = {
            'cb<nu<clos-brack'  :       self.__close_bracket_func,
            'tx<nu<__________'  :       self.__found_text_func,
            'tx<hx<__________'  :       self.__found_text_func,
            'tx<ut<__________'  :       self.__found_text_func,
            'text'              :       self.__found_text_func,
            'mi<mk<inline-fld'  :       self.__found_text_func,
            'ob<nu<open-brack':         self.__found_open_bracket_func,
            'mi<mk<par-end___'  :       self.__end_para_func,
            'mi<mk<footnt-ope'  :       self.__end_para_func,
            'mi<mk<footnt-ind'  :       self.__end_para_func,
            'cw<fd<field_____'  :       self.__found_field_func,
        }
        self.__state = 'default'
        self.__brac_count = 0  # do I need this?
        self.__list_inline_list = []
        self.__body_inline_list = []
        self.__groups_in_waiting_list = [0]
        self.__groups_in_waiting_body = [0]
        self.__groups_in_waiting = self.__groups_in_waiting_body
        self.__place = 'non_list'
        self.__inline_list = self.__body_inline_list
        self.__in_para = 0  # not in paragraph
        self.__char_dict = {
            # character info => ci
            'annotation'    :   'annotation',
            'blue______'    :   'blue',
            'bold______'    :   'bold',
            'caps______'    :   'caps',
            'char-style'    :   'character-style',
            'dbl-strike'    :   'double-strike-through',
            'emboss____'    :   'emboss',
            'engrave___'    :   'engrave',
            'font-color'    :   'font-color',
            'font-down_'    :   'subscript',
            'font-size_'    :   'font-size',
            'font-style'    :   'font-style',
            'font-up___'    :   'superscript',
            'footnot-mk'    :   'footnote-marker',
            'green_____'    :   'green',
            'hidden____'    :   'hidden',
            'italics___'    :   'italics',
            'outline___'    :   'outline',
            'red_______'    :   'red',
            'shadow____'    :   'shadow',
            'small-caps'    :   'small-caps',
            'strike-thr'    :   'strike-through',
            'subscript_'    :   'subscript',
            'superscrip'    :   'superscript',
            'underlined'    :   'underlined',
        }
        self.__caps_list = ['false']

    def __set_list_func(self, line):
        """
        Requires:
            line--line of text
        Returns:
            nothing
        Logic:
        """
        if self.__place == 'in_list':
            if self.__token_info == 'mi<mk<lst-tx-end':
                self.__place = 'not_in_list'
                self.__inline_list = self.__body_inline_list
                self.__groups_in_waiting = self.__groups_in_waiting_body
        else:
            if self.__token_info == 'mi<mk<lst-tx-beg':
                self.__place = 'in_list'
                self.__inline_list = self.__list_inline_list
                self.__groups_in_waiting = self.__groups_in_waiting_list

    def __default_func(self, line):
        """
        Requires:
            line-- line of text
        Returns:
            nothing
        Logic:
            Write if not hardline break
        """
        action = self.__default_dict.get(self.__token_info)
        if action:
            action(line)
        self.__write_obj.write(line)

    def __found_open_bracket_func(self, line):
        """
        Requires:
            line -- current line of text
        Returns:
            nothing
        Logic:
            Change the state to 'after_open_bracket'
        """
        self.__state = 'after_open_bracket'
        self.__brac_count += 1
        self.__groups_in_waiting[0] += 1
        self.__inline_list.append({})
        self.__inline_list[-1]['contains_inline'] = 0

    def __after_open_bracket_func(self, line):
        """
        Requires:
            line --line of text
        Returns:
            nothing
        Logic:
            If the token is a control word for character info (cw<ci), use another
            method to add to the dictionary.
            Use the dictionary to get the appropriate function.
            Always print out the line.
        """
        if line[0:5] == 'cw<ci':  # calibre: bug in original function no diff between cw<ci and cw<pf
            self.__handle_control_word(line)
        else:
            action = self.__after_open_bracket_dict.get(self.__token_info)
            if action:
                self.__state = 'default'  # a non control word?
                action(line)
        self.__write_obj.write(line)

    def __handle_control_word(self, line):
        """
        Required:
            line --line of text
        Returns:
            nothing
        Logic:
            Handle the control word for inline groups.
            Add each name - value to a dictionary.
            If the font style of Symbol, Wingdings, or Dingbats is found,
            always mark this. I need this later to convert the text to
            the right utf.
        """
        # cw<ci<shadow_____<nu<true
        # self.__char_dict = {
        char_info = line[6:16]
        char_value = line[20:-1]
        name = self.__char_dict.get(char_info)
        if name:
            self.__inline_list[-1]['contains_inline'] = 1
            self.__inline_list[-1][name] = char_value
            """
            if name == 'font-style':
                if char_value == 'Symbol':
                    self.__write_obj.write('mi<mk<font-symbo\n')
                elif char_value == 'Wingdings':
                    self.__write_obj.write('mi<mk<font-wingd\n')
                elif char_value == 'Zapf Dingbats':
                    self.__write_obj.write('mi<mk<font-dingb\n')
            """

    def __close_bracket_func(self, line):
        """
        Requires:
            line --line of text
        Returns:
            Nothing
        Logic:
            If there are no inline groups, do nothing.
            Get the keys of the last dictionary in the inline_groups.
            If 'contains_inline' in the keys, write a close tag.
            If the_dict contains font information, write a mk tag.
        """
        if len(self.__inline_list) == 0:
            # nothing to add
            return
        the_dict = self.__inline_list[-1]
        the_keys = the_dict.keys()
        # always close out
        if self.__place == 'in_list':
            if 'contains_inline' in the_keys and the_dict['contains_inline'] == 1\
                and self.__groups_in_waiting[0] == 0:
                self.__write_obj.write('mi<tg<close_____<inline\n')
                if 'font-style' in the_keys:
                    self.__write_obj.write('mi<mk<font-end__\n')
                if 'caps' in the_keys:
                    self.__write_obj.write('mi<mk<caps-end__\n')
        else:
            # close out only if in a paragraph
            if 'contains_inline' in the_keys and the_dict['contains_inline'] == 1\
                and self.__in_para and self.__groups_in_waiting[0] == 0:
                self.__write_obj.write('mi<tg<close_____<inline\n')
                if 'font-style' in the_keys:
                    self.__write_obj.write('mi<mk<font-end__\n')
                if 'caps' in the_keys:
                    self.__write_obj.write('mi<mk<caps-end__\n')
        self.__inline_list.pop()
        if self.__groups_in_waiting[0] != 0:
            self.__groups_in_waiting[0] -= 1

    def __found_text_func(self, line):
        """
        Required:
            line--line of text
        Return:
            nothing
        Logic:
            Three cases:
            1. in a list. Simply write inline
            2. Not in a list
                Text can mark the start of a paragraph.
                If already in a paragraph, check to see if any groups are waiting
                to be added. If so, use another method to write these groups.
        """
        if self.__place == 'in_list':
            self.__write_inline()
        else:
            if not self.__in_para:
                self.__in_para = 1
                self.__start_para_func(line)
            elif self.__groups_in_waiting[0] != 0:
                self.__write_inline()

    def __write_inline(self):
        """
        Required:
            nothing
        Returns
            Nothing
        Logic:
            Method for writing inline when text is found.
            Only write those groups that are "waiting", or that have no
            tags yet.
            First, slice the list self.__inline list to get just the groups
            in waiting.
            Iterate through this slice, which contains only dictionaries.
            Get the keys in each dictionary. If 'font-style' is in the keys,
            write a marker tag. (I will use this marker tag later when converting
            hext text to utf8.)
            Write a tag for the inline values.
        """
        if self.__groups_in_waiting[0] != 0:
            last_index = -1 * self.__groups_in_waiting[0]
            inline_list = self.__inline_list[last_index:]
            if len(inline_list) <= 0:
                if self.__run_level > 3:
                    msg = 'self.__inline_list is %s\n' % self.__inline_list
                    raise self.__bug_handler(msg)
                self.__write_obj.write('error\n')
                self.__groups_in_waiting[0] = 0
                return
            for the_dict in inline_list:
                if the_dict['contains_inline']:
                    the_keys = the_dict.keys()
                    if 'font-style' in the_keys:
                        face = the_dict['font-style']
                        self.__write_obj.write('mi<mk<font______<%s\n' % face)
                    if 'caps' in the_keys:
                        value = the_dict['caps']
                        self.__write_obj.write('mi<mk<caps______<%s\n' % value)
                    self.__write_obj.write('mi<tg<open-att__<inline')
                    for the_key in the_keys:
                        if the_key != 'contains_inline':
                            self.__write_obj.write(f'<{the_key}>{the_dict[the_key]}')
                    self.__write_obj.write('\n')
        self.__groups_in_waiting[0] = 0

    def __end_para_func(self, line):
        """
        Requires:
            line -- line of text
        Returns:
            nothing
        Logic:
            Slice from the end the groups in waiting.
            Iterate through the list. If the dictionary contaings info, write
            a closing tag.
        """
        if not self.__in_para:
            return
        if self.__groups_in_waiting[0] == 0:
            inline_list = self.__inline_list
        else:
            last_index = -1 * self.__groups_in_waiting[0]
            inline_list = self.__inline_list[0:last_index]
        for the_dict in inline_list:
            contains_info = the_dict.get('contains_inline')
            if contains_info:
                the_keys = the_dict.keys()
                if 'font-style' in the_keys:
                    self.__write_obj.write('mi<mk<font-end__\n')
                if 'caps' in the_keys:
                    self.__write_obj.write('mi<mk<caps-end__\n')
                self.__write_obj.write('mi<tg<close_____<inline\n')
        self.__in_para = 0

    def __start_para_func(self, line):
        """
        Requires:
            line -- line of text
        Returns:
            nothing
        Logic:
            Iterate through the self.__inline_list to get each dict.
            If the dict containst inline info, get the keys.
            Iterate through the keys and print out the key and value.
        """
        for the_dict in self.__inline_list:
            contains_info = the_dict.get('contains_inline')
            if contains_info :
                the_keys = the_dict.keys()
                if 'font-style' in the_keys:
                    face = the_dict['font-style']
                    self.__write_obj.write('mi<mk<font______<%s\n' % face)
                if 'caps' in the_keys:
                    value = the_dict['caps']
                    self.__write_obj.write('mi<mk<caps______<%s\n' % value)
                self.__write_obj.write('mi<tg<open-att__<inline')
                for the_key in the_keys:
                    if the_key != 'contains_inline':
                        self.__write_obj.write(f'<{the_key}>{the_dict[the_key]}')
                self.__write_obj.write('\n')
        self.__groups_in_waiting[0] = 0

    def __found_field_func(self, line):
        """
        Just a default function to make sure I don't prematurely exit
        default state
        """
        pass

    def form_tags(self):
        """
        Requires:
            area--area to parse (list or non-list)
        Returns:
            nothing
        Logic:
            Read one line in at a time. Determine what action to take based on
            the state.
        """
        self.__initiate_values()
        with open_for_read(self.__file) as read_obj:
            with open_for_write(self.__write_to) as self.__write_obj:
                for line in read_obj:
                    token = line[0:-1]
                    self.__token_info = ''
                    if token == 'tx<mc<__________<rdblquote'\
                        or token == 'tx<mc<__________<ldblquote'\
                        or token == 'tx<mc<__________<lquote'\
                        or token == 'tx<mc<__________<rquote'\
                        or token == 'tx<mc<__________<emdash'\
                        or token == 'tx<mc<__________<endash'\
                        or token == 'tx<mc<__________<bullet':
                        self.__token_info = 'text'
                    else:
                        self.__token_info = line[:16]
                    self.__set_list_func(line)
                    action = self.__state_dict.get(self.__state)
                    if action is None:
                        sys.stderr.write('No matching state in module inline.py\n')
                        sys.stderr.write(self.__state + '\n')
                    action(line)
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "inline.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
