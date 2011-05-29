'''
Created on 13 Jan 2011

@author: charles
'''

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import inspect, re, traceback

from calibre.utils.titlecase import titlecase
from calibre.utils.icu import capitalize, strcmp, sort_key
from calibre.utils.date import parse_date, format_date


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

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        raise NotImplementedError()

    def eval_(self, formatter, kwargs, mi, locals, *args):
        ret = self.evaluate(formatter, kwargs, mi, locals, *args)
        if isinstance(ret, (str, unicode)):
            return ret
        if isinstance(ret, (int, float, bool)):
            return unicode(ret)
        if isinstance(ret, list):
            return ','.join(list)

all_builtin_functions = []
class BuiltinFormatterFunction(FormatterFunction):
    def __init__(self):
        formatter_functions.register_builtin(self)
        eval_func = inspect.getmembers(self.__class__,
                        lambda x: inspect.ismethod(x) and x.__name__ == 'evaluate')
        try:
            lines = [l[4:] for l in inspect.getsourcelines(eval_func[0][1])[0]]
        except:
            lines = []
        self.program_text = ''.join(lines)
        all_builtin_functions.append(self)

class BuiltinStrcmp(BuiltinFormatterFunction):
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

class BuiltinCmp(BuiltinFormatterFunction):
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

class BuiltinStrcat(BuiltinFormatterFunction):
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

