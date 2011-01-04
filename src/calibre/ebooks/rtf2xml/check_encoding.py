#!/usr/bin/env python
import sys
class CheckEncoding:

    def __init__(self, bug_handler):
        self.__bug_handler = bug_handler

    def __get_position_error(self, line, encoding, line_num):
        char_position = 0
        for char in line:
            char_position +=1
            try:
                char.decode(encoding)
            except UnicodeError, msg:
                sys.stderr.write(_('line: %s char: %s\n') %  (line_num, char_position))
                sys.stderr.write(str(msg) + '\n')

    def check_encoding(self, path, encoding='us-ascii'):
        line_num = 0
        with open(path, 'r') as read_obj:
            for line in read_obj:
                line_num += 1
                try:
                    line.decode(encoding)
                except UnicodeError:
                    if len(line) < 1000:
                        self.__get_position_error(line, encoding, line_num)
                    else:
                        sys.stderr.write(_('line: %d has bad encoding\n') % line_num)
                    return True
        return False

if __name__ == '__main__':
    check_encoding_obj = CheckEncoding()
    check_encoding_obj.check_encoding(sys.argv[1])
