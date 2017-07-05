# -*- coding: utf-8 -*-
#
# calibre documentation build configuration file, created by
# sphinx-quickstart.py on Sun Mar 23 01:23:55 2008.
#
# This file is execfile()d with the current directory set to its containing dir.
#
# The contents of this file are pickled, so don't put values in the namespace
# that aren't pickleable (module imports are okay, they're removed automatically).
#
# All configuration values have a default value; values that are commented out
# serve to show the default value.

import sys, os, errno
from datetime import date

# If your extensions are in another directory, add it here.
base = os.path.dirname(os.path.abspath(__file__))
sys.path.append(base)
sys.path.insert(0, os.path.dirname(base))
from setup import __appname__, __version__
import calibre.utils.localization as l  # Ensure calibre translations are installed
import custom
del sys.path[0]
del l
custom
# General configuration
# ---------------------

needs_sphinx = '1.2'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.addons.*') or your custom ones.
extensions = ['sphinx.ext.autodoc', 'custom', 'sidebar_toc', 'sphinx.ext.viewcode']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index' if tags.has('online') else 'simple_index'  # noqa
# kill the warning about index/simple_index not being in a toctree
exclude_patterns = ['simple_index.rst'] if master_doc == 'index' else ['index.rst']
exclude_patterns.append('cli-options-header.rst')
if tags.has('gettext'):  # noqa
    # Do not exclude anything as the strings must be translated. This will
    # generate a warning about the documents not being in a toctree, just ignore
    # it.
    exclude_patterns = []

# The language
language = os.environ.get('CALIBRE_OVERRIDE_LANG', 'en')


def generated_langs():
    try:
        return os.listdir(os.path.join(base, 'generated'))
    except EnvironmentError as e:
        if e.errno != errno.ENOENT:
            raise
    return ()


# ignore generated files in languages other than the language we are building for
ge = {'generated/' + x for x in generated_langs()} | {
    'generated/' + x for x in os.environ.get('ALL_USER_MANUAL_LANGUAGES', '').split()}
ge.discard('generated/' + language)
exclude_patterns += list(ge)
del ge

# General substitutions.
project = __appname__
copyright = 'Kovid Goyal'

# The default replacements for |version| and |release|, also used in various
# other places throughout the built documents.
#
# The short X.Y version.
version = __version__
# The full version, including alpha/beta/rc tags.
release = __version__

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
# today = ''
# Else, today_fmt is used as the format for a strftime call.
today_fmt = '%B %d, %Y'

# List of documents that shouldn't be included in the build.
unused_docs = ['global', 'cli/global']

locale_dirs = ['locale/']
title = '%s User Manual' % __appname__
if language not in {'en', 'eng'}:
    import gettext
    try:
        t = gettext.translation('simple_index', locale_dirs[0], [language])
    except IOError:
        pass
    else:
        title = t.ugettext(title)

# If true, '()' will be appended to :func: etc. cross-reference text.
# add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
# add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
# show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'


# Options for HTML output
# -----------------------

# The style sheet to use for HTML and HTML Help pages. A file of that name
# must exist either in Sphinx' static/ path, or in one of the custom paths
# given in html_static_path.
html_theme = 'alabaster'
html_sidebars = {
    '**': [
        'about.html',
        'searchbox.html',
        'localtoc.html',
        'relations.html',
    ]
}
html_theme_options = {
    'logo': 'logo.png',
    'show_powered_by': False,
    'fixed_sidebar': True,
    'sidebar_collapse': True,
    'analytics_id': 'UA-20736318-1',
    'github_button': False,
}

# The favicon
html_favicon = '../icons/favicon.ico'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the built-in static files,
# so a file named "default.css" will overwrite the built-in "default.css".
html_static_path = ['resources', '../icons/favicon.ico']

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
html_last_updated_fmt = '%b %d, %Y'

# Overall title of the documentation
# html_title       = title
html_short_title = _('Start')

from calibre.utils.localization import get_language
html_context = {}
html_context['other_languages'] = [
    (lc, get_language(lc)) for lc in os.environ.get('ALL_USER_MANUAL_LANGUAGES', '').split() if lc != language]


def sort_languages(x):
    from calibre.utils.icu import sort_key
    lc, name = x
    if lc == language:
        return ''
    return sort_key(unicode(name))


html_context['other_languages'].sort(key=sort_languages)
html_context['support_text'] = _('Support calibre')
html_context['support_tooltip'] = _('Contribute to support calibre development')
del sort_languages, get_language

epub_author      = u'Kovid Goyal'
epub_publisher   = u'Kovid Goyal'
epub_copyright   = u'© {} Kovid Goyal'.format(date.today().year)
epub_description = u'Comprehensive documentation for calibre'
epub_identifier  = u'https://manual.calibre-ebook.com'
epub_scheme      = u'url'
epub_uid         = u'S54a88f8e9d42455e9c6db000e989225f'
epub_tocdepth    = 4
epub_tocdup      = True
epub_cover       = ('epub_cover.jpg', 'epub_cover_template.html')

# Custom sidebar templates, maps document names to template names.
# html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
# html_additional_pages = {}

html_use_modindex = False
html_use_index = False

# If true, the reST sources are included in the HTML build as _sources/<name>.
html_copy_source = True

# Output file base name for HTML help builder.
htmlhelp_basename = 'calibredoc'

html_use_opensearch = 'https://manual.calibre-ebook.com'

html_show_sphinx = False

# Options for LaTeX output
# ------------------------

# The paper size ('letter' or 'a4').
latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, document class [howto/manual]).
latex_documents = [(master_doc, 'calibre.tex', title, 'Kovid Goyal', 'manual', False)]

# Additional stuff for the LaTeX preamble.
# latex_preamble = ''

# Documents to append as an appendix to all manuals.
# latex_appendices = []

# If false, no module index is generated.
# latex_use_modindex = True

latex_logo = 'resources/logo.png'
latex_show_pagerefs = True
latex_show_urls = 'footnote'
latex_elements = {
    'papersize':'letterpaper',
    'fontenc':r'\usepackage[T2A,T1]{fontenc}',
    'preamble': r'\renewcommand{\pageautorefname}{%s}' % _('page'),
}
