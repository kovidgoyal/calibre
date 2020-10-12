
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
from . import open_for_read, open_for_write

"""
Simply write the list of strings after style table
"""


class BodyStyles:
    """
    Insert table data for tables.
    Logic:
    """

    def __init__(self,
            in_file,
            list_of_styles,
            bug_handler,
            copy=None,
            run_level=1,):
        """
        Required:
            'file'--file to parse
            'table_data' -- a dictionary for each table.
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
        self.__list_of_styles = list_of_styles
        self.__run_level = run_level
        self.__write_to = better_mktemp()
        # self.__write_to = 'table_info.data'

    def insert_info(self):
        """
        """
        read_obj = open_for_read(self.__file)
        self.__write_obj = open_for_write(self.__write_to)
        line_to_read = 1
        while line_to_read:
            line_to_read = read_obj.readline()
            line = line_to_read
            if line == 'mi<tg<close_____<style-table\n':
                if len(self.__list_of_styles) > 0:
                    self.__write_obj.write('mi<tg<open______<styles-in-body\n')
                    the_string = ''.join(self.__list_of_styles)
                    self.__write_obj.write(the_string)
                    self.__write_obj.write('mi<tg<close_____<styles-in-body\n')
                else:
                    # this shouldn't happen!
                    if self.__run_level > 3:
                        msg = 'Not enough data for each table\n'
                        raise self.__bug_handler(msg)
                    # why was this line even here?
                    # self.__write_obj.write('mi<tg<open______<table\n')
            self.__write_obj.write(line)
        read_obj.close()
        self.__write_obj.close()
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "body_styles.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
