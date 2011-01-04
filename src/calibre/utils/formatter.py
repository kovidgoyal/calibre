'''
Created on 23 Sep 2010

@author: charles
'''

import re, string, traceback
from functools import partial

from calibre.constants import DEBUG
from calibre.utils.titlecase import titlecase
from calibre.utils.icu import capitalize, strcmp

class _Parser(object):
    LEX_OP  = 1
    LEX_ID  = 2
    LEX_STR = 3
    LEX_NUM = 4
    LEX_EOF = 5

    def _strcmp(self, x, y, lt, eq, gt):
        v = strcmp(x, y)
        if v < 0:
            return lt
        if v == 0:
            return eq
        return gt

    def _cmp(self, x, y, lt, eq, gt):
        x = float(x if x else 0)
        y = float(y if y else 0)
        if x < y:
            return lt
        if x == y:
            return eq
        return gt

    def _assign(self, target, value):
        self.variables[target] = value
        return value

    def _concat(self, *args):
        i = 0
        res = ''
        for i in range(0, len(args)):
            res += args[i]
        return res

    def _math(self, x, y, op=None):
        ops = {
               '+': lambda x, y: x + y,
               '-': lambda x, y: x - y,
               '*': lambda x, y: x * y,
               '/': lambda x, y: x / y,
            }
        x = float(x if x else 0)
        y = float(y if y else 0)
        return unicode(ops[op](x, y))

    def _template(self, template):
        template = template.replace('[[', '{').replace(']]', '}')
        return self.parent.safe_format(template, self.parent.kwargs, 'TEMPLATE',
                                       self.parent.book)

    def _eval(self, template):
        template = template.replace('[[', '{').replace(']]', '}')
        return eval_formatter.safe_format(template, self.variables, 'EVAL', None)

    def _print(self, *args):
        print args
        return None

    local_functions = {
            'add'      : (2, partial(_math, op='+')),
            'assign'   : (2, _assign),
            'cmp'      : (5, _cmp),
            'divide'   : (2, partial(_math, op='/')),
            'eval'     : (1, _eval),
            'field'    : (1, lambda s, x: s.parent.get_value(x, [], s.parent.kwargs)),
            'multiply' : (2, partial(_math, op='*')),
            'print'    : (-1, _print),
            'strcat'   : (-1, _concat),
            'strcmp'   : (5, _strcmp),
            'substr'   : (3, lambda s, x, y, z: x[int(y): len(x) if int(z) == 0 else int(z)]),
            'subtract' : (2, partial(_math, op='-')),
            'template' : (1, _template)
    }

    def __init__(self, val, prog, parent):
        self.lex_pos = 0
        self.prog = prog[0]
        if prog[1] != '':
            self.error(_('failed to scan program. Invalid input {0}').format(prog[1]))
        self.parent = parent
        self.variables = {'$':val}

    def error(self, message):
        m = 'Formatter: ' + message + _(' near ')
        if self.lex_pos > 0:
            m = '{0} {1}'.format(m, self.prog[self.lex_pos-1][1])
        m = '{0} {1}'.format(m, self.prog[self.lex_pos][1])
        if self.lex_pos < len(self.prog):
            m = '{0} {1}'.format(m, self.prog[self.lex_pos+1][1])
        raise ValueError(m)

    def token(self):
        if self.lex_pos >= len(self.prog):
            return None
        token = self.prog[self.lex_pos]
        self.lex_pos += 1
        return token[1]

    def lookahead(self):
        if self.lex_pos >= len(self.prog):
            return (self.LEX_EOF, '')
        return self.prog[self.lex_pos]

    def consume(self):
        self.lex_pos += 1

    def token_op_is_a(self, val):
        token = self.lookahead()
        return token[0] == self.LEX_OP and token[1] == val

    def token_is_id(self):
        token = self.lookahead()
        return token[0] == self.LEX_ID

    def token_is_constant(self):
        token = self.lookahead()
        return token[0] == self.LEX_STR or token[0] == self.LEX_NUM

    def token_is_eof(self):
        token = self.lookahead()
        return token[0] == self.LEX_EOF

    def program(self):
        val = self.statement()
        if not self.token_is_eof():
            self.error(_('syntax error - program ends before EOF'))
        return val

    def statement(self):
        while True:
            val = self.expr()
            if self.token_is_eof():
                return val
            if not self.token_op_is_a(';'):
                return val
            self.consume()
            if self.token_is_eof():
                return val

    def expr(self):
        if self.token_is_id():
            # We have an identifier. Determine if it is a function
            id = self.token()
            if not self.token_op_is_a('('):
                if self.token_op_is_a('='):
                    # classic assignment statement
                    self.consume()
                    return self._assign(id, self.expr())
                return self.variables.get(id, _('unknown id ') + id)
            # We have a function.
            # Check if it is a known one. We do this here so error reporting is
            # better, as it can identify the tokens near the problem.
            if id not in self.parent.functions and id not in self.local_functions:
                self.error(_('unknown function {0}').format(id))
            # Eat the paren
            self.consume()
            args = list()
            while not self.token_op_is_a(')'):
                if id == 'assign' and len(args) == 0:
                    # Must handle the lvalue semantics of the assign function.
                    # The first argument is the name of the destination, not
                    # the value.
                    if not self.token_is_id():
                        self.error('assign requires the first parameter be an id')
                    args.append(self.token())
                else:
                    # evaluate the argument (recursive call)
                    args.append(self.statement())
                if not self.token_op_is_a(','):
                    break
                self.consume()
            if self.token() != ')':
                self.error(_('missing closing parenthesis'))

            # Evaluate the function
            if id in self.local_functions:
                f = self.local_functions[id]
                if f[0] != -1 and len(args) != f[0]:
                    self.error('incorrect number of arguments for function {}'.format(id))
                return f[1](self, *args)
            else:
                f = self.parent.functions[id]
                if f[0] != -1 and len(args) != f[0]+1:
                    self.error('incorrect number of arguments for function {}'.format(id))
                return f[1](self.parent, *args)
            # can't get here
        elif self.token_is_constant():
            # String or number
            return self.token()
        else:
            self.error(_('expression is not function or constant'))


