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
class DefaultEncoding:
    """
    Find the default encoding for the doc
    """
    def __init__(self, in_file, bug_handler, run_level = 1,):
        """
        Required:
            'file'
        Returns:
            nothing
            """
        self.__file = in_file
        self.__bug_handler = bug_handler
    def find_default_encoding(self):
        platform = 'Windows'
        default_num = 'not-defined'
        code_page = 'ansicpg1252'
        read_obj = open(self.__file, 'r')
        line_to_read = 1
        while line_to_read:
            line_to_read = read_obj.readline()
            line = line_to_read
            self.__token_info = line[:16]
            if self.__token_info == 'mi<mk<rtfhed-end':
                break
            if self.__token_info == 'cw<ri<ansi-codpg':
                #cw<ri<ansi-codpg<nu<10000
                num = line[20:-1]
                if not num:
                    num = '1252'
                code_page = 'ansicpg' + num
            if self.__token_info == 'cw<ri<macintosh_':
                platform = 'Macintosh'
            if self.__token_info == 'cw<ri<deflt-font':
                default_num = line[20:-1]
                #cw<ri<deflt-font<nu<0
            #action = self.__state_dict.get(self.__state)
            #if action == None:
                #print self.__state
            #action(line)
        read_obj.close()
        if platform == 'Macintosh':
            code_page = 'mac_roman'
        return platform, code_page, default_num
