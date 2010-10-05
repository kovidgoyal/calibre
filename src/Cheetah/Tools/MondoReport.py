"""
@@TR: This code is pretty much unsupported.

MondoReport.py -- Batching module for Python and Cheetah.

Version 2001-Nov-18.  Doesn't do much practical yet, but the companion
testMondoReport.py passes all its tests.
-Mike Orr (Iron)

TODO: BatchRecord.prev/next/prev_batches/next_batches/query, prev.query,
next.query.

How about Report: .page(), .all(), .summary()?  Or PageBreaker.
"""
import operator
try:
    from functools import reduce
except ImportError:
    # If functools doesn't exist, we must be on an old 
    # enough version that has reduce() in builtins
    pass

try:
    from Cheetah.NameMapper import valueForKey as lookup_func
except ImportError:
    def lookup_func(obj, name):
        if hasattr(obj, name):
            return getattr(obj, name)
        else:
            return obj[name] # Raises KeyError.

########## PUBLIC GENERIC FUNCTIONS ##############################

class NegativeError(ValueError):
    pass

def isNumeric(v):
    return isinstance(v, (int, float))

def isNonNegative(v):
    ret = isNumeric(v)
    if ret and v < 0:
        raise NegativeError(v)

def isNotNone(v):
    return v is not None

def Roman(n):
    n = int(n) # Raises TypeError.
    if n < 1:
        raise ValueError("roman numeral for zero or negative undefined: " + n)
    roman = ''
    while n >= 1000:
            n = n - 1000
            roman = roman + 'M'
    while n >= 500:
            n = n - 500
            roman = roman + 'D'
    while n >= 100:
            n = n - 100
            roman = roman + 'C'
    while n >= 50:
            n = n - 50
            roman = roman + 'L'
    while n >= 10:
            n = n - 10
            roman = roman + 'X'
    while n >= 5:
            n = n - 5
            roman = roman + 'V'
    while n < 5 and n >= 1:
            n = n - 1
            roman = roman + 'I'
    roman = roman.replace('DCCCC', 'CM')
    roman = roman.replace('CCCC', 'CD')
    roman = roman.replace('LXXXX', 'XC')
    roman = roman.replace('XXXX', 'XL')
    roman = roman.replace('VIIII', 'IX')
    roman = roman.replace('IIII', 'IV')
    return roman


def sum(lis):
    return reduce(operator.add, lis, 0)
    
def mean(lis):
    """Always returns a floating-point number.
    """
    lis_len = len(lis)
    if lis_len == 0:
        return 0.00 # Avoid ZeroDivisionError (not raised for floats anyway)
    total = float( sum(lis) )
    return total / lis_len

def median(lis):
    lis = sorted(lis[:])
    return lis[int(len(lis)/2)]


def variance(lis):
    raise NotImplementedError()
    
def variance_n(lis):
    raise NotImplementedError()
    
def standardDeviation(lis):
    raise NotImplementedError()
    
def standardDeviation_n(lis):
    raise NotImplementedError()



class IndexFormats:
    """Eight ways to display a subscript index.
       ("Fifty ways to leave your lover....")
    """
    def __init__(self, index, item=None):
        self._index = index
        self._number = index + 1
        self._item = item

    def index(self):
        return self._index

    __call__ = index

    def number(self):
        return self._number

    def even(self):
        return self._number % 2 == 0

    def odd(self):
        return not self.even()

    def even_i(self):
        return self._index % 2 == 0

    def odd_i(self):
        return not self.even_i()

    def letter(self):
        return self.Letter().lower()

    def Letter(self):
        n = ord('A') + self._index
        return chr(n)

    def roman(self):
        return self.Roman().lower()

    def Roman(self):
        return Roman(self._number)

    def item(self):
        return self._item



########## PRIVATE CLASSES ##############################

class ValuesGetterMixin:
    def __init__(self, origList):
        self._origList = origList

    def _getValues(self, field=None, criteria=None):
        if field:
            ret = [lookup_func(elm, field) for elm in self._origList]
        else:
            ret = self._origList
        if criteria:
            ret = list(filter(criteria, ret))
        return ret


