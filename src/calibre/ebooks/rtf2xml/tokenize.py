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
import os, re, tempfile
from calibre.ebooks.rtf2xml import copy
class Tokenize:
    """Tokenize RTF into one line per field. Each line will contain information useful for the rest of the script"""
    def __init__(self,
            in_file,
            bug_handler,
            copy = None,
            run_level = 1,
    ):
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__copy = copy
        self.__special_tokens = [ '_', '~', "'", '{', '}' ]
        self.__write_to = tempfile.mktemp()
    def __from_ms_to_utf8(self,match_obj):
        uni_char = int(match_obj.group(1))
        if uni_char < 0:
            uni_char +=  65536
        return   '&#x' + str('%X' % uni_char) + ';'
    def __neg_unicode_func(self, match_obj):
        neg_uni_char = int(match_obj.group(1)) * -1
        # sys.stderr.write(str( neg_uni_char))
        uni_char = neg_uni_char + 65536
        return   '&#x' + str('%X' % uni_char) + ';'
    def __sub_line_reg(self,line):
        line = line.replace("\\\\", "\\backslash ")
        line = line.replace("\\~", "\\~ ")
        line = line.replace("\\;", "\\; ")
        line = line.replace("&", "&amp;")
        line = line.replace("<", "&lt;")
        line = line.replace(">", "&gt;")
        line = line.replace("\\~", "\\~ ")
        line = line.replace("\\_", "\\_ ")
        line = line.replace("\\:", "\\: ")
        line = line.replace("\\-", "\\- ")
        # turn into a generic token to eliminate special
        # cases and make processing easier
        line = line.replace("\\{", "\\ob ")
        # turn into a generic token to eliminate special
        # cases and make processing easier
        line = line.replace("\\}", "\\cb ")
        # put a backslash in front of to eliminate special cases and
        # make processing easier
        line = line.replace("{", "\\{")
        # put a backslash in front of to eliminate special cases and
        # make processing easier
        line = line.replace("}", "\\}")
        line = re.sub(self.__utf_exp, self.__from_ms_to_utf8, line)
        # line = re.sub( self.__neg_utf_exp, self.__neg_unicode_func, line)
        line = re.sub(self.__ms_hex_exp, "\\mshex0\g<1> ", line)
        ##line = line.replace("\\backslash", "\\\\")
        # this is for older RTF
        line = re.sub(self.__par_exp, '\\par ', line)
        return line
    def __compile_expressions(self):
        self.__ms_hex_exp = re.compile(r"\\\'(..)")
        self.__utf_exp = re.compile(r"\\u(-?\d{3,6})")
        self.__splitexp = re.compile(r"(\\[\\{}]|{|}|\\[^\s\\{}&]+(?:\s)?)")
        self.__par_exp = re.compile(r'\\$')
        self.__mixed_exp = re.compile(r"(\\[a-zA-Z]+\d+)(\D+)")
        ##self.num_exp = re.compile(r"(\*|:|[a-zA-Z]+)(.*)")
    def __create_tokens(self):
        self.__compile_expressions()
        read_obj = open(self.__file, 'r')
        write_obj = open(self.__write_to, 'w')
        line_to_read = "dummy"
        while line_to_read:
            line_to_read = read_obj.readline()
            line = line_to_read
            line = line.replace("\n", "")
            line =  self.__sub_line_reg(line)
            tokens = re.split(self.__splitexp, line)
            ##print tokens
            for token in tokens:
                if token != "":
                    write_obj.write(token + "\n")
                    """
                    match_obj = re.search(self.__mixed_exp, token)
                    if match_obj != None:
                        first = match_obj.group(1)
                        second = match_obj.group(2)
                        write_obj.write(first + "\n")
                        write_obj.write(second + "\n")
                    else:
                        write_obj.write(token + "\n")
                    """
        read_obj.close()
        write_obj.close()
    def tokenize(self):
        """Main class for handling other methods. Reads in one line \
        at a time, usues method self.sub_line to make basic substitutions,\
        uses ? to process tokens"""
        self.__create_tokens()
        copy_obj = copy.Copy(bug_handler = self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "tokenize.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
