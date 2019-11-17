
import os, sys
from . import open_for_read


class Configure:

    def __init__(self,
                    configuration_file,
                    bug_handler,
                    debug_dir=None,
                    show_config_file=None,
                    ):
        """
        Requires:
            file --file to be read
            output --file to output to
        Returns:
            Nothing. Outputs a file
        Logic:
        """
        self.__configuration_file = configuration_file
        self.__debug_dir = debug_dir
        self.__bug_handler = bug_handler
        self.__show_config_file = show_config_file

    def get_configuration(self, type):
        self.__configuration_file = self.__get_file_name()
        return_dict = {}
        return_dict['config-location'] = self.__configuration_file
        if self.__show_config_file and self.__configuration_file:
            sys.stderr.write('configuration file is "%s"\n' % self.__configuration_file)
        if self.__show_config_file and not self.__configuration_file:
            sys.stderr.write('No configuraiton file found; using default values\n')
        if self.__configuration_file:
            read_obj = open_for_read(self.__configuration_file)
            line_to_read = 1
            line_num = 0
            while line_to_read:
                line_num += 1
                line_to_read = read_obj.readline()
                line = line_to_read
                line = line.strip()
                if line[0:1] == '#':
                    continue
                if not line:
                    continue
                fields = line.split('=')
                if len(fields) != 2:
                    msg =  line
                    msg += ('Error in configuration.txt, line %s\n' % line_num)
                    msg += ('Options take the form of option = value.\n')
                    msg += ('Please correct the configuration file "%s" before continuing\n'
                        % self.__configuration_file)
                    raise self.__bug_handler(msg)
                att = fields[0]
                value = fields[1]
                att = att.strip()
                value = value.strip()
                return_dict[att] = value
        return_dict = self.__parse_dict(return_dict)
        if return_dict == 1:
            msg = ('Please correct the configuration file "%s" before continuing\n'
                    % self.__configuration_file)
            raise self.__bug_handler(msg)
        return return_dict

    def __get_file_name(self):
        home_var = os.environ.get('HOME')
        if home_var:
            home_config = os.path.join(home_var, '.rtf2xml')
            if os.path.isfile(home_config):
                return home_config
        home_var = os.environ.get('USERPROFILE')
        if home_var:
            home_config = os.path.join(home_var, '.rtf2xml')
            if os.path.isfile(home_config):
                return home_config
        script_file = os.path.join(sys.path[0], '.rtf2xml')
        if os.path.isfile(script_file):
            return script_file
        return self.__configuration_file

    def __parse_dict(self, return_dict):
        allowable = [
            'configuration-directory',
            'smart-output',  # = false
            'level',  # = 1
            'convert-symbol',  # = true
            'convert-wingdings',  # = true
            'convert-zapf-dingbats',  # = true
            'convert-caps',  # true
            'indent',  # = 1
            'group-styles',
            'group-borders',
            'headings-to-sections',
            'lists',
            'raw-dtd-path',
            'write-empty-paragraphs',
            'config-location',
            'script-name',
        ]
        the_keys = return_dict.keys()
        for the_key in the_keys:
            if the_key not in allowable:
                sys.stderr.write('options "%s" not a legal option.\n'
                        % the_key)
                return 1
        configuration_dir = return_dict.get('configuration-directory')
        if configuration_dir is None:
            return_dict['configure-directory'] = None
        else:
            if not os.path.isdir(configuration_dir):
                sys.stderr.write('The dirctory "%s" does not appear to be a directory.\n'
                        % configuration_dir)
                return 1
            else:
                return_dict['configure-directory'] = configuration_dir
        smart_output = return_dict.get('smart-output')
        if not smart_output:
            return_dict['smart-output'] = 0
        elif smart_output != 'true' and smart_output != 'false':
            sys.stderr.write('"smart-output" must be true or false.\n')
            return 1
        elif smart_output == 'false':
            return_dict['smart-output'] = 0
        int_options = ['level', 'indent']
        for int_option in int_options:
            value = return_dict.get(int_option)
            if not value:
                if int_option == 'level':
                    return_dict['level'] = 1
                else:
                    return_dict['indent'] = 0
            else:
                try:
                    int_num = int(return_dict[int_option])
                    return_dict[int_option] = int_num
                except:
                    sys.stderr.write('"%s" must be a number\n' % int_option)
                    sys.stderr.write('You choose "%s" ' % return_dict[int_option])
                    return 1
        fonts = ['convert-symbol', 'convert-wingdings', 'convert-zapf-dingbats',
            'convert-caps'
            ]
        for font in fonts:
            value = return_dict.get(font)
            if not value:
                return_dict[font] = 0
            elif value != 'true' and value != 'false':
                sys.stderr.write(
                    '"%s" must be true or false.\n' % font)
            elif value == 'false':
                return_dict[font] = 0
        return_dict['xslt-processor'] = None
        return_dict['no-namespace'] = None
        return_dict['format'] = 'raw'
        return_dict['no-pyxml'] = 'true'
        return return_dict
