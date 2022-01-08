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


class ListTable:
    """
    Parse the list table line. Make a string. Form a dictionary.
    Return the string and the dictionary.
    """

    def __init__(
                self,
                bug_handler,
                run_level=1,
                ):
        self.__bug_handler = bug_handler
        self.__initiate_values()
        self.__run_level = run_level

    def __initiate_values(self):
        self.__list_table_final = ''
        self.__state = 'default'
        self.__final_dict = {}
        self.__list_dict = {}
        self.__all_lists = []
        self.__level_text_string = ''
        self.__level_text_list = []
        self.__found_level_text_length = 0
        self.__level_text_position = None
        self.__prefix_string = None
        self.__level_numbers_string = ''
        self.__state_dict = {
            'default'       : self.__default_func,
            'level'         : self.__level_func,
            'list'          : self.__list_func,
            'unsure_ob'     : self.__after_bracket_func,
            'level_number'  : self.__level_number_func,
            'level_text'    : self.__level_text_func,
            'list_name'     : self.__list_name_func,
        }
        self.__main_list_dict = {
            'cw<ls<ls-tem-id_'  :       'list-template-id',
            'cw<ls<list-hybri'  :       'list-hybrid',
            'cw<ls<lis-tbl-id'  :       'list-table-id',
        }
        self.__level_dict = {
            'cw<ls<level-star'  :       'list-number-start',
            'cw<ls<level-spac'  :       'list-space',
            'cw<ls<level-inde'  :       'level-indent',
            'cw<ls<fir-ln-ind'  :       'first-line-indent',
            'cw<ls<left-inden'  :       'left-indent',
            'cw<ls<tab-stop__'  :       'tabs',
            'cw<ls<level-type'  :       'numbering-type',
            'cw<pf<right-inde'  :       'right-indent',
            'cw<pf<left-inden'  :       'left-indent',
            'cw<pf<fir-ln-ind'  :       'first-line-indent',
            'cw<ci<italics___'  :       'italics',
            'cw<ci<bold______'  :       'bold',
            'cw<ss<para-style'  :       'paragraph-style-name',
        }
        """
        all_lists =
        [{anything here?}
            [{list-templateid = ""}
                [{level-indent}],[{level-indent}]
            ]
        ],
        """

    def __parse_lines(self, line):
        """
        Required : line --line to parse
        Returns:  nothing
        Logic:
            Split the lines into a list by a new line. Process the line
            according to the state.
        """
        lines = line.split('\n')
        self.__ob_count = 0
        self.__ob_group = 0
        for line in lines:
            self.__token_info = line[:16]
            if self.__token_info == 'ob<nu<open-brack':
                self.__ob_count = line[-4:]
                self.__ob_group += 1
            if self.__token_info == 'cb<nu<clos-brack':
                self.__cb_count = line[-4:]
                self.__ob_group -= 1
            action = self.__state_dict.get(self.__state)
            if action is None:
                print(self.__state)
            action(line)
        self.__write_final_string()
        # self.__add_to_final_line()

    def __default_func(self, line):
        """
        Requires: line --line to process
        Return: nothing
        Logic:
            This state is used at the start and end of a list. Look for an
            opening bracket, which marks the change of state.
        """
        if self.__token_info == 'ob<nu<open-brack':
            self.__state = 'unsure_ob'

    def __found_list_func(self, line):
        """
        Requires: line -- line to process
        Returns: nothing
        Logic:
            I have found \\list.
            Change the state to list
            Get the open bracket count so you know when this state ends.
            Append an empty list to all lists.
            Create a temporary dictionary. This dictionary has the key of
            "list-id" and the value of an empty list. Later, this empty list
            will be filled with all the ids for which the formatting is valid.
            Append the temporary dictionary to the new list.
        """
        self.__state = 'list'
        self.__list_ob_count = self.__ob_count
        self.__all_lists.append([])
        the_dict = {'list-id': []}
        self.__all_lists[-1].append(the_dict)

    def __list_func(self, line):
        """
        Requires: line --line to process
        Returns: nothing
        Logic:
            This method is called when you are in a list, but outside of a level.
            Check for the end of the list. Otherwise, use the self.__mainlist_dict
            to determine if you need to add a lines values to the main list.
        """
        if self.__token_info == 'cb<nu<clos-brack' and\
            self.__cb_count == self.__list_ob_count:
            self.__state = 'default'
        elif self.__token_info == 'ob<nu<open-brack':
            self.__state = 'unsure_ob'
        else:
            att = self.__main_list_dict.get(self.__token_info)
            if att:
                value = line[20:]
                # dictionary is always the first item in the last list
                # [{att:value}, [], [att:value, []]
                self.__all_lists[-1][0][att] = value

    def __found_level_func(self, line):
        """
        Requires: line -- line to process
        Returns: nothing
        Logic:
            I have found \\listlevel.
            Change the state to level
            Get the open bracket count so you know when this state ends.
            Append an empty list to the last list inside all lists.
            Create a temporary dictionary.
            Append the temporary dictionary to the new list.
            self.__all_lists now looks like:
                [[{list-id:[]}, [{}]]]
                Where:
                    self.__all_lists[-1] => a list. The first item is a dictionary.
                    The second item is a list containing a dictionary:
                    [{list-id:[]}, [{}]]
                    self.__all_lists[-1][0] => a dictionary of the list attributes
                    self.__all_lists[-1][-1] => a list with just a dictionary
                    self.__all_lists[-1][-1][0] => the dictionary of level attributes
        """
        self.__state = 'level'
        self.__level_ob_count = self.__ob_count
        self.__all_lists[-1].append([])
        the_dict = {}
        self.__all_lists[-1][-1].append(the_dict)
        self.__level_dict

    def __level_func(self, line):
        """
        Requires:
            line -- line to parse
        Returns:
            nothing
        Logic:
            Look for the end of the this group.
            Change states if an open bracket is found.
            Add attributes to all_dicts if an appropriate token is found.
        """
        if self.__token_info == 'cb<nu<clos-brack' and\
            self.__cb_count == self.__level_ob_count:
            self.__state = 'list'
        elif self.__token_info == 'ob<nu<open-brack':
            self.__state = 'unsure_ob'
        else:
            att = self.__level_dict.get(self.__token_info)
            if att:
                value = line[20:]
                self.__all_lists[-1][-1][0][att] = value

    def __level_number_func(self, line):
        """
        Requires:
            line -- line to process
        Returns:
            nothing
        Logic:
            Check for the end of the group.
            Otherwise, if the token is hexadecimal, create an attribute.
            Do so by finding the base-10 value of the number. Then divide
            this by 2 and round it. Remove the ".0". Sandwwhich the result to
            give you something like level1-show-level.
            The show-level attribute means the numbering for this level.
        """
        if self.__token_info == 'cb<nu<clos-brack' and\
            self.__cb_count == self.__level_number_ob_count:
            self.__state = 'level'
            self.__all_lists[-1][-1][0]['level-numbers'] = self.__level_numbers_string
            self.__level_numbers_string = ''
        elif self.__token_info == 'tx<hx<__________':
            self.__level_numbers_string += '\\&#x0027;%s' % line[18:]
        elif self.__token_info == 'tx<nu<__________':
            self.__level_numbers_string += line[17:]
            """
            num = line[18:]
            num = int(num, 16)
            level = str(round((num - 1)/2, 0))
            level = level[:-2]
            level = 'level%s-show-level' % level
            self.__all_lists[-1][-1][0][level] = 'true'
            """

    def __level_text_func(self, line):
        """
        Requires:
            line --line to process
        Returns:
            nothing
        Logic:
            Check for the end of the group.
            Otherwise, if the text is hexadecimal, call on the method
            __parse_level_text_length.
            Otherwise, if the text is regular text, create an attribute.
            This attribute indicates the puncuation after a certain level.
            An example is "level1-marker = '.'"
            Otherwise, check for a level-template-id.
        """
        if self.__token_info == 'cb<nu<clos-brack' and\
            self.__cb_count == self.__level_text_ob_count:
            if self.__prefix_string:
                if self.__all_lists[-1][-1][0]['numbering-type'] == 'bullet':
                    self.__prefix_string = self.__prefix_string.replace('_', '')
                    self.__all_lists[-1][-1][0]['bullet-type'] = self.__prefix_string
            self.__state = 'level'
            # self.__figure_level_text_func()
            self.__level_text_string = ''
            self.__found_level_text_length = 0
        elif self.__token_info == 'tx<hx<__________':
            self.__parse_level_text_length(line)
        elif self.__token_info == 'tx<nu<__________':
            text = line[17:]
            if text and text[-1] == ';':
                text = text.replace(';', '')
            if not self.__level_text_position:
                self.__prefix_string = text
            else:
                self.__all_lists[-1][-1][0][self.__level_text_position] = text
        elif self.__token_info == 'cw<ls<lv-tem-id_':
            value = line[20:]
            self.__all_lists[-1][-1][0]['level-template-id'] = value

    def __parse_level_text_length(self, line):
        """
        Requires:
            line --line with hexadecimal number
        Returns:
            nothing
        Logic:
            Method is used for to parse text in the \\leveltext group.
        """
        num = line[18:]
        the_num = int(num, 16)
        if not self.__found_level_text_length:
            self.__all_lists[-1][-1][0]['list-text-length'] = str(the_num)
            self.__found_level_text_length = 1
        else:
            the_num += 1
            the_string = str(the_num)
            level_marker = 'level%s-suffix' % the_string
            show_marker = 'show-level%s' % the_string
            self.__level_text_position = level_marker
            self.__all_lists[-1][-1][0][show_marker] = 'true'
            if self.__prefix_string:
                prefix_marker = 'level%s-prefix' % the_string
                self.__all_lists[-1][-1][0][prefix_marker] = self.__prefix_string
                self.__prefix_string = None

    def __list_name_func(self, line):
        """
        Requires:
            line --line to process
        Returns:
            nothing
        Logic:
            Simply check for the end of the group and change states.
        """
        if self.__token_info == 'cb<nu<clos-brack' and\
            self.__cb_count == self.__list_name_ob_count:
            self.__state = 'list'

    def __after_bracket_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing.
        Logic:
            The last token found was "{". This method determines what group
            you are now in.
            WARNING: this could cause problems. If no group is found, the state will remain
            unsure_ob, which means no other text will be parsed.
        """
        if self.__token_info == 'cw<ls<level-text':
            self.__state = 'level_text'
            self.__level_text_ob_count = self.__ob_count
        elif self.__token_info == 'cw<ls<level-numb':
            self.__level_number_ob_count = self.__ob_count
            self.__state = 'level_number'
        elif self.__token_info == 'cw<ls<list-tb-le':
            self.__found_level_func(line)
        elif self.__token_info == 'cw<ls<list-in-tb':
            self.__found_list_func(line)
        elif self.__token_info == 'cw<ls<list-name_':
            self.__state = 'list_name'
            self.__list_name_ob_count = self.__ob_count
        else:
            if self.__run_level > 3:
                msg = 'No matching token after open bracket\n'
                msg += 'token is "%s\n"' % (line)
                raise self.__bug_handler

    def __add_to_final_line(self):
        """
        Method no longer used.
        """
        self.__list_table_final = 'mi<mk<listabbeg_\n'
        self.__list_table_final += 'mi<tg<open______<list-table\n' + \
        'mi<mk<listab-beg\n' + self.__list_table_final
        self.__list_table_final += \
        'mi<mk<listab-end\n' + 'mi<tg<close_____<list-table\n'
        self.__list_table_final += 'mi<mk<listabend_\n'

    def __write_final_string(self):
        """
        Requires:
            nothing
        Returns:
            nothing
        Logic:
            Write out the list-table start tag.
            Iterate through self.__all_lists. For each list, write out
            a list-in-table tag. Get the dictionary of this list
            (the first item). Print out the key => value pair.
            Remove the first item (the dictionary) form this list. Now iterate
            through what is left in the list. Each list will contain one item,
            a dictionary. Get this dictionary and print out key => value pair.
        """
        not_allow = ['list-id',]
        id = 0
        self.__list_table_final = 'mi<mk<listabbeg_\n'
        self.__list_table_final += 'mi<tg<open______<list-table\n' + \
        'mi<mk<listab-beg\n' + self.__list_table_final
        for list in self.__all_lists:
            id += 1
            self.__list_table_final += 'mi<tg<open-att__<list-in-table'
            # self.__list_table_final += '<list-id>%s' % (str(id))
            the_dict = list[0]
            the_keys = the_dict.keys()
            for the_key in the_keys:
                if the_key in not_allow:
                    continue
                att = the_key
                value = the_dict[att]
                self.__list_table_final += f'<{att}>{value}'
            self.__list_table_final += '\n'
            levels = list[1:]
            level_num = 0
            for level in levels:
                level_num += 1
                self.__list_table_final += 'mi<tg<empty-att_<level-in-table'
                self.__list_table_final += '<level>%s' % (str(level_num))
                the_dict2 = level[0]
                the_keys2 = the_dict2.keys()
                is_bullet = 0
                bullet_text = ''
                for the_key2 in the_keys2:
                    if the_key2 in not_allow:
                        continue
                    test_bullet = the_dict2.get('numbering-type')
                    if test_bullet == 'bullet':
                        is_bullet = 1
                    att2 = the_key2
                    value2 = the_dict2[att2]
                    # sys.stderr.write('%s\n' % att2[0:10])
                    if att2[0:10] == 'show-level' and is_bullet:
                        # sys.stderr.write('No print %s\n' % att2)
                        pass
                    elif att2[-6:] == 'suffix' and is_bullet:
                        # sys.stderr.write('%s\n' % att2)
                        bullet_text += value2
                    elif att2[-6:] == 'prefix' and is_bullet:
                        # sys.stderr.write('%s\n' % att2)
                        bullet_text += value2
                    else:
                        self.__list_table_final += f'<{att2}>{value2}'
                if is_bullet:
                    pass
                    # self.__list_table_final += '<bullet-type>%s' % (bullet_text)
                self.__list_table_final += '\n'
            self.__list_table_final += 'mi<tg<close_____<list-in-table\n'
        self.__list_table_final += \
        'mi<mk<listab-end\n' + 'mi<tg<close_____<list-table\n'
        self.__list_table_final += 'mi<mk<listabend_\n'

    def parse_list_table(self, line):
        """
        Requires:
            line -- line with border definition in it
        Returns:
            A string and the dictionary of list-table values and attributes.
        Logic:
            Call on the __parse_lines method, which splits the text string into
            lines (which will be tokens) and processes them.
        """
        self.__parse_lines(line)
        return self.__list_table_final, self.__all_lists
