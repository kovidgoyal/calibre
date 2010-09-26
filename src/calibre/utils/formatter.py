'''
Created on 23 Sep 2010

@author: charles
'''

import re, string

class TemplateFormatter(string.Formatter):
    '''
    Provides a format function that substitutes '' for any missing value
    '''

    def __init__(self):
        string.Formatter.__init__(self)
        self.book = None
        self.kwargs = None
        self.sanitize = None

    def _lookup(self, val, field_if_set, field_not_set):
        if val:
            return self.vformat('{'+field_if_set.strip()+'}', [], self.kwargs)
        else:
            return self.vformat('{'+field_not_set.strip()+'}', [], self.kwargs)

    def _test(self, val, value_if_set, value_not_set):
        if val:
            return value_if_set
        else:
            return value_not_set

    def _contains(self, val, test, value_if_present, value_if_not):
        if re.search(test, val):
            return value_if_present
        else:
            return value_if_not

    def _re(self, val, pattern, replacement):
        return re.sub(pattern, replacement, val)

    def _ifempty(self, val, value_if_empty):
        if val:
            return val
        else:
            return value_if_empty

    def _shorten(self, val, leading, center_string, trailing):
        l = int(leading)
        t = int(trailing)
        if len(val) > l + len(center_string) + t:
            return val[0:l] + center_string + val[-t:]
        else:
            return val

    functions = {
                    'uppercase'     : (0, lambda s,x: x.upper()),
                    'lowercase'     : (0, lambda s,x: x.lower()),
                    'titlecase'     : (0, lambda s,x: x.title()),
                    'capitalize'    : (0, lambda s,x: x.capitalize()),
                    'contains'      : (3, _contains),
                    'ifempty'       : (1, _ifempty),
                    'lookup'        : (2, _lookup),
                    're'            : (2, _re),
                    'shorten'       : (3, _shorten),
                    'test'          : (2, _test),
        }

    format_string_re = re.compile(r'^(.*)\|(.*)\|(.*)$')
    compress_spaces = re.compile(r'\s+')

    def get_value(self, key, args, kwargs):
        raise Exception('get_value must be implemented in the subclass')


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
        # Handle conditional text
        fmt, prefix, suffix = self._explode_format_string(fmt)

        # Handle functions
        p = fmt.find('(')
        if p >= 0 and fmt[-1] == ')' and fmt[0:p] in self.functions:
            field = fmt[0:p]
            func = self.functions[field]
            args = fmt[p+1:-1].split(',')
            if (func[0] == 0 and (len(args) != 1 or args[0])) or \
                    (func[0] > 0 and func[0] != len(args)):
                raise ValueError('Incorrect number of arguments for function '+ fmt[0:p])
            if func[0] == 0:
                val = func[1](self, val)
            else:
                val = func[1](self, val, *args)
        elif val:
            val = string.Formatter.format_field(self, val, fmt)
        if not val:
            return ''
        return prefix + val + suffix

    def vformat(self, fmt, args, kwargs):
        ans = string.Formatter.vformat(self, fmt, args, kwargs)
        return self.compress_spaces.sub(' ', ans).strip()

    def safe_format(self, fmt, kwargs, error_value, book, sanitize=None):
        self.kwargs = kwargs
        self.book = book
        self.sanitize = sanitize
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


