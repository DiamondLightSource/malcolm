# -*- coding: utf-8 -*-
#
# malcolm documentation build configuration file

import os
import re
import sys


def get_version():
    """
    Extracts the version number from the version.py file.
    """
    VERSION_FILE = '../malcolm/version.py'
    mo = re.search(
        r'^__version__ = [\'"]([^\'"]*)[\'"]', open(VERSION_FILE, 'rt').read(), re.M)
    if mo:
        return mo.group(1)
    else:
        raise RuntimeError(
            'Unable to find version string in {0}.'.format(VERSION_FILE))

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
try:
    from pkg_resources import require
except:
    pass
else:
    require("mock")
    require("sphinxcontrib-plantuml")
sys.path.insert(0, os.path.abspath(os.path.join(__file__, '..', '..')))

from mock import MagicMock


class Mock(MagicMock):
    @classmethod
    def __getattr__(cls, name):
            return Mock()

MOCK_MODULES = ['numpy']
sys.modules.update((mod_name, Mock()) for mod_name in MOCK_MODULES)


# -- General configuration ------------------------------------------------

extensions = [
    'sphinx.ext.autodoc',
    'sphinxcontrib.plantuml',
    #    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
]

# http://twistedmatrix.com/trac/browser/tags/releases/twisted-8.2.0/twisted/python/procutils.py?format=txt
def which(name, flags=os.X_OK):
    """Search PATH for executable files with the given name.

    On newer versions of MS-Windows, the PATHEXT environment variable will be
    set to the list of file extensions for files considered executable. This
    will normally include things like ".EXE". This fuction will also find files
    with the given name ending with any of these extensions.

    On MS-Windows the only flag that has any meaning is os.F_OK. Any other
    flags will be ignored.

    @type name: C{str}
    @param name: The name for which to search.

    @type flags: C{int}
    @param flags: Arguments to L{os.access}.

    @rtype: C{list}
    @param: A list of the full paths to files found, in the
    order in which they were found.
    """
    result = []
    exts = filter(None, os.environ.get('PATHEXT', '').split(os.pathsep))
    path = os.environ.get('PATH', None)
    if path is None:
        return []
    for p in os.environ.get('PATH', '').split(os.pathsep):
        p = os.path.join(p, name)
        if os.access(p, flags):
            result.append(p)
        for e in exts:
            pext = p + e
            if os.access(pext, flags):
                result.append(pext)
    return result

if not which("plantuml"):
    # download plantuml
    import urllib
    here = os.path.abspath(os.path.dirname(__file__))
    down = os.path.join(here, "plantuml_downloaded.jar")
    urllib.urlretrieve("http://downloads.sourceforge.net/project/plantuml/plantuml.8031.jar?r=http%3A%2F%2Fplantuml.com%2Fdownload.html&ts=1446734489&use_mirror=kent", down)
    plantuml = 'java -jar %s' % down
    print which("java")
    print os.listdir("/usr/bin")
    print os.listdir("/bin")
    print os.listdir(here)
    import platform
    print platform.linux_distribution()
    

autodoc_member_order = 'bysource'

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'toc'

# General information about the project.
project = u'malcolm'
copyright = u'2015, Diamond Light Source'

# The short X.Y version.
version = get_version()
# The full version, including alpha/beta/rc tags.
release = version

exclude_patterns = ['_build']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# intersphinx_mapping = {
#    'python': ('http://python.readthedocs.org/en/v2.7.2/', None),
#}

# -- Options for HTML output ----------------------------------------------

html_theme = 'default'

# Add any paths that contain custom themes here, relative to this directory.
#html_theme_path = []

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# Custom sidebar templates, maps document names to template names.
#html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.
#html_additional_pages = {}

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
html_show_sphinx = False

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
html_show_copyright = True

# Output file base name for HTML help builder.
htmlhelp_basename = 'malcolmdoc'


# -- Options for LaTeX output ---------------------------------------------

latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    #'papersize': 'letterpaper',

    # The font size ('10pt', '11pt' or '12pt').
    #'pointsize': '10pt',

    # Additional stuff for the LaTeX preamble.
    #'preamble': '',
}

# Grouping the document tree into LaTeX files. List of tuples
# (source start file, target name, title,
#  author, documentclass [howto, manual, or own class]).
latex_documents = [
    ('index', 'malcolm.tex', u'malcolm Documentation',
     u'Tom Cobb', 'manual'),
]

# -- Options for manual page output ---------------------------------------

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section).
man_pages = [
    ('index', 'malcolm', u'malcolm Documentation',
     [u'Tom Cobb'], 1)
]

# -- Options for Texinfo output -------------------------------------------

# Grouping the document tree into Texinfo files. List of tuples
# (source start file, target name, title, author,
#  dir menu entry, description, category)
texinfo_documents = [
    ('index', 'malcolm', u'malcolm Documentation',
     u'Tom Cobb', 'malcolm', 'A short description',
     'Miscellaneous'),
]