class TemplateFormatter(string.Formatter):
    '''
    Provides a format function that substitutes '' for any missing value
    '''

    _validation_string = 'This Is Some Text THAT SHOULD be LONG Enough.%^&*'

    # Dict to do recursion detection. It is up the the individual get_value
    # method to use it. It is cleared when starting to format a template
    composite_values = {}

    def __init__(self):
        string.Formatter.__init__(self)
        self.book = None
        self.kwargs = None
        self.program_cache = {}

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

    def _do_format(self, val, fmt):
        if not fmt or not val:
            return val
        if val == self._validation_string:
            val = '0'
        typ = fmt[-1]
        if typ == 's':
            pass
        elif 'bcdoxXn'.find(typ) >= 0:
            try:
                val = int(val)
            except:
                raise ValueError(
                    _('format: type {0} requires an integer value, got {1}').format(typ, val))
        elif 'eEfFgGn%'.find(typ) >= 0:
            try:
                val = float(val)
            except:
                raise ValueError(
                    _('format: type {0} requires a decimal (float) value, got {1}').format(typ, val))
        else:
            raise ValueError(_('format: unknown format type letter {0}').format(typ))
        return unicode(('{0:'+fmt+'}').format(val))

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

    format_string_re = re.compile(r'^(.*)\|([^\|]*)\|(.*)$', re.DOTALL)
    compress_spaces = re.compile(r'\s+')
    backslash_comma_to_comma = re.compile(r'\\,')

    arg_parser = re.Scanner([
                (r',', lambda x,t: ''),
                (r'.*?((?<!\\),)', lambda x,t: t[:-1]),
                (r'.*?\)', lambda x,t: t[:-1]),
        ])

    ################## 'Functional' template language ######################

    lex_scanner = re.Scanner([
                (r'[(),=;]',            lambda x,t: (1, t)),
                (r'-?[\d\.]+',          lambda x,t: (3, t)),
                (r'\$',                 lambda x,t: (2, t)),
                (r'\w+',                lambda x,t: (2, t)),
                (r'".*?((?<!\\)")',     lambda x,t: (3, t[1:-1])),
                (r'\'.*?((?<!\\)\')',   lambda x,t: (3, t[1:-1])),
                (r'\n#.*?(?=\n)',       None),
                (r'\s',                 None)
        ])

    def _eval_program(self, val, prog):
        # keep a cache of the lex'ed program under the theory that re-lexing
        # is much more expensive than the cache lookup. This is certainly true
        # for more than a few tokens, but it isn't clear for simple programs.
        lprog = self.program_cache.get(prog, None)
        if not lprog:
            lprog = self.lex_scanner.scan(prog)
            self.program_cache[prog] = lprog
        parser = _Parser(val, lprog, self)
        return parser.program()

    ################## Override parent classes methods #####################

    def get_value(self, key, args, kwargs):
        raise Exception('get_value must be implemented in the subclass')

    def format_field(self, val, fmt):
        # ensure we are dealing with a string.
        if isinstance(val, (int, float)):
            if val:
                val = unicode(val)
            else:
                val = ''
        # Handle conditional text
        fmt, prefix, suffix = self._explode_format_string(fmt)

        # Handle functions
        # First see if we have a functional-style expression
        if fmt.startswith('\''):
            p = 0
        else:
            p = fmt.find(':\'')
            if p >= 0:
                p += 1
        if p >= 0 and fmt[-1] == '\'':
            val = self._eval_program(val, fmt[p+1:-1])
            colon = fmt[0:p].find(':')
            if colon < 0:
                dispfmt = ''
            else:
                dispfmt = fmt[0:colon]
        else:
            # check for old-style function references
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
            val = self._do_format(val, dispfmt)
        if not val:
            return ''
        return prefix + val + suffix

    def vformat(self, fmt, args, kwargs):
        if fmt.startswith('program:'):
            ans = self._eval_program(None, fmt[8:])
        else:
            ans = string.Formatter.vformat(self, fmt, args, kwargs)
        return self.compress_spaces.sub(' ', ans).strip()

    ########## a formatter guaranteed not to throw and exception ############

    def safe_format(self, fmt, kwargs, error_value, book):
        self.kwargs = kwargs
        self.book = book
        self.composite_values = {}
        try:
            ans = self.vformat(fmt, [], kwargs).strip()
        except Exception, e:
            if DEBUG:
                traceback.print_exc()
            ans = error_value + ' ' + e.message
        return ans

class ValidateFormatter(TemplateFormatter):
    '''
    Provides a format function that substitutes '' for any missing value
    '''
    def get_value(self, key, args, kwargs):
        return self._validation_string

    def validate(self, x):
        return self.vformat(x, [], {})

validation_formatter = ValidateFormatter()

class EvalFormatter(TemplateFormatter):
    '''
    A template formatter that uses a simple dict instead of an mi instance
    '''
    def get_value(self, key, args, kwargs):
        return kwargs.get(key, _('No such variable ') + key)

eval_formatter = EvalFormatter()

