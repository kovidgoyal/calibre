'''
    Filters for the #filter directive as well as #transform
    
    #filter results in output filters Cheetah's $placeholders .
    #transform results in a filter on the entirety of the output
'''
import sys

# Additional entities WebSafe knows how to transform.  No need to include
# '<', '>' or '&' since those will have been done already.
webSafeEntities = {' ': '&nbsp;', '"': '&quot;'}

class Filter(object):
    """A baseclass for the Cheetah Filters."""
    
    def __init__(self, template=None):
        """Setup a reference to the template that is using the filter instance.
        This reference isn't used by any of the standard filters, but is
        available to Filter subclasses, should they need it.
        
        Subclasses should call this method.
        """
        self.template = template
        
    def filter(self, val, encoding=None, str=str, **kw):
        '''
            Pass Unicode strings through unmolested, unless an encoding is specified.
        '''
        if val is None:
            return u''
        if isinstance(val, unicode):
            # ignore the encoding and return the unicode object
            return val
        else:
            try:
                return unicode(val)
            except UnicodeDecodeError:
                # we could put more fallbacks here, but we'll just pass the str
                # on and let DummyTransaction worry about it
                return str(val)

RawOrEncodedUnicode = Filter

EncodeUnicode = Filter

class Markdown(EncodeUnicode):
    '''
        Markdown will change regular strings to Markdown
            (http://daringfireball.net/projects/markdown/)

        Such that:
            My Header
            =========
        Becaomes:
            <h1>My Header</h1>

        and so on.

        Markdown is meant to be used with the #transform 
        tag, as it's usefulness with #filter is marginal at
        best
    '''
    def filter(self,  value, **kwargs):
        # This is a bit of a hack to allow outright embedding of the markdown module
        try:
            import markdown
        except ImportError:
            print('>>> Exception raised importing the "markdown" module')
            print('>>> Are you sure you have the ElementTree module installed?')
            print('          http://effbot.org/downloads/#elementtree')
            raise

        encoded = super(Markdown, self).filter(value, **kwargs)
        return markdown.markdown(encoded)

class CodeHighlighter(EncodeUnicode):
    '''
        The CodeHighlighter filter depends on the "pygments" module which you can 
        download and install from: http://pygments.org

        What the CodeHighlighter assumes the string that it's receiving is source
        code and uses pygments.lexers.guess_lexer() to try to guess which parser
        to use when highlighting it. 

        CodeHighlighter will return the HTML and CSS to render the code block, syntax 
        highlighted, in a browser

        NOTE: I had an issue installing pygments on Linux/amd64/Python 2.6 dealing with
        importing of pygments.lexers, I was able to correct the failure by adding:
            raise ImportError
        to line 39 of pygments/plugin.py (since importing pkg_resources was causing issues)
    '''
    def filter(self, source, **kwargs):
        encoded = super(CodeHighlighter, self).filter(source, **kwargs)
        try:
            from pygments import highlight
            from pygments import lexers
            from pygments import formatters
        except ImportError, ex:
            print('<%s> - Failed to import pygments! (%s)' % (self.__class__.__name__, ex))
            print('-- You may need to install it from: http://pygments.org')
            return encoded

        lexer = None
        try:
            lexer = lexers.guess_lexer(source)
        except lexers.ClassNotFound:
            lexer = lexers.PythonLexer()

        formatter = formatters.HtmlFormatter(cssclass='code_highlighter')
        encoded = highlight(encoded, lexer, formatter)
        css = formatter.get_style_defs('.code_highlighter')
        return '''<style type="text/css"><!--
                %(css)s
            --></style>%(source)s''' % {'css' : css, 'source' : encoded}



class MaxLen(Filter):
    def filter(self, val, **kw):
        """Replace None with '' and cut off at maxlen."""
        
        output = super(MaxLen, self).filter(val, **kw)
        if 'maxlen' in kw and len(output) > kw['maxlen']:
            return output[:kw['maxlen']]
        return output

class WebSafe(Filter):
    """Escape HTML entities in $placeholders.
    """
    def filter(self, val, **kw):
        s = super(WebSafe, self).filter(val, **kw)
        # These substitutions are copied from cgi.escape().
        s = s.replace("&", "&amp;") # Must be done first!
        s = s.replace("<", "&lt;")
        s = s.replace(">", "&gt;")
        # Process the additional transformations if any.
        if 'also' in kw:
            also = kw['also']
            entities = webSafeEntities   # Global variable.
            for k in also:
                if k in entities:
                    v = entities[k]
                else:
                    v = "&#%s;" % ord(k)
                s = s.replace(k, v)
        return s


class Strip(Filter):
    """Strip leading/trailing whitespace but preserve newlines.

    This filter goes through the value line by line, removing leading and
    trailing whitespace on each line.  It does not strip newlines, so every
    input line corresponds to one output line, with its trailing newline intact.

    We do not use val.split('\n') because that would squeeze out consecutive
    blank lines.  Instead, we search for each newline individually.  This
    makes us unable to use the fast C .split method, but it makes the filter
    much more widely useful.

    This filter is intended to be usable both with the #filter directive and
    with the proposed #sed directive (which has not been ratified yet.)
    """
    def filter(self, val, **kw):
        s = super(Strip, self).filter(val, **kw)
        result = []
        start = 0   # The current line will be s[start:end].
        while True: # Loop through each line.
            end = s.find('\n', start)  # Find next newline.
            if end == -1:  # If no more newlines.
                break
            chunk = s[start:end].strip()
            result.append(chunk)
            result.append('\n')
            start = end + 1
        # Write the unfinished portion after the last newline, if any.
        chunk = s[start:].strip()
        result.append(chunk)
        return "".join(result)

class StripSqueeze(Filter):
    """Canonicalizes every chunk of whitespace to a single space.

    Strips leading/trailing whitespace.  Removes all newlines, so multi-line
    input is joined into one ling line with NO trailing newline.
    """
    def filter(self, val, **kw):
        s = super(StripSqueeze, self).filter(val, **kw)
        s = s.split()
        return " ".join(s)
    
##################################################
## MAIN ROUTINE -- testing
    
def test():
    s1 = "abc <=> &"
    s2 = "   asdf  \n\t  1  2    3\n"
    print("WebSafe INPUT:", repr(s1))
    print("      WebSafe:", repr(WebSafe().filter(s1)))
    
    print()
    print(" Strip INPUT:", repr(s2))
    print("       Strip:", repr(Strip().filter(s2)))
    print("StripSqueeze:", repr(StripSqueeze().filter(s2)))

    print("Unicode:", repr(EncodeUnicode().filter(u'aoeu12345\u1234')))
    
if __name__ == "__main__":  
    test()
    
# vim: shiftwidth=4 tabstop=4 expandtab
