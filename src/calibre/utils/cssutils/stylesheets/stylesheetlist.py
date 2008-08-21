"""
StyleSheetList implements DOM Level 2 Style Sheets StyleSheetList.
"""
__all__ = ['StyleSheetList']
__docformat__ = 'restructuredtext'
__version__ = '$Id: stylesheetlist.py 1116 2008-03-05 13:52:23Z cthedot $'

class StyleSheetList(list):
    """
    Interface StyleSheetList (introduced in DOM Level 2)

    The StyleSheetList interface provides the abstraction of an ordered
    collection of style sheets.

    The items in the StyleSheetList are accessible via an integral index,
    starting from 0.

    This Python implementation is based on a standard Python list so e.g.
    allows ``examplelist[index]`` usage.
    """
    def item(self, index):
        """
        Used to retrieve a style sheet by ordinal index. If index is
        greater than or equal to the number of style sheets in the list,
        this returns None.
        """
        try:
            return self[index]
        except IndexError:
            return None

    length = property(lambda self: len(self),
        doc="""The number of StyleSheets in the list. The range of valid
        child stylesheet indices is 0 to length-1 inclusive.""")

