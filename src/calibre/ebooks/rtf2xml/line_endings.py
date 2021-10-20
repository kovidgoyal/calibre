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
from calibre.utils.cleantext import clean_ascii_chars
from calibre.ptempfile import better_mktemp


class FixLineEndings:
    """Fix line endings"""

    def __init__(self,
            bug_handler,
            in_file=None,
            copy=None,
            run_level=1,
            replace_illegals=1,
            ):
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__copy = copy
        self.__run_level = run_level
        self.__write_to = better_mktemp()
        self.__replace_illegals = replace_illegals

    def fix_endings(self):
        # read
        with open(self.__file, 'rb') as read_obj:
            input_file = read_obj.read()
        # calibre go from win and mac to unix
        input_file = input_file.replace(b'\r\n', b'\n')
        input_file = input_file.replace(b'\r', b'\n')
        # remove ASCII invalid chars : 0 to 8 and 11-14 to 24-26-27
        if self.__replace_illegals:
            input_file = clean_ascii_chars(input_file)
        # write
        with open(self.__write_to, 'wb') as write_obj:
            write_obj.write(input_file)
        # copy
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "line_endings.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
