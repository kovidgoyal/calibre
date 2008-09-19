"""cssutils helper
"""
__all__ = ['Deprecated', 'normalize']
__docformat__ = 'restructuredtext'
__version__ = '$Id: errorhandler.py 1234 2008-05-22 20:26:12Z cthedot $'

import re

class Deprecated(object):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.

    It accepts a single paramter ``msg`` which is shown with the warning.
    It should contain information which function or method to use instead.
    """
    def __init__(self, msg):
        self.msg = msg

    def __call__(self, func):
        def newFunc(*args, **kwargs):
            import warnings
            warnings.warn("Call to deprecated method %r. %s" %
                            (func.__name__, self.msg),
                            category=DeprecationWarning,
                            stacklevel=2)
            return func(*args, **kwargs)
        newFunc.__name__ = func.__name__
        newFunc.__doc__ = func.__doc__
        newFunc.__dict__.update(func.__dict__)
        return newFunc

# simple escapes, all non unicodes
_simpleescapes = re.compile(ur'(\\[^0-9a-fA-F])').sub
        
def normalize(x):
    """
    normalizes x, namely:

    - remove any \ before non unicode sequences (0-9a-zA-Z) so for
      x=="c\olor\" return "color" (unicode escape sequences should have
      been resolved by the tokenizer already)
    - lowercase
    """
    if x:
        def removeescape(matchobj):
            return matchobj.group(0)[1:]
        x = _simpleescapes(removeescape, x)
        return x.lower()
    else:
        return x