.. image:: https://travis-ci.org/django/djangopeople.png?branch=master
   :alt: Build Status
   :target: https://travis-ci.org/django/djangopeople

This is the codebase behind what used to be djangopeople.net and now lives at
people.djangoproject.com.

If you want to add features or make big changes, please `create a new issue`_
first!

.. _create a new issue: https://github.com/django/djangopeople/issues/new

Hacking
-------

::

    git clone git@github.com:django/djangopeople.git
    cd djangopeople
    mkvirtualenv -p python3.7 djangopeople
    pip install -r requirements-dev.txt
    add2virtualenv .
    npm install
    ln -s node_modules/.bin/grunt grunt

Check ``env/DATABASE_URL`` to configure a local DB.

Then::

    python manage.py migrate --noinput && python manage.py fix_counts
    python manage.py runserver

The development server is now running on http://localhost:8000.

To run the tests::

    python manage.py test

Translations
------------

To update translations from Transifex, run::

    make txpull
    python manage.py compilemessages

To push new strings to Transifex, run::

    python manage.py makemessages -l en
    make txpush

Update the ``LANGUAGES`` setting in ``settings.py`` when adding new languages
to the ``locale`` directory.

Deploying on Heroku
-------------------

Set a bunch of environment variables:

* ``AWS_ACCESS_KEY``
* ``AWS_SECRET_KEY``
* ``AWS_BUCKET_NAME``
* ``DATABASE_URL``
* ``SECRET_KEY``
* ``SENTRY_DSN``
* ``DJANGO_SETTINGS_MODULE`` (set it to ``djangopeople.settings``)
* ``FROM_EMAIL``
* ``API_PASSWORD``
* ``CANONICAL_HOSTNAME`` (e.g. people.djangoproject.com)

Optionally:

* Add the redistogo addon

First deploy::

    make initialdeploy

Subsequent deploys::

    make deploy

-------

Original README from Simon Willison:

This is an unmodified (except removal of secrets and API keys) dump of the
code now running on djangopeople.net - the vast majority of which was
developed between January and April 2008 by Simon Willison and Natalie Downe.

It originally ran on Django r7400, but has recently been updated for Django 1.1.

This code was not originally intended for public consumption, so there are
probably one or two eyebrow raising design decisions. In particular, the
machine tags stuff for user profiles was an ambitious experiment which I
wouldn't mind seeing the back of.
