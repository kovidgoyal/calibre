
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

from calibre.ebooks.rtf2xml import copy
from calibre.ptempfile import better_mktemp
from . import open_for_read, open_for_write


class DeleteInfo:
    """Delete unecessary destination groups"""

    def __init__(self,
            in_file ,
            bug_handler,
            copy=None,
            run_level=1,
            ):
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__copy = copy
        self.__write_to = better_mktemp()
        self.__run_level = run_level
        self.__initiate_allow()
        self.__bracket_count= 0
        self.__ob_count = 0
        self.__cb_count = 0
        self.__ob = 0
        self.__write_cb = False
        self.__found_delete = False

    def __initiate_allow(self):
        """
        Initiate a list of destination groups which should be printed out.
        """
        self.__allowable = ('cw<ss<char-style',
                            'cw<it<listtable_',
                            'cw<it<revi-table',
                            'cw<ls<list-lev-d',
                            # Field allowed
                            'cw<fd<field-inst',
                            'cw<an<book-mk-st',
                            'cw<an<book-mk-en',
                            'cw<an<annotation',
                            'cw<cm<comment___',
                            'cw<it<lovr-table',
                            # info table
                            'cw<di<company___',
                            # 'cw<ls<list______',
                        )
        self.__not_allowable = (
                'cw<un<unknown___',
                'cw<un<company___',
                'cw<ls<list-level',
                'cw<fd<datafield_',
                )
        self.__state = 'default'
        self.__state_dict = {
            'default'           : self.__default_func,
            'after_asterisk'    : self.__asterisk_func,
            'delete'            : self.__delete_func,
            'list'              : self.__list_func,
        }

    def __default_func(self,line):
        """Handle lines when in no special state. Look for an asterisk to
        begin a special state. Otherwise, print out line."""
        # cw<ml<asterisk__<nu<true
        if self.__token_info == 'cw<ml<asterisk__':
            self.__state = 'after_asterisk'
            self.__delete_count = self.__ob_count
        elif self.__token_info == 'ob<nu<open-brack':
            # write previous bracket, if exists
            if self.__ob:
                self.__write_obj.write(self.__ob)
            self.__ob = line
            return False
        else:
            # write previous bracket, since didn't find asterisk
            if self.__ob:
                self.__write_obj.write(self.__ob)
                self.__ob = 0
            return True

    def __delete_func(self,line):
        """Handle lines when in delete state. Don't print out lines
        unless the state has ended."""
        if self.__delete_count == self.__cb_count:
            self.__state = 'default'
            if self.__write_cb:
                self.__write_cb = True
                return True
            return False

    def __asterisk_func(self,line):
        """
        Determine whether to delete info in group
        Note on self.__cb flag.
        If you find that you are in a delete group, and the previous
        token in not an open bracket (self.__ob = 0), that means
        that the delete group is nested inside another acceptable
        detination group. In this case, you have already written
        the open bracket, so you will need to write the closed one
        as well.
        """
        # Test for {\*}, in which case don't enter
        # delete state
        self.__found_delete = True
        if self.__token_info == 'cb<nu<clos-brack':
            if self.__delete_count == self.__cb_count:
                self.__state = 'default'
                self.__ob = 0
                # changed this because haven't printed out start
                return False
            else:
                # not sure what happens here!
                # believe I have a '{\*}
                if self.__run_level > 3:
                    msg = 'Flag problem\n'
                    raise self.__bug_handler(msg)
                return True
        elif self.__token_info in self.__allowable :
            if self.__ob:
                self.__write_obj.write(self.__ob)
                self.__ob = 0
                self.__state = 'default'
            else:
                pass
            return True
        elif self.__token_info == 'cw<ls<list______':
            self.__ob = 0
            self.__found_list_func(line)
        elif self.__token_info in self.__not_allowable:
            if not self.__ob:
                self.__write_cb = True
            self.__ob = 0
            self.__state = 'delete'
            self.__cb_count = 0
            return False
        else:
            if self.__run_level > 5:
                msg = ('After an asterisk, and found neither an allowable or non-allowable token\n\
                            token is "%s"\n') % self.__token_info
                raise self.__bug_handler(msg)
            if not self.__ob:
                self.__write_cb = True
            self.__ob = 0
            self.__state = 'delete'
            self.__cb_count = 0
            return False

    def __found_list_func(self, line):
        """
        print out control words in this group
        """
        self.__state = 'list'

    def __list_func(self, line):
        """
        Check to see if the group has ended.
        Return True for all control words.
        Return False otherwise.
        """
        if self.__delete_count == self.__cb_count and \
                self.__token_info == 'cb<nu<clos-brack':
            self.__state = 'default'
            if self.__write_cb:
                self.__write_cb = False
                return True
            return False
        elif line[0:2] == 'cw':
            return True
        else:
            return False

    def delete_info(self):
        """Main method for handling other methods. Read one line at
        a time, and determine whether to print the line based on the state."""
        with open_for_read(self.__file) as read_obj:
            with open_for_write(self.__write_to) as self.__write_obj:
                for line in read_obj:
                    # ob<nu<open-brack<0001
                    self.__token_info = line[:16]
                    if self.__token_info == 'ob<nu<open-brack':
                        self.__ob_count = line[-5:-1]
                    if self.__token_info == 'cb<nu<clos-brack':
                        self.__cb_count = line[-5:-1]
                    # Get action to perform
                    action = self.__state_dict.get(self.__state)
                    if not action:
                        sys.stderr.write('No action in dictionary state is "%s" \n'
                                % self.__state)
                    # Print if allowed by action
                    if action(line):
                        self.__write_obj.write(line)
        copy_obj = copy.Copy(bug_handler=self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "delete_info.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
        return self.__found_delete
