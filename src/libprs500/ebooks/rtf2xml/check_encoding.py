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
                sys.stderr.write('line: %s char: %s\n' %  (line_num, char_position))
                sys.stderr.write(str(msg) + '\n')
    def check_encoding(self, path, encoding='us-ascii'):
        read_obj = open(path, 'r')
        line_to_read = 1
        line_num = 0
        while line_to_read:
            line_num += 1
            line_to_read = read_obj.readline()
            line = line_to_read
            try:
                line.decode(encoding)
            except UnicodeError:
                self.__get_position_error(line, encoding, line_num)
if __name__ == '__main__':
    check_encoding_obj = CheckEncoding()
    check_encoding_obj.check_encoding(sys.argv[1])
