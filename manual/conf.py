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

import sys, os

# If your extensions are in another directory, add it here.
sys.path.append(os.path.abspath('../src'))
sys.path.append(os.path.abspath('.'))
__appname__ = os.environ.get('__appname__', 'calibre')
__version__ = os.environ.get('__version__', '0.0.0')
import custom
custom
# General configuration
# ---------------------

needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.addons.*') or your custom ones.
extensions = ['sphinx.ext.autodoc', 'custom', 'sphinx.ext.viewcode']

# Add any paths that contain templates here, relative to this directory.
templates_path = ['templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# The language
language = 'en'

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
#today = ''
# Else, today_fmt is used as the format for a strftime call.
today_fmt = '%B %d, %Y'

# List of documents that shouldn't be included in the build.
unused_docs = ['global', 'cli/global']


# If true, '()' will be appended to :func: etc. cross-reference text.
#add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
#add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
#show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'


# Options for HTML output
# -----------------------

# The style sheet to use for HTML and HTML Help pages. A file of that name
# must exist either in Sphinx' static/ path, or in one of the custom paths
# given in html_static_path.
html_theme = 'default'
html_theme_options = {'stickysidebar':'true', 'relbarbgcolor':'black'}
# Put the quick search box on top
html_sidebars = {
        '**' : ['searchbox.html', 'localtoc.html', 'relations.html',
            'sourcelink.html'],
}

# The favicon
html_favicon = 'favicon.ico'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the built-in static files,
# so a file named "default.css" will overwrite the built-in "default.css".
html_static_path = ['resources', '../icons/favicon.ico']

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
html_use_smartypants = True

# Overall title of the documentation
html_title       = 'calibre User Manual'
html_short_title = 'Start'
html_logo        = 'resources/logo.png'

epub_author      = 'Kovid Goyal'
kovid_epub_cover       = 'epub_cover.jpg'
epub_publisher   = 'Kovid Goyal'
epub_identifier  = 'http://manual.calibre-ebook.com'
epub_scheme      = 'url'
epub_uid         = 'S54a88f8e9d42455e9c6db000e989225f'
epub_tocdepth    = 4
epub_tocdup      = True
epub_pre_files    = [('epub_titlepage.html', 'Cover')]

# Custom sidebar templates, maps document names to template names.
#html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
#html_additional_pages = {}

html_use_modindex = False
html_use_index = False

# If true, the reST sources are included in the HTML build as _sources/<name>.
html_copy_source = True

# Output file base name for HTML help builder.
htmlhelp_basename = 'calibredoc'

html_use_opensearch = 'http://manual.calibre-ebook.com'

html_show_sphinx = False

# Options for LaTeX output
# ------------------------

# The paper size ('letter' or 'a4').
latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title, author, document class [howto/manual]).
#latex_documents = []

# Additional stuff for the LaTeX preamble.
#latex_preamble = ''

# Documents to append as an appendix to all manuals.
#latex_appendices = []

# If false, no module index is generated.
#latex_use_modindex = True
