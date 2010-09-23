'''
Created on 23 Sep 2010

@author: charles
'''

import re, string

def _lookup(val, mi, field_if_set, field_not_set):
    if hasattr(mi, 'format_field'):
        if val:
            return mi.format_field(field_if_set.strip())[1]
        else:
            return mi.format_field(field_not_set.strip())[1]
    else:
        if val:
            return mi.get(field_if_set.strip(), '')
        else:
            return mi.get(field_not_set.strip(), '')

def _ifempty(val, mi, value_if_empty):
    if val:
        return val
    else:
        return value_if_empty

def _shorten(val, mi, leading, center_string, trailing):
    l = int(leading)
    t = int(trailing)
    if len(val) > l + len(center_string) + t:
        return val[0:l] + center_string + val[-t:]
    else:
        return val

class TemplateFormatter(string.Formatter):
    '''
    Provides a format function that substitutes '' for any missing value
    '''

    functions = {
                    'uppercase'     : (0, lambda x: x.upper()),
                    'lowercase'     : (0, lambda x: x.lower()),
                    'titlecase'     : (0, lambda x: x.title()),
                    'capitalize'    : (0, lambda x: x.capitalize()),
                    'ifempty'       : (1, _ifempty),
                    'lookup'        : (2, _lookup),
                    'shorten'       : (3, _shorten),
        }

    def get_value(self, key, args, mi):
        raise Exception('get_value must be implemented in the subclass')

    format_string_re = re.compile(r'^(.*)\|(.*)\|(.*)$')

    def _explode_format_string(self, fmt):
        try:
            matches = self.format_string_re.match(fmt)
            if matches is None or matches.lastindex != 3:
                return fmt, '', ''
            return matches.groups()
        except:
            import traceback
            traceback.print_exc()
            return fmt, '', ''

    def format_field(self, val, fmt):
        fmt, prefix, suffix = self._explode_format_string(fmt)

        p = fmt.find('(')
        if p >= 0 and fmt[-1] == ')' and fmt[0:p] in self.functions:
            field = fmt[0:p]
            func = self.functions[field]
            args = fmt[p+1:-1].split(',')
            if (func[0] == 0 and (len(args) != 1 or args[0])) or \
                    (func[0] > 0 and func[0] != len(args)):
                raise Exception ('Incorrect number of arguments for function '+ fmt[0:p])
            if func[0] == 0:
                val = func[1](val, self.mi)
            else:
                val = func[1](val, self.mi, *args)
        else:
            val = string.Formatter.format_field(self, val, fmt)
        if not val:
            return ''
        return prefix + val + suffix

    compress_spaces = re.compile(r'\s+')

    def vformat(self, fmt, args, kwargs):
        self.mi = kwargs
        ans = string.Formatter.vformat(self, fmt, args, kwargs)
        return self.compress_spaces.sub(' ', ans).strip()

    def safe_format(self, fmt, kwargs, error_value):
        try:
            ans = self.vformat(fmt, [], kwargs).strip()
        except:
            ans = error_value
        return ans

class ValidateFormat(TemplateFormatter):
    '''
    Provides a format function that substitutes '' for any missing value
    '''
    def get_value(self, key, args, kwargs):
            return 'this is some text that should be long enough'

    def validate(self, x):
        return self.vformat(x, [], {})

validation_formatter = ValidateFormat()


