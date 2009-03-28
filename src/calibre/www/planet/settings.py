# Django settings for planet project.

from calibre.www.settings import DEBUG, TEMPLATE_DEBUG, ADMINS, MANAGERS, \
        TEMPLATE_LOADERS, TEMPLATE_DIRS, MIDDLEWARE_CLASSES, MEDIA_ROOT, \
        MEDIA_URL, ADMIN_MEDIA_PREFIX

if not DEBUG:
    MEDIA_URL = 'http://planet.calibre-ebook.com/site_media/'
    ADMIN_MEDIA_PREFIX = 'http://planet.calibre-ebook.com/admin_media/'
    MEDIA_ROOT = '/usr/local/calibre/src/calibre/www/static/'


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


ROOT_URLCONF = 'calibre.www.planet.urls'

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'calibre.www.apps.feedjack',
)


