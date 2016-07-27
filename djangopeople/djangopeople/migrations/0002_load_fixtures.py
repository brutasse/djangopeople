# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core.management import call_command
from django.db import migrations


def forwards_func(apps, schema_editor):
    call_command('loaddata', 'initial', verbosity=0)


class Migration(migrations.Migration):

    dependencies = [
        ('djangopeople', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards_func),
    ]
