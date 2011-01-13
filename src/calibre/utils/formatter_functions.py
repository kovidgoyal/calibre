'''
Created on 13 Jan 2011

@author: charles
'''

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, traceback

from calibre.utils.titlecase import titlecase
from calibre.utils.icu import capitalize, strcmp


class FormatterFunctions(object):

    def __init__(self):
        self.builtins = {}
        self.functions = {}

    def register_builtin(self, func_class):
        if not isinstance(func_class, FormatterFunction):
            raise ValueError('Class %s is not an instance of FormatterFunction'%(
                                    func_class.__class__.__name__))
        name = func_class.name
        if name in self.functions:
            raise ValueError('Name %s already used'%name)
        self.builtins[name] = func_class
        self.functions[name] = func_class

    def register_function(self, func_class):
        if not isinstance(func_class, FormatterFunction):
            raise ValueError('Class %s is not an instance of FormatterFunction'%(
                                    func_class.__class__.__name__))
        name = func_class.name
        if name in self.functions:
            raise ValueError('Name %s already used'%name)
        self.functions[name] = func_class

    def get_builtins(self):
        return self.builtins

    def get_functions(self):
        return self.functions

    def reset_to_builtins(self):
        self.functions = dict([t for t in self.builtins.items()])

formatter_functions = FormatterFunctions()



class FormatterFunction(object):

    doc = _('No documentation provided')
    name = 'no name provided'
    arg_count = 0

    def __init__(self):
        formatter_functions.register_builtin(self)

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        raise NotImplementedError()

    def eval(self, formatter, kwargs, mi, locals, *args):
        try:
            ret = self.evaluate(formatter, kwargs, mi, locals, *args)
            if isinstance(ret, (str, unicode)):
                return ret
            if isinstance(ret, (int, float, bool)):
                return unicode(ret)
            if isinstance(ret, list):
                return ','.join(list)
        except:
            return _('Function threw exception' + traceback.format_exc())

