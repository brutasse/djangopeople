# Django settings for djangopeoplenet project.
import os
OUR_ROOT = os.path.realpath(os.path.dirname(__file__))

DEBUG = False
TEMPLATE_DEBUG = DEBUG

# Thumbnail settings
THUMBNAIL_DEBUG = True
THUMBNAIL_SUBDIR = '_thumbs'

# OpenID settings
OPENID_REDIRECT_NEXT = '/openid/whatnext/'
LOGIN_URL = '/login/'

# Tagging settings
FORCE_LOWERCASE_TAGS = True

AUTH_PROFILE_MODULE = 'djangopeople.DjangoPerson'
RECOVERY_EMAIL_FROM = 'simon@simonwillison.net'

ADMINS = (
    ('Simon Willison', 'simon@simonwillison.net'),
)

MANAGERS = ADMINS

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be avilable on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Europe/London'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = os.path.join(OUR_ROOT, 'media')

# Absolute path to the directory where static media will be collected.
STATIC_ROOT = os.path.join(OUR_ROOT, 'static')

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = '/media/'
STATIC_URL = '/static/'

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
ADMIN_MEDIA_PREFIX = STATIC_URL + 'admin/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'SECRET-KEY-GOES-HERE'

# Password used by the IRC bot for the API
API_PASSWORD = 'API-PASSWORD-GOES-HERE'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'djangopeople.middleware.RemoveWWW',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django_openidconsumer.middleware.OpenIDMiddleware',
    'django.middleware.doc.XViewMiddleware',
    'djangopeople.middleware.NoDoubleSlashes',
)

ROOT_URLCONF = 'urls'

TEMPLATE_DIRS = ()

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.humanize',
    'django.contrib.staticfiles',
    'django_openidconsumer',
    'django_openidauth',
    'djangopeople',
    'machinetags',
    'sorl.thumbnail',
    'tagging',
)
