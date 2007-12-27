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
class CheckBrackets:
    """Check that brackets match up"""
    def __init__(self, bug_handler = None, file=None):
        self.__file=file
        self.__bug_handler = bug_handler
        self.__bracket_count=0
        self.__ob_count = 0
        self.__cb_count = 0
        self.__open_bracket_num = []
    def open_brack(self, line):
        num = line[-5:-1]
        self.__open_bracket_num.append(num)
        self.__bracket_count += 1
    def close_brack(self, line):
        num = line[-5:-1]
        ##self.__open_bracket_num.append(num)
        try:
            last_num = self.__open_bracket_num.pop()
        except:
            return 0
        if num != last_num:
            return 0
        self.__bracket_count -= 1
        return 1
    def check_brackets(self):
        read_obj = open(self.__file, 'r')
        line = 'dummy'
        line_count = 0
        while line:
            line_count += 1
            line = read_obj.readline()
            self.__token_info = line[:16]
            if self.__token_info == 'ob<nu<open-brack':
                self.open_brack(line)
            if self.__token_info == 'cb<nu<clos-brack':
                right_count = self.close_brack(line)
                if not right_count:
                    return (0, "closed bracket doesn't match, line %s" % line_count)
        read_obj.close()
        if self.__bracket_count != 0:
            msg = 'At end of file open and closed brackets don\'t match\n'
            msg = msg + 'total number of brackets is %s' % self.__bracket_count
            return (0, msg)
        return (1, "brackets match!")
