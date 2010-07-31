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
import os, tempfile, re
from calibre.ebooks.rtf2xml import copy
class FixLineEndings:
    """Fix line endings"""
    def __init__(self,
            bug_handler,
            in_file = None,
            copy = None,
            #run_level = 1, calibre why keep it?
            replace_illegals = 1,
            ):
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__copy = copy
        self.__write_to = tempfile.mktemp()
        self.__replace_illegals = replace_illegals
    def fix_endings(self):
        illegal_regx = re.compile( '\x00|\x01|\x02|\x03|\x04|\x05|\x06|\x07|\x08|\x0B|\x0E|\x0F|\x10|\x11|\x12|\x13')
        # always check since I have to get rid of illegal characters
        #read
        read_obj = open(self.__file, 'r')
        input_file = read_obj.read()
        read_obj.close()
        #calibre go from win and mac to unix
        input_file = input_file.replace ('\r\n', '\n')
        input_file = input_file.replace ('\r', '\n')
        if self.__replace_illegals:
            input_file = re.sub(illegal_regx, '', input_file)
        #write
        write_obj = open(self.__write_to, 'wb')
        write_obj.write(input_file)
        write_obj.close()
        #copy
        copy_obj = copy.Copy(bug_handler = self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "line_endings.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
