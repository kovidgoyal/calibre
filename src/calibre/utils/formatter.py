'''
Created on 23 Sep 2010

@author: charles
'''

import re, string, traceback

from calibre.constants import DEBUG
from calibre.utils.titlecase import titlecase
from calibre.utils.icu import capitalize

class TemplateFormatter(string.Formatter):
    '''
    Provides a format function that substitutes '' for any missing value
    '''

    # Dict to do recursion detection. It is up the the individual get_value
    # method to use it. It is cleared when starting to format a template
    composite_values = {}

    def __init__(self):
        string.Formatter.__init__(self)
        self.book = None
        self.kwargs = None

    def _lookup(self, val, *args):
        if len(args) == 2: # here for backwards compatibility
            if val:
                return self.vformat('{'+args[0].strip()+'}', [], self.kwargs)
            else:
                return self.vformat('{'+args[1].strip()+'}', [], self.kwargs)
        if (len(args) % 2) != 1:
            raise ValueError(_('lookup requires either 2 or an odd number of arguments'))
        i = 0
        while i < len(args):
            if i + 1 >= len(args):
                return self.vformat('{' + args[i].strip() + '}', [], self.kwargs)
            if re.search(args[i], val):
                return self.vformat('{'+args[i+1].strip() + '}', [], self.kwargs)
            i += 2

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

    def _switch(self, val, *args):
        if (len(args) % 2) != 1:
            raise ValueError(_('switch requires an odd number of arguments'))
        i = 0
        while i < len(args):
            if i + 1 >= len(args):
                return args[i]
            if re.search(args[i], val):
                return args[i+1]
            i += 2

    def _re(self, val, pattern, replacement):
        return re.sub(pattern, replacement, val)

    def _ifempty(self, val, value_if_empty):
        if val:
            return val
        else:
            return value_if_empty

    def _shorten(self, val, leading, center_string, trailing):
        l = max(0, int(leading))
        t = max(0, int(trailing))
        if len(val) > l + len(center_string) + t:
            return val[0:l] + center_string + ('' if t == 0 else val[-t:])
        else:
            return val

    def _count(self, val, sep):
        return unicode(len(val.split(sep)))

    functions = {
                    'uppercase'     : (0, lambda s,x: x.upper()),
                    'lowercase'     : (0, lambda s,x: x.lower()),
                    'titlecase'     : (0, lambda s,x: titlecase(x)),
                    'capitalize'    : (0, lambda s,x: capitalize(x)),
                    'contains'      : (3, _contains),
                    'ifempty'       : (1, _ifempty),
                    'lookup'        : (-1, _lookup),
                    're'            : (2, _re),
                    'shorten'       : (3, _shorten),
                    'switch'        : (-1, _switch),
                    'test'          : (2, _test),
                    'count'         : (1, _count),
        }

    format_string_re = re.compile(r'^(.*)\|(.*)\|(.*)$')
    compress_spaces = re.compile(r'\s+')
    backslash_comma_to_comma = re.compile(r'\\,')

    arg_parser = re.Scanner([
                (r',', lambda x,t: ''),
                (r'.*?((?<!\\),)', lambda x,t: t[:-1]),
                (r'.*?\)', lambda x,t: t[:-1]),
        ])

    def get_value(self, key, args, kwargs):
        raise Exception('get_value must be implemented in the subclass')


    def _explode_format_string(self, fmt):
        try:
            matches = self.format_string_re.match(fmt)
            if matches is None or matches.lastindex != 3:
                return fmt, '', ''
            return matches.groups()
        except:
            if DEBUG:
                traceback.print_exc()
            return fmt, '', ''

    def format_field(self, val, fmt):
        # Handle conditional text
        fmt, prefix, suffix = self._explode_format_string(fmt)

        # Handle functions
        p = fmt.find('(')
        dispfmt = fmt
        if p >= 0 and fmt[-1] == ')':
            colon = fmt[0:p].find(':')
            if colon < 0:
                dispfmt = ''
                colon = 0
            else:
                dispfmt = fmt[0:colon]
                colon += 1
            if fmt[colon:p] in self.functions:
                field = fmt[colon:p]
                func = self.functions[field]
                if func[0] == 1:
                    # only one arg expected. Don't bother to scan. Avoids need
                    # for escaping characters
                    args = [fmt[p+1:-1]]
                else:
                    args = self.arg_parser.scan(fmt[p+1:])[0]
                    args = [self.backslash_comma_to_comma.sub(',', a) for a in args]
                if (func[0] == 0 and (len(args) != 1 or args[0])) or \
                        (func[0] > 0 and func[0] != len(args)):
                    raise ValueError('Incorrect number of arguments for function '+ fmt[0:p])
                if func[0] == 0:
                    val = func[1](self, val).strip()
                else:
                    val = func[1](self, val, *args).strip()
        if val:
            val = string.Formatter.format_field(self, val, dispfmt)
        if not val:
            return ''
        return prefix + val + suffix

    def vformat(self, fmt, args, kwargs):
        ans = string.Formatter.vformat(self, fmt, args, kwargs)
        return self.compress_spaces.sub(' ', ans).strip()

    def safe_format(self, fmt, kwargs, error_value, book):
        self.kwargs = kwargs
        self.book = book
        self.composite_values = {}
        try:
            ans = self.vformat(fmt, [], kwargs).strip()
        except:
            if DEBUG:
                traceback.print_exc()
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