class BuiltinStrcmp(FormatterFunction):
    name = 'strcmp'
    arg_count = 5
    doc = _('strcmp(x, y, lt, eq, gt) -- does a case-insensitive comparison of x '
            'and y as strings. Returns lt if x < y. Returns eq if x == y. '
            'Otherwise returns gt.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y, lt, eq, gt):
        v = strcmp(x, y)
        if v < 0:
            return lt
        if v == 0:
            return eq
        return gt

class BuiltinCmp(FormatterFunction):
    name = 'cmp'
    arg_count = 5
    doc =   _('cmp(x, y, lt, eq, gt) -- compares x and y after converting both to '
            'numbers. Returns lt if x < y. Returns eq if x == y. Otherwise returns gt.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y, lt, eq, gt):
        x = float(x if x else 0)
        y = float(y if y else 0)
        if x < y:
            return lt
        if x == y:
            return eq
        return gt

class BuiltinStrcat(FormatterFunction):
    name = 'strcat'
    arg_count = -1
    doc = _('strcat(a, b, ...) -- can take any number of arguments. Returns a '
            'string formed by concatenating all the arguments')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        i = 0
        res = ''
        for i in range(0, len(args)):
            res += args[i]
        return res

class BuiltinAdd(FormatterFunction):
    name = 'add'
    arg_count = 2
    doc = _('add(x, y) -- returns x + y. Throws an exception if either x or y are not numbers.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y):
        x = float(x if x else 0)
        y = float(y if y else 0)
        return unicode(x + y)

class BuiltinSubtract(FormatterFunction):
    name = 'subtract'
    arg_count = 2
    doc = _('subtract(x, y) -- returns x - y. Throws an exception if either x or y are not numbers.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y):
        x = float(x if x else 0)
        y = float(y if y else 0)
        return unicode(x - y)

class BuiltinMultiply(FormatterFunction):
    name = 'multiply'
    arg_count = 2
    doc = _('multiply(x, y) -- returns x * y. Throws an exception if either x or y are not numbers.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y):
        x = float(x if x else 0)
        y = float(y if y else 0)
        return unicode(x * y)

class BuiltinDivide(FormatterFunction):
    name = 'divide'
    arg_count = 2
    doc = _('divide(x, y) -- returns x / y. Throws an exception if either x or y are not numbers.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y):
        x = float(x if x else 0)
        y = float(y if y else 0)
        return unicode(x / y)

class BuiltinTemplate(FormatterFunction):
    name = 'template'
    arg_count = 1
    doc = _('template(x) -- evaluates x as a template. The evaluation is done '
            'in its own context, meaning that variables are not shared between '
            'the caller and the template evaluation. Because the { and } '
            'characters are special, you must use [[ for the { character and '
            ']] for the } character; they are converted automatically. '
            'For example, ``template(\'[[title_sort]]\') will evaluate the '
            'template {title_sort} and return its value.')

    def evaluate(self, formatter, kwargs, mi, locals, template):
        template = template.replace('[[', '{').replace(']]', '}')
        return formatter.safe_format(template, kwargs, 'TEMPLATE', mi)

class BuiltinEval(FormatterFunction):
    name = 'eval'
    arg_count = 1
    doc = _('eval(template)`` -- evaluates the template, passing the local '
            'variables (those \'assign\'ed to) instead of the book metadata. '
            ' This permits using the template processor to construct complex '
            'results from local variables.')

    def evaluate(self, formatter, kwargs, mi, locals, template):
        from formatter import eval_formatter
        template = template.replace('[[', '{').replace(']]', '}')
        return eval_formatter.safe_format(template, locals, 'EVAL', None)

class BuiltinAssign(FormatterFunction):
    name = 'assign'
    arg_count = 2
    doc = _('assign(id, val) -- assigns val to id, then returns val. '
            'id must be an identifier, not an expression')

    def evaluate(self, formatter, kwargs, mi, locals, target, value):
        locals[target] = value
        return value

class BuiltinPrint(FormatterFunction):
    name = 'print'
    arg_count = -1
    doc = _('print(a, b, ...) -- prints the arguments to standard output. '
            'Unless you start calibre from the command line (calibre-debug -g), '
            'the output will go to a black hole.')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        print args
        return None

class BuiltinField(FormatterFunction):
    name = 'field'
    arg_count = 1
    doc = _('field(name) -- returns the metadata field named by name')

    def evaluate(self, formatter, kwargs, mi, locals, name):
        return formatter.get_value(name, [], kwargs)

class BuiltinSubstr(FormatterFunction):
    name = 'substr'
    arg_count = 3
    doc = _('substr(str, start, end) -- returns the start\'th through the end\'th '
            'characters of str. The first character in str is the zero\'th '
            'character. If end is negative, then it indicates that many '
            'characters counting from the right. If end is zero, then it '
            'indicates the last character. For example, substr(\'12345\', 1, 0) '
            'returns \'2345\', and substr(\'12345\', 1, -1) returns \'234\'.')

    def evaluate(self, formatter, kwargs, mi, locals, str_, start_, end_):
        return str_[int(start_): len(str_) if int(end_) == 0 else int(end_)]

class BuiltinLookup(FormatterFunction):
    name = 'lookup'
    arg_count = -1
    doc = _('lookup(val, pattern, field, pattern, field, ..., else_field) -- '
            'like switch, except the arguments are field (metadata) names, not '
            'text. The value of the appropriate field will be fetched and used. '
            'Note that because composite columns are fields, you can use this '
            'function in one composite field to use the value of some other '
            'composite field. This is extremely useful when constructing '
            'variable save paths')

    def evaluate(self, formatter, kwargs, mi, locals, val, *args):
        if len(args) == 2: # here for backwards compatibility
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
            if re.search(args[i], val):
                return formatter.vformat('{'+args[i+1].strip() + '}', [], kwargs)
            i += 2

class BuiltinTest(FormatterFunction):
    name = 'test'
    arg_count = 3
    doc = _('test(val, text if not empty, text if empty) -- return `text if not '
            'empty` if the field is not empty, otherwise return `text if empty`')

    def evaluate(self, formatter, kwargs, mi, locals, val, value_if_set, value_not_set):
        if val:
            return value_if_set
        else:
            return value_not_set

class BuiltinContains(FormatterFunction):
    name = 'contains'
    arg_count = 4
    doc = _('contains(val, pattern, text if match, text if not match) -- checks '
            'if field contains matches for the regular expression `pattern`. '
            'Returns `text if match` if matches are found, otherwise it returns '
            '`text if no match`')

    def evaluate(self, formatter, kwargs, mi, locals,
                 val, test, value_if_present, value_if_not):
        if re.search(test, val):
            return value_if_present
        else:
            return value_if_not

class BuiltinSwitch(FormatterFunction):
    name = 'switch'
    arg_count = -1
    doc = _('switch(val, pattern, value, pattern, value, ..., else_value) -- '
            'for each ``pattern, value`` pair, checks if the field matches '
            'the regular expression ``pattern`` and if so, returns that '
            'value. If no pattern matches, then else_value is returned. '
            'You can have as many `pattern, value` pairs as you want')

    def evaluate(self, formatter, kwargs, mi, locals, val, *args):
        if (len(args) % 2) != 1:
            raise ValueError(_('switch requires an odd number of arguments'))
        i = 0
        while i < len(args):
            if i + 1 >= len(args):
                return args[i]
            if re.search(args[i], val):
                return args[i+1]
            i += 2

class BuiltinRe(FormatterFunction):
    name = 're'
    arg_count = 3
    doc = _('re(val, pattern, replacement) -- return the field after applying '
            'the regular expression. All instances of `pattern` are replaced '
            'with `replacement`. As in all of calibre, these are '
            'python-compatible regular expressions')

    def evaluate(self, formatter, kwargs, mi, locals, val, pattern, replacement):
        return re.sub(pattern, replacement, val)

class BuiltinEvaluate(FormatterFunction):
    name = 'evaluate'
    arg_count = 2
    doc = _('evaluate(val, text if empty) -- return val if val is not empty, '
            'otherwise return `text if empty`')

    def evaluate(self, formatter, kwargs, mi, locals, val, value_if_empty):
        if val:
            return val
        else:
            return value_if_empty

class BuiltinShorten(FormatterFunction):
    name = 'shorten    '
    arg_count = 4
    doc = _('shorten(val, left chars, middle text, right chars) -- Return a '
            'shortened version of the field, consisting of `left chars` '
            'characters from the beginning of the field, followed by '
            '`middle text`, followed by `right chars` characters from '
            'the end of the string. `Left chars` and `right chars` must be '
            'integers. For example, assume the title of the book is '
            '`Ancient English Laws in the Times of Ivanhoe`, and you want '
            'it to fit in a space of at most 15 characters. If you use '
            '{title:shorten(9,-,5)}, the result will be `Ancient E-nhoe`. '
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

class BuiltinCount(FormatterFunction):
    name = 'count'
    arg_count = 2
    doc = _('count(val, separator) -- interprets the value as a list of items '
            'separated by `separator`, returning the number of items in the '
            'list. Most lists use a comma as the separator, but authors '
            'uses an ampersand. Examples: {tags:count(,)}, {authors:count(&)}')

    def evaluate(self, formatter, kwargs, mi, locals, val, sep):
        return unicode(len(val.split(sep)))

class BuiltinListitem(FormatterFunction):
    name = 'list_item'
    arg_count = 3
    doc = _('list_item(val, index, separator) -- interpret the value as a list of '
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
            return val[index]
        except:
            return ''

class BuiltinUppercase(FormatterFunction):
    name = 'uppercase'
    arg_count = 1
    doc = _('uppercase(val) -- return value of the field in upper case')

    def evaluate(self, formatter, kwargs, mi, locals, val):
        return val.upper()

class BuiltinLowercase(FormatterFunction):
    name = 'lowercase'
    arg_count = 1
    doc = _('lowercase(val) -- return value of the field in lower case')

    def evaluate(self, formatter, kwargs, mi, locals, val):
        return val.lower()

class BuiltinTitlecase(FormatterFunction):
    name = 'titlecase'
    arg_count = 1
    doc = _('titlecase(val) -- return value of the field in title case')

    def evaluate(self, formatter, kwargs, mi, locals, val):
        return titlecase(val)

class BuiltinCapitalize(FormatterFunction):
    name = 'capitalize'
    arg_count = 1
    doc = _('capitalize(val) -- return value of the field capitalized')

    def evaluate(self, formatter, kwargs, mi, locals, val):
        return capitalize(val)

builtin_add         = BuiltinAdd()
builtin_assign      = BuiltinAssign()
builtin_capitalize  = BuiltinCapitalize()
builtin_cmp         = BuiltinCmp()
builtin_contains    = BuiltinContains()
builtin_count       = BuiltinCount()
builtin_divide      = BuiltinDivide()
builtin_eval        = BuiltinEval()
builtin_evaluate    = BuiltinEvaluate()
builtin_field       = BuiltinField()
builtin_list_item   = BuiltinListitem()
builtin_lookup      = BuiltinLookup()
builtin_lowercase   = BuiltinLowercase()
builtin_multiply    = BuiltinMultiply()
builtin_print       = BuiltinPrint()
builtin_re          = BuiltinRe()
builtin_shorten     = BuiltinShorten()
builtin_strcat      = BuiltinStrcat()
builtin_strcmp      = BuiltinStrcmp()
builtin_substr      = BuiltinSubstr()
builtin_subtract    = BuiltinSubtract()
builtin_switch      = BuiltinSwitch()
builtin_template    = BuiltinTemplate()
builtin_test        = BuiltinTest()
builtin_titlecase   = BuiltinTitlecase()
builtin_uppercase   = BuiltinUppercase()

class FormatterUserFunction(FormatterFunction):
    def __init__(self, name, doc, arg_count, program_text):
        self.name = name
        self.doc = doc
        self.arg_count = arg_count
        self.program_text = program_text

def compile_user_function(name, doc, arg_count, eval_func):
    func = '\t' + eval_func.replace('\n', '\n\t')
    prog = '''
from calibre.utils.formatter_functions import FormatterUserFunction
class UserFunction(FormatterUserFunction):
''' + func
    locals = {}
    exec prog in locals
    cls = locals['UserFunction'](name, doc, arg_count, eval_func)
    return cls

def load_user_template_functions(funcs):
    for func in funcs:
        try:
            cls = compile_user_function(*func)
            formatter_functions.register_function(cls)
        except:
            traceback.print_exc()