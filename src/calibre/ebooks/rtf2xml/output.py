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
# , codecs

class Output:
    """
    Output file
    """
    def __init__(self,
            file,
            orig_file,
            output_dir = None,
            out_file = None,
            no_ask = True
            ):
        """
        Required:
            'file' -- xml file ready to output
            orig_file -- original rtf file
        Optional:
            output_file -- the file to output to
        Returns:
            nothing
            """
        self.__file = file
        self.__orig_file = orig_file
        self.__output_dir = output_dir
        self.__no_ask = no_ask
        self.__out_file = out_file

    def output(self):
        """
        Required:
            nothing
        Returns:
            nothing
        Logic:
            output the line to the screen if no output file given. Otherwise, output to
            the file.
        """
        if self.__output_dir:
            self.__output_to_dir_func()
        elif self.__out_file:
            self.__output_to_file_func()
            # self.__output_xml(self.__file, self.__out_file)
        else:
            self.__output_to_standard_func()

    def __output_to_dir_func(self):
        """
        Requires:
            nothing
        Returns:
            nothing
        Logic:
            Create a file within the output directory.
            Read one file at a time. Output line to the newly-created file.
        """
        base_name = os.path.basename(self.__orig_file)
        base_name, ext  = os.path.splitext(base_name)
        output_file = os.path.join(self.__output_dir, '%s.xml' % base_name)
        # change if user wants to output to a specific file
        if self.__out_file:
            output_file = os.path.join(self.__output_dir, self.__out_file)
        user_response = 'o'
        if os.path.isfile(output_file) and not self.__no_ask:
            msg = 'Do you want to overwrite %s?\n' % output_file
            msg += ('Type "o" to overwrite.\n'
                    'Type any other key to print to standard output.\n')
            sys.stderr.write(msg)
            user_response = raw_input()
        if user_response == 'o':
            with open(self.__file, 'r') as read_obj:
                with open(self.output_file, 'w') as write_obj:
                    for line in read_obj:
                        write_obj.write(line)
        else:
            self.__output_to_standard_func()

    def __output_to_file_func(self):
        """
        Required:
            nothing
        Returns:
            nothing
        Logic:
            read one line at a time. Output to standard
        """
        with open(self.__file, 'r') as read_obj:
            with open(self.__out_file, 'w') as write_obj:
                for line in read_obj:
                    write_obj.write(line)

    def __output_to_standard_func(self):
        """
        Required:
            nothing
        Returns:
            nothing
        Logic:
            read one line at a time. Output to standard
        """
        with open(self.__file, 'r') as read_obj:
            for line in read_obj:
                sys.stdout.write(line)

    # def __output_xml(self, in_file, out_file):
        # """
        # output the ill-formed xml file
        # """
        # (utf8_encode, utf8_decode, utf8_reader, utf8_writer) = codecs.lookup("utf-8")
        # write_obj = utf8_writer(open(out_file, 'w'))
        # write_obj = open(out_file, 'w')
        # read_obj = utf8_writer(open(in_file, 'r'))
        # read_obj = open(in_file, 'r')
        # line = 1
        # while line:
            # line = read_obj.readline()
            # if isinstance(line, type(u"")):
                # line = line.encode("utf-8")
            # write_obj.write(line)
        # read_obj.close()
        # write_obj.close()
