__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

from setuptools import find_packages, setup

# name can be any name.  This name will be used to create .egg file.
# name that is used in packages is the one that is used in the trac.ini file.
# use package name as entry_points
setup(
    name='TracLibprs500Plugins', version='0.1',
    packages=find_packages(exclude=['*.tests*']),
    entry_points = """
        [trac.plugins]
        download = plugins.download
        changelog = plugins.Changelog
    """,
    package_data={'plugins': ['templates/*.html',
                               'htdocs/css/*.css', 
                               'htdocs/images/*']},
)

