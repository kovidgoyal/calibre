"""
CSSRuleList implements DOM Level 2 CSS CSSRuleList.

Partly also
    * http://dev.w3.org/csswg/cssom/#the-cssrulelist
"""
__all__ = ['CSSRuleList']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssrulelist.py 1116 2008-03-05 13:52:23Z cthedot $'

class CSSRuleList(list):
    """
    The CSSRuleList object represents an (ordered) list of statements.

    The items in the CSSRuleList are accessible via an integral index,
    starting from 0.

    Subclasses a standard Python list so theoretically all standard list
    methods are available. Setting methods like ``__init__``, ``append``,
    ``extend`` or ``__setslice__`` are added later on instances of this
    class if so desired.
    E.g. CSSStyleSheet adds ``append`` which is not available in a simple
    instance of this class! 

    Properties
    ==========
    length: of type unsigned long, readonly
        The number of CSSRules in the list. The range of valid child rule
        indices is 0 to length-1 inclusive.
    """
    def __init__(self, *ignored):
        "nothing is set as this must also be defined later"
        pass
    
    def __notimplemented(self, *ignored):
        "no direct setting possible"
        raise NotImplementedError(
            'Must be implemented by class using an instance of this class.')
    
    append = extend =  __setitem__ = __setslice__ = __notimplemented
    
    def item(self, index):
        """
        (DOM)
        Used to retrieve a CSS rule by ordinal index. The order in this
        collection represents the order of the rules in the CSS style
        sheet. If index is greater than or equal to the number of rules in
        the list, this returns None.

        Returns CSSRule, the style rule at the index position in the
        CSSRuleList, or None if that is not a valid index.
        """
        try:
            return self[index]
        except IndexError:
            return None

    length = property(lambda self: len(self),
        doc="(DOM) The number of CSSRules in the list.")

