#!/usr/bin/env python

'''
Created on 13 Jan 2011

@author: charles
'''


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import inspect
import numbers
import posixpath
import re
import traceback
from contextlib import suppress
from datetime import datetime, timedelta
from enum import Enum, auto
from functools import partial
from math import ceil, floor, modf, trunc

from lxml import html

from calibre import human_readable, prepare_string_for_xml, prints
from calibre.constants import DEBUG
from calibre.db.constants import DATA_DIR_NAME, DATA_FILE_PATTERN
from calibre.db.notes.exim import expand_note_resources, parse_html
from calibre.ebooks.metadata import title_sort
from calibre.utils.config import tweaks
from calibre.utils.date import UNDEFINED_DATE, format_date, now, parse_date
from calibre.utils.icu import capitalize, sort_key, strcmp
from calibre.utils.icu import lower as icu_lower
from calibre.utils.localization import _, calibre_langcode_to_name, canonicalize_lang
from calibre.utils.titlecase import titlecase
from polyglot.builtins import iteritems, itervalues


class StoredObjectType(Enum):
    PythonFunction = auto()
    StoredGPMTemplate = auto()
    StoredPythonTemplate = auto()


class FormatterFunctions:

    error_function_body = ('def evaluate(self, formatter, kwargs, mi, locals):\n'
                       '\treturn "' +
                            _('Duplicate user function name {0}. '
                              'Change the name or ensure that the functions are identical') + '"')

    def __init__(self):
        self._builtins = {}
        self._functions = {}
        self._functions_from_library = {}

    def register_builtin(self, func_class):
        if not isinstance(func_class, FormatterFunction):
            raise ValueError('Class %s is not an instance of FormatterFunction'%(
                                    func_class.__class__.__name__))
        name = func_class.name
        if name in self._functions:
            raise ValueError('Name %s already used'%name)
        self._builtins[name] = func_class
        self._functions[name] = func_class
        for a in func_class.aliases:
            self._functions[a] = func_class

    def _register_function(self, func_class, replace=False):
        if not isinstance(func_class, FormatterFunction):
            raise ValueError('Class %s is not an instance of FormatterFunction'%(
                                    func_class.__class__.__name__))
        name = func_class.name
        if not replace and name in self._functions:
            raise ValueError('Name %s already used'%name)
        self._functions[name] = func_class

    def register_functions(self, library_uuid, funcs):
        self._functions_from_library[library_uuid] = funcs
        self._register_functions()

    def _register_functions(self):
        for compiled_funcs in itervalues(self._functions_from_library):
            for cls in compiled_funcs:
                f = self._functions.get(cls.name, None)
                replace = False
                if f is not None:
                    existing_body = f.program_text
                    new_body = cls.program_text
                    if new_body != existing_body:
                        # Change the body of the template function to one that will
                        # return an error message. Also change the arg count to
                        # -1 (variable) to avoid template compilation errors
                        if DEBUG:
                            print(f'attempt to replace formatter function {f.name} with a different body')
                        replace = True
                        func = [cls.name, '', -1, self.error_function_body.format(cls.name)]
                        cls = compile_user_function(*func)
                    else:
                        continue
                formatter_functions()._register_function(cls, replace=replace)

    def unregister_functions(self, library_uuid):
        if library_uuid in self._functions_from_library:
            for cls in self._functions_from_library[library_uuid]:
                self._functions.pop(cls.name, None)
            self._functions_from_library.pop(library_uuid)
            self._register_functions()

    def get_builtins(self):
        return self._builtins

    def get_builtins_and_aliases(self):
        res = {}
        for f in itervalues(self._builtins):
            res[f.name] = f
            for a in f.aliases:
                res[a] = f
        return res

    def get_functions(self):
        return self._functions

    def reset_to_builtins(self):
        self._functions = {}
        for n,c in self._builtins.items():
            self._functions[n] = c
            for a in c.aliases:
                self._functions[a] = c


_ff = FormatterFunctions()


def formatter_functions():
    global _ff
    return _ff


def only_in_gui_error(name):
    raise ValueError(_('The function {} can be used only in the GUI').format(name))


def get_database(mi, name):
    proxy = mi.get('_proxy_metadata', None)
    if proxy is None:
        if name is not None:
            only_in_gui_error(name)
        return None
    wr = proxy.get('_db', None)
    if wr is None:
        if name is not None:
            raise ValueError(_('In function {}: The database has been closed').format(name))
        return None
    cache = wr()
    if cache is None:
        if name is not None:
            raise ValueError(_('In function {}: The database has been closed').format(name))
        return None
    wr = getattr(cache, 'library_database_instance', None)
    if wr is None:
        if name is not None:
            only_in_gui_error()
        return None
    db = wr()
    if db is None:
        if name is not None:
            raise ValueError(_('In function {}: The database has been closed').format(name))
        return None
    return db


class FormatterFunction:

    doc = _('No documentation provided')
    name = 'no name provided'
    category = 'Unknown'
    arg_count = 0
    aliases = []
    object_type = StoredObjectType.PythonFunction

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        raise NotImplementedError()

    def eval_(self, formatter, kwargs, mi, locals, *args):
        ret = self.evaluate(formatter, kwargs, mi, locals, *args)
        if isinstance(ret, (bytes, str)):
            return ret
        if isinstance(ret, list):
            return ','.join(ret)
        if isinstance(ret, (numbers.Number, bool)):
            return str(ret)

    def only_in_gui_error(self):
        only_in_gui_error(self.name)

    def get_database(self, mi):
        return get_database(mi, self.name)


class BuiltinFormatterFunction(FormatterFunction):

    def __init__(self):
        formatter_functions().register_builtin(self)
        eval_func = inspect.getmembers(self.__class__,
                        lambda x: inspect.isfunction(x) and x.__name__ == 'evaluate')
        try:
            lines = [l[4:] for l in inspect.getsourcelines(eval_func[0][1])[0]]
        except:
            lines = []
        self.program_text = ''.join(lines)


