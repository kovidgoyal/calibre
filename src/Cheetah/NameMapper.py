#!/usr/bin/env python
"""This module supports Cheetah's optional NameMapper syntax.

Overview
================================================================================

NameMapper provides a simple syntax for accessing Python data structures,
functions, and methods from Cheetah. It's called NameMapper because it 'maps'
simple 'names' in Cheetah templates to possibly more complex syntax in Python.

Its purpose is to make working with Cheetah easy for non-programmers.
Specifically, non-programmers using Cheetah should NOT need to be taught (a)
what the difference is between an object and a dictionary, (b) what functions
and methods are, and (c) what 'self' is.  A further aim (d) is to buffer the
code in Cheetah templates from changes in the implementation of the Python data
structures behind them.

Consider this scenario:

You are building a customer information system. The designers with you want to
use information from your system on the client's website --AND-- they want to
understand the display code and so they can maintian it themselves.

You write a UI class with a 'customers' method that returns a dictionary of all
the customer objects.  Each customer object has an 'address' method that returns
the a dictionary with information about the customer's address.  The designers
want to be able to access that information.

Using PSP, the display code for the website would look something like the
following, assuming your servlet subclasses the class you created for managing
customer information:

  <%= self.customer()[ID].address()['city'] %>   (42 chars)

Using Cheetah's NameMapper syntax it could be any of the following:

   $self.customers()[$ID].address()['city']       (39 chars)
   --OR--
   $customers()[$ID].address()['city']
   --OR--
   $customers()[$ID].address().city
   --OR--
   $customers()[$ID].address.city
   --OR--
   $customers()[$ID].address.city
   --OR--
   $customers[$ID].address.city                   (27 chars)


Which of these would you prefer to explain to the designers, who have no
programming experience?  The last form is 15 characters shorter than the PSP
and, conceptually, is far more accessible. With PHP or ASP, the code would be
even messier than the PSP

This is a rather extreme example and, of course, you could also just implement
'$getCustomer($ID).city' and obey the Law of Demeter (search Google for more on that).
But good object orientated design isn't the point here.

Details
================================================================================
The parenthesized letters below correspond to the aims in the second paragraph.

DICTIONARY ACCESS (a)
---------------------

NameMapper allows access to items in a dictionary using the same dotted notation
used to access object attributes in Python.  This aspect of NameMapper is known
as 'Unified Dotted Notation'.

For example, with Cheetah it is possible to write:
   $customers()['kerr'].address()  --OR--  $customers().kerr.address()
where the second form is in NameMapper syntax.

This only works with dictionary keys that are also valid python identifiers:
  regex = '[a-zA-Z_][a-zA-Z_0-9]*'


AUTOCALLING (b,d)
-----------------

NameMapper automatically detects functions and methods in Cheetah $vars and calls
them if the parentheses have been left off.

For example if 'a' is an object, 'b' is a method
  $a.b
is equivalent to
  $a.b()

If b returns a dictionary, then following variations are possible
  $a.b.c  --OR--  $a.b().c  --OR--  $a.b()['c']
where 'c' is a key in the dictionary that a.b() returns.

Further notes:
* NameMapper autocalls the function or method without any arguments.  Thus
autocalling can only be used with functions or methods that either have no
arguments or have default values for all arguments.

* NameMapper only autocalls functions and methods.  Classes and callable object instances
will not be autocalled.

* Autocalling can be disabled using Cheetah's 'useAutocalling' setting.

LEAVING OUT 'self' (c,d)
------------------------

NameMapper makes it possible to access the attributes of a servlet in Cheetah
without needing to include 'self' in the variable names.  See the NAMESPACE
CASCADING section below for details.

NAMESPACE CASCADING (d)
--------------------
...

Implementation details
================================================================================

* NameMapper's search order is dictionary keys then object attributes

* NameMapper.NotFound is raised if a value can't be found for a name.

Performance and the C version
================================================================================

Cheetah comes with both a C version and a Python version of NameMapper.  The C
version is significantly faster and the exception tracebacks are much easier to
read.  It's still slower than standard Python syntax, but you won't notice the
difference in realistic usage scenarios.

Cheetah uses the optimized C version (_namemapper.c) if it has
been compiled or falls back to the Python version if not.
"""

__author__ = "Tavis Rudd <tavis@damnsimple.com>," +\
             "\nChuck Esterbrook <echuck@mindspring.com>"
from pprint import pformat
import inspect

_INCLUDE_NAMESPACE_REPR_IN_NOTFOUND_EXCEPTIONS = False
_ALLOW_WRAPPING_OF_NOTFOUND_EXCEPTIONS = True
__all__ = ['NotFound',
           'hasKey',
           'valueForKey',
           'valueForName',
           'valueFromSearchList',
           'valueFromFrameOrSearchList',
           'valueFromFrame',
           ]

if not hasattr(inspect.imp, 'get_suffixes'):
    # This is to fix broken behavior of the inspect module under the
    # Google App Engine, see the following issue:
    # http://bugs.communitycheetah.org/view.php?id=10
    setattr(inspect.imp, 'get_suffixes', lambda: [('.py', 'U', 1)])

## N.B. An attempt is made at the end of this module to import C versions of
## these functions.  If _namemapper.c has been compiled succesfully and the
## import goes smoothly, the Python versions defined here will be replaced with
## the C versions.

class NotFound(LookupError):
    pass

def _raiseNotFoundException(key, namespace):
    excString = "cannot find '%s'"%key
    if _INCLUDE_NAMESPACE_REPR_IN_NOTFOUND_EXCEPTIONS:
        excString += ' in the namespace %s'%pformat(namespace)
    raise NotFound(excString)

