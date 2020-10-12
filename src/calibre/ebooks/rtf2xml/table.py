
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

"""
States.
1. 'not_in_table'
    1. 'cw<tb<row-def___' start a row definition
    2. 'mi<mk<in-table__' start table
2. 'in_table'
    1. 'mi<mk<pard-start', start of a row, cell
    2. 'mi<mk<not-in-tbl', end the table.
    3. 'cw<tb<row-def___' start a row definition
3. in_row_definition
    1.  'mi<mk<not-in-tbl'  :   end the row defintion. If in table, end the table.
    2.  'mi<mk<pard-start'  :   end the row defintion
        if already in the table, start a row and cell.
    3.  'cw<tb<row_______'  : end the row definition, end the row
    4.  'cw...' use another method to handle the control word
        control word might be added to dictionary.
    5.  'mi<mk<in-table__' If already in table, do nothing. Otherwise
        start the table.
4. 'in_row'
    1. 'mi<mk<pard-start', start  cell
    2. 'mi<mk<not-in-tbl'  end table,
    3. 'cw<tb<row_______'  close row,
5. 'in_cell'
    1. 'mi<mk<not-in-tbl', end table
    2. 'cw<tb<cell______', end cell
"""


class Table:
    """
    Make tables.
    Logic:
    Read one line at a time. The default state (self.__state) is
    'not_in_table'. Look for either a 'cw<tb<in-table__', or a row definition.
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
        'in_table':         self.__in_table_func,
        'in_row_def':       self.__in_row_def_func,
        'not_in_table':     self.__not_in_table_func,
        'in_cell':          self.__in_cell_func,
        'in_row':           self.__in_row_func,
        }
        self.__not_in_table_dict = {
        'cw<tb<row-def___':   self.__found_row_def_func,
        'cw<tb<in-table__': self.__start_table_func,
        'mi<mk<in-table__'  : self.__start_table_func,
        }
        # can't use this dictionary. When in row_definition, many tokens
        # require multiple definitions
        self.__in_row_definition_dict = {
        'mi<mk<not-in-tbl'  :   self.__end_row_table_func,
        'mi<mk<pard-start'  :   self.__end_row_def_func,
        }
        self.__in_row_dict = {
        'mi<mk<not-in-tbl'  :   self.__close_table,
        'mi<mk<pard-start'  :   self.__start_cell_func,
        'cw<tb<row_______'  :   self.__end_row_func,
        'cw<tb<cell______'  :   self.__empty_cell,
        }
        # set the default state
        self.__state = ['not_in_table']
        # set empty data for all tables
        self.__table_data = []
        # just in case there is no table data
        self.__row_dict = {}
        self.__cell_list = []
        self.__cell_widths = []

    def __in_table_func(self, line):
        """
        Requires:
            line -- line to parse
        Logic:
            Look for the end of the table. If found, close out the table.
            Look for  'mi<mk<pard-start', which marks the beginning of a row. Start
            a row and start a cell.
        """
        # 'cell'               :	('tb', 'cell______', self.default_func),
        if self.__token_info == 'mi<mk<not-in-tbl' or\
            self.__token_info == 'mi<mk<sect-start' or\
            self.__token_info == 'mi<mk<sect-close' or\
            self.__token_info == 'mi<mk<body-close':
            self.__close_table(line)
        elif self.__token_info == 'mi<mk<pard-start':
            self.__start_row_func(line)
            self.__start_cell_func(line)
        elif self.__token_info == 'cw<tb<row-def___':
            self.__found_row_def_func(line)
        elif self.__token_info == 'cw<tb<cell______':
            self.__start_row_func(line)
            self.__empty_cell(line)
        self.__write_obj.write(line)

    def __not_in_table_func(self, line):
        """
        Requires:
            line -- the line of text read in from document
        Returns:
            nothing
        Logic:
            The state is not in a table, so look for the two tokens that
            mark the start of a table: 'cw<tb<row-def', or 'cw<tb<in-table__'.
            If these tokens are found, use another method to start a table
            and change states. Otherwise, just output the line.
        """
        action = self.__not_in_table_dict.get(self.__token_info)
        if action:
            action(line)
        self.__write_obj.write(line)

    def __close_table(self, line):
        """
        Requires:
            line -- line to parse
        Returns:
            ?
        Logic:
            Write the end marker for the table.
            Write the end tag for the table.
            Set the state to ['not_in_table']
        """
        self.__write_obj.write('mi<mk<table-end_\n')
        self.__state = ['not_in_table']
        self.__table_data[-1]['number-of-columns'] = self.__max_number_cells_in_row
        self.__table_data[-1]['number-of-rows'] = self.__rows_in_table
        average_cells_in_row = self.__mode(self.__list_of_cells_in_row)
        self.__table_data[-1]['average-cells-per-row'] = average_cells_in_row
        average_cell_width = self.__mode(self.__cell_widths)
        self.__table_data[-1]['average-cell-width'] = average_cell_width

    def __found_row_def_func(self, line):
        """
        Requires:
            line don't need this except for consistency with other methods.
        Returns:
            nothing
        Logic:
            A row definition has been found. Collect all the data from this
            to use later in writing attributes for the table.
        """
        self.__state.append('in_row_def')
        self.__last_cell_position = 0
        self.__row_dict = {}
        self.__cell_list = []
        self.__cell_list.append({})
        self.__cell_widths = []

    def __start_table_func(self, line):
        """
        Requires:
            line -- line to parse
        Returns:
            ?
        Logic:
            Add the 'in_table' to the state list.
            Write out the table marker.
            Initialize table values (not sure about these yet)
        """
        self.__rows_in_table = 0
        self.__cells_in_table = 0
        self.__cells_in_row = 0
        self.__max_number_cells_in_row = 0
        self.__table_data.append({})
        self.__list_of_cells_in_row = []
        self.__write_obj.write('mi<mk<tabl-start\n')
        self.__state.append('in_table')

    def __end_row_table_func(self, line):
        """
        Requires:
            line --just for consistencey
        Returns:
            ?
        Logic:
            ?
        """
        self.__close_table(self, line)

    def __end_row_def_func(self, line):
        """
        Requires:
            line --just for consistency
        Returns:
            nothing
        Logic:
            change the state.
            get rid of the last {} in the cell list
            figure out the number of cells based on the self.__row_dict[widths]
            ('122, 122')
        """
        if len(self.__state) > 0:
            if self.__state[-1] == 'in_row_def':
                self.__state.pop()
        # added [{]] at the *end* of each /cell. Get rid of extra one
        self.__cell_list.pop()
        widths = self.__row_dict.get('widths')
        if widths:
            width_list = widths.split(',')
            num_cells = len(width_list)
            self.__row_dict['number-of-cells'] = num_cells

    def __in_row_def_func(self, line):
        """
        Requires:
            line --line to parse
        Returns:
            nothing
        Logic:
            In the text that defines a row. If a control word is found, handle the
            control word with another method.
            Check for states that will end this state.
            While in the row definition, certain tokens can end a row or end a table.
            If a paragrah definition (pard-start) is found, and the you are already in
            a table, start of a row.
        """
        if self.__token_info == 'cw<tb<row_______':
            # write tags
            self.__end_row_func(line)
            # change the state
            self.__end_row_def_func(line)
            self.__write_obj.write(line)
        elif line[0:2] == 'cw':
            self.__handle_row_token(line)
            self.__write_obj.write(line)
        elif self.__token_info == 'mi<mk<not-in-tbl' and 'in_table' in self.__state:
            self.__end_row_def_func(line)
            self.__close_table(line)
            self.__write_obj.write(line)
        elif self.__token_info == 'mi<mk<pard-start':
            self.__end_row_def_func(line)
            # if already in the table, start a row, then cell.
            if (self.__state) > 0 and self.__state[-1] == 'in_table':
                self.__start_row_func(line)
                self.__start_cell_func(line)
            self.__write_obj.write(line)
        elif self.__token_info == 'mi<mk<in-table__':
            self.__end_row_def_func(line)
            # if not in table, start a new table
            if len(self.__state) > 0 and self.__state[-1] != 'in_table':
                self.__start_table_func(line)
            self.__write_obj.write(line)
        else:
            self.__write_obj.write(line)

    def __handle_row_token(self, line):
        """
        Requires:
            line -- line to parse
        Returns:
            ?
        Logic:
            the tokens in the row definition contain the following information:
               1. row borders.
               2. cell borders for all cells in the row.
               3. cell postions for all cells in the row.
            Put all information about row borders into a row dictionary.
            Put all information about cell borders into into the dictionary in
            the last item in the cell list. ([{border:something, width:something},
                    {border:something, width:something}])
    cw<bd<bor-t-r-to<nu<bdr-hair__|bdr-li-wid:0.50
        """
        if line[3:5] == 'bd':
            border_obj = border_parse.BorderParse()
            the_dict = border_obj.parse_border(line)
            keys = the_dict.keys()
            # border-cell-top-hairline
            in_cell = 0
            for key in keys:
                if key[0:11] == 'border-cell':
                    in_cell = 1
            for key in keys:
                if in_cell:
                    self.__cell_list[-1][key] = the_dict[key]
                else:
                    self.__row_dict[key] = the_dict[key]
        # cw<tb<cell-posit<nu<216.00
        elif self.__token_info == 'cw<tb<cell-posit':
            self.__found_cell_position(line)
        # cw<tb<row-pos-le<nu<-5.40
        elif self.__token_info == 'cw<tb<row-pos-le':
            position = line[20:-1]
            self.__row_dict['left-row-position'] = position
        elif self.__token_info == 'cw<tb<row-header':
            self.__row_dict['header'] = 'true'

    def __start_cell_func(self, line):
        """
        Required:
            line -- the line of text
        Returns:
            nothing
        Logic:
            Append 'in_cell' for states
            If the self.__cell list containst dictionaries, get the last dictionary.
            Write value => attributes for key=> value
            pop the self.__cell_list.
            Otherwise, print out a cell tag.
        """
        self.__state.append('in_cell')
        # self.__cell_list = []
        if len(self.__cell_list) > 0:
            self.__write_obj.write('mi<tg<open-att__<cell')
            # cell_dict = self.__cell_list[-1]
            cell_dict = self.__cell_list[0]
            keys = cell_dict.keys()
            for key in keys:
                self.__write_obj.write('<%s>%s' % (key, cell_dict[key]))
            self.__write_obj.write('\n')
            # self.__cell_list.pop()
            self.__cell_list.pop(0)
            # self.__cell_list = self.__cell_list[1:]
        else:
            self.__write_obj.write('mi<tg<open______<cell\n')
        self.__cells_in_table += 1
        self.__cells_in_row += 1

    def __start_row_func(self, line):
        """
        Required:
            line -- the line of text
        Returns:
            nothing
        Logic:
            Append 'in_row' for states
            Write value => attributes for key=> value
        """
        self.__state.append('in_row')
        self.__write_obj.write('mi<tg<open-att__<row')
        keys = self.__row_dict.keys()
        for key in keys:
            self.__write_obj.write('<%s>%s' % (key, self.__row_dict[key]))
        self.__write_obj.write('\n')
        self.__cells_in_row = 0
        self.__rows_in_table += 1

    def __found_cell_position(self, line):
        """
        needs:
            line: current line
        returns:
            nothing
        logic:
           Calculate the cell width.
           If the cell is the first cell, you should add the left cell position to it.
           (This value is often negative.)
            Next, set the new last_cell_position to the current cell position.
        """
        # cw<tb<cell-posit<nu<216.00
        new_cell_position = round(float(line[20:-1]), 2)
        left_position = 0
        if self.__last_cell_position == 0:
            left_position = self.__row_dict.get('left-row-position', 0)
            left_position = float(left_position)
        width = new_cell_position - self.__last_cell_position - left_position
        # width = round(width, 2)
        width = unicode_type('%.2f' % width)
        self.__last_cell_position = new_cell_position
        widths_exists = self.__row_dict.get('widths')
        if widths_exists:
            self.__row_dict['widths'] += ', %s' % unicode_type(width)
        else:
            self.__row_dict['widths'] = unicode_type(width)
        self.__cell_list[-1]['width'] = width
        self.__cell_list.append({})
        self.__cell_widths.append(width)

    def __in_cell_func(self, line):
        """
        Required:
            line
        Returns:
            nothing
        Logic:
            In the middle of a cell.
            Look for the close of the table. If found, use the close table function to close
            the table.
            Look for the close of the cell. If found, use the close cell function to close out
            the cell.
            Otherwise, print out the line.
        """
        # cw<tb<cell______<nu<true
        # mi<mk<sect-start
        if self.__token_info == 'mi<mk<not-in-tbl' or\
            self.__token_info == 'mi<mk<sect-start' or\
            self.__token_info == 'mi<mk<sect-close' or\
            self.__token_info == 'mi<mk<body-close':
            self.__end_cell_func(line)
            self.__end_row_func(line)
            self.__close_table(line)
            self.__write_obj.write(line)
        elif self.__token_info ==  'cw<tb<cell______':
            self.__end_cell_func(line)
        else:
            self.__write_obj.write(line)

    def __end_cell_func(self, line):
        """
        Requires:
            line
        Returns:
            nothing
        Logic:
            End the cell. Print out the closing marks. Pop the self.__state.
        """
        if len(self.__state) > 1:
            if self.__state[-1] == 'in_cell':
                self.__state.pop()
        self.__write_obj.write('mi<mk<close_cell\n')
        self.__write_obj.write('mi<tg<close_____<cell\n')
        self.__write_obj.write('mi<mk<closecell_\n')

    def __in_row_func(self, line):
        if self.__token_info == 'mi<mk<not-in-tbl' or\
            self.__token_info == 'mi<mk<sect-start' or\
            self.__token_info == 'mi<mk<sect-close' or\
            self.__token_info == 'mi<mk<body-close':
            self.__end_row_func(line)
            self.__close_table(line)
            self.__write_obj.write(line)
        else:
            action = self.__in_row_dict.get(self.__token_info)
            if action:
                action(line)
            self.__write_obj.write(line)
        """
        elif self.__token_info == 'mi<mk<pard-start':
            self.__start_cell_func(line)
            self.__write_obj.write(line)
        elif self.__token_info == 'cw<tb<row_______':
            self.__end_row_func(line)
            self.__write_obj.write(line)
        else:
            self.__write_obj.write(line)
        """

    def __end_row_func(self, line):
        """
        """
        if len(self.__state) > 1 and self.__state[-1] == 'in_row':
            self.__state.pop()
            self.__write_obj.write('mi<tg<close_____<row\n')
        else:
            self.__write_obj.write('mi<tg<empty_____<row\n')
            self.__rows_in_table += 1
        if self.__cells_in_row > self.__max_number_cells_in_row:
            self.__max_number_cells_in_row = self.__cells_in_row
        self.__list_of_cells_in_row.append(self.__cells_in_row)

    def __empty_cell(self, line):
        """
        Required:
            line -- line of text
        Returns:
            nothing
        Logic:
            Write an empty tag with attributes if there are attributes.
            Otherwise, writen an empty tag with cell as element.
        """
        if len(self.__cell_list) > 0:
            self.__write_obj.write('mi<tg<empty-att_<cell')
            cell_dict = self.__cell_list[-1]
            keys = cell_dict.keys()
            for key in keys:
                self.__write_obj.write('<%s>%s' % (key, cell_dict[key]))
            self.__write_obj.write('\n')
        else:
            self.__write_obj.write('mi<tg<empty_____<cell\n')
        self.__cells_in_table += 1
        self.__cells_in_row += 1

    def __mode(self, the_list):
        """
        Required:
            the_list -- a list of something
        Returns:
            the number that occurs the most
        Logic:
            get the count of each item in list. The count that is the greatest
            is the mode.
        """
        max = 0
        mode = 'not-defined'
        for item in the_list:
            num_of_values = the_list.count(item)
            if num_of_values > max:
                mode = item
                max = num_of_values
        return mode

    def make_table(self):
        """
        Requires:
            nothing
        Returns:
            A dictionary of values for the beginning of the table.
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
            action = self.__state_dict.get(self.__state[-1])
            # print self.__state[-1]
            if action is None:
                sys.stderr.write('No matching state in module table.py\n')
                sys.stderr.write(self.__state[-1] + '\n')
            action(line)
        read_obj.close()
        self.__write_obj.close()
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "table.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
        return self.__table_data
