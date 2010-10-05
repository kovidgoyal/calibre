# $Id: WebInputMixin.py,v 1.10 2006/01/06 21:56:54 tavis_rudd Exp $
"""Provides helpers for Template.webInput(), a method for importing web
transaction variables in bulk.  See the docstring of webInput for full details.

Meta-Data
================================================================================
Author: Mike Orr <iron@mso.oz.net>
License: This software is released for unlimited distribution under the
         terms of the MIT license.  See the LICENSE file.
Version: $Revision: 1.10 $
Start Date: 2002/03/17
Last Revision Date: $Date: 2006/01/06 21:56:54 $
""" 
__author__ = "Mike Orr <iron@mso.oz.net>"
__revision__ = "$Revision: 1.10 $"[11:-2]

from Cheetah.Utils.Misc import useOrRaise

class NonNumericInputError(ValueError): pass

##################################################
## PRIVATE FUNCTIONS AND CLASSES

class _Converter:
    """A container object for info about type converters.
    .name, string, name of this converter (for error messages).
    .func, function, factory function.
    .default, value to use or raise if the real value is missing.
    .error, value to use or raise if .func() raises an exception.
    """
    def __init__(self, name, func, default, error):
        self.name = name
        self.func = func
        self.default = default
        self.error = error


def _lookup(name, func, multi, converters):
    """Look up a Webware field/cookie/value/session value.  Return
    '(realName, value)' where 'realName' is like 'name' but with any
    conversion suffix strips off.  Applies numeric conversion and
    single vs multi values according to the comments in the source.
    """
    # Step 1 -- split off the conversion suffix from 'name'; e.g. "height:int".
    # If there's no colon, the suffix is "".  'longName' is the name with the 
    # suffix, 'shortName' is without.    
    # XXX This implementation assumes "height:" means "height".
    colon = name.find(':')
    if colon != -1:
        longName = name
        shortName, ext = name[:colon], name[colon+1:]
    else:
        longName = shortName = name
        ext = ''

    # Step 2 -- look up the values by calling 'func'.
    if longName != shortName:
        values = func(longName, None) or func(shortName, None)
    else:
        values = func(shortName, None)
    # 'values' is a list of strings, a string or None.

    # Step 3 -- Coerce 'values' to a list of zero, one or more strings.
    if   values is None:
        values = []
    elif isinstance(values, str):
        values = [values]

    # Step 4 -- Find a _Converter object or raise TypeError.
    try:
        converter = converters[ext]
    except KeyError:
        fmt = "'%s' is not a valid converter name in '%s'"
        tup = (ext, longName)
        raise TypeError(fmt % tup)    

    # Step 5 -- if there's a converter func, run it on each element.
    # If the converter raises an exception, use or raise 'converter.error'.
    if converter.func is not None:
        tmp = values[:]
        values = []
        for elm in tmp:
            try:
                elm = converter.func(elm)
            except (TypeError, ValueError):
                tup = converter.name, elm
                errmsg = "%s '%s' contains invalid characters" % tup
                elm = useOrRaise(converter.error, errmsg)
            values.append(elm)
    # 'values' is now a list of strings, ints or floats.

    # Step 6 -- If we're supposed to return a multi value, return the list
    # as is.  If we're supposed to return a single value and the list is
    # empty, return or raise 'converter.default'.  Otherwise, return the
    # first element in the list and ignore any additional values.
    if   multi:
        return shortName, values
    if len(values) == 0:
        return shortName, useOrRaise(converter.default)
    return shortName, values[0]

# vim: sw=4 ts=4 expandtab