def _wrapNotFoundException(exc, fullName, namespace):
    if not _ALLOW_WRAPPING_OF_NOTFOUND_EXCEPTIONS:
        raise
    else:
        excStr = exc.args[0]
        if excStr.find('while searching')==-1: # only wrap once!
            excStr +=" while searching for '%s'"%fullName
            if _INCLUDE_NAMESPACE_REPR_IN_NOTFOUND_EXCEPTIONS:
                excStr += ' in the namespace %s'%pformat(namespace)
            exc.args = (excStr,)
        raise

def _isInstanceOrClass(obj):
    if isinstance(obj, type):
        # oldstyle
        return True

    if hasattr(obj, "__class__"):
        # newstyle
        if hasattr(obj, 'mro'):
            # type/class
            return True
        elif (hasattr(obj, 'im_func') or hasattr(obj, 'func_code') or hasattr(obj, '__self__')):
            # method, func, or builtin func
            return False
        elif hasattr(obj, '__init__'):
            # instance
            return True
    return False

def hasKey(obj, key):
    """Determine if 'obj' has 'key' """
    if hasattr(obj, 'has_key') and key in obj:
        return True
    elif hasattr(obj, key):
        return True
    else:
        return False

def valueForKey(obj, key):
    if hasattr(obj, 'has_key') and key in obj:
        return obj[key]
    elif hasattr(obj, key):
        return getattr(obj, key)
    else:
        _raiseNotFoundException(key, obj)

def _valueForName(obj, name, executeCallables=False):
    nameChunks=name.split('.')
    for i in range(len(nameChunks)):
        key = nameChunks[i]
        if hasattr(obj, 'has_key') and key in obj:
            nextObj = obj[key]
        else:
            try:
                nextObj = getattr(obj, key)
            except AttributeError:
                _raiseNotFoundException(key, obj)

        if executeCallables and hasattr(nextObj, '__call__') and not _isInstanceOrClass(nextObj):
            obj = nextObj()
        else:
            obj = nextObj
    return obj

def valueForName(obj, name, executeCallables=False):
    try:
        return _valueForName(obj, name, executeCallables)
    except NotFound, e:
        _wrapNotFoundException(e, fullName=name, namespace=obj)

def valueFromSearchList(searchList, name, executeCallables=False):
    key = name.split('.')[0]
    for namespace in searchList:
        if hasKey(namespace, key):
            return _valueForName(namespace, name,
                                executeCallables=executeCallables)
    _raiseNotFoundException(key, searchList)

def _namespaces(callerFrame, searchList=None):
    yield callerFrame.f_locals
    if searchList:
        for namespace in searchList:
            yield namespace
    yield callerFrame.f_globals
    yield __builtins__

def valueFromFrameOrSearchList(searchList, name, executeCallables=False,
                               frame=None):
    def __valueForName():
        try:
            return _valueForName(namespace, name, executeCallables=executeCallables)
        except NotFound, e:
            _wrapNotFoundException(e, fullName=name, namespace=searchList)
    try:
        if not frame:
            frame = inspect.stack()[1][0]
        key = name.split('.')[0]
        for namespace in _namespaces(frame, searchList):
            if hasKey(namespace, key):
                return __valueForName()
        _raiseNotFoundException(key, searchList)
    finally:
        del frame

def valueFromFrame(name, executeCallables=False, frame=None):
    # @@TR consider implementing the C version the same way
    # at the moment it provides a seperate but mirror implementation
    # to valueFromFrameOrSearchList
    try:
        if not frame:
            frame = inspect.stack()[1][0]
        return valueFromFrameOrSearchList(searchList=None,
                                          name=name,
                                          executeCallables=executeCallables,
                                          frame=frame)
    finally:
        del frame

def hasName(obj, name):
    #Not in the C version
    """Determine if 'obj' has the 'name' """
    key = name.split('.')[0]
    if not hasKey(obj, key):
        return False
    try:
        valueForName(obj, name)
        return True
    except NotFound:
        return False
try:
    from Cheetah._namemapper import NotFound, valueForKey, valueForName, \
         valueFromSearchList, valueFromFrameOrSearchList, valueFromFrame
    # it is possible with Jython or Windows, for example, that _namemapper.c hasn't been compiled
    C_VERSION = True
except:
    C_VERSION = False

##################################################
## CLASSES

class Mixin:
    """@@ document me"""
    def valueForName(self, name):
        return valueForName(self, name)

    def valueForKey(self, key):
        return valueForKey(self, key)

##################################################
## if run from the command line ##

def example():
    class A(Mixin):
        classVar = 'classVar val'
        def method(self,arg='method 1 default arg'):
            return arg

        def method2(self, arg='meth 2 default arg'):
            return {'item1':arg}

        def method3(self, arg='meth 3 default'):
            return arg

    class B(A):
        classBvar = 'classBvar val'

    a = A()
    a.one = 'valueForOne'
    def function(whichOne='default'):
        values = {
            'default': 'default output',
            'one': 'output option one',
            'two': 'output option two'
            }
        return values[whichOne]

    a.dic = {
        'func': function,
        'method': a.method3,
        'item': 'itemval',
        'subDict': {'nestedMethod':a.method3}
        }
    b = 'this is local b'

    print(valueForKey(a.dic, 'subDict'))
    print(valueForName(a, 'dic.item'))
    print(valueForName(vars(), 'b'))
    print(valueForName(__builtins__, 'dir')())
    print(valueForName(vars(), 'a.classVar'))
    print(valueForName(vars(), 'a.dic.func', executeCallables=True))
    print(valueForName(vars(), 'a.method2.item1', executeCallables=True))

if __name__ == '__main__':
    example()



