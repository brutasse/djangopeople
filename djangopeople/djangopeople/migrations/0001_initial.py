# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Country',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=50, verbose_name='Name')),
                ('iso_code', models.CharField(unique=True, max_length=2, verbose_name='ISO code')),
                ('iso_numeric', models.CharField(unique=True, max_length=3, verbose_name='ISO numeric code')),
                ('iso_alpha3', models.CharField(unique=True, max_length=3, verbose_name='ISO alpha-3')),
                ('fips_code', models.CharField(unique=True, max_length=2, verbose_name='FIPS code')),
                ('continent', models.CharField(max_length=2, verbose_name='Continent')),
                ('capital', models.CharField(max_length=30, verbose_name='Capital', blank=True)),
                ('area_in_sq_km', models.FloatField(verbose_name='Area in square kilometers')),
                ('population', models.IntegerField(verbose_name='Population')),
                ('currency_code', models.CharField(max_length=3, verbose_name='Currency code')),
                ('languages', models.CharField(max_length=60, verbose_name='Languages')),
                ('geoname_id', models.IntegerField(verbose_name='Geonames ID')),
                ('bbox_west', models.FloatField()),
                ('bbox_north', models.FloatField()),
                ('bbox_east', models.FloatField()),
                ('bbox_south', models.FloatField()),
                ('num_people', models.IntegerField(default=0, verbose_name='Number of people')),
            ],
            options={
                'ordering': ('name',),
                'verbose_name': 'Country',
                'verbose_name_plural': 'Countries',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CountrySite',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=100, verbose_name='Title')),
                ('url', models.URLField(max_length=255, verbose_name='URL')),
                ('country', models.ForeignKey(verbose_name='Country', to='djangopeople.Country')),
            ],
            options={
                'verbose_name': 'Country site',
                'verbose_name_plural': 'Country sites',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='DjangoPerson',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('bio', models.TextField(verbose_name='Bio', blank=True)),
                ('latitude', models.FloatField(verbose_name='Latitude')),
                ('longitude', models.FloatField(verbose_name='Longitude')),
                ('location_description', models.CharField(max_length=50, verbose_name='Location')),
                ('photo', models.FileField(upload_to=b'profiles', blank=True)),
                ('profile_views', models.IntegerField(default=0, verbose_name='Profile views')),
                ('openid_server', models.URLField(max_length=255, verbose_name='OpenID server', blank=True)),
                ('openid_delegate', models.URLField(max_length=255, verbose_name='OpenID delegate', blank=True)),
                ('last_active_on_irc', models.DateTimeField(null=True, verbose_name='Last active on IRC', blank=True)),
                ('country', models.ForeignKey(verbose_name='Country', to='djangopeople.Country')),
            ],
            options={
                'verbose_name': 'Django person',
                'verbose_name_plural': 'Django people',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PortfolioSite',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=100, verbose_name='Title')),
                ('url', models.URLField(max_length=255, verbose_name='URL')),
                ('contributor', models.ForeignKey(verbose_name='Contributor', to='djangopeople.DjangoPerson')),
            ],
            options={
                'verbose_name': 'Portfolio site',
                'verbose_name_plural': 'Portfolio sites',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Region',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(max_length=20, verbose_name='Code')),
                ('name', models.CharField(max_length=50, verbose_name='Name')),
                ('flag', models.CharField(max_length=100, verbose_name='Flag', blank=True)),
                ('bbox_west', models.FloatField()),
                ('bbox_north', models.FloatField()),
                ('bbox_east', models.FloatField()),
                ('bbox_south', models.FloatField()),
                ('num_people', models.IntegerField(default=0, verbose_name='Number of people')),
                ('country', models.ForeignKey(verbose_name='Country', to='djangopeople.Country')),
            ],
            options={
                'ordering': ('name',),
                'verbose_name': 'Region',
                'verbose_name_plural': 'Regions',
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='djangoperson',
            name='region',
            field=models.ForeignKey(verbose_name='Region', blank=True, to='djangopeople.Region', null=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='djangoperson',
            name='user',
            field=models.OneToOneField(verbose_name='User', to=settings.AUTH_USER_MODEL),
            preserve_default=True,
        ),
    ]