class BuiltinAdd(BuiltinFormatterFunction):
    name = 'add'
    arg_count = 2
    doc = _('add(x, y) -- returns x + y. Throws an exception if either x or y are not numbers.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y):
        x = float(x if x else 0)
        y = float(y if y else 0)
        return unicode(x + y)

class BuiltinSubtract(BuiltinFormatterFunction):
    name = 'subtract'
    arg_count = 2
    doc = _('subtract(x, y) -- returns x - y. Throws an exception if either x or y are not numbers.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y):
        x = float(x if x else 0)
        y = float(y if y else 0)
        return unicode(x - y)

class BuiltinMultiply(BuiltinFormatterFunction):
    name = 'multiply'
    arg_count = 2
    doc = _('multiply(x, y) -- returns x * y. Throws an exception if either x or y are not numbers.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y):
        x = float(x if x else 0)
        y = float(y if y else 0)
        return unicode(x * y)

class BuiltinDivide(BuiltinFormatterFunction):
    name = 'divide'
    arg_count = 2
    doc = _('divide(x, y) -- returns x / y. Throws an exception if either x or y are not numbers.')

    def evaluate(self, formatter, kwargs, mi, locals, x, y):
        x = float(x if x else 0)
        y = float(y if y else 0)
        return unicode(x / y)

class BuiltinTemplate(BuiltinFormatterFunction):
    name = 'template'
    arg_count = 1
    doc = _('template(x) -- evaluates x as a template. The evaluation is done '
            'in its own context, meaning that variables are not shared between '
            'the caller and the template evaluation. Because the { and } '
            'characters are special, you must use [[ for the { character and '
            ']] for the } character; they are converted automatically. '
            'For example, template(\'[[title_sort]]\') will evaluate the '
            'template {title_sort} and return its value.')

    def evaluate(self, formatter, kwargs, mi, locals, template):
        template = template.replace('[[', '{').replace(']]', '}')
        return formatter.__class__().safe_format(template, kwargs, 'TEMPLATE', mi)

class BuiltinEval(BuiltinFormatterFunction):
    name = 'eval'
    arg_count = 1
    doc = _('eval(template) -- evaluates the template, passing the local '
            'variables (those \'assign\'ed to) instead of the book metadata. '
            ' This permits using the template processor to construct complex '
            'results from local variables.')

    def evaluate(self, formatter, kwargs, mi, locals, template):
        from formatter import eval_formatter
        template = template.replace('[[', '{').replace(']]', '}')
        return eval_formatter.safe_format(template, locals, 'EVAL', None)

class BuiltinAssign(BuiltinFormatterFunction):
    name = 'assign'
    arg_count = 2
    doc = _('assign(id, val) -- assigns val to id, then returns val. '
            'id must be an identifier, not an expression')

    def evaluate(self, formatter, kwargs, mi, locals, target, value):
        locals[target] = value
        return value

class BuiltinPrint(BuiltinFormatterFunction):
    name = 'print'
    arg_count = -1
    doc = _('print(a, b, ...) -- prints the arguments to standard output. '
            'Unless you start calibre from the command line (calibre-debug -g), '
            'the output will go to a black hole.')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        print args
        return None

class BuiltinField(BuiltinFormatterFunction):
    name = 'field'
    arg_count = 1
    doc = _('field(name) -- returns the metadata field named by name')

    def evaluate(self, formatter, kwargs, mi, locals, name):
        return formatter.get_value(name, [], kwargs)

class BuiltinRaw_field(BuiltinFormatterFunction):
    name = 'raw_field'
    arg_count = 1
    doc = _('raw_field(name) -- returns the metadata field named by name '
            'without applying any formatting.')

    def evaluate(self, formatter, kwargs, mi, locals, name):
        return unicode(getattr(mi, name, None))

class BuiltinSubstr(BuiltinFormatterFunction):
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

class BuiltinLookup(BuiltinFormatterFunction):
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
            if re.search(args[i], val, flags=re.I):
                return formatter.vformat('{'+args[i+1].strip() + '}', [], kwargs)
            i += 2

class BuiltinTest(BuiltinFormatterFunction):
    name = 'test'
    arg_count = 3
    doc = _('test(val, text if not empty, text if empty) -- return `text if not '
            'empty` if the field is not empty, otherwise return `text if empty`')

    def evaluate(self, formatter, kwargs, mi, locals, val, value_if_set, value_not_set):
        if val:
            return value_if_set
        else:
            return value_not_set

class BuiltinContains(BuiltinFormatterFunction):
    name = 'contains'
    arg_count = 4
    doc = _('contains(val, pattern, text if match, text if not match) -- checks '
            'if field contains matches for the regular expression `pattern`. '
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
    doc = _('switch(val, pattern, value, pattern, value, ..., else_value) -- '
            'for each `pattern, value` pair, checks if the field matches '
            'the regular expression `pattern` and if so, returns that '
            '`value`. If no pattern matches, then else_value is returned. '
            'You can have as many `pattern, value` pairs as you want')

    def evaluate(self, formatter, kwargs, mi, locals, val, *args):
        if (len(args) % 2) != 1:
            raise ValueError(_('switch requires an odd number of arguments'))
        i = 0
        while i < len(args):
            if i + 1 >= len(args):
                return args[i]
            if re.search(args[i], val, flags=re.I):
                return args[i+1]
            i += 2

class BuiltinInList(BuiltinFormatterFunction):
    name = 'in_list'
    arg_count = 5
    doc = _('in_list(val, separator, pattern, found_val, not_found_val) -- '
            'treat val as a list of items separated by separator, '
            'comparing the pattern against each value in the list. If the '
            'pattern matches a value, return found_val, otherwise return '
            'not_found_val.')

    def evaluate(self, formatter, kwargs, mi, locals, val, sep, pat, fv, nfv):
        l = [v.strip() for v in val.split(sep) if v.strip()]
        if l:
            for v in l:
                if re.search(pat, v, flags=re.I):
                    return fv
        return nfv

class BuiltinStrInList(BuiltinFormatterFunction):
    name = 'str_in_list'
    arg_count = 5
    doc = _('str_in_list(val, separator, string, found_val, not_found_val) -- '
            'treat val as a list of items separated by separator, '
            'comparing the string against each value in the list. If the '
            'string matches a value, return found_val, otherwise return '
            'not_found_val. If the string contains separators, then it is '
            'also treated as a list and each value is checked.')

    def evaluate(self, formatter, kwargs, mi, locals, val, sep, str, fv, nfv):
        l = [v.strip() for v in val.split(sep) if v.strip()]
        c = [v.strip() for v in str.split(sep) if v.strip()]
        if l:
            for v in l:
                for t in c:
                    if strcmp(t, v) == 0:
                        return fv
        return nfv

class BuiltinRe(BuiltinFormatterFunction):
    name = 're'
    arg_count = 3
    doc = _('re(val, pattern, replacement) -- return the field after applying '
            'the regular expression. All instances of `pattern` are replaced '
            'with `replacement`. As in all of calibre, these are '
            'python-compatible regular expressions')

    def evaluate(self, formatter, kwargs, mi, locals, val, pattern, replacement):
        return re.sub(pattern, replacement, val, flags=re.I)

class BuiltinIfempty(BuiltinFormatterFunction):
    name = 'ifempty'
    arg_count = 2
    doc = _('ifempty(val, text if empty) -- return val if val is not empty, '
            'otherwise return `text if empty`')

    def evaluate(self, formatter, kwargs, mi, locals, val, value_if_empty):
        if val:
            return val
        else:
            return value_if_empty

class BuiltinShorten(BuiltinFormatterFunction):
    name = 'shorten'
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

class BuiltinCount(BuiltinFormatterFunction):
    name = 'count'
    arg_count = 2
    doc = _('count(val, separator) -- interprets the value as a list of items '
            'separated by `separator`, returning the number of items in the '
            'list. Most lists use a comma as the separator, but authors '
            'uses an ampersand. Examples: {tags:count(,)}, {authors:count(&)}')

    def evaluate(self, formatter, kwargs, mi, locals, val, sep):
        return unicode(len(val.split(sep)))

class BuiltinListitem(BuiltinFormatterFunction):
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

class BuiltinSelect(BuiltinFormatterFunction):
    name = 'select'
    arg_count = 2
    doc = _('select(val, key) -- interpret the value as a comma-separated list '
            'of items, with the items being "id:value". Find the pair with the'
            'id equal to key, and return the corresponding value.'
            )

    def evaluate(self, formatter, kwargs, mi, locals, val, key):
        if not val:
            return ''
        vals = [v.strip() for v in val.split(',')]
        for v in vals:
            if v.startswith(key+':'):
                return v[len(key)+1:]
        return ''

class BuiltinSublist(BuiltinFormatterFunction):
    name = 'sublist'
    arg_count = 4
    doc = _('sublist(val, start_index, end_index, separator) -- interpret the '
            'value as a list of items separated by `separator`, returning a '
            'new list made from the `start_index`th to the `end_index`th item. '
            'The first item is number zero. If an index is negative, then it '
            'counts from the end of the list. As a special case, an end_index '
            'of zero is assumed to be the length of the list. Examples using '
            'basic template mode and assuming that the tags column (which is '
            'comma-separated) contains "A, B, C": '
            '{tags:sublist(0,1,\,)} returns "A". '
            '{tags:sublist(-1,0,\,)} returns "C". '
            '{tags:sublist(0,-1,\,)} returns "A, B".')

    def evaluate(self, formatter, kwargs, mi, locals, val, start_index, end_index, sep):
        if not val:
            return ''
        si = int(start_index)
        ei = int(end_index)
        val = val.split(sep)
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
    doc = _('subitems(val, start_index, end_index) -- This function is used to '
            'break apart lists of items such as genres. It interprets the value '
            'as a comma-separated list of items, where each item is a period-'
            'separated list. Returns a new list made by first finding all the '
            'period-separated items, then for each such item extracting the '
            'start_index`th to the `end_index`th components, then combining '
            'the results back together. The first component in a period-'
            'separated list has an index of zero. If an index is negative, '
            'then it counts from the end of the list. As a special case, an '
            'end_index of zero is assumed to be the length of the list. '
            'Example using basic template mode and assuming a #genre value of '
            '"A.B.C": {#genre:subitems(0,1)} returns "A". {#genre:subitems(0,2)} '
            'returns "A.B". {#genre:subitems(1,0)} returns "B.C". Assuming a #genre '
            'value of "A.B.C, D.E.F", {#genre:subitems(0,1)} returns "A, D". '
            '{#genre:subitems(0,2)} returns "A.B, D.E"')

    def evaluate(self, formatter, kwargs, mi, locals, val, start_index, end_index):
        if not val:
            return ''
        si = int(start_index)
        ei = int(end_index)
        items = [v.strip() for v in val.split(',')]
        rv = set()
        for item in items:
            component = item.split('.')
            try:
                if ei == 0:
                    rv.add('.'.join(component[si:]))
                else:
                    rv.add('.'.join(component[si:ei]))
            except:
                pass
        return ', '.join(sorted(rv, key=sort_key))

class BuiltinFormat_date(BuiltinFormatterFunction):
    name = 'format_date'
    arg_count = 2
    doc = _('format_date(val, format_string) -- format the value, which must '
            'be a date field, using the format_string, returning a string. '
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
            'iso  : the date with time and timezone. Must be the only format present')

    def evaluate(self, formatter, kwargs, mi, locals, val, format_string):
        if not val:
            return ''
        try:
            dt = parse_date(val)
            s = format_date(dt, format_string)
        except:
            s = 'BAD DATE'
        return s

class BuiltinUppercase(BuiltinFormatterFunction):
    name = 'uppercase'
    arg_count = 1
    doc = _('uppercase(val) -- return value of the field in upper case')

    def evaluate(self, formatter, kwargs, mi, locals, val):
        return val.upper()

class BuiltinLowercase(BuiltinFormatterFunction):
    name = 'lowercase'
    arg_count = 1
    doc = _('lowercase(val) -- return value of the field in lower case')

    def evaluate(self, formatter, kwargs, mi, locals, val):
        return val.lower()

class BuiltinTitlecase(BuiltinFormatterFunction):
    name = 'titlecase'
    arg_count = 1
    doc = _('titlecase(val) -- return value of the field in title case')

    def evaluate(self, formatter, kwargs, mi, locals, val):
        return titlecase(val)

class BuiltinCapitalize(BuiltinFormatterFunction):
    name = 'capitalize'
    arg_count = 1
    doc = _('capitalize(val) -- return value of the field capitalized')

    def evaluate(self, formatter, kwargs, mi, locals, val):
        return capitalize(val)

class BuiltinBooksize(BuiltinFormatterFunction):
    name = 'booksize'
    arg_count = 0
    doc = _('booksize() -- return value of the size field')

    def evaluate(self, formatter, kwargs, mi, locals):
        if mi.book_size is not None:
            try:
                return str(mi.book_size)
            except:
                pass
        return ''

class BuiltinOndevice(BuiltinFormatterFunction):
    name = 'ondevice'
    arg_count = 0
    doc = _('ondevice() -- return Yes if ondevice is set, otherwise return '
            'the empty string')

    def evaluate(self, formatter, kwargs, mi, locals):
        if mi.ondevice_col:
            return _('Yes')
        return ''

class BuiltinFirstNonEmpty(BuiltinFormatterFunction):
    name = 'first_non_empty'
    arg_count = -1
    doc = _('first_non_empty(value, value, ...) -- '
            'returns the first value that is not empty. If all values are '
            'empty, then the empty value is returned.'
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
    doc = _('and(value, value, ...) -- '
            'returns the string "1" if all values are not empty, otherwise '
            'returns the empty string. This function works well with test or '
            'first_non_empty. You can have as many values as you want.')

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
    doc = _('or(value, value, ...) -- '
            'returns the string "1" if any value is not empty, otherwise '
            'returns the empty string. This function works well with test or '
            'first_non_empty. You can have as many values as you want.')

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
    doc = _('not(value) -- '
            'returns the string "1" if the value is empty, otherwise '
            'returns the empty string. This function works well with test or '
            'first_non_empty. You can have as many values as you want.')

    def evaluate(self, formatter, kwargs, mi, locals, *args):
        i = 0
        while i < len(args):
            if args[i]:
                return '1'
            i += 1
        return ''

class BuiltinMergeLists(BuiltinFormatterFunction):
    name = 'merge_lists'
    arg_count = 3
    doc = _('merge_lists(list1, list2, separator) -- '
            'return a list made by merging the items in list1 and list2, '
            'removing duplicate items using a case-insensitive compare. If '
            'items differ in case, the one in list1 is used. '
            'The items in list1 and list2 are separated by separator, as are '
            'the items in the returned list.')

    def evaluate(self, formatter, kwargs, mi, locals, list1, list2, separator):
        l1 = [l.strip() for l in list1.split(separator) if l.strip()]
        l2 = [l.strip() for l in list2.split(separator) if l.strip()]
        lcl1 = set([icu_lower(l) for l in l1])

        res = []
        for i in l1:
            res.append(i)
        for i in l2:
            if icu_lower(i) not in lcl1:
                res.append(i)
        return ', '.join(sorted(res, key=sort_key))


builtin_add         = BuiltinAdd()
builtin_and         = BuiltinAnd()
builtin_assign      = BuiltinAssign()
builtin_booksize    = BuiltinBooksize()
builtin_capitalize  = BuiltinCapitalize()
builtin_cmp         = BuiltinCmp()
builtin_contains    = BuiltinContains()
builtin_count       = BuiltinCount()
builtin_divide      = BuiltinDivide()
builtin_eval        = BuiltinEval()
builtin_first_non_empty = BuiltinFirstNonEmpty()
builtin_field       = BuiltinField()
builtin_format_date = BuiltinFormat_date()
builtin_ifempty     = BuiltinIfempty()
builtin_in_list     = BuiltinInList()
builtin_list_item   = BuiltinListitem()
builtin_lookup      = BuiltinLookup()
builtin_lowercase   = BuiltinLowercase()
builtin_merge_lists = BuiltinMergeLists()
builtin_multiply    = BuiltinMultiply()
builtin_not         = BuiltinNot()
builtin_ondevice    = BuiltinOndevice()
builtin_or          = BuiltinOr()
builtin_print       = BuiltinPrint()
builtin_raw_field   = BuiltinRaw_field()
builtin_re          = BuiltinRe()
builtin_select      = BuiltinSelect()
builtin_shorten     = BuiltinShorten()
builtin_strcat      = BuiltinStrcat()
builtin_strcmp      = BuiltinStrcmp()
builtin_str_in_list = BuiltinStrInList()
builtin_subitems    = BuiltinSubitems()
builtin_sublist     = BuiltinSublist()
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

tabs = re.compile(r'^\t*')
def compile_user_function(name, doc, arg_count, eval_func):
    def replace_func(mo):
        return  mo.group().replace('\t', '    ')

    func = '    ' + '\n    '.join([tabs.sub(replace_func, line )
                                   for line in eval_func.splitlines()])
    prog = '''
from calibre.utils.formatter_functions import FormatterUserFunction
class UserFunction(FormatterUserFunction):
''' + func
    locals = {}
    exec prog in locals
    cls = locals['UserFunction'](name, doc, arg_count, eval_func)
    return cls

def load_user_template_functions(funcs):
    formatter_functions.reset_to_builtins()
    for func in funcs:
        try:
            cls = compile_user_function(*func)
            formatter_functions.register_function(cls)
        except:
            traceback.print_exc()
