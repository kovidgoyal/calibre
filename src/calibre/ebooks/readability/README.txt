This code is under the Apache License 2.0.  http://www.apache.org/licenses/LICENSE-2.0

This is a python port of a ruby port of arc90's readability project, taken
from https://github.com/buriy/python-readability

The original readability project:
http://lab.arc90.com/experiments/readability/

In few words,
Given a html document, it pulls out the main body text and cleans it up.
It also can clean up title based on latest readability.js code.

Based on:
 - Latest readability.js ( https://github.com/MHordecki/readability-redux/blob/master/readability/readability.js )
 - Ruby port by starrhorne and iterationlabs
 - Python port by gfxmonk ( https://github.com/gfxmonk/python-readability , based on BeautifulSoup )
 - Decruft effort to move to lxml ( http://www.minvolai.com/blog/decruft-arc90s-readability-in-python/ )
 - "BR to P" fix from readability.js which improves quality for smaller texts.
 - Github users contributions.

Installation::

    easy_install readability-lxml
    or
    pip install readability-lxml

Usage::

    from readability.readability import Document
    import urllib
    html = urllib.urlopen(url).read()
    readable_article = Document(html).summary()
    readable_title = Document(html).short_title()

Command-line usage::

    python -m readability.readability -u http://pypi.python.org/pypi/readability-lxml
