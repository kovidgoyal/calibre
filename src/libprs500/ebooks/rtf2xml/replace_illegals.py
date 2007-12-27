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
#   You should have received a copy of the GNU General Public License   #
#   along with this program; if not, write to the Free Software         #
#   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA            #
#   02111-1307 USA                                                      #
#                                                                       #
#                                                                       #
#########################################################################
import os, tempfile
from libprs500.ebooks.rtf2xml import copy
class ReplaceIllegals:
    """
    reaplace illegal lower ascii characters
    """
    def __init__(self,
            in_file,
            copy = None,
            run_level = 1,
            ):
        self.__file = in_file
        self.__copy = copy
        self.__run_level = run_level
        self.__write_to = tempfile.mktemp()
    def replace_illegals(self):
        """
        """
        nums = [0, 1, 2, 3, 4, 5, 6, 7, 8,  11,  13, 14, 15, 16, 17, 18, 19]
        read_obj = open(self.__file, 'r')
        write_obj = open(self.__write_to, 'w')
        line_to_read = 1
        while line_to_read:
            line_to_read = read_obj.readline()
            line = line_to_read
            for num in nums:
                line = line.replace(chr(num), '')
            write_obj.write(line)
        read_obj.close()
        write_obj.close()
        copy_obj = copy.Copy()
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "replace_illegals.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
