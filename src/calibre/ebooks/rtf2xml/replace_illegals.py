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
from . import open_for_read, open_for_write


class ReplaceIllegals:
    """
    reaplace illegal lower ascii characters
    """

    def __init__(self,
            in_file,
            copy=None,
            run_level=1,
            ):
        self.__file = in_file
        self.__copy = copy
        self.__run_level = run_level
        self.__write_to = better_mktemp()

    def replace_illegals(self):
        """
        """
        with open_for_read(self.__file) as read_obj:
            with open_for_write(self.__write_to) as write_obj:
                for line in read_obj:
                    write_obj.write(clean_ascii_chars(line))
        copy_obj = copy.Copy()
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "replace_illegals.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
