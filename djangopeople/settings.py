import dj_database_url
import os
import urlparse

from django.core.urlresolvers import reverse_lazy

OUR_ROOT = os.path.realpath(os.path.dirname(__file__))

DEBUG = bool(os.environ.get('DEBUG', False))
TEMPLATE_DEBUG = DEBUG

# OpenID settings
OPENID_REDIRECT_NEXT = reverse_lazy('openid_whatnext')
LOGIN_URL = reverse_lazy('login')

# Tagging settings
FORCE_LOWERCASE_TAGS = True

ADMINS = MANAGERS = ()

DATABASES = {'default': dj_database_url.config()}

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be avilable on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

gettext = lambda s: s
LANGUAGES = (
    ('en', gettext('English')),
    ('cs', gettext('Czech')),
    ('ru', gettext('Russian')),
    ('fr', gettext('French')),
    ('es', gettext('Spanish')),
    ('he', gettext('Hebrew')),
    ('pt', gettext('Portuguese')),
    ('sk', gettext('Slovak')),
)

LOCALE_PATHS = (
    os.path.join(OUR_ROOT, 'locale'),
)

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory where static media will be collected.
STATIC_ROOT = os.path.join(OUR_ROOT, 'static')

SECRET_KEY = os.environ['SECRET_KEY']

MEDIA_URL = '/media/'
STATIC_URL = '/static/'

# Password used by the IRC bot for the API
API_PASSWORD = os.environ['API_PASSWORD']

if DEBUG:
    TEMPLATE_LOADERS = (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    )
else:
    TEMPLATE_LOADERS = (
        ('django.template.loaders.cached.Loader', (
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        )),
    )

MIDDLEWARE_CLASSES = (
    'djangopeople.djangopeople.middleware.CanonicalDomainMiddleware',
    'django.middleware.common.CommonMiddleware',
    'djangopeople.djangopeople.middleware.RemoveWWW',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'djangopeople.django_openidconsumer.middleware.OpenIDMiddleware',
    'django.contrib.admindocs.middleware.XViewMiddleware',
    'djangopeople.djangopeople.middleware.NoDoubleSlashes',
)

if 'SENTRY_DSN' in os.environ:
    MIDDLEWARE_CLASSES += (
        'raven.contrib.django.middleware.Sentry404CatchMiddleware',
    )

ROOT_URLCONF = 'djangopeople.urls'

TEMPLATE_DIRS = ()

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.contrib.auth.context_processors.auth",
    "django.core.context_processors.debug",
    "django.core.context_processors.i18n",
    "django.core.context_processors.media",
    "django.core.context_processors.static",
    "django.core.context_processors.tz",
    "django.contrib.messages.context_processors.messages",
    "sekizai.context_processors.sekizai",
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.humanize',
    'django.contrib.staticfiles',
    'djangosecure',
    'tagging',

    'djangopeople.django_openidconsumer',
    'djangopeople.django_openidauth',
    'djangopeople.djangopeople',
    'djangopeople.machinetags',

    'password_reset',
    'sekizai',
)

if 'SENTRY_DSN' in os.environ:
    INSTALLED_APPS += (
        'raven.contrib.django',
    )

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(asctime)s %(levelname)s: %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'sentry': {
            'level': 'DEBUG',
            'class': 'raven.contrib.django.handlers.SentryHandler',
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': True,
        },
        'raven': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'sentry.errors': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

GEONAMES_USERNAME = os.environ.get('GEONAMES_USERNAME', 'brutasse')

if 'CANONICAL_HOSTNAME' in os.environ:
    CANONICAL_HOSTNAME = os.environ['CANONICAL_HOSTNAME']
    ALLOWED_HOSTS = [CANONICAL_HOSTNAME]

SERVER_EMAIL = DEFAULT_FROM_EMAIL = os.environ['FROM_EMAIL']
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django_ses.SESBackend'
    AWS_ACCESS_KEY_ID = os.environ['AWS_ACCESS_KEY']
    AWS_SECRET_ACCESS_KEY = os.environ['AWS_SECRET_KEY']
    AWS_STORAGE_BUCKET_NAME = os.environ['AWS_BUCKET_NAME']
    AWS_QUERYSTRING_AUTH = False
    STATICFILES_STORAGE = 'djangopeople.s3storage.S3HashedFilesStorage'
    STATIC_URL = 'https://%s.s3.amazonaws.com/' % AWS_STORAGE_BUCKET_NAME

    # Run the site over SSL
    MIDDLEWARE_CLASSES = (
        'djangosecure.middleware.SecurityMiddleware',
    ) + MIDDLEWARE_CLASSES
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SECURE = True

    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 2592000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_FRAME_DENY = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if 'REDISTOGO_URL' in os.environ:
    urlparse.uses_netloc.append('redis')
    redis_url = urlparse.urlparse(os.environ['REDISTOGO_URL'])
    CACHES = {
        'default': {
            'BACKEND': 'redis_cache.RedisCache',
            'LOCATION': '{0}:{1}'.format(redis_url.hostname, redis_url.port),
            'OPTIONS': {
                'DB': 0,
                'PASSWORD': redis_url.password,
            },
            'VERSION': os.environ.get('CACHE_VERSION', 0),
        },
    }

try:
    import debug_toolbar  # noqa
except ImportError:
    pass
else:
    INSTALLED_APPS += (
        'debug_toolbar',
    )
