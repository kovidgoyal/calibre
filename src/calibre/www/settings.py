# Django settings
# Import base settings from here into the site specific settings files

import socket, os

DEBUG = socket.gethostname() != 'divok'
TEMPLATE_DEBUG = DEBUG

ADMINS = (
     ('Kovid Goyal', 'kovid@kovidgoyal.net'),
)

MANAGERS = ADMINS

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
if DEBUG:
    MEDIA_ROOT = os.path.join(os.path.dirname(__file__), 'static/')
else:
    MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
if DEBUG:
    MEDIA_URL = 'http://127.0.0.1:8000/site_media/'
else:
    MEDIA_URL = 'http://planet.calibre-ebook.com/site_media/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = '/media/'

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/Los_Angeles'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source',
#     'django.template.loaders.eggs.load_template_source',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
)

ROOT_URLCONF = 'planet.urls'


if DEBUG:
    TEMPLATE_DIRS = (
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
        os.path.join(os.path.dirname(__file__), 'templates'),
    )
else:
    TEMPLATE_DIRS = (
            '/usr/local/calibre/src/calibre/www/templates',
    )




