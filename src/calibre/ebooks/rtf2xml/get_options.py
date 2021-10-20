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
"""
Gets options for main part of script
"""
import sys, os
from calibre.ebooks.rtf2xml import options_trem, configure_txt


class GetOptions:

    def __init__(self,
            system_arguments,
            rtf_dir,
            bug_handler,
            configuration_file=None,
            ):
        self.__system_arguments = system_arguments
        self.__rtf_dir = rtf_dir
        self.__configuration_file = configuration_file
        self.__bug_handler = bug_handler

    def get_options(self):
        """
        return valid, output, help, show_warnings, debug, file
        """
        return_options = self.__get_config_options()
        options_dict = {
                        'dir'               :       [1],
                        'help'              :       [0, 'h'],
                        'show-warnings'     :       [0],
                        'caps'              :       [0,],
                        'no-caps'           :       [0],
                        'symbol'            :       [0],
                        'no-symbol'         :       [0],
                        'windings'          :       [0],
                        'no-wingdings'      :       [0],
                        'zapf'              :       [0],
                        'no-zapf'           :       [0],
                        'font'              :       [0],
                        'no-font'           :       [0],
                        'dtd'               :       [1],
                        'no-dtd'            :       [0],
                        'version'           :       [0],
                        'output'            :       [1, 'o'],
                        'no-namespace'      :       [0],
                        'level'             :       [1],
                        'indent'            :       [1],
                        'no-lists'          :       [0],
                        'lists'             :       [0],
                        'group-styles'      :       [0],
                        'no-group-styles'   :       [0],
                        'group-borders'      :       [0],
                        'no-group-borders'   :       [0],
                        'headings-to-sections'  :   [0],
                        'no-headings-to-sections'   :   [0],
                        'empty-para'  :       [0],
                        'no-empty-para' :      [0],
                        'format'            :       [1, 'f'],
                        'config'            :       [0],
                }
        options_obj = options_trem.ParseOptions(
                        system_string=self.__system_arguments,
                        options_dict=options_dict
                    )
        options, arguments = options_obj.parse_options()
        if options == 0:
            return_options['valid'] = 0
            return return_options
        the_keys = options.keys()
        return_options['help'] = 0
        if 'help' in the_keys:
            return_options['help'] = 1
            return return_options
        return_options['config'] = 0
        if 'config' in the_keys:
            return_options['config'] = 1
            return return_options
        return_options['version'] = 0
        if 'version' in the_keys:
            return_options['version'] = 1
            return return_options
        # unused
        return_options['out-dir'] = 0
        if 'dir' in the_keys:
            out_dir = options['dir']
            if not os.path.isdir(out_dir):
                sys.stderr.write('Your output must be an existing directory.\n')
                return_options['valid'] = 0
            else:
                return_options['dir'] = options['dir']
        return_options['out-file'] = 0
        if 'output' in the_keys:
            # out_file = options['output']
            return_options['out-file'] = options['output']
        else:
            pass
            """
            sys.stderr.write(
                'You must provide an output file with the \'o\' option\n')
            return_options['valid'] = 0
            """
        if 'level' in the_keys:
            return_options['level'] = options['level']
        the_level = return_options.get('level')
        if the_level:
            try:
                return_options['level'] = int(the_level)
            except ValueError:
                sys.stderr.write('The options "--level" must be a number.\n')
                return_options['valid'] = 0
                return return_options
        if 'dtd' in the_keys:
            # dtd = options['dtd']
            return_options['raw-dtd-path'] = options['dtd']
        acceptable = ['sdoc', 'raw', 'tei']
        if 'format' in the_keys:
            format = options['format']
            if format not in acceptable:
                sys.stderr.write('--format must take either \'sdoc\' or '
                        '\'tei\'\n')
                return_options['valid'] = 0
                return return_options
            else:
                return_options['format'] = options['format']
        # a hack! python chokes on external dtd
        # Was able to fix this
        # format = return_options.get('format')
        # if format != 'raw' and format != None:
            # return_options['raw-dtd-path'] = ''
        return_options['show-warnings'] = 0
        if 'show-warnings' in the_keys:
            return_options['show-warnings'] = 1
        if 'no-font' in the_keys:
            return_options['convert-symbol'] = 0
            return_options['convert-zapf'] = 0
            return_options['convert-wingdings'] = 0
        if 'font' in the_keys:
            return_options['convert-symbol'] = 1
            return_options['convert-zapf'] = 1
            return_options['convert-wingdings'] = 1
        if 'symbol' in the_keys:
            return_options['convert-symbol'] = 1
        if 'no-symbol' in the_keys:
            return_options['convert-symbol'] = 0
        if 'wingdings' in the_keys:
            return_options['convert-wingdings'] = 1
        if 'no-wingdings' in the_keys:
            return_options['convert-wingdings'] = 0
        if 'zapf' in the_keys:
            return_options['convert-zapf'] = 1
        if 'no-zapf' in the_keys:
            return_options['convert-zapf'] = 0
        if 'caps' in the_keys:
            return_options['convert-caps'] = 1
        if 'no-caps' in the_keys:
            return_options['convert-caps'] = 0
        if 'no-dtd' in the_keys:
            return_options['no-dtd'] = 1
        else:
            return_options['no-dtd'] = 0
        return_options['no-ask'] = 0
        if 'no-ask' in the_keys:
            return_options['no-ask'] = 1
            sys.stderr.write('You can also permanetly set the no-ask option in the rtf2xml file.\n')
        if 'no-namespace' in the_keys:
            return_options['no-namespace'] = 1
        if 'headings-to-sections' in the_keys:
            return_options['headings-to-sections'] = 1
        elif 'no-headings-to-sections' in the_keys:
            return_options['headings-to-sections'] = 0
        if 'no-lists' in the_keys:
            return_options['form-lists'] = 0
        elif 'lists' in the_keys:
            return_options['form-lists'] = 1
        if 'group-styles' in the_keys:
            return_options['group-styles'] = 1
        elif 'no-group-styles' in the_keys:
            return_options['group-styles'] = 0
        if 'group-borders' in the_keys:
            return_options['group-borders'] = 1
        elif 'no-group-borders' in the_keys:
            return_options['group-borders'] = 0
        if 'empty-para' in the_keys:
            return_options['empty-paragraphs'] = 1
        elif 'no-empty-para' in the_keys:
            return_options['empty-paragraphs'] = 0
        if len(arguments) == 0:
            sys.stderr.write(
                'You must provide a file to convert.\n')
            return_options['valid'] = 0
            return return_options
        elif len(arguments) > 1:
            sys.stderr.write(
                'You can only convert one file at a time.\n')
            return_options['valid'] = 0
        else:
            return_options['in-file'] = arguments[0]
        # check for out file
        smart_output = return_options.get('smart-output')
        if smart_output == 'false':
            smart_output = 0
        if smart_output and not return_options['out-file']:
            in_file = return_options['in-file']
            the_file_name, ext = os.path.splitext(in_file)
            if ext != '.rtf':
                sys.stderr.write(
                    'Sorry, but this file does not have an "rtf" extension, so \n'
                    'the script will not attempt to convert it.\n'
                    'If it is in fact an rtf file, use the "-o" option.\n'
                        )
                return_options['valid'] = 0
            else:
                return_options['out-file'] = '%s.xml' % the_file_name
        if not smart_output and not return_options['out-file']:
            """
            sys.stderr.write(
                'Please provide and file to output with the -o option.\n'
                'Or set \'<smart-output value = "true"/>\'.\n'
                'in the configuration file.\n'
                )
            return_options['valid'] = 0
            """
            pass
        if 'indent' in the_keys:
            try:
                value = int(options['indent'])
                return_options['indent'] = value
            except ValueError:
                sys.stderr.write('--indent must take an integer')
                return_options['valid'] = 0
        # check for format and pyxml
        """
        the_format = return_options.get('format')
        if the_format != 'raw':
            no_pyxml = return_options.get('no-pyxml')
            if no_pyxml:
                sys.stderr.write('You want to convert your file to "%s".\n'
                        'Sorry, but you must have pyxml installed\n'
                        'in order to convert your document to anything but raw XML.\n'
                        'Please do not use the --format option.\n\n'
                        % the_format
                    )
                return_options['valid'] = 0
            xslt_proc = return_options.get('xslt-processor')
            if xslt_proc == None and not no_pyxml:
                sys.stderr.write('You want to convert your file to "%s".\n'
                        'Sorry, but you must have an xslt processor set up\n'
                        'in order to conevert your document to anything but raw XML.\n'
                        'Please use --format raw.\n\n'
                        % the_format
                        )
                return_options['valid'] = 0
        """
        return return_options

    def __get_config_options(self):
        configure_obj = configure_txt.Configure(
            bug_handler=self.__bug_handler,
            configuration_file=self.__configuration_file)
        options_dict = configure_obj.get_configuration(type='normal')
        if options_dict == 1:
            sys.exit(1)
        options_dict['valid'] = 1
        convert_caps = options_dict.get('convert-caps')
        if convert_caps == 'false':
            options_dict['convert-caps'] = 0
        convert_symbol = options_dict.get('convert-symbol')
        if convert_symbol == 'false':
            options_dict['convert-symbol'] = 0
        convert_wingdings = options_dict.get('convert-wingdings')
        if convert_wingdings == 'false':
            options_dict['convert-wingdings'] = 0
        convert_zapf = options_dict.get('convert-zapf-dingbats')
        if convert_zapf == 'false':
            options_dict['convert-zapf'] = 0
        elif convert_zapf == 'true':
            options_dict['convert-zapf'] = 1
        headings_to_sections = options_dict.get('headings-to-sections')
        if headings_to_sections == 'true':
            options_dict['headings-to-sections'] = 1
        elif headings_to_sections == '1':
            options_dict['headings-to-sections'] = 1
        elif headings_to_sections == 'false':
            options_dict['headings-to-sections'] = 0
        elif headings_to_sections == '0':
            options_dict['headings-to-sections'] = 0
        else:
            options_dict['headings-to-sections'] = 0
        write_empty_paragraphs = options_dict.get('write-empty-paragraphs')
        if write_empty_paragraphs == 'true':
            options_dict['empty-paragraphs'] = 1
        elif write_empty_paragraphs == '1':
            options_dict['empty-paragraphs'] = 1
        elif write_empty_paragraphs == 'false':
            options_dict['empty-paragraphs'] = 0
        elif write_empty_paragraphs == '0':
            options_dict['empty-paragraphs'] = 0
        else:
            options_dict['empty-paragraphs'] = 1
        form_lists = options_dict.get('lists')
        if form_lists == 'true' or form_lists == '1':
            options_dict['form-lists'] = 1
        elif form_lists == 'false' or form_lists == '0':
            options_dict['form-lists'] = 0
        else:
            options_dict['form-lists'] = 0
        group_styles = options_dict.get('group-styles')
        if group_styles == 'true' or group_styles == '1':
            options_dict['group-styles'] = 1
        elif group_styles == 'false' or group_styles == '0':
            options_dict['group-styles'] = 0
        else:
            options_dict['group-styles'] = 0
        group_borders = options_dict.get('group-borders')
        if group_borders == 'true' or group_borders == '1':
            options_dict['group-borders'] = 1
        elif group_borders == 'false' or group_borders == '0':
            options_dict['group-borders'] = 0
        else:
            options_dict['group-borders'] = 0
        return options_dict
