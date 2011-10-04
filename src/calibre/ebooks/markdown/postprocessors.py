"""
POST-PROCESSORS
=============================================================================

Markdown also allows post-processors, which are similar to preprocessors in
that they need to implement a "run" method. However, they are run after core
processing.

"""


import markdown

class Processor:
    def __init__(self, markdown_instance=None):
        if markdown_instance:
            self.markdown = markdown_instance

class Postprocessor(Processor):
    """
    Postprocessors are run after the ElementTree it converted back into text.

    Each Postprocessor implements a "run" method that takes a pointer to a
    text string, modifies it as necessary and returns a text string.

    Postprocessors must extend markdown.Postprocessor.

    """

    def run(self, text):
        """
        Subclasses of Postprocessor should implement a `run` method, which
        takes the html document as a single text string and returns a
        (possibly modified) string.

        """
        pass


class RawHtmlPostprocessor(Postprocessor):
    """ Restore raw html to the document. """

    def run(self, text):
        """ Iterate over html stash and restore "safe" html. """
        for i in range(self.markdown.htmlStash.html_counter):
            html, safe  = self.markdown.htmlStash.rawHtmlBlocks[i]
            if self.markdown.safeMode and not safe:
                if str(self.markdown.safeMode).lower() == 'escape':
                    html = self.escape(html)
                elif str(self.markdown.safeMode).lower() == 'remove':
                    html = ''
                else:
                    html = markdown.HTML_REMOVED_TEXT
            if safe or not self.markdown.safeMode:
                text = text.replace("<p>%s</p>" % 
                            (markdown.preprocessors.HTML_PLACEHOLDER % i),
                            html + "\n")
            text =  text.replace(markdown.preprocessors.HTML_PLACEHOLDER % i, 
                                 html)
        return text

    def escape(self, html):
        """ Basic html escaping """
        html = html.replace('&', '&amp;')
        html = html.replace('<', '&lt;')
        html = html.replace('>', '&gt;')
        return html.replace('"', '&quot;')


class AndSubstitutePostprocessor(Postprocessor):
    """ Restore valid entities """
    def __init__(self):
        pass

    def run(self, text):
        text =  text.replace(markdown.AMP_SUBSTITUTE, "&")
        return text
