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
import os, re,  tempfile
from libprs500.ebooks.rtf2xml import copy
class CorrectUnicode:
    """
    corrects sequences such as \u201c\'F0\'BE
    Where \'F0\'BE has to be eliminated.
    """
    def __init__(self,
            in_file,
            exception_handler,
            bug_handler,
            copy = None,
            run_level = 1,
            ):
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__copy = copy
        self.__run_level = run_level
        self.__write_to = tempfile.mktemp()
        self.__exception_handler = exception_handler
        self.__bug_handler = bug_handler
        self.__state = 'outside'
        self.__utf_exp = re.compile(r'&#x(.*?);')
    def __process_token(self, line):
        if self.__state == 'outside':
            if line[:5] == 'tx<ut':
                self.__handle_unicode(line)
            else:
                self.__write_obj.write(line)
        elif self.__state == 'after':
            if line[:5] == 'tx<hx':
                pass
            elif line[:5] == 'tx<ut':
                self.__handle_unicode(line)
            else:
                self.__state = 'outside'
                self.__write_obj.write(line)
        else:
            raise 'should\'t happen'
    def __handle_unicode(self, line):
        token = line[16:]
        match_obj = re.search(self.__utf_exp, token)
        if match_obj:
            uni_char = match_obj.group(1)
            dec_num = int(uni_char, 16)
            if dec_num > 57343 and dec_num < 63743:
                self.__state = 'outside'
            else:
                self.__write_obj.write(line)
                self.__state = 'after'
        else:
            self.__write_obj.write(line)
            self.__state = 'outside'
    def correct_unicode(self):
        """
        Requires:
            nothing
        Returns:
            nothing (changes the original file)
        Logic:
            Read one line in at a time.
        """
        read_obj = open(self.__file, 'r')
        self.__write_obj = open(self.__write_to, 'w')
        line_to_read = 1
        while line_to_read:
            line_to_read = read_obj.readline()
            line = line_to_read
            self.__token_info = line[:16]
            self.__process_token(line)
        read_obj.close()
        self.__write_obj.close()
        copy_obj = copy.Copy(bug_handler = self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "correct_unicode.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
