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


class OverrideTable:
    """
    Parse a line of text to make the override table. Return a string
    (which will convert to XML) and the dictionary containing all the
    information about the lists. This dictionary is the result of the
    dictionary that is first passed to this module. This module
    modifies the dictionary, assigning lists numbers to each list.
    """

    def __init__(
                self,
                list_of_lists,
                run_level=1,
                ):
        self.__list_of_lists = list_of_lists
        self.__initiate_values()
        self.__run_level = run_level

    def __initiate_values(self):
        self.__override_table_final = ''
        self.__state = 'default'
        self.__override_list = []
        self.__state_dict = {
            'default'       : self.__default_func,
            'override'      : self.__override_func,
            'unsure_ob'     : self.__after_bracket_func,
        }
        self.__override_dict = {
            'cw<ls<lis-tbl-id'  :       'list-table-id',
            'cw<ls<list-id___'  :       'list-id',
        }

    def __override_func(self, line):
        """
        Requires:
            line -- line to parse
        Returns:
            nothing
        Logic:
            The group {\\override has been found.
            Check for the end of the group.
            Otherwise, add appropriate tokens to the override dictionary.
        """
        if self.__token_info == 'cb<nu<clos-brack' and\
            self.__cb_count == self.__override_ob_count:
            self.__state = 'default'
            self.__parse_override_dict()
        else:
            att = self.__override_dict.get(self.__token_info)
            if att:
                value = line[20:]
                self.__override_list[-1][att] = value

    def __parse_override_dict(self):
        """
        Requires:
            nothing
        Returns:
            nothing
        Logic:
            The list of all information about RTF lists has been passed to
            this module. As of this point, this python list has no id number,
            which is needed later to identify which lists in the body should
            be assigned which formatting commands from the list-table.
            In order to get an id, I have to check to see when the list-table-id
            from the override_dict (generated in this module) matches the list-table-id
            in list_of_lists (generated in the list_table.py module). When a match is found,
            append the lists numbers to the self.__list_of_lists dictionary
            that contains the empty lists:
                [[{list-id:[HERE!],[{}]]
            This is a list, since one list in the table in the preamble of RTF can
            apply to multiple lists in the body.
        """
        override_dict = self.__override_list[-1]
        list_id = override_dict.get('list-id')
        if list_id is None and self.__level > 3:
            msg = 'This override does not appear to have a list-id\n'
            raise self.__bug_handler(msg)
        current_table_id = override_dict.get('list-table-id')
        if current_table_id is None and self.__run_level > 3:
            msg = 'This override does not appear to have a list-table-id\n'
            raise self.__bug_handler(msg)
        counter = 0
        for list in self.__list_of_lists:
            info_dict = list[0]
            old_table_id = info_dict.get('list-table-id')
            if old_table_id == current_table_id:
                self.__list_of_lists[counter][0]['list-id'].append(list_id)
                break
            counter += 1

    def __parse_lines(self, line):
        """
        Requires:
            line --ine to parse
        Returns:
            nothing
        Logic:
            Break the into tokens by splitting it on the newline.
            Call on the method according to the state.
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
        Requires:
            line -- line to parse
        Return:
            nothing
        Logic:
            Look for an open bracket and change states when found.
        """
        if self.__token_info == 'ob<nu<open-brack':
            self.__state = 'unsure_ob'

    def __after_bracket_func(self, line):
        """
        Requires:
            line -- line to parse
        Returns:
            nothing
        Logic:
            The last token was an open bracket. You need to determine
            the group based on the token after.
            WARNING: this could cause problems. If no group is found, the
            state will remain unsure_ob, which means no other text will be
            parsed. I should do states by a list and simply pop this
            unsure_ob state to get the previous state.
        """
        if self.__token_info == 'cw<ls<lis-overid':
            self.__state = 'override'
            self.__override_ob_count = self.__ob_count
            the_dict = {}
            self.__override_list.append(the_dict)
        elif self.__run_level > 3:
            msg = 'No matching token after open bracket\n'
            msg += 'token is "%s\n"' % (line)
            raise self.__bug_handler(msg)

    def __write_final_string(self):
        """
        Requires:
            line -- line to parse
        Returns:
            nothing
        Logic:
            First write out the override-table tag.
            Iteratere through the dictionaries in the main override_list.
            For each dictionary, write an empty tag "override-list". Add
            the attributes and values of the tag from the dictionary.
        """
        self.__override_table_final = 'mi<mk<over_beg_\n'
        self.__override_table_final += 'mi<tg<open______<override-table\n' + \
        'mi<mk<overbeg__\n' + self.__override_table_final
        for the_dict in self.__override_list:
            self.__override_table_final += 'mi<tg<empty-att_<override-list'
            the_keys = the_dict.keys()
            for the_key in the_keys:
                self.__override_table_final += \
                    '<%s>%s' % (the_key, the_dict[the_key])
            self.__override_table_final += '\n'
        self.__override_table_final += '\n'
        self.__override_table_final += \
        'mi<mk<overri-end\n' + 'mi<tg<close_____<override-table\n'
        self.__override_table_final += 'mi<mk<overribend_\n'

    def parse_override_table(self, line):
        """
        Requires:
            line -- line with border definition in it
        Returns:
            A string that will be converted to XML, and a dictionary of
            all the properties of the RTF lists.
        Logic:
        """
        self.__parse_lines(line)
        return self.__override_table_final, self.__list_of_lists