class RecordStats(IndexFormats, ValuesGetterMixin):
    """The statistics that depend on the current record.
    """
    def __init__(self, origList, index):
        record = origList[index] # Raises IndexError.
        IndexFormats.__init__(self, index, record)
        ValuesGetterMixin.__init__(self, origList)
    
    def length(self):
        return len(self._origList)

    def first(self):
        return self._index == 0
        
    def last(self):
        return self._index >= len(self._origList) - 1

    def _firstOrLastValue(self, field, currentIndex, otherIndex):
        currentValue = self._origList[currentIndex] # Raises IndexError.
        try:
            otherValue = self._origList[otherIndex]
        except IndexError:
            return True
        if field:
            currentValue = lookup_func(currentValue, field)
            otherValue = lookup_func(otherValue, field)
        return currentValue != otherValue

    def firstValue(self, field=None):
        return self._firstOrLastValue(field, self._index, self._index - 1)

    def lastValue(self, field=None):
        return self._firstOrLastValue(field, self._index, self._index + 1)

    # firstPage and lastPage not implemented.  Needed?

    def percentOfTotal(self, field=None, suffix='%', default='N/A', decimals=2):
        rec = self._origList[self._index]
        if field:
            val = lookup_func(rec, field)
        else:
            val = rec
        try:
            lis = self._getValues(field, isNumeric)
        except NegativeError:
            return default
        total = sum(lis)
        if total == 0.00: # Avoid ZeroDivisionError.
            return default
        val = float(val)
        try:
            percent = (val / total) * 100
        except ZeroDivisionError:
            return default
        if decimals == 0:
            percent = int(percent)
        else:
            percent = round(percent, decimals)
        if suffix:
            return str(percent) + suffix # String.
        else:
            return percent # Numeric.

    def __call__(self): # Overrides IndexFormats.__call__
        """This instance is not callable, so we override the super method.
        """
        raise NotImplementedError()

    def prev(self):
        if self._index == 0:
            return None
        else:
            length = self.length()
            start = self._index - length
            return PrevNextPage(self._origList, length, start)

    def next(self):
        if self._index + self.length() == self.length():
            return None
        else:
            length = self.length()
            start = self._index + length
            return PrevNextPage(self._origList, length, start)
            
    def prevPages(self):
        raise NotImplementedError()
        
    def nextPages(self):
        raise NotImplementedError()

    prev_batches = prevPages
    next_batches = nextPages

    def summary(self):
        raise NotImplementedError()



    def _prevNextHelper(self, start, end, size, orphan, sequence):
        """Copied from Zope's DT_InSV.py's "opt" function.
        """
        if size < 1:
            if start > 0 and end > 0 and end >= start:
                size=end+1-start
            else: size=7

        if start > 0:

            try: sequence[start-1]
            except: start=len(sequence)
            # if start > l: start=l

            if end > 0:
                if end < start: end=start
            else:
                end=start+size-1
                try: sequence[end+orphan-1]
                except: end=len(sequence)
                # if l - end < orphan: end=l
        elif end > 0:
            try: sequence[end-1]
            except: end=len(sequence)
            # if end > l: end=l
            start=end+1-size
            if start - 1 < orphan: start=1
        else:
            start=1
            end=start+size-1
            try: sequence[end+orphan-1]
            except: end=len(sequence)
            # if l - end < orphan: end=l
        return start, end, size