class BuiltinStrcmp(BuiltinFormatterFunction):
    name = 'strcmp'
    arg_count = 5
    category = 'Relational'
    __doc__ = doc = _('strcmp(x, y, lt, eq, gt) -- does a case-insensitive comparison of x '
            'and y as strings. Returns lt if x < y. Returns eq if x == y. '
            'Otherwise returns gt. In many cases the lexical comparison operators '
            '(>, <, == etc) can replace this function.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y, lt, eq, gt):
        v = strcmp(x, y)
        if v < 0:
            return lt
        if v == 0:
            return eq
        return gt


class BuiltinStrcmpcase(BuiltinFormatterFunction):
    name = 'strcmpcase'
    arg_count = 5
    category = 'Relational'
    __doc__ = doc = _('strcmpcase(x, y, lt, eq, gt) -- does a case-sensitive comparison of x '
            'and y as strings. Returns lt if x < y. Returns eq if x == y. '
            'Otherwise returns gt.\n'
            'Note: This is NOT the default behavior used by calibre, for example, in the '
            'lexical comparison operators (==, >, <, etc.). This function could '
            'cause unexpected results, preferably use strcmp() whenever possible.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y, lt, eq, gt):
        from calibre.utils.icu import case_sensitive_strcmp as case_strcmp
        v = case_strcmp(x, y)
        if v < 0:
            return lt
        if v == 0:
            return eq
        return gt


class BuiltinCmp(BuiltinFormatterFunction):
    name = 'cmp'
    category = 'Relational'
    arg_count = 5
    __doc__ = doc =   _('cmp(x, y, lt, eq, gt) -- compares x and y after converting both to '
            'numbers. Returns lt if x < y. Returns eq if x == y. Otherwise returns gt. '
            'In many cases the numeric comparison operators '
            '(>#, <#, ==# etc) can replace this function.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y, lt, eq, gt):
        x = float(x if x and x != 'None' else 0)
        y = float(y if y and y != 'None' else 0)
        if x < y:
            return lt
        if x == y:
            return eq
        return gt


class BuiltinFirstMatchingCmp(BuiltinFormatterFunction):
    name = 'first_matching_cmp'
    category = 'Relational'
    arg_count = -1
    __doc__ = doc =   _('first_matching_cmp(val, [cmp1, result1,]+, else_result) -- '
            'compares "val < cmpN" in sequence, returning resultN for '
            'the first comparison that succeeds. Returns else_result '
            'if no comparison succeeds. Example: '
            'first_matching_cmp(10,5,"small",10,"middle",15,"large","giant") '
            'returns "large". The same example with a first value of 16 returns "giant".')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        if (len(args) % 2) != 0:
            raise ValueError(_('first_matching_cmp requires an even number of arguments'))
        val = float(args[0] if args[0] and args[0] != 'None' else 0)
        for i in range(1, len(args) - 1, 2):
            c = float(args[i] if args[i] and args[i] != 'None' else 0)
            if val < c:
                return args[i+1]
        return args[len(args)-1]


class BuiltinStrcat(BuiltinFormatterFunction):
    name = 'strcat'
    arg_count = -1
    category = 'String manipulation'
    __doc__ = doc = _('strcat(a [, b]*) -- can take any number of arguments. Returns the '
            'string formed by concatenating all the arguments')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        i = 0
        res = ''
        for i in range(0, len(args)):
            res += args[i]
        return res


class BuiltinStrlen(BuiltinFormatterFunction):
    name = 'strlen'
    arg_count = 1
    category = 'String manipulation'
    __doc__ = doc = _('strlen(a) -- Returns the length of the string passed as '
            'the argument')

    def evaluate(self, formatter, kwargs, mi, locals, a):
        try:
            return len(a)
        except:
            return -1


class BuiltinAdd(BuiltinFormatterFunction):
    name = 'add'
    arg_count = -1
    category = 'Arithmetic'
    __doc__ = doc = _('add(x [, y]*) -- returns the sum of its arguments. '
                      'Throws an exception if an argument is not a number. '
                      'This function can often be '
                      'replaced with the + operator.')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        res = 0
        for v in args:
            v = float(v if v and v != 'None' else 0)
            res += v
        return str(res)


class BuiltinSubtract(BuiltinFormatterFunction):
    name = 'subtract'
    arg_count = 2
    category = 'Arithmetic'
    __doc__ = doc = _('subtract(x, y) -- returns x - y. Throws an exception if '
                      'either x or y are not numbers. This function can often be '
                      'replaced with the - operator.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y):
        x = float(x if x and x != 'None' else 0)
        y = float(y if y and y != 'None' else 0)
        return str(x - y)


class BuiltinMultiply(BuiltinFormatterFunction):
    name = 'multiply'
    arg_count = -1
    category = 'Arithmetic'
    __doc__ = doc = _('multiply(x [, y]*) -- returns the product of its arguments. '
                      'Throws an exception if any argument is not a number. '
                      'This function can often be replaced with the * operator.')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        res = 1
        for v in args:
            v = float(v if v and v != 'None' else 0)
            res *= v
        return str(res)


class BuiltinDivide(BuiltinFormatterFunction):
    name = 'divide'
    arg_count = 2
    category = 'Arithmetic'
    __doc__ = doc = _('divide(x, y) -- returns x / y. Throws an exception if '
                      'either x or y are not numbers.'
                      ' This function can often be replaced with the / operator.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y):
        x = float(x if x and x != 'None' else 0)
        y = float(y if y and y != 'None' else 0)
        return str(x / y)


class BuiltinCeiling(BuiltinFormatterFunction):
    name = 'ceiling'
    arg_count = 1
    category = 'Arithmetic'
    __doc__ = doc = _('ceiling(x) -- returns the smallest integer greater '
                      'than or equal to x. Throws an exception if x is '
                      'not a number.')

    def evaluate(self, formatter, kwargs, mi, locals, x):
        x = float(x if x and x != 'None' else 0)
        return str(int(ceil(x)))


class BuiltinFloor(BuiltinFormatterFunction):
    name = 'floor'
    arg_count = 1
    category = 'Arithmetic'
    __doc__ = doc = _('floor(x) -- returns the largest integer less '
                      'than or equal to x. Throws an exception if x is '
                      'not a number.')

    def evaluate(self, formatter, kwargs, mi, locals, x):
        x = float(x if x and x != 'None' else 0)
        return str(int(floor(x)))


class BuiltinRound(BuiltinFormatterFunction):
    name = 'round'
    arg_count = 1
    category = 'Arithmetic'
    __doc__ = doc = _('round(x) -- returns the nearest integer to x. '
                      'Throws an exception if x is not a number.')

    def evaluate(self, formatter, kwargs, mi, locals, x):
        x = float(x if x and x != 'None' else 0)
        return str(int(round(x)))


class BuiltinMod(BuiltinFormatterFunction):
    name = 'mod'
    arg_count = 2
    category = 'Arithmetic'
    __doc__ = doc = _('mod(x) -- returns floor(remainder of x / y). '
                      'Throws an exception if either x or y is not a number.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y):
        x = float(x if x and x != 'None' else 0)
        y = float(y if y and y != 'None' else 0)
        return str(int(x % y))


class BuiltinFractionalPart(BuiltinFormatterFunction):
    name = 'fractional_part'
    arg_count = 1
    category = 'Arithmetic'
    __doc__ = doc = _('fractional_part(x) -- returns the value after the decimal '
                      'point.  For example, fractional_part(3.14) returns 0.14. '
                      'Throws an exception if x is not a number.')

    def evaluate(self, formatter, kwargs, mi, locals, x):
        x = float(x if x and x != 'None' else 0)
        return str(modf(x)[0])


class BuiltinTemplate(BuiltinFormatterFunction):
    name = 'template'
    arg_count = 1
    category = 'Recursion'

    __doc__ = doc = _('template(x) -- evaluates x as a template. The evaluation is done '
            'in its own context, meaning that variables are not shared between '
            'the caller and the template evaluation. Because the { and } '
            'characters are special, you must use [[ for the { character and '
            ']] for the } character; they are converted automatically. '
            'For example, template(\'[[title_sort]]\') will evaluate the '
            'template {title_sort} and return its value. Note also that '
            'prefixes and suffixes (the `|prefix|suffix` syntax) cannot be '
            'used in the argument to this function when using template program mode.')

    def evaluate(self, formatter, kwargs, mi, locals, template):
        template = template.replace('[[', '{').replace(']]', '}')
        return formatter.__class__().safe_format(template, kwargs, 'TEMPLATE', mi)


class BuiltinEval(BuiltinFormatterFunction):
    name = 'eval'
    arg_count = 1
    category = 'Recursion'
    __doc__ = doc = _('eval(template) -- evaluates the template, passing the local '
            'variables (those \'assign\'ed to) instead of the book metadata. '
            ' This permits using the template processor to construct complex '
            'results from local variables. Because the { and } '
            'characters are special, you must use [[ for the { character and '
            ']] for the } character; they are converted automatically. '
            'Note also that prefixes and suffixes (the `|prefix|suffix` syntax) '
            'cannot be used in the argument to this function when using '
            'template program mode.')

    def evaluate(self, formatter, kwargs, mi, locals, template):
        from calibre.utils.formatter import EvalFormatter
        template = template.replace('[[', '{').replace(']]', '}')
        return EvalFormatter().safe_format(template, locals, 'EVAL', None)


class BuiltinAssign(BuiltinFormatterFunction):
    name = 'assign'
    arg_count = 2
    category = 'Other'
    __doc__ = doc = _('assign(id, val) -- assigns val to id, then returns val. '
            'id must be an identifier, not an expression. '
            'This function can often be replaced with the = operator.')

    def evaluate(self, formatter, kwargs, mi, locals, target, value):
        locals[target] = value
        return value


class BuiltinListSplit(BuiltinFormatterFunction):
    name = 'list_split'
    arg_count = 3
    category = 'List manipulation'
    __doc__ = doc = _('list_split(list_val, sep, id_prefix) -- splits the list_val '
                    "into separate values using 'sep', then assigns the values "
                    "to variables named 'id_prefix_N' where N is the position "
                    "of the value in the list. The first item has position 0 (zero). "
                    "The function returns the last element in the list. "
                    "Example: split('one:two:foo', ':', 'var') is equivalent "
                    "to var_0 = 'one'; var_1 = 'two'; var_2 = 'foo'.")

    def evaluate(self, formatter, kwargs, mi, locals, list_val, sep, id_prefix):
        l = [v.strip() for v in list_val.split(sep)]
        res = ''
        for i,v in enumerate(l):
            res = locals[id_prefix+'_'+str(i)] = v
        return res


class BuiltinPrint(BuiltinFormatterFunction):
    name = 'print'
    arg_count = -1
    category = 'Other'
    __doc__ = doc = _('print(a[, b]*) -- prints the arguments to standard output. '
            'Unless you start calibre from the command line (calibre-debug -g), '
            'the output will go to a black hole.')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        print(args)
        return ''


class BuiltinField(BuiltinFormatterFunction):
    name = 'field'
    arg_count = 1
    category = 'Get values from metadata'
    __doc__ = doc = _('field(lookup_name) -- returns the metadata field named by lookup_name')

    def evaluate(self, formatter, kwargs, mi, locals, name):
        return formatter.get_value(name, [], kwargs)


class BuiltinRawField(BuiltinFormatterFunction):
    name = 'raw_field'
    arg_count = -1
    category = 'Get values from metadata'
    __doc__ = doc = _('raw_field(lookup_name [, optional_default]) -- returns the '
            'metadata field named by lookup_name without applying any formatting. '
            'It evaluates and returns the optional second argument '
            "'default' if the field is undefined ('None').")

    def evaluate(self, formatter, kwargs, mi, locals, name, default=None):
        res = getattr(mi, name, None)
        if res is None and default is not None:
            return default
        if isinstance(res, list):
            fm = mi.metadata_for_field(name)
            if fm is None:
                return ', '.join(res)
            return fm['is_multiple']['list_to_ui'].join(res)
        return str(res)


class BuiltinRawList(BuiltinFormatterFunction):
    name = 'raw_list'
    arg_count = 2
    category = 'Get values from metadata'
    __doc__ = doc = _('raw_list(lookup_name, separator) -- returns the metadata list '
            'named by lookup_name without applying any formatting or sorting and '
            'with items separated by separator.')

    def evaluate(self, formatter, kwargs, mi, locals, name, separator):
        res = getattr(mi, name, None)
        if not isinstance(res, list):
            return "%s is not a list" % name
        return separator.join(res)


class BuiltinSubstr(BuiltinFormatterFunction):
    name = 'substr'
    arg_count = 3
    category = 'String manipulation'
    __doc__ = doc = _('substr(str, start, end) -- returns the start\'th through the end\'th '
            'characters of str. The first character in str is the zero\'th '
            'character. If end is negative, then it indicates that many '
            'characters counting from the right. If end is zero, then it '
            'indicates the last character. For example, substr(\'12345\', 1, 0) '
            'returns \'2345\', and substr(\'12345\', 1, -1) returns \'234\'.')

    def evaluate(self, formatter, kwargs, mi, locals, str_, start_, end_):
        return str_[int(start_): len(str_) if int(end_) == 0 else int(end_)]


class BuiltinLookup(BuiltinFormatterFunction):
    name = 'lookup'
    arg_count = -1
    category = 'Iterating over values'
    __doc__ = doc = _('lookup(val, [pattern, field,]+ else_field) -- '
            'like switch, except the arguments are field (metadata) names, not '
            'text. The value of the appropriate field will be fetched and used. '
            'Note that because composite columns are fields, you can use this '
            'function in one composite field to use the value of some other '
            'composite field. This is extremely useful when constructing '
            'variable save paths')

    def evaluate(self, formatter, kwargs, mi, locals, val, *args):
        if len(args) == 2:  # here for backwards compatibility
            if val:
                return formatter.vformat('{'+args[0].strip()+'}', [], kwargs)
            else:
                return formatter.vformat('{'+args[1].strip()+'}', [], kwargs)
        if (len(args) % 2) != 1:
            raise ValueError(_('lookup requires either 2 or an odd number of arguments'))
        i = 0
        while i < len(args):
            if i + 1 >= len(args):
                return formatter.vformat('{' + args[i].strip() + '}', [], kwargs)
            if re.search(args[i], val, flags=re.I):
                return formatter.vformat('{'+args[i+1].strip() + '}', [], kwargs)
            i += 2


class BuiltinTest(BuiltinFormatterFunction):
    name = 'test'
    arg_count = 3
    category = 'If-then-else'
    __doc__ = doc = _('test(val, text if not empty, text if empty) -- return `text if not '
            'empty` if val is not empty, otherwise return `text if empty`')

    def evaluate(self, formatter, kwargs, mi, locals, val, value_if_set, value_not_set):
        if val:
            return value_if_set
        else:
            return value_not_set


class BuiltinContains(BuiltinFormatterFunction):
    name = 'contains'
    arg_count = 4
    category = 'If-then-else'
    __doc__ = doc = _('contains(val, pattern, text if match, text if not match) -- checks '
            'if val contains matches for the regular expression `pattern`. '
            'Returns `text if match` if matches are found, otherwise it returns '
            '`text if no match`')

    def evaluate(self, formatter, kwargs, mi, locals,
                 val, test, value_if_present, value_if_not):
        if re.search(test, val, flags=re.I):
            return value_if_present
        else:
            return value_if_not


class BuiltinSwitch(BuiltinFormatterFunction):
    name = 'switch'
    arg_count = -1
    category = 'Iterating over values'
    __doc__ = doc = _('switch(val, [pattern, value,]+ else_value) -- '
            'for each `pattern, value` pair, checks if `val` matches '
            'the regular expression `pattern` and if so, returns that '
            '`value`. If no pattern matches, then `else_value` is returned. '
            'You can have as many `pattern, value` pairs as you want')

    def evaluate(self, formatter, kwargs, mi, locals, val, *args):
        if (len(args) % 2) != 1:
            raise ValueError(_('switch requires an even number of arguments'))
        i = 0
        while i < len(args):
            if i + 1 >= len(args):
                return args[i]
            if re.search(args[i], val, flags=re.I):
                return args[i+1]
            i += 2


class BuiltinSwitchIf(BuiltinFormatterFunction):
    name = 'switch_if'
    arg_count = -1
    category = 'Iterating over values'
    __doc__ = doc = _('switch_if([test_expression, value_expression,]+ else_expression) -- '
        'for each "test_expression, value_expression" pair, checks if test_expression '
        'is True (non-empty) and if so returns the result of value_expression. '
        'If no test_expression is True then the result of else_expression is returned. '
        'You can have as many "test_expression, value_expression" pairs as you want.')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        if (len(args) % 2) != 1:
            raise ValueError(_('switch_if requires an odd number of arguments'))
        # We shouldn't get here because the function is inlined. However, someone
        # might call it directly.
        i = 0
        while i < len(args):
            if i + 1 >= len(args):
                return args[i]
            if args[i]:
                return args[i+1]
            i += 2


class BuiltinStrcatMax(BuiltinFormatterFunction):
    name = 'strcat_max'
    arg_count = -1
    category = 'String manipulation'
    __doc__ = doc = _('strcat_max(max, string1 [, prefix2, string2]*) -- '
            'Returns a string formed by concatenating the arguments. The '
            'returned value is initialized to string1. `Prefix, string` '
            'pairs are added to the end of the value as long as the '
            'resulting string length is less than `max`. String1 is returned '
            'even if string1 is longer than max. You can pass as many '
            '`prefix, string` pairs as you wish.')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        if len(args) < 2:
            raise ValueError(_('strcat_max requires 2 or more arguments'))
        if (len(args) % 2) != 0:
            raise ValueError(_('strcat_max requires an even number of arguments'))
        try:
            max = int(args[0])
        except:
            raise ValueError(_('first argument to strcat_max must be an integer'))

        i = 2
        result = args[1]
        try:
            while i < len(args):
                if (len(result) + len(args[i]) + len(args[i+1])) > max:
                    break
                result = result + args[i] + args[i+1]
                i += 2
        except:
            pass
        return result.strip()


class BuiltinInList(BuiltinFormatterFunction):
    name = 'in_list'
    arg_count = -1
    category = 'List lookup'
    __doc__ = doc = _('in_list(val, separator, [ pattern, found_val, ]+ not_found_val) -- '
            'treating val as a list of items separated by separator, '
            'if the pattern matches any of the list values then return found_val.'
            'If the pattern matches no list value then return '
            'not_found_val. The pattern and found_value pairs can be repeated as '
            'many times as desired. The patterns are checked in order. The '
            'found_val for the first match is returned. '
            'Aliases: in_list(), list_contains()')
    aliases = ['list_contains']

    def evaluate(self, formatter, kwargs, mi, locals, val, sep, *args):
        if (len(args) % 2) != 1:
            raise ValueError(_('in_list requires an odd number of arguments'))
        l = [v.strip() for v in val.split(sep) if v.strip()]
        i = 0
        while i < len(args):
            if i + 1 >= len(args):
                return args[i]
            sf = args[i]
            fv = args[i+1]
            if l:
                for v in l:
                    if re.search(sf, v, flags=re.I):
                        return fv
            i += 2


class BuiltinStrInList(BuiltinFormatterFunction):
    name = 'str_in_list'
    arg_count = -1
    category = 'List lookup'
    __doc__ = doc = _('str_in_list(val, separator, [string, found_val, ]+ not_found_val) -- '
            'treating val as a list of items separated by separator, if the '
            'string matches any of the list values then return found_val.'
            'If the string matches no list value then return '
            'not_found_val. The comparison is exact match (not contains) and is '
            'case insensitive. The string and found_value pairs can be repeated as '
            'many times as desired. The patterns are checked in order. The '
            'found_val for the first match is returned.')

    def evaluate(self, formatter, kwargs, mi, locals, val, sep, *args):
        if (len(args) % 2) != 1:
            raise ValueError(_('str_in_list requires an odd number of arguments'))
        l = [v.strip() for v in val.split(sep) if v.strip()]
        i = 0
        while i < len(args):
            if i + 1 >= len(args):
                return args[i]
            sf = args[i]
            fv = args[i+1]
            c = [v.strip() for v in sf.split(sep) if v.strip()]
            if l:
                for v in l:
                    for t in c:
                        if strcmp(t, v) == 0:
                            return fv
            i += 2


class BuiltinIdentifierInList(BuiltinFormatterFunction):
    name = 'identifier_in_list'
    arg_count = -1
    category = 'List lookup'
    __doc__ = doc = _('identifier_in_list(val, id_name [, found_val, not_found_val]) -- '
            'treat val as a list of identifiers separated by commas. An identifier '
            'has the format "id_name:value". The id_name parameter is the id_name '
            'text to search for, either "id_name" or "id_name:regexp". The first case '
            'matches if there is any identifier matching that id_name. The second '
            'case matches if id_name matches an identifier and the regexp '
            'matches the identifier\'s value. If found_val and not_found_val '
            'are provided then if there is a match then return found_val, otherwise '
            'return not_found_val. If found_val and not_found_val are not '
            'provided then if there is a match then return the identifier:value '
            'pair, otherwise the empty string.')

    def evaluate(self, formatter, kwargs, mi, locals, val, ident, *args):
        if len(args) == 0:
            fv_is_id = True
            nfv = ''
        elif len(args) == 2:
            fv_is_id = False
            fv = args[0]
            nfv = args[1]
        else:
            raise ValueError(_("{} requires 2 or 4 arguments").format(self.name))

        l = [v.strip() for v in val.split(',') if v.strip()]
        (id_, __, regexp) = ident.partition(':')
        if not id_:
            return nfv
        for candidate in l:
            i, __, v =  candidate.partition(':')
            if v and i == id_:
                if not regexp or re.search(regexp, v, flags=re.I):
                    return candidate if fv_is_id else fv
        return nfv


class BuiltinRe(BuiltinFormatterFunction):
    name = 're'
    arg_count = 3
    category = 'String manipulation'
    __doc__ = doc = _('re(val, pattern, replacement) -- return val after applying '
            'the regular expression. All instances of `pattern` are replaced '
            'with `replacement`. As in all of calibre, these are '
            'Python-compatible regular expressions')

    def evaluate(self, formatter, kwargs, mi, locals, val, pattern, replacement):
        return re.sub(pattern, replacement, val, flags=re.I)


class BuiltinReGroup(BuiltinFormatterFunction):
    name = 're_group'
    arg_count = -1
    category = 'String manipulation'
    __doc__ = doc = _('re_group(val, pattern [, template_for_group]*) -- '
            'return a string made by applying the regular expression pattern '
            'to the val and replacing each matched instance with the string '
            'computed by replacing each matched group by the value returned '
            'by the corresponding template. The original matched value for the '
            'group is available as $. In template program mode, like for '
            'the template and the eval functions, you use [[ for { and ]] for }.'
            ' The following example in template program mode looks for series '
            'with more than one word and uppercases the first word: '
            "{series:'re_group($, \"(\\S* )(.*)\", \"[[$:uppercase()]]\", \"[[$]]\")'}")

    def evaluate(self, formatter, kwargs, mi, locals, val, pattern, *args):
        from calibre.utils.formatter import EvalFormatter

        def repl(mo):
            res = ''
            if mo and mo.lastindex:
                for dex in range(0, mo.lastindex):
                    gv = mo.group(dex+1)
                    if gv is None:
                        continue
                    if len(args) > dex:
                        template = args[dex].replace('[[', '{').replace(']]', '}')
                        res += EvalFormatter().safe_format(template, {'$': gv},
                                           'EVAL', None, strip_results=False)
                    else:
                        res += gv
            return res
        return re.sub(pattern, repl, val, flags=re.I)


class BuiltinSwapAroundComma(BuiltinFormatterFunction):
    name = 'swap_around_comma'
    arg_count = 1
    category = 'String manipulation'
    __doc__ = doc = _('swap_around_comma(val) -- given a value of the form '
            '"B, A", return "A B". This is most useful for converting names '
            'in LN, FN format to FN LN. If there is no comma, the function '
            'returns val unchanged')

    def evaluate(self, formatter, kwargs, mi, locals, val):
        return re.sub(r'^(.*?),\s*(.*$)', r'\2 \1', val, flags=re.I).strip()


class BuiltinIfempty(BuiltinFormatterFunction):
    name = 'ifempty'
    arg_count = 2
    category = 'If-then-else'
    __doc__ = doc = _('ifempty(val, text if empty) -- return val if val is not empty, '
            'otherwise return `text if empty`')

    def evaluate(self, formatter, kwargs, mi, locals, val, value_if_empty):
        if val:
            return val
        else:
            return value_if_empty


class BuiltinShorten(BuiltinFormatterFunction):
    name = 'shorten'
    arg_count = 4
    category = 'String manipulation'
    __doc__ = doc = _('shorten(val, left chars, middle text, right chars) -- Return a '
            'shortened version of val, consisting of `left chars` '
            'characters from the beginning of val, followed by '
            '`middle text`, followed by `right chars` characters from '
            'the end of the string. `Left chars` and `right chars` must be '
            'integers. For example, assume the title of the book is '
            '`Ancient English Laws in the Times of Ivanhoe`, and you want '
            'it to fit in a space of at most 15 characters. If you use '
            '{title:shorten(9,-,5)}, the result will be `Ancient E-anhoe`. '
            'If the field\'s length is less than left chars + right chars + '
            'the length of `middle text`, then the field will be used '
            'intact. For example, the title `The Dome` would not be changed.')

    def evaluate(self, formatter, kwargs, mi, locals,
                 val, leading, center_string, trailing):
        l = max(0, int(leading))
        t = max(0, int(trailing))
        if len(val) > l + len(center_string) + t:
            return val[0:l] + center_string + ('' if t == 0 else val[-t:])
        else:
            return val


class BuiltinCount(BuiltinFormatterFunction):
    name = 'count'
    arg_count = 2
    category = 'List manipulation'
    aliases = ['list_count']

    __doc__ = doc = _('count(val, separator) -- interprets the value as a list of items '
            'separated by `separator`, returning the number of items in the '
            'list. Most lists use a comma as the separator, but authors '
            'uses an ampersand. Examples: {tags:count(,)}, {authors:count(&)}. '
            'Aliases: count(), list_count()')

    def evaluate(self, formatter, kwargs, mi, locals, val, sep):
        return str(len([v for v in val.split(sep) if v]))


class BuiltinListCountMatching(BuiltinFormatterFunction):
    name = 'list_count_matching'
    arg_count = 3
    category = 'List manipulation'
    aliases = ['count_matching']

    __doc__ = doc = _('list_count_matching(list, pattern, separator) -- '
            "interprets 'list' as a list of items separated by 'separator', "
            'returning the number of items in the list that match the regular '
            "expression 'pattern'. Aliases: list_count_matching(), count_matching()")

    def evaluate(self, formatter, kwargs, mi, locals, list_, pattern, sep):
        res = 0
        for v in [x.strip() for x in list_.split(sep) if x.strip()]:
            if re.search(pattern, v, flags=re.I):
                res += 1
        return str(res)


class BuiltinListitem(BuiltinFormatterFunction):
    name = 'list_item'
    arg_count = 3
    category = 'List lookup'
    __doc__ = doc = _('list_item(val, index, separator) -- interpret the value as a list of '
            'items separated by `separator`, returning the `index`th item. '
            'The first item is number zero. The last item can be returned '
            'using `list_item(-1,separator)`. If the item is not in the list, '
            'then the empty value is returned. The separator has the same '
            'meaning as in the count function.')

    def evaluate(self, formatter, kwargs, mi, locals, val, index, sep):
        if not val:
            return ''
        index = int(index)
        val = val.split(sep)
        try:
            return val[index].strip()
        except:
            return ''


class BuiltinSelect(BuiltinFormatterFunction):
    name = 'select'
    arg_count = 2
    category = 'List lookup'
    __doc__ = doc = _('select(val, key) -- interpret the value as a comma-separated list '
            'of items, with the items being "id:value". Find the pair with the '
            'id equal to key, and return the corresponding value. Returns the '
            'empty string if no match is found.'
            )

    def evaluate(self, formatter, kwargs, mi, locals, val, key):
        if not val:
            return ''
        vals = [v.strip() for v in val.split(',')]
        tkey = key+':'
        for v in vals:
            if v.startswith(tkey):
                return v[len(tkey):]
        return ''


class BuiltinApproximateFormats(BuiltinFormatterFunction):
    name = 'approximate_formats'
    arg_count = 0
    category = 'Get values from metadata'
    __doc__ = doc = _('approximate_formats() -- return a comma-separated '
                  'list of formats that at one point were associated with the '
                  'book. There is no guarantee that this list is correct, '
                  'although it probably is. '
                  'This function can be called in template program mode using '
                  'the template "{:\'approximate_formats()\'}". '
                  'Note that format names are always uppercase, as in EPUB. '
                  'This function works only in the GUI. If you want to use these values '
                  'in save-to-disk or send-to-device templates then you '
                  'must make a custom "Column built from other columns", use '
                  'the function in that column\'s template, and use that '
                  'column\'s value in your save/send templates'
            )

    def evaluate(self, formatter, kwargs, mi, locals):
        if hasattr(mi, '_proxy_metadata'):
            fmt_data = mi._proxy_metadata.db_approx_formats
            if not fmt_data:
                return ''
            data = sorted(fmt_data)
            return ','.join(v.upper() for v in data)
        self.only_in_gui_error()


class BuiltinFormatsModtimes(BuiltinFormatterFunction):
    name = 'formats_modtimes'
    arg_count = 1
    category = 'Get values from metadata'
    __doc__ = doc = _('formats_modtimes(date_format) -- return a comma-separated '
                  'list of colon-separated items representing modification times '
                  'for the formats of a book. The date_format parameter '
                  'specifies how the date is to be formatted. See the '
                  'format_date function for details. You can use the select '
                  'function to get the mod time for a specific '
                  'format. Note that format names are always uppercase, '
                  'as in EPUB.'
            )

    def evaluate(self, formatter, kwargs, mi, locals, fmt):
        fmt_data = mi.get('format_metadata', {})
        try:
            data = sorted(fmt_data.items(), key=lambda x:x[1]['mtime'], reverse=True)
            return ','.join(k.upper()+':'+format_date(v['mtime'], fmt)
                        for k,v in data)
        except:
            return ''


class BuiltinFormatsSizes(BuiltinFormatterFunction):
    name = 'formats_sizes'
    arg_count = 0
    category = 'Get values from metadata'
    __doc__ = doc = _('formats_sizes() -- return a comma-separated list of '
                      'colon-separated items representing sizes in bytes '
                      'of the formats of a book. You can use the select '
                      'function to get the size for a specific '
                      'format. Note that format names are always uppercase, '
                      'as in EPUB.'
            )

    def evaluate(self, formatter, kwargs, mi, locals):
        fmt_data = mi.get('format_metadata', {})
        try:
            return ','.join(k.upper()+':'+str(v['size']) for k,v in iteritems(fmt_data))
        except:
            return ''


class BuiltinFormatsPaths(BuiltinFormatterFunction):
    name = 'formats_paths'
    arg_count = 0
    category = 'Get values from metadata'
    __doc__ = doc = _('formats_paths() -- return a comma-separated list of '
                      'colon-separated items representing full path to '
                      'the formats of a book. You can use the select '
                      'function to get the path for a specific '
                      'format. Note that format names are always uppercase, '
                      'as in EPUB.')

    def evaluate(self, formatter, kwargs, mi, locals):
        fmt_data = mi.get('format_metadata', {})
        try:
            return ','.join(k.upper()+':'+str(v['path']) for k,v in iteritems(fmt_data))
        except:
            return ''


class BuiltinHumanReadable(BuiltinFormatterFunction):
    name = 'human_readable'
    arg_count = 1
    category = 'Formatting values'
    __doc__ = doc = _('human_readable(v) -- return a string '
                      'representing the number v in KB, MB, GB, etc.'
            )

    def evaluate(self, formatter, kwargs, mi, locals, val):
        try:
            return human_readable(round(float(val)))
        except:
            return ''


class BuiltinFormatNumber(BuiltinFormatterFunction):
    name = 'format_number'
    arg_count = 2
    category = 'Formatting values'
    __doc__ = doc = _('format_number(v, template) -- format the number v using '
                  'a Python formatting template such as "{0:5.2f}" or '
                  '"{0:,d}" or "${0:5,.2f}". The field_name part of the '
                  'template must be a 0 (zero) (the "{0:" in the above examples). '
                  'See the template language and Python documentation for more '
                  'examples. You can leave off the leading "{0:" and trailing '
                  '"}" if the template contains only a format. Returns the empty '
                  'string if formatting fails.'
            )

    def evaluate(self, formatter, kwargs, mi, locals, val, template):
        if val == '' or val == 'None':
            return ''
        if '{' not in template:
            template = '{0:' + template + '}'
        try:
            v1 = float(val)
        except:
            return ''
        try:  # Try formatting the value as a float
            return template.format(v1)
        except:
            pass
        try:  # Try formatting the value as an int
            v2 = trunc(v1)
            if v2 == v1:
                return template.format(v2)
        except:
            pass
        return ''


class BuiltinSublist(BuiltinFormatterFunction):
    name = 'sublist'
    arg_count = 4
    category = 'List manipulation'
    __doc__ = doc = _('sublist(val, start_index, end_index, separator) -- interpret the '
            'value as a list of items separated by `separator`, returning a '
            'new list made from the `start_index` to the `end_index` item. '
            'The first item is number zero. If an index is negative, then it '
            'counts from the end of the list. As a special case, an end_index '
            'of zero is assumed to be the length of the list. Examples using '
            'basic template mode and assuming that the tags column (which is '
            'comma-separated) contains "A, B, C": '
            '{tags:sublist(0,1,\\\\,)} returns "A". '
            '{tags:sublist(-1,0,\\\\,)} returns "C". '
            '{tags:sublist(0,-1,\\\\,)} returns "A, B".'
            )

    def evaluate(self, formatter, kwargs, mi, locals, val, start_index, end_index, sep):
        if not val:
            return ''
        si = int(start_index)
        ei = int(end_index)
        # allow empty list items so counts are what the user expects
        val = [v.strip() for v in val.split(sep)]

        if sep == ',':
            sep = ', '
        try:
            if ei == 0:
                return sep.join(val[si:])
            else:
                return sep.join(val[si:ei])
        except:
            return ''


class BuiltinSubitems(BuiltinFormatterFunction):
    name = 'subitems'
    arg_count = 3
    category = 'List manipulation'
    __doc__ = doc = _('subitems(val, start_index, end_index) -- This function is used to '
            'break apart lists of items such as genres. It interprets the value '
            'as a comma-separated list of items, where each item is a period-'
            'separated list. Returns a new list made by first finding all the '
            'period-separated items, then for each such item extracting the '
            '`start_index` to the `end_index` components, then combining '
            'the results back together. The first component in a period-'
            'separated list has an index of zero. If an index is negative, '
            'then it counts from the end of the list. As a special case, an '
            'end_index of zero is assumed to be the length of the list. '
            'Example using basic template mode and assuming a #genre value of '
            '"A.B.C": {#genre:subitems(0,1)} returns "A". {#genre:subitems(0,2)} '
            'returns "A.B". {#genre:subitems(1,0)} returns "B.C". Assuming a #genre '
            'value of "A.B.C, D.E.F", {#genre:subitems(0,1)} returns "A, D". '
            '{#genre:subitems(0,2)} returns "A.B, D.E"')

    period_pattern = re.compile(r'(?<=[^\.\s])\.(?=[^\.\s])', re.U)

    def evaluate(self, formatter, kwargs, mi, locals, val, start_index, end_index):
        if not val:
            return ''
        si = int(start_index)
        ei = int(end_index)
        has_periods = '.' in val
        items = [v.strip() for v in val.split(',') if v.strip()]
        rv = set()
        for item in items:
            if has_periods and '.' in item:
                components = self.period_pattern.split(item)
            else:
                components = [item]
            try:
                if ei == 0:
                    t = '.'.join(components[si:]).strip()
                else:
                    t = '.'.join(components[si:ei]).strip()
                if t:
                    rv.add(t)
            except:
                pass
        return ', '.join(sorted(rv, key=sort_key))


class BuiltinFormatDate(BuiltinFormatterFunction):
    name = 'format_date'
    arg_count = 2
    category = 'Formatting values'
    __doc__ = doc = _('format_date(val, format_string) -- format the value, '
            'which must be a date, using the format_string, returning a string. '
            'The formatting codes are: '
            'd    : the day as number without a leading zero (1 to 31) '
            'dd   : the day as number with a leading zero (01 to 31) '
            'ddd  : the abbreviated localized day name (e.g. "Mon" to "Sun"). '
            'dddd : the long localized day name (e.g. "Monday" to "Sunday"). '
            'M    : the month as number without a leading zero (1 to 12). '
            'MM   : the month as number with a leading zero (01 to 12) '
            'MMM  : the abbreviated localized month name (e.g. "Jan" to "Dec"). '
            'MMMM : the long localized month name (e.g. "January" to "December"). '
            'yy   : the year as two digit number (00 to 99). '
            'yyyy : the year as four digit number. '
            'h    : the hours without a leading 0 (0 to 11 or 0 to 23, depending on am/pm) '
            'hh   : the hours with a leading 0 (00 to 11 or 00 to 23, depending on am/pm) '
            'm    : the minutes without a leading 0 (0 to 59) '
            'mm   : the minutes with a leading 0 (00 to 59) '
            's    : the seconds without a leading 0 (0 to 59) '
            'ss   : the seconds with a leading 0 (00 to 59) '
            'ap   : use a 12-hour clock instead of a 24-hour clock, with "ap" replaced by the localized string for am or pm '
            'AP   : use a 12-hour clock instead of a 24-hour clock, with "AP" replaced by the localized string for AM or PM '
            'iso  : the date with time and timezone. Must be the only format present '
            'to_number: the date as a floating point number '
            'from_number[:fmt]: format the timestamp using fmt if present otherwise iso')

    def evaluate(self, formatter, kwargs, mi, locals, val, format_string):
        if not val or val == 'None':
            return ''
        try:
            if format_string == 'to_number':
                s = parse_date(val).timestamp()
            elif format_string.startswith('from_number'):
                val = datetime.fromtimestamp(float(val))
                f = format_string[12:]
                s = format_date(val, f if f else 'iso')
            else:
                s = format_date(parse_date(val), format_string)
            return s
        except:
            s = 'BAD DATE'
        return s


class BuiltinFormatDateField(BuiltinFormatterFunction):
    name = 'format_date_field'
    arg_count = 2
    category = 'Formatting values'
    __doc__ = doc = _("format_date_field(field_name, format_string) -- format "
            "the value in the field 'field_name', which must be the lookup name "
            "of date field, either standard or custom. See 'format_date' for "
            "the formatting codes. This function is much faster than format_date "
            "and should be used when you are formatting the value in a field "
            "(column). It can't be used for computed dates or dates in string "
            "variables. Example: format_date_field('pubdate', 'yyyy.MM.dd')")

    def evaluate(self, formatter, kwargs, mi, locals, field, format_string):
        try:
            if field not in mi.all_field_keys():
                return _('Unknown field %s passed to function %s')%(field, 'format_date_field')
            val = mi.get(field, None)
            if val is None:
                s = ''
            elif format_string == 'to_number':
                s = val.timestamp()
            elif format_string.startswith('from_number'):
                val = datetime.fromtimestamp(float(val))
                f = format_string[12:]
                s = format_date(val, f if f else 'iso')
            else:
                s = format_date(val, format_string)
            return s
        except:
            traceback.print_exc()
            s = 'BAD DATE'
        return s


class BuiltinUppercase(BuiltinFormatterFunction):
    name = 'uppercase'
    arg_count = 1
    category = 'String case changes'
    __doc__ = doc = _('uppercase(val) -- return val in upper case')

    def evaluate(self, formatter, kwargs, mi, locals, val):
        return val.upper()


class BuiltinLowercase(BuiltinFormatterFunction):
    name = 'lowercase'
    arg_count = 1
    category = 'String case changes'
    __doc__ = doc = _('lowercase(val) -- return val in lower case')

    def evaluate(self, formatter, kwargs, mi, locals, val):
        return val.lower()


class BuiltinTitlecase(BuiltinFormatterFunction):
    name = 'titlecase'
    arg_count = 1
    category = 'String case changes'
    __doc__ = doc = _('titlecase(val) -- return val in title case')

    def evaluate(self, formatter, kwargs, mi, locals, val):
        return titlecase(val)


class BuiltinCapitalize(BuiltinFormatterFunction):
    name = 'capitalize'
    arg_count = 1
    category = 'String case changes'
    __doc__ = doc = _('capitalize(val) -- return val capitalized')

    def evaluate(self, formatter, kwargs, mi, locals, val):
        return capitalize(val)


class BuiltinBooksize(BuiltinFormatterFunction):
    name = 'booksize'
    arg_count = 0
    category = 'Get values from metadata'
    __doc__ = doc = _('booksize() -- return value of the size field. '
                'This function works only in the GUI. If you want to use this value '
                'in save-to-disk or send-to-device templates then you '
                'must make a custom "Column built from other columns", use '
                'the function in that column\'s template, and use that '
                'column\'s value in your save/send templates')

    def evaluate(self, formatter, kwargs, mi, locals):
        if hasattr(mi, '_proxy_metadata'):
            try:
                v = mi._proxy_metadata.book_size
                if v is not None:
                    return str(mi._proxy_metadata.book_size)
                return ''
            except:
                pass
            return ''
        self.only_in_gui_error()


class BuiltinOndevice(BuiltinFormatterFunction):
    name = 'ondevice'
    arg_count = 0
    category = 'Get values from metadata'
    __doc__ = doc = _('ondevice() -- return Yes if ondevice is set, otherwise return '
              'the empty string. This function works only in the GUI. If you want to '
              'use this value in save-to-disk or send-to-device templates then you '
              'must make a custom "Column built from other columns", use '
              'the function in that column\'s template, and use that '
              'column\'s value in your save/send templates')

    def evaluate(self, formatter, kwargs, mi, locals):
        if hasattr(mi, '_proxy_metadata'):
            if mi._proxy_metadata.ondevice_col:
                return _('Yes')
            return ''
        self.only_in_gui_error()


class BuiltinAnnotationCount(BuiltinFormatterFunction):
    name = 'annotation_count'
    arg_count = 0
    category = 'Get values from metadata'
    __doc__ = doc = _('annotation_count() -- return the total number of annotations '
                      'of all types attached to the current book. '
                      'This function works only in the GUI.')

    def evaluate(self, formatter, kwargs, mi, locals):
        c = self.get_database(mi).new_api.annotation_count_for_book(mi.id)
        return '' if c == 0 else str(c)


class BuiltinIsMarked(BuiltinFormatterFunction):
    name = 'is_marked'
    arg_count = 0
    category = 'Get values from metadata'
    __doc__ = doc = _("is_marked() -- check whether the book is 'marked' in "
                      "calibre. If it is then return the value of the mark, "
                      "either 'true' or the comma-separated list of named "
                      "marks. Returns '' if the book is not marked.")

    def evaluate(self, formatter, kwargs, mi, locals):
        c = self.get_database(mi).data.get_marked(mi.id)
        return c if c else ''


class BuiltinSeriesSort(BuiltinFormatterFunction):
    name = 'series_sort'
    arg_count = 0
    category = 'Get values from metadata'
    __doc__ = doc = _('series_sort() -- return the series sort value')

    def evaluate(self, formatter, kwargs, mi, locals):
        if mi.series:
            langs = mi.languages
            lang = langs[0] if langs else None
            return title_sort(mi.series, lang=lang)
        return ''


class BuiltinHasCover(BuiltinFormatterFunction):
    name = 'has_cover'
    arg_count = 0
    category = 'Get values from metadata'
    __doc__ = doc = _('has_cover() -- return Yes if the book has a cover, '
                      'otherwise return the empty string')

    def evaluate(self, formatter, kwargs, mi, locals):
        if mi.has_cover:
            return _('Yes')
        return ''


class BuiltinFirstNonEmpty(BuiltinFormatterFunction):
    name = 'first_non_empty'
    arg_count = -1
    category = 'Iterating over values'
    __doc__ = doc = _('first_non_empty(value [, value]*) -- '
            'returns the first value that is not empty. If all values are '
            'empty, then the empty string is returned. '
            'You can have as many values as you want.')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        i = 0
        while i < len(args):
            if args[i]:
                return args[i]
            i += 1
        return ''


class BuiltinAnd(BuiltinFormatterFunction):
    name = 'and'
    arg_count = -1
    category = 'Boolean'
    __doc__ = doc = _('and(value [, value]*) -- '
            'returns the string "1" if all values are not empty, otherwise '
            'returns the empty string. This function works well with test or '
            'first_non_empty. You can have as many values as you want. In many '
            'cases the && operator can replace this function.')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        i = 0
        while i < len(args):
            if not args[i]:
                return ''
            i += 1
        return '1'


class BuiltinOr(BuiltinFormatterFunction):
    name = 'or'
    arg_count = -1
    category = 'Boolean'
    __doc__ = doc = _('or(value [, value]*) -- '
            'returns the string "1" if any value is not empty, otherwise '
            'returns the empty string. This function works well with test or '
            'first_non_empty. You can have as many values as you want.  In many '
            'cases the || operator can replace this function.')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        i = 0
        while i < len(args):
            if args[i]:
                return '1'
            i += 1
        return ''


class BuiltinNot(BuiltinFormatterFunction):
    name = 'not'
    arg_count = 1
    category = 'Boolean'
    __doc__ = doc = _('not(value) -- '
            'returns the string "1" if the value is empty, otherwise '
            'returns the empty string. This function works well with test or '
            'first_non_empty.  In many cases the ! operator can replace this '
            'function.')

    def evaluate(self, formatter, kwargs, mi, locals, val):
        return '' if val else '1'


class BuiltinListJoin(BuiltinFormatterFunction):
    name = 'list_join'
    arg_count = -1
    category = 'List manipulation'
    __doc__ = doc = _("list_join(with_separator, list1, separator1 [, list2, separator2]*) -- "
                      "return a list made by joining the items in the source lists "
                      "(list1, etc) using with_separator between the items in the "
                      "result list. Items in each source list[123...] are separated "
                      "by the associated separator[123...]. A list can contain "
                      "zero values. It can be a field like publisher that is "
                      "single-valued, effectively a one-item list. Duplicates "
                      "are removed using a case-insensitive comparison. Items are "
                      "returned in the order they appear in the source lists. "
                      "If items on lists differ only in letter case then the last "
                      "is used. All separators can be more than one character.\n"
                      "Example:") + "\n\n" + (
                      "  program:\n"
                      "    list_join('#@#', $authors, '&', $tags, ',')\n\n") + _(
                      "You can use list_join on the results of previous "
                      "calls to list_join as follows:") + "\n" + (
                      "  program:\n\n"
                      "    a = list_join('#@#', $authors, '&', $tags, ',');\n"
                      "    b = list_join('#@#', a, '#@#', $#genre, ',', $#people, '&')\n\n") + _(
                      "You can use expressions to generate a list. For example, "
                      "assume you want items for authors and #genre, but "
                      "with the genre changed to the word 'Genre: ' followed by "
                      "the first letter of the genre, i.e. the genre 'Fiction' "
                      "becomes 'Genre: F'. The following will do that:") + "\n" + (
                      "  program:\n"
                      "    list_join('#@#', $authors, '&', list_re($#genre, ',', '^(.).*$', 'Genre: \\1'),  ',')")

    def evaluate(self, formatter, kwargs, mi, locals, with_separator, *args):
        if len(args) % 2 != 0:
            raise ValueError(
                _("Invalid 'List, separator' pairs. Every list must have one "
                  "associated separator"))

        # Starting in python 3.7 dicts preserve order so we don't need OrderedDict
        result = dict()
        i = 0
        while i < len(args):
            lst = [v.strip() for v in args[i].split(args[i+1]) if v.strip()]
            result.update({item.lower():item for item in lst})
            i += 2
        return with_separator.join(result.values())


class BuiltinListUnion(BuiltinFormatterFunction):
    name = 'list_union'
    arg_count = 3
    category = 'List manipulation'
    __doc__ = doc = _('list_union(list1, list2, separator) -- '
            'return a list made by merging the items in list1 and list2, '
            'removing duplicate items using a case-insensitive comparison. If '
            'items differ in case, the one in list1 is used. '
            'The items in list1 and list2 are separated by separator, as are '
            'the items in the returned list. Aliases: list_union(), merge_lists()')
    aliases = ['merge_lists']

    def evaluate(self, formatter, kwargs, mi, locals, list1, list2, separator):
        res = {icu_lower(l.strip()): l.strip() for l in list2.split(separator) if l.strip()}
        res.update({icu_lower(l.strip()): l.strip() for l in list1.split(separator) if l.strip()})
        if separator == ',':
            separator = ', '
        return separator.join(res.values())


class BuiltinRange(BuiltinFormatterFunction):
    name = 'range'
    arg_count = -1
    category = 'List manipulation'
    __doc__ = doc = _("range(start, stop, step, limit) -- "
                      "returns a list of numbers generated by looping over the "
                      "range specified by the parameters start, stop, and step, "
                      "with a maximum length of limit. The first value produced "
                      "is 'start'. Subsequent values next_v are "
                      "current_v+step. The loop continues while "
                      "next_v < stop assuming step is positive, otherwise "
                      "while next_v > stop. An empty list is produced if "
                      "start fails the test: start>=stop if step "
                      "is positive. The limit sets the maximum length of "
                      "the list and has a default of 1000. The parameters "
                      "start, step, and limit are optional. "
                      "Calling range() with one argument specifies stop. "
                      "Two arguments specify start and stop. Three arguments "
                      "specify start, stop, and step. Four "
                      "arguments specify start, stop, step and limit. "
                      "Examples: range(5) -> '0,1,2,3,4'. range(0,5) -> '0,1,2,3,4'. "
                      "range(-1,5) -> '-1,0,1,2,3,4'. range(1,5) -> '1,2,3,4'. "
                      "range(1,5,2) -> '1,3'. range(1,5,2,5) -> '1,3'. "
                      "range(1,5,2,1) -> error(limit exceeded).")

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        limit_val = 1000
        start_val = 0
        step_val = 1
        if len(args) == 1:
            stop_val = int(args[0] if args[0] and args[0] != 'None' else 0)
        elif len(args) == 2:
            start_val = int(args[0] if args[0] and args[0] != 'None' else 0)
            stop_val = int(args[1] if args[1] and args[1] != 'None' else 0)
        elif len(args) >= 3:
            start_val = int(args[0] if args[0] and args[0] != 'None' else 0)
            stop_val = int(args[1] if args[1] and args[1] != 'None' else 0)
            step_val = int(args[2] if args[2] and args[2] != 'None' else 0)
            if len(args) > 3:
                limit_val = int(args[3] if args[3] and args[3] != 'None' else 0)
        r = range(start_val, stop_val, step_val)
        if len(r) > limit_val:
            raise ValueError(
                _("{0}: length ({1}) longer than limit ({2})").format(
                            'range', len(r), str(limit_val)))
        return ', '.join([str(v) for v in r])


class BuiltinListRemoveDuplicates(BuiltinFormatterFunction):
    name = 'list_remove_duplicates'
    arg_count = 2
    category = 'List manipulation'
    __doc__ = doc = _('list_remove_duplicates(list, separator) -- '
            'return a list made by removing duplicate items in the source list. '
            'If items differ only in case, the last of them is returned. '
            'The items in source list are separated by separator, as are '
            'the items in the returned list.')

    def evaluate(self, formatter, kwargs, mi, locals, list_, separator):
        res = {icu_lower(l.strip()): l.strip() for l in list_.split(separator) if l.strip()}
        if separator == ',':
            separator = ', '
        return separator.join(res.values())


class BuiltinListDifference(BuiltinFormatterFunction):
    name = 'list_difference'
    arg_count = 3
    category = 'List manipulation'
    __doc__ = doc = _('list_difference(list1, list2, separator) -- '
            'return a list made by removing from list1 any item found in list2, '
            'using a case-insensitive comparison. The items in list1 and list2 '
            'are separated by separator, as are the items in the returned list.')

    def evaluate(self, formatter, kwargs, mi, locals, list1, list2, separator):
        l1 = [l.strip() for l in list1.split(separator) if l.strip()]
        l2 = {icu_lower(l.strip()) for l in list2.split(separator) if l.strip()}

        res = []
        for i in l1:
            if icu_lower(i) not in l2 and i not in res:
                res.append(i)
        if separator == ',':
            return ', '.join(res)
        return separator.join(res)


class BuiltinListIntersection(BuiltinFormatterFunction):
    name = 'list_intersection'
    arg_count = 3
    category = 'List manipulation'
    __doc__ = doc = _('list_intersection(list1, list2, separator) -- '
            'return a list made by removing from list1 any item not found in list2, '
            'using a case-insensitive comparison. The items in list1 and list2 '
            'are separated by separator, as are the items in the returned list.')

    def evaluate(self, formatter, kwargs, mi, locals, list1, list2, separator):
        l1 = [l.strip() for l in list1.split(separator) if l.strip()]
        l2 = {icu_lower(l.strip()) for l in list2.split(separator) if l.strip()}

        res = []
        for i in l1:
            if icu_lower(i) in l2 and i not in res:
                res.append(i)
        if separator == ',':
            return ', '.join(res)
        return separator.join(res)


class BuiltinListSort(BuiltinFormatterFunction):
    name = 'list_sort'
    arg_count = 3
    category = 'List manipulation'
    __doc__ = doc = _('list_sort(list, direction, separator) -- '
            'return list sorted using a case-insensitive sort. If direction is '
            'zero, the list is sorted ascending, otherwise descending. The list items '
            'are separated by separator, as are the items in the returned list.')

    def evaluate(self, formatter, kwargs, mi, locals, list1, direction, separator):
        res = [l.strip() for l in list1.split(separator) if l.strip()]
        if separator == ',':
            return ', '.join(sorted(res, key=sort_key, reverse=direction != "0"))
        return separator.join(sorted(res, key=sort_key, reverse=direction != "0"))


class BuiltinListEquals(BuiltinFormatterFunction):
    name = 'list_equals'
    arg_count = 6
    category = 'List manipulation'
    __doc__ = doc = _('list_equals(list1, sep1, list2, sep2, yes_val, no_val) -- '
            'return yes_val if list1 and list2 contain the same items, '
            'otherwise return no_val. The items are determined by splitting '
            'each list using the appropriate separator character (sep1 or '
            'sep2). The order of items in the lists is not relevant. '
            'The comparison is case insensitive.')

    def evaluate(self, formatter, kwargs, mi, locals, list1, sep1, list2, sep2, yes_val, no_val):
        s1 = {icu_lower(l.strip()) for l in list1.split(sep1) if l.strip()}
        s2 = {icu_lower(l.strip()) for l in list2.split(sep2) if l.strip()}
        if s1 == s2:
            return yes_val
        return no_val


class BuiltinListRe(BuiltinFormatterFunction):
    name = 'list_re'
    arg_count = 4
    category = 'List manipulation'
    __doc__ = doc = _('list_re(src_list, separator, include_re, opt_replace) -- '
            'Construct a list by first separating src_list into items using '
            'the separator character. For each item in the list, check if it '
            'matches include_re. If it does, then add it to the list to be '
            'returned. If opt_replace is not the empty string, then apply the '
            'replacement before adding the item to the returned list.')

    def evaluate(self, formatter, kwargs, mi, locals, src_list, separator, include_re, opt_replace):
        l = [l.strip() for l in src_list.split(separator) if l.strip()]
        res = []
        for item in l:
            if re.search(include_re, item, flags=re.I) is not None:
                if opt_replace:
                    item = re.sub(include_re, opt_replace, item)
                for i in [t.strip() for t in item.split(separator) if t.strip()]:
                    if i not in res:
                        res.append(i)
        if separator == ',':
            return ', '.join(res)
        return separator.join(res)


class BuiltinListReGroup(BuiltinFormatterFunction):
    name = 'list_re_group'
    arg_count = -1
    category = 'List manipulation'
    __doc__ = doc = _('list_re_group(src_list, separator, include_re, search_re [, group_template]+) -- '
                      'Like list_re except replacements are not optional. It '
                      'uses re_group(list_item, search_re, group_template, ...) when '
                      'doing the replacements on the resulting list.')

    def evaluate(self, formatter, kwargs, mi, locals, src_list, separator, include_re,
                 search_re, *args):
        from calibre.utils.formatter import EvalFormatter

        l = [l.strip() for l in src_list.split(separator) if l.strip()]
        res = []
        for item in l:
            def repl(mo):
                newval = ''
                if mo and mo.lastindex:
                    for dex in range(0, mo.lastindex):
                        gv = mo.group(dex+1)
                        if gv is None:
                            continue
                        if len(args) > dex:
                            template = args[dex].replace('[[', '{').replace(']]', '}')
                            newval += EvalFormatter().safe_format(template, {'$': gv},
                                              'EVAL', None, strip_results=False)
                        else:
                            newval += gv
                return newval
            if re.search(include_re, item, flags=re.I) is not None:
                item = re.sub(search_re, repl, item, flags=re.I)
                for i in [t.strip() for t in item.split(separator) if t.strip()]:
                    if i not in res:
                        res.append(i)
        if separator == ',':
            return ', '.join(res)
        return separator.join(res)


class BuiltinToday(BuiltinFormatterFunction):
    name = 'today'
    arg_count = 0
    category = 'Date functions'
    __doc__ = doc = _('today() -- '
            'return a date string for today. This value is designed for use in '
            'format_date or days_between, but can be manipulated like any '
            'other string. The date is in ISO format.')

    def evaluate(self, formatter, kwargs, mi, locals):
        return format_date(now(), 'iso')


class BuiltinDaysBetween(BuiltinFormatterFunction):
    name = 'days_between'
    arg_count = 2
    category = 'Date functions'
    __doc__ = doc = _('days_between(date1, date2) -- '
            'return the number of days between date1 and date2. The number is '
            'positive if date1 is greater than date2, otherwise negative. If '
            'either date1 or date2 are not dates, the function returns the '
            'empty string.')

    def evaluate(self, formatter, kwargs, mi, locals, date1, date2):
        try:
            d1 = parse_date(date1)
            if d1 == UNDEFINED_DATE:
                return ''
            d2 = parse_date(date2)
            if d2 == UNDEFINED_DATE:
                return ''
        except:
            return ''
        i = d1 - d2
        return '%.1f'%(i.days + (i.seconds/(24.0*60.0*60.0)))


class BuiltinDateArithmetic(BuiltinFormatterFunction):
    name = 'date_arithmetic'
    arg_count = -1
    category = 'Date functions'
    __doc__ = doc = _('date_arithmetic(date, calc_spec, fmt) -- '
            "Calculate a new date from 'date' using 'calc_spec'. Return the "
            "new date formatted according to optional 'fmt': if not supplied "
            "then the result will be in iso format. The calc_spec is a string "
            "formed by concatenating pairs of 'vW' (valueWhat) where 'v' is a "
            "possibly-negative number and W is one of the following letters: "
            "s: add 'v' seconds to 'date' "
            "m: add 'v' minutes to 'date' "
            "h: add 'v' hours to 'date' "
            "d: add 'v' days to 'date' "
            "w: add 'v' weeks to 'date' "
            "y: add 'v' years to 'date', where a year is 365 days. "
            "Example: '1s3d-1m' will add 1 second, add 3 days, and subtract 1 "
            "minute from 'date'.")

    calc_ops = {
        's': lambda v: timedelta(seconds=v),
        'm': lambda v: timedelta(minutes=v),
        'h': lambda v: timedelta(hours=v),
        'd': lambda v: timedelta(days=v),
        'w': lambda v: timedelta(weeks=v),
        'y': lambda v: timedelta(days=v * 365),
    }

    def evaluate(self, formatter, kwargs, mi, locals, date, calc_spec, fmt=None):
        try:
            d = parse_date(date)
            if d == UNDEFINED_DATE:
                return ''
            while calc_spec:
                mo = re.match(r'([-+\d]+)([smhdwy])', calc_spec)
                if mo is None:
                    raise ValueError(
                        _("{0}: invalid calculation specifier '{1}'").format(
                            'date_arithmetic', calc_spec))
                d += self.calc_ops[mo[2]](int(mo[1]))
                calc_spec = calc_spec[len(mo[0]):]
            return format_date(d, fmt if fmt else 'iso')
        except ValueError as e:
            raise e
        except Exception as e:
            traceback.print_exc()
            raise ValueError(_("{0}: error: {1}").format('date_arithmetic', str(e)))


class BuiltinLanguageStrings(BuiltinFormatterFunction):
    name = 'language_strings'
    arg_count = 2
    category = 'Get values from metadata'
    __doc__ = doc = _('language_strings(lang_codes, localize) -- '
            'return the strings for the language codes passed in lang_codes. '
            'If localize is zero, return the strings in English. If '
            'localize is not zero, return the strings in the language of '
            'the current locale. Lang_codes is a comma-separated list.')

    def evaluate(self, formatter, kwargs, mi, locals, lang_codes, localize):
        retval = []
        for c in [c.strip() for c in lang_codes.split(',') if c.strip()]:
            try:
                n = calibre_langcode_to_name(c, localize != '0')
                if n:
                    retval.append(n)
            except:
                pass
        return ', '.join(retval)


class BuiltinLanguageCodes(BuiltinFormatterFunction):
    name = 'language_codes'
    arg_count = 1
    category = 'Get values from metadata'
    __doc__ = doc = _('language_codes(lang_strings) -- '
            'return the language codes for the strings passed in lang_strings. '
            'The strings must be in the language of the current locale. '
            'Lang_strings is a comma-separated list.')

    def evaluate(self, formatter, kwargs, mi, locals, lang_strings):
        retval = []
        for c in [c.strip() for c in lang_strings.split(',') if c.strip()]:
            try:
                cv = canonicalize_lang(c)
                if cv:
                    retval.append(canonicalize_lang(cv))
            except:
                pass
        return ', '.join(retval)


class BuiltinCurrentLibraryName(BuiltinFormatterFunction):
    name = 'current_library_name'
    arg_count = 0
    category = 'Get values from metadata'
    __doc__ = doc = _('current_library_name() -- '
            'return the last name on the path to the current calibre library. '
            'This function can be called in template program mode using the '
            'template "{:\'current_library_name()\'}".')

    def evaluate(self, formatter, kwargs, mi, locals):
        from calibre.library import current_library_name
        return current_library_name()


class BuiltinCurrentLibraryPath(BuiltinFormatterFunction):
    name = 'current_library_path'
    arg_count = 0
    category = 'Get values from metadata'
    __doc__ = doc = _('current_library_path() -- '
                'return the path to the current calibre library. This function can '
                'be called in template program mode using the template '
                '"{:\'current_library_path()\'}".')

    def evaluate(self, formatter, kwargs, mi, locals):
        from calibre.library import current_library_path
        return current_library_path()


class BuiltinFinishFormatting(BuiltinFormatterFunction):
    name = 'finish_formatting'
    arg_count = 4
    category = 'Formatting values'
    __doc__ = doc = _('finish_formatting(val, fmt, prefix, suffix) -- apply the '
                      'format, prefix, and suffix to a value in the same way as '
                      'done in a template like `{series_index:05.2f| - |- }`. For '
                      'example, the following program produces the same output '
                      'as the above template: '
                      'program: finish_formatting(field("series_index"), "05.2f", " - ", " - ")')

    def evaluate(self, formatter, kwargs, mi, locals_, val, fmt, prefix, suffix):
        if not val:
            return val
        return prefix + formatter._do_format(val, fmt) + suffix


class BuiltinVirtualLibraries(BuiltinFormatterFunction):
    name = 'virtual_libraries'
    arg_count = 0
    category = 'Get values from metadata'
    __doc__ = doc = _('virtual_libraries() -- return a comma-separated list of '
                      'Virtual libraries that contain this book. This function '
                      'works only in the GUI. If you want to use these values '
                      'in save-to-disk or send-to-device templates then you '
                      'must make a custom "Column built from other columns", use '
                      'the function in that column\'s template, and use that '
                      'column\'s value in your save/send templates')

    def evaluate(self, formatter, kwargs, mi, locals_):
        db = self.get_database(mi)
        try:
            a = db.data.get_virtual_libraries_for_books((mi.id,))
            return ', '.join(a[mi.id])
        except ValueError as v:
            return str(v)


class BuiltinCurrentVirtualLibraryName(BuiltinFormatterFunction):
    name = 'current_virtual_library_name'
    arg_count = 0
    category = 'Get values from metadata'
    __doc__ = doc = _('current_virtual_library_name() -- '
            'return the name of the current virtual library if there is one, '
            'otherwise the empty string. Library name case is preserved. '
            'Example: "program: current_virtual_library_name()".')

    def evaluate(self, formatter, kwargs, mi, locals):
        return self.get_database(mi).data.get_base_restriction_name()


class BuiltinUserCategories(BuiltinFormatterFunction):
    name = 'user_categories'
    arg_count = 0
    category = 'Get values from metadata'
    __doc__ = doc = _('user_categories() -- return a comma-separated list of '
                      'the user categories that contain this book. This function '
                      'works only in the GUI. If you want to use these values '
                      'in save-to-disk or send-to-device templates then you '
                      'must make a custom "Column built from other columns", use '
                      'the function in that column\'s template, and use that '
                      'column\'s value in your save/send templates')

    def evaluate(self, formatter, kwargs, mi, locals_):
        if hasattr(mi, '_proxy_metadata'):
            cats = {k for k, v in iteritems(mi._proxy_metadata.user_categories) if v}
            cats = sorted(cats, key=sort_key)
            return ', '.join(cats)
        self.only_in_gui_error()


class BuiltinTransliterate(BuiltinFormatterFunction):
    name = 'transliterate'
    arg_count = 1
    category = 'String manipulation'
    __doc__ = doc = _('transliterate(a) -- Returns a string in a latin alphabet '
                      'formed by approximating the sound of the words in the '
                      'source string. For example, if the source is "{0}"'
                      ' the function returns "{1}".').format(
                          "Фёдор Миха́йлович Достоевский", 'Fiodor Mikhailovich Dostoievskii')

    def evaluate(self, formatter, kwargs, mi, locals, source):
        from calibre.utils.filenames import ascii_text
        return ascii_text(source)


class BuiltinGetLink(BuiltinFormatterFunction):
    name = 'get_link'
    arg_count = 2
    category = 'Template database functions'
    __doc__ = doc = _("get_link(field_name, field_value) -- fetch the link for "
                      "field 'field_name' with value 'field_value'. If there is "
                      "no attached link, return ''. Example: "
                      "get_link('tags', 'Fiction') returns the link attached to "
                      "the tag 'Fiction'.")

    def evaluate(self, formatter, kwargs, mi, locals, field_name, field_value):
        db = self.get_database(mi).new_api
        try:
            link = None
            item_id = db.get_item_id(field_name, field_value, case_sensitive=True)
            if item_id is not None:
                link = db.link_for(field_name, item_id)
            return link if link is not None else ''
        except Exception as e:
            traceback.print_exc()
            raise ValueError(e)


class BuiltinAuthorLinks(BuiltinFormatterFunction):
    name = 'author_links'
    arg_count = 2
    category = 'Get values from metadata'
    __doc__ = doc = _('author_links(val_separator, pair_separator) -- returns '
                      'a string containing a list of authors and that author\'s '
                      'link values in the '
                      'form author1 val_separator author1link pair_separator '
                      'author2 val_separator author2link etc. An author is '
                      'separated from its link value by the val_separator string '
                      'with no added spaces. author:linkvalue pairs are separated '
                      'by the pair_separator string argument with no added spaces. '
                      'It is up to you to choose separator strings that do '
                      'not occur in author names or links. An author is '
                      'included even if the author link is empty.')

    def evaluate(self, formatter, kwargs, mi, locals, val_sep, pair_sep):
        if hasattr(mi, '_proxy_metadata'):
            link_data = mi._proxy_metadata.link_maps
            if not link_data:
                return ''
            link_data = link_data.get('authors')
            if not link_data:
                return ''
            names = sorted(link_data.keys(), key=sort_key)
            return pair_sep.join(n + val_sep + link_data[n] for n in names)
        self.only_in_gui_error()


class BuiltinAuthorSorts(BuiltinFormatterFunction):
    name = 'author_sorts'
    arg_count = 1
    category = 'Get values from metadata'
    __doc__ = doc = _('author_sorts(val_separator) -- returns a string '
                      'containing a list of author\'s sort values for the '
                      'authors of the book. The sort is the one in the author '
                      'metadata (different from the author_sort in books). The '
                      'returned list has the form author sort 1 val_separator '
                      'author sort 2 etc. The author sort values in this list '
                      'are in the same order as the authors of the book. If '
                      'you want spaces around val_separator then include them '
                      'in the separator string')

    def evaluate(self, formatter, kwargs, mi, locals, val_sep):
        sort_data = mi.author_sort_map
        if not sort_data:
            return ''
        names = [sort_data.get(n) for n in mi.authors if n.strip()]
        return val_sep.join(n for n in names)


class BuiltinConnectedDeviceName(BuiltinFormatterFunction):
    name = 'connected_device_name'
    arg_count = 1
    category = 'Get values from metadata'
    __doc__ = doc = _("connected_device_name(storage_location) -- if a device is "
                      "connected then return the device name, otherwise return "
                      "the empty string. Each storage location on a device can "
                      "have a different name. The location names are 'main', "
                      "'carda' and 'cardb'. This function works only in the GUI.")

    def evaluate(self, formatter, kwargs, mi, locals, storage_location):
        # We can't use get_database() here because we need the device manager.
        # In other words, the function really does need the GUI
        with suppress(Exception):
            # Do the import here so that we don't entangle the GUI when using
            # command line functions
            from calibre.gui2.ui import get_gui
            info = get_gui().device_manager.get_current_device_information()
            if info is None:
                return ''
            try:
                if storage_location not in {'main', 'carda', 'cardb'}:
                    raise ValueError(
                         _('connected_device_name: invalid storage location "{}"'
                                    .format(storage_location)))
                info = info['info'][4]
                if storage_location not in info:
                    return ''
                return info[storage_location]['device_name']
            except Exception:
                traceback.print_exc()
                raise
        self.only_in_gui_error()


class BuiltinConnectedDeviceUUID(BuiltinFormatterFunction):
    name = 'connected_device_uuid'
    arg_count = 1
    category = 'Get values from metadata'
    __doc__ = doc = _("connected_device_uuid(storage_location) -- if a device is "
                      "connected then return the device uuid (unique id), "
                      "otherwise return the empty string. Each storage location "
                      "on a device has a different uuid. The location names are "
                      "'main', 'carda' and 'cardb'. This function works only in "
                      "the GUI.")

    def evaluate(self, formatter, kwargs, mi, locals, storage_location):
        # We can't use get_database() here because we need the device manager.
        # In other words, the function really does need the GUI
        with suppress(Exception):
            # Do the import here so that we don't entangle the GUI when using
            # command line functions
            from calibre.gui2.ui import get_gui
            info = get_gui().device_manager.get_current_device_information()
            if info is None:
                return ''
            try:
                if storage_location not in {'main', 'carda', 'cardb'}:
                    raise ValueError(
                         _('connected_device_name: invalid storage location "{}"'
                                    .format(storage_location)))
                info = info['info'][4]
                if storage_location not in info:
                    return ''
                return info[storage_location]['device_store_uuid']
            except Exception:
                traceback.print_exc()
                raise
        self.only_in_gui_error()


class BuiltinCheckYesNo(BuiltinFormatterFunction):
    name = 'check_yes_no'
    arg_count = 4
    category = 'If-then-else'
    __doc__ = doc = _('check_yes_no(field_name, is_undefined, is_false, is_true) '
                      '-- checks the value of the yes/no field named by the '
                      'lookup key field_name for a value specified by the '
                      'parameters, returning "yes" if a match is found, otherwise '
                      'returning an empty string. Set the parameter is_undefined, '
                      'is_false, or is_true to 1 (the number) to check that '
                      'condition, otherwise set it to 0. Example: '
                      'check_yes_no("#bool", 1, 0, 1) returns "yes" if the '
                      'yes/no field "#bool" is either undefined (neither True '
                      'nor False) or True. More than one of is_undefined, '
                      'is_false, or is_true can be set to 1.  This function '
                      'is usually used by the test() or is_empty() functions.')

    def evaluate(self, formatter, kwargs, mi, locals, field, is_undefined, is_false, is_true):
        # 'field' is a lookup name, not a value
        if field not in self.get_database(mi).field_metadata:
            raise ValueError(_("The column {} doesn't exist").format(field))
        res = getattr(mi, field, None)
        if res is None:
            if is_undefined == '1':
                return 'Yes'
            return ""
        if not isinstance(res, bool):
            raise ValueError(_('check_yes_no requires the field be a Yes/No custom column'))
        if is_false == '1' and not res:
            return 'Yes'
        if is_true == '1' and res:
            return 'Yes'
        return ""


class BuiltinRatingToStars(BuiltinFormatterFunction):
    name = 'rating_to_stars'
    arg_count = 2
    category = 'Formatting values'
    __doc__ = doc = _('rating_to_stars(value, use_half_stars) '
                      '-- Returns the rating as string of star characters. '
                      'The value is a number between 0 and 5. Set use_half_stars '
                      'to 1 if you want half star characters for custom ratings '
                      'columns that support non-integer ratings, for example 2.5.')

    def evaluate(self, formatter, kwargs, mi, locals, value, use_half_stars):
        if not value:
            return ''
        err_msg = _('The rating must be a number between 0 and 5')
        try:
            v = float(value) * 2
        except:
            raise ValueError(err_msg)
        if v < 0 or v > 10:
            raise ValueError(err_msg)
        from calibre.ebooks.metadata import rating_to_stars
        return rating_to_stars(v, use_half_stars == '1')


class BuiltinSwapAroundArticles(BuiltinFormatterFunction):
    name = 'swap_around_articles'
    arg_count = 2
    category = 'String manipulation'
    __doc__ = doc = _('swap_around_articles(val, separator) '
                      '-- returns the val with articles moved to the end. '
                      'The value can be a list, in which case each member '
                      'of the list is processed. If the value is a list then '
                      'you must provide the list value separator. If no '
                      'separator is provided then the value is treated as '
                      'being a single value, not a list.')

    def evaluate(self, formatter, kwargs, mi, locals, val, separator):
        if not val:
            return ''
        if not separator:
            return title_sort(val).replace(',', ';')
        result = []
        try:
            for v in [x.strip() for x in val.split(separator)]:
                result.append(title_sort(v).replace(',', ';'))
        except:
            traceback.print_exc()
        return separator.join(sorted(result, key=sort_key))


class BuiltinArguments(BuiltinFormatterFunction):
    name = 'arguments'
    arg_count = -1
    category = 'Other'
    __doc__ = doc = _('arguments(id[=expression] [, id[=expression]]*) '
                      '-- Used in a stored template to retrieve the arguments '
                      'passed in the call. It both declares and initializes '
                      'local variables, effectively parameters. The variables '
                      'are positional; they get the value of the parameter given '
                      'in the call in the same position. If the corresponding '
                      'parameter is not provided in the call then arguments '
                      'assigns that variable the provided default value. If '
                      'there is no default value then the variable is set to '
                      'the empty string.')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        # The arguments function is implemented in-line in the formatter
        raise NotImplementedError()


class BuiltinGlobals(BuiltinFormatterFunction):
    name = 'globals'
    arg_count = -1
    category = 'Other'
    __doc__ = doc = _('globals(id[=expression] [, id[=expression]]*) '
                      '-- Retrieves "global variables" that can be passed into '
                      'the formatter. It both declares and initializes local '
                      'variables with the names of the global variables passed '
                      'in. If the corresponding variable is not provided in '
                      'the passed-in globals then it assigns that variable the '
                      'provided default value. If there is no default value '
                      'then the variable is set to the empty string.')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        # The globals function is implemented in-line in the formatter
        raise NotImplementedError()


class BuiltinSetGlobals(BuiltinFormatterFunction):
    name = 'set_globals'
    arg_count = -1
    category = 'other'
    __doc__ = doc = _('set_globals(id[=expression] [, id[=expression]]*) '
                      '-- Sets "global variables" that can be passed into '
                      'the formatter. The globals are given the name of the id '
                      'passed in. The value of the id is used unless an '
                      'expression is provided.')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        # The globals function is implemented in-line in the formatter
        raise NotImplementedError()


class BuiltinFieldExists(BuiltinFormatterFunction):
    name = 'field_exists'
    arg_count = 1
    category = 'If-then-else'
    __doc__ = doc = _('field_exists(field_name) -- checks if a field '
                      '(column) named field_name exists, returning '
                      "'1' if so and '' if not.")

    def evaluate(self, formatter, kwargs, mi, locals, field_name):
        if field_name.lower() in mi.all_field_keys():
            return '1'
        return ''


class BuiltinCharacter(BuiltinFormatterFunction):
    name = 'character'
    arg_count = 1
    category = 'String manipulation'
    __doc__ = doc = _('character(character_name) -- returns the '
                      'character named by character_name. For example, '
                      r"character('newline') returns a newline character ('\n'). "
                      "The supported character names are 'newline', 'return', "
                      "'tab', and 'backslash'.")

    def evaluate(self, formatter, kwargs, mi, locals, character_name):
        # The globals function is implemented in-line in the formatter
        raise NotImplementedError()


class BuiltinToHex(BuiltinFormatterFunction):
    name = 'to_hex'
    arg_count = 1
    category = 'String manipulation'
    __doc__ = doc = _('to_hex(val) -- returns the string encoded in hex. '
                      'This is useful when constructing calibre URLs.')

    def evaluate(self, formatter, kwargs, mi, locals, val):
        return val.encode().hex()


class BuiltinUrlsFromIdentifiers(BuiltinFormatterFunction):
    name = 'urls_from_identifiers'
    arg_count = 2
    category = 'Formatting values'
    __doc__ = doc = _('urls_from_identifiers(identifiers, sort_results) -- given '
                      'a comma-separated list of identifiers, where an identifier '
                      'is a colon-separated pair of values (name:id_value), returns a '
                      'comma-separated list of HTML URLs generated from the '
                      'identifiers. The list not sorted if sort_results is 0 '
                      '(character or number), otherwise it is sorted alphabetically '
                      'by the identifier name. The URLs are generated in the same way '
                      'as the built-in identifiers column when shown in Book details.')

    def evaluate(self, formatter, kwargs, mi, locals, identifiers, sort_results):
        from calibre.ebooks.metadata.sources.identify import urls_from_identifiers
        try:
            v = {}
            for id_ in identifiers.split(','):
                if id_:
                    pair = id_.split(':', maxsplit=1)
                    if len(pair) == 2:
                        l = pair[0].strip()
                        r = pair[1].strip()
                        if l and r:
                            v[l] = r
            urls = urls_from_identifiers(v, sort_results=str(sort_results) != '0')
            p = prepare_string_for_xml
            a = partial(prepare_string_for_xml, attribute=True)
            links = [f'<a href="{a(url)}" title="{a(id_typ)}:{a(id_val)}">{p(name)}</a>'
                for name, id_typ, id_val, url in urls]
            return ', '.join(links)
        except Exception as e:
            return str(e)


class BuiltinBookCount(BuiltinFormatterFunction):
    name = 'book_count'
    arg_count = 2
    category = 'Template database functions'
    __doc__ = doc = _('book_count(query, use_vl) -- returns the count of '
                      'books found by searching for query. If use_vl is '
                      '0 (zero) then virtual libraries are ignored. This '
                      'function can be used only in the GUI.')

    def evaluate(self, formatter, kwargs, mi, locals, query, use_vl):
        from calibre.db.fields import rendering_composite_name
        if (not tweaks.get('allow_template_database_functions_in_composites', False) and
                formatter.global_vars.get(rendering_composite_name, None)):
            raise ValueError(_('The book_count() function cannot be used in a composite column'))
        db = self.get_database(mi)
        try:
            ids = db.search_getting_ids(query, None, use_virtual_library=use_vl != '0')
            return len(ids)
        except Exception:
            traceback.print_exc()


class BuiltinBookValues(BuiltinFormatterFunction):
    name = 'book_values'
    arg_count = 4
    category = 'Template database functions'
    __doc__ = doc = _('book_values(column, query, sep, use_vl) -- returns a list '
                      'of the values contained in the column "column", separated '
                      'by "sep", in the books found by searching for "query". '
                      'If use_vl is 0 (zero) then virtual libraries are ignored. '
                      'This function can be used only in the GUI.')

    def evaluate(self, formatter, kwargs, mi, locals, column, query, sep, use_vl):
        from calibre.db.fields import rendering_composite_name
        if (not tweaks.get('allow_template_database_functions_in_composites', False) and
                formatter.global_vars.get(rendering_composite_name, None)):
            raise ValueError(_('The book_values() function cannot be used in a composite column'))
        db = self.get_database(mi)
        if column not in db.field_metadata:
            raise ValueError(_("The column {} doesn't exist").format(column))
        try:
            ids = db.search_getting_ids(query, None, use_virtual_library=use_vl != '0')
            s = set()
            for id_ in ids:
                f = db.new_api.get_proxy_metadata(id_).get(column, None)
                if isinstance(f, (tuple, list)):
                    s.update(f)
                elif f is not None:
                    s.add(str(f))
            return sep.join(s)
        except Exception as e:
            raise ValueError(e)


class BuiltinHasExtraFiles(BuiltinFormatterFunction):
    name = 'has_extra_files'
    arg_count = -1
    category = 'Template database functions'
    __doc__ = doc = _("has_extra_files([pattern]) -- returns the count of extra "
                      "files, otherwise '' (the empty string). "
                      "If the optional parameter 'pattern' (a regular expression) "
                      "is supplied then the list is filtered to files that match "
                      "pattern before the files are counted. The pattern match is "
                      "case insensitive. "
                      'This function can be used only in the GUI.')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        if len(args) > 1:
            raise ValueError(_('Incorrect number of arguments for function {0}').format('has_extra_files'))
        pattern = args[0] if len(args) == 1 else None
        db = self.get_database(mi).new_api
        try:
            files = tuple(f.relpath.partition('/')[-1] for f in
                          db.list_extra_files(mi.id, use_cache=True, pattern=DATA_FILE_PATTERN))
            if pattern:
                r = re.compile(pattern, re.IGNORECASE)
                files = tuple(filter(r.search, files))
            return len(files) if len(files) > 0 else ''
        except Exception as e:
            traceback.print_exc()
            raise ValueError(e)


class BuiltinExtraFileNames(BuiltinFormatterFunction):
    name = 'extra_file_names'
    arg_count = -1
    category = 'Template database functions'
    __doc__ = doc = _("extra_file_names(sep [, pattern]) -- returns a sep-separated "
                      "list of extra files in the book's '{}/' folder. If the "
                      "optional parameter 'pattern', a regular expression, is "
                      "supplied then the list is filtered to files that match pattern. "
                      "The pattern match is case insensitive. "
                      'This function can be used only in the GUI.').format(DATA_DIR_NAME)

    def evaluate(self, formatter, kwargs, mi, locals, sep, *args):
        if len(args) > 1:
            raise ValueError(_('Incorrect number of arguments for function {0}').format('has_extra_files'))
        pattern = args[0] if len(args) == 1 else None
        db = self.get_database(mi).new_api
        try:
            files = tuple(f.relpath.partition('/')[-1] for f in
                          db.list_extra_files(mi.id, use_cache=True, pattern=DATA_FILE_PATTERN))
            if pattern:
                r = re.compile(pattern, re.IGNORECASE)
                files = tuple(filter(r.search, files))
            return sep.join(files)
        except Exception as e:
            traceback.print_exc()
            raise ValueError(e)


class BuiltinExtraFileSize(BuiltinFormatterFunction):
    name = 'extra_file_size'
    arg_count = 1
    category = 'Template database functions'
    __doc__ = doc = _("extra_file_size(file_name) -- returns the size in bytes of "
                      "the extra file 'file_name' in the book's '{}/' folder if "
                      "it exists, otherwise -1."
                      'This function can be used only in the GUI.').format(DATA_DIR_NAME)

    def evaluate(self, formatter, kwargs, mi, locals, file_name):
        db = self.get_database(mi).new_api
        try:
            q = posixpath.join(DATA_DIR_NAME, file_name)
            for f in db.list_extra_files(mi.id, use_cache=True, pattern=DATA_FILE_PATTERN):
                if f.relpath == q:
                    return str(f.stat_result.st_size)
            return str(-1)
        except Exception as e:
            traceback.print_exc()
            raise ValueError(e)


class BuiltinExtraFileModtime(BuiltinFormatterFunction):
    name = 'extra_file_modtime'
    arg_count = 2
    category = 'Template database functions'
    __doc__ = doc = _("extra_file_modtime(file_name, format_string) -- returns the "
                      "modification time of the extra file 'file_name' in the "
                      "book's '{}/' folder if it exists, otherwise -1.0. The "
                      "modtime is formatted according to 'format_string' "
                      "(see format_date()). If 'format_string' is empty, returns "
                      "the modtime as the floating point number of seconds since "
                      "the epoch. The epoch is OS dependent. "
                      "This function can be used only in the GUI.").format(DATA_DIR_NAME)

    def evaluate(self, formatter, kwargs, mi, locals, file_name, format_string):
        db = self.get_database(mi).new_api
        try:
            q = posixpath.join(DATA_DIR_NAME, file_name)
            for f in db.list_extra_files(mi.id, use_cache=True, pattern=DATA_FILE_PATTERN):
                if f.relpath == q:
                    val = f.stat_result.st_mtime
                    if format_string:
                        return format_date(datetime.fromtimestamp(val), format_string)
                    return str(val)
            return str(1.0)
        except Exception as e:
            traceback.print_exc()
            raise ValueError(e)


class BuiltinGetNote(BuiltinFormatterFunction):
    name = 'get_note'
    arg_count = 3
    category = 'Template database functions'
    __doc__ = doc = _("get_note(field_name, field_value, plain_text) -- fetch the "
                      "note for field 'field_name' with value 'field_value'. If "
                      "'plain_text' is empty, return the note's HTML including "
                      "images. If 'plain_text' is 1 (or '1'), return the "
                      "note's plain text. If the note doesn't exist, return the "
                      "empty string in both cases. Example: "
                      "get_note('tags', 'Fiction', '') returns the HTML of the "
                      "note attached to the tag 'Fiction'.")

    def evaluate(self, formatter, kwargs, mi, locals, field_name, field_value, plain_text):
        db = self.get_database(mi).new_api
        try:
            note = None
            item_id = db.get_item_id(field_name, field_value, case_sensitive=True)
            if item_id is not None:
                note = db.notes_data_for(field_name, item_id)
                if note is not None:
                    if plain_text == '1':
                        note = note['searchable_text'].partition('\n')[2]
                    else:
                        # Return the full HTML of the note, including all images
                        # as data: URLs. Reason: non-exported note html contains
                        # "calres://" URLs for images. These images won't render
                        # outside the context of the library where the note
                        # "lives". For example, they don't work in book jackets
                        # and book details from a different library. They also
                        # don't work in tooltips.

                        # This code depends on the note being wrapped in <body>
                        # tags by parse_html. The body is changed to a <div>.
                        # That means we often end up with <div><div> or some
                        # such, but that is OK
                        root = parse_html(note['doc'])
                        # There should be only one <body>
                        root = root.xpath('//body')[0]
                        # Change the body to a div
                        root.tag = 'div'
                        # Expand all the resources in the note
                        root = expand_note_resources(root, db.get_notes_resource)
                        note = html.tostring(root, encoding='unicode')
            return '' if note is None else note
        except Exception as e:
            traceback.print_exc()
            raise ValueError(e)


class BuiltinHasNote(BuiltinFormatterFunction):
    name = 'has_note'
    arg_count = 2
    category = 'Template database functions'
    __doc__ = doc = _("has_note(field_name, field_value) -- return '1' "
                      "if the value 'field_value' in the field 'field_name' "
                      "has an attached note, '' otherwise. Example: "
                      "has_note('tags', 'Fiction') returns '1' if the tag "
                      "'fiction' has an attached note, '' otherwise.")

    def evaluate(self, formatter, kwargs, mi, locals, field_name, field_value):
        db = self.get_database(mi).new_api
        note = None
        try:
            item_id = db.get_item_id(field_name, field_value, case_sensitive=True)
            if item_id is not None:
                note = db.notes_data_for(field_name, item_id)
        except Exception as e:
            traceback.print_exc()
            raise ValueError(e)
        return '1' if note is not None else ''


class BuiltinIsDarkMode(BuiltinFormatterFunction):
    name = 'is_dark_mode'
    arg_count = 0
    category = 'other'
    __doc__ = doc = _("is_dark_mode() -- Returns '1' if calibre is running "
                      "in dark mode, '' (the empty string) otherwise. This "
                      "function can be used in advanced color and icon rules "
                      "to choose different colors/icons according to the mode. "
                      "Example: {} ").format("if is_dark_mode() then 'dark.png' else 'light.png' fi")

    def evaluate(self, formatter, kwargs, mi, locals):
        try:
            # Import this here so that Qt isn't referenced unless this function is used.
            from calibre.gui2 import is_dark_theme
            return '1' if is_dark_theme() else ''
        except Exception:
            only_in_gui_error('is_dark_mode')


_formatter_builtins = [
    BuiltinAdd(), BuiltinAnd(), BuiltinApproximateFormats(), BuiltinArguments(),
    BuiltinAssign(),
    BuiltinAuthorLinks(), BuiltinAuthorSorts(), BuiltinBookCount(),
    BuiltinBookValues(), BuiltinBooksize(),
    BuiltinCapitalize(), BuiltinCharacter(), BuiltinCheckYesNo(), BuiltinCeiling(),
    BuiltinCmp(), BuiltinConnectedDeviceName(), BuiltinConnectedDeviceUUID(), BuiltinContains(),
    BuiltinCount(), BuiltinCurrentLibraryName(), BuiltinCurrentLibraryPath(),
    BuiltinCurrentVirtualLibraryName(), BuiltinDateArithmetic(),
    BuiltinDaysBetween(), BuiltinDivide(), BuiltinEval(),
    BuiltinExtraFileNames(), BuiltinExtraFileSize(), BuiltinExtraFileModtime(),
    BuiltinFirstNonEmpty(), BuiltinField(), BuiltinFieldExists(),
    BuiltinFinishFormatting(), BuiltinFirstMatchingCmp(), BuiltinFloor(),
    BuiltinFormatDate(), BuiltinFormatDateField(), BuiltinFormatNumber(), BuiltinFormatsModtimes(),
    BuiltinFormatsPaths(), BuiltinFormatsSizes(), BuiltinFractionalPart(),
    BuiltinGetLink(),
    BuiltinGetNote(), BuiltinGlobals(), BuiltinHasCover(), BuiltinHasExtraFiles(),
    BuiltinHasNote(), BuiltinHumanReadable(), BuiltinIdentifierInList(),
    BuiltinIfempty(), BuiltinIsDarkMode(), BuiltinLanguageCodes(), BuiltinLanguageStrings(),
    BuiltinInList(), BuiltinIsMarked(), BuiltinListCountMatching(),
    BuiltinListDifference(), BuiltinListEquals(), BuiltinListIntersection(),
    BuiltinListitem(), BuiltinListJoin(), BuiltinListRe(),
    BuiltinListReGroup(), BuiltinListRemoveDuplicates(), BuiltinListSort(),
    BuiltinListSplit(), BuiltinListUnion(),BuiltinLookup(),
    BuiltinLowercase(), BuiltinMod(), BuiltinMultiply(), BuiltinNot(), BuiltinOndevice(),
    BuiltinOr(), BuiltinPrint(), BuiltinRatingToStars(), BuiltinRange(),
    BuiltinRawField(), BuiltinRawList(),
    BuiltinRe(), BuiltinReGroup(), BuiltinRound(), BuiltinSelect(), BuiltinSeriesSort(),
    BuiltinSetGlobals(), BuiltinShorten(), BuiltinStrcat(), BuiltinStrcatMax(),
    BuiltinStrcmp(), BuiltinStrcmpcase(), BuiltinStrInList(), BuiltinStrlen(), BuiltinSubitems(),
    BuiltinSublist(),BuiltinSubstr(), BuiltinSubtract(), BuiltinSwapAroundArticles(),
    BuiltinSwapAroundComma(), BuiltinSwitch(), BuiltinSwitchIf(),
    BuiltinTemplate(), BuiltinTest(), BuiltinTitlecase(), BuiltinToday(),
    BuiltinToHex(), BuiltinTransliterate(), BuiltinUppercase(), BuiltinUrlsFromIdentifiers(),
    BuiltinUserCategories(), BuiltinVirtualLibraries(), BuiltinAnnotationCount()
]


class FormatterUserFunction(FormatterFunction):

    def __init__(self, name, doc, arg_count, program_text, object_type):
        self.object_type = object_type
        self.name = name
        self.doc = doc
        self.arg_count = arg_count
        self.program_text = program_text
        self.cached_compiled_text = None
        # Keep this for external code compatibility. Set it to True if we have a
        # python template function, otherwise false. This might break something
        # if the code depends on stored templates being in GPM.
        self.is_python = True if object_type is StoredObjectType.PythonFunction else False

    def to_pref(self):
        return [self.name, self.doc, self.arg_count, self.program_text]


tabs = re.compile(r'^\t*')


def function_object_type(thing):
    # 'thing' can be a preference instance, program text, or an already-compiled function
    if isinstance(thing, FormatterUserFunction):
        return thing.object_type
    if isinstance(thing, list):
        text = thing[3]
    else:
        text = thing
    if text.startswith('def'):
        return StoredObjectType.PythonFunction
    if text.startswith('program'):
        return StoredObjectType.StoredGPMTemplate
    if text.startswith('python'):
        return StoredObjectType.StoredPythonTemplate
    raise ValueError('Unknown program type in formatter function pref')


def function_pref_name(pref):
    return pref[0]


def compile_user_function(name, doc, arg_count, eval_func):
    typ = function_object_type(eval_func)
    if typ is not StoredObjectType.PythonFunction:
        return FormatterUserFunction(name, doc, arg_count, eval_func, typ)

    def replace_func(mo):
        return mo.group().replace('\t', '    ')

    func = '    ' + '\n    '.join([tabs.sub(replace_func, line)
                                   for line in eval_func.splitlines()])
    prog = '''
from calibre.utils.formatter_functions import FormatterUserFunction
from calibre.utils.formatter_functions import formatter_functions
class UserFunction(FormatterUserFunction):
''' + func
    locals_ = {}
    if DEBUG and tweaks.get('enable_template_debug_printing', False):
        print(prog)
    exec(prog, locals_)
    cls = locals_['UserFunction'](name, doc, arg_count, eval_func, typ)
    return cls


def compile_user_template_functions(funcs):
    compiled_funcs = {}
    for func in funcs:
        try:
            # Force a name conflict to test the logic
            # if func[0] == 'myFunc2':
            #     func[0] = 'myFunc3'

            # Compile the function so that the tab processing is done on the
            # source. This helps ensure that if the function already is defined
            # then white space differences don't cause them to compare differently

            cls = compile_user_function(*func)
            cls.object_type = function_object_type(func)
            compiled_funcs[cls.name] = cls
        except Exception:
            try:
                func_name = func[0]
            except Exception:
                func_name = 'Unknown'
            prints('**** Compilation errors in user template function "%s" ****' % func_name)
            traceback.print_exc(limit=10)
            prints('**** End compilation errors in %s "****"' % func_name)
    return compiled_funcs


def load_user_template_functions(library_uuid, funcs, precompiled_user_functions=None):
    unload_user_template_functions(library_uuid)
    if precompiled_user_functions:
        compiled_funcs = precompiled_user_functions
    else:
        compiled_funcs = compile_user_template_functions(funcs)
    formatter_functions().register_functions(library_uuid, list(compiled_funcs.values()))


def unload_user_template_functions(library_uuid):
    formatter_functions().unregister_functions(library_uuid)
