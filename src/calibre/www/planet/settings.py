# Django settings for planet project.

from calibre.www.settings import DEBUG, TEMPLATE_DEBUG, ADMINS, MANAGERS, \
        TEMPLATE_LOADERS, TEMPLATE_DIRS, MIDDLEWARE_CLASSES, MEDIA_ROOT, \
        MEDIA_URL, ADMIN_MEDIA_PREFIX

DATABASE_USER = ''             # Not used with sqlite3.
DATABASE_PASSWORD = ''         # Not used with sqlite3.
DATABASE_HOST = ''             # Set to empty string for localhost. Not used with sqlite3.
DATABASE_PORT = ''             # Set to empty string for default. Not used with sqlite3.


if DEBUG:
    DATABASE_ENGINE = 'sqlite3'           # 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
    DATABASE_NAME = '/tmp/planet.db'      # Or path to database file if using sqlite3.
else:
    DATABASE_ENGINE = 'mysql'
    DATABASE_NAME   = 'calibre_planet'
    DATABASE_USER   = 'calibre_django'
    DATABASE_PASSWORD = open('/var/www/calibre-ebook.com/dbpass').read().strip()

SITE_ID = 1

# Make this unique, and don't share it with anybody.
if DEBUG:
    SECRET_KEY = '06mv&t$cobjkijgg#0ndwm5#&90_(tm=oqi1bv-x^vii$*33n5'
else:
    SECRET_KEY = open('/var/www/planet.calibre-ebook.com/django_secret_key').read().strip()


ROOT_URLCONF = 'planet.urls'

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'calibre.www.apps.feedjack',
)