class Summary(ValuesGetterMixin):
    """The summary statistics, that don't depend on the current record.
    """
    def __init__(self, origList):
        ValuesGetterMixin.__init__(self, origList)
        
    def sum(self, field=None):
        lis = self._getValues(field, isNumeric)
        return sum(lis)

    total = sum

    def count(self, field=None):
        lis = self._getValues(field, isNotNone)
        return len(lis)
        
    def min(self, field=None):
        lis = self._getValues(field, isNotNone)
        return min(lis) # Python builtin function min.
        
    def max(self, field=None):
        lis = self._getValues(field, isNotNone)
        return max(lis) # Python builtin function max.

    def mean(self, field=None):
        """Always returns a floating point number.
        """
        lis = self._getValues(field, isNumeric)
        return mean(lis)

    average = mean

    def median(self, field=None):
        lis = self._getValues(field, isNumeric)
        return median(lis)

    def variance(self, field=None):
        raiseNotImplementedError()

    def variance_n(self, field=None):
        raiseNotImplementedError()

    def standardDeviation(self, field=None):
        raiseNotImplementedError()

    def standardDeviation_n(self, field=None):
        raiseNotImplementedError()


class PrevNextPage:
    def __init__(self, origList, size, start):
        end = start + size
        self.start = IndexFormats(start, origList[start])
        self.end = IndexFormats(end, origList[end])
        self.length = size
        

########## MAIN PUBLIC CLASS ##############################
class MondoReport:
    _RecordStatsClass = RecordStats
    _SummaryClass = Summary

    def __init__(self, origlist):
        self._origList = origlist

    def page(self, size, start, overlap=0, orphan=0):
        """Returns list of ($r, $a, $b)
        """
        if overlap != 0:
            raise NotImplementedError("non-zero overlap")
        if orphan != 0:
            raise NotImplementedError("non-zero orphan")
        origList = self._origList
        origList_len = len(origList)
        start = max(0, start)
        end = min( start + size, len(self._origList) )
        mySlice = origList[start:end]
        ret = []
        for rel in range(size):
            abs_ = start + rel
            r = mySlice[rel]
            a = self._RecordStatsClass(origList, abs_)
            b = self._RecordStatsClass(mySlice, rel)
            tup = r, a, b
            ret.append(tup)
        return ret


    batch = page

    def all(self):
        origList_len = len(self._origList)
        return self.page(origList_len, 0, 0, 0)
    
    
    def summary(self):
        return self._SummaryClass(self._origList)

"""
**********************************
    Return a pageful of records from a sequence, with statistics.

       in : origlist, list or tuple.  The entire set of records.  This is
              usually a list of objects or a list of dictionaries.
            page, int >= 0.  Which page to display.
            size, int >= 1.  How many records per page.
            widow, int >=0.  Not implemented.
            orphan, int >=0.  Not implemented.
            base, int >=0.  Number of first page (usually 0 or 1).

       out: list of (o, b) pairs.  The records for the current page.  'o' is
              the original element from 'origlist' unchanged.  'b' is a Batch
              object containing meta-info about 'o'.
       exc: IndexError if 'page' or 'size' is < 1.  If 'origlist' is empty or
              'page' is too high, it returns an empty list rather than raising
              an error.
        
        origlist_len = len(origlist)
        start = (page + base) * size
        end = min(start + size, origlist_len)
        ret = []
        # widow, orphan calculation: adjust 'start' and 'end' up and down, 
        # Set 'widow', 'orphan', 'first_nonwidow', 'first_nonorphan' attributes.
        for i in range(start, end):
            o = origlist[i]
            b = Batch(origlist, size, i)
            tup = o, b
            ret.append(tup)
        return ret

    def prev(self):
        # return a PrevNextPage or None

    def next(self):
        # return a PrevNextPage or None

    def prev_batches(self):
        # return a list of SimpleBatch for the previous batches

    def next_batches(self):
        # return a list of SimpleBatch for the next batches

########## PUBLIC MIXIN CLASS FOR CHEETAH TEMPLATES ##############
class MondoReportMixin:
    def batch(self, origList, size=None, start=0, overlap=0, orphan=0):
        bat = MondoReport(origList)
        return bat.batch(size, start, overlap, orphan)
    def batchstats(self, origList):
        bat = MondoReport(origList)
        return bat.stats()
"""

# vim: shiftwidth=4 tabstop=4 expandtab textwidth=79
