from django.test import TestCase

from djangopeople.models import (Country, DjangoPerson, Region, CountrySite,
                                 PortfolioSite)


class DjangoPeopleUnitTest(TestCase):
    fixtures = ['test_data']

    def test_region(self):
        ak = Region.objects.get(pk=36)
        self.assertEquals(ak.__unicode__(), u'Alaska')
        self.assertEquals(ak.get_absolute_url(), '/us/ak/')

    def test_country(self):
        us = Country.objects.get(pk=219)
        self.assertEquals(us.__unicode__(), u'United States')
        hawaii = Region.objects.get(pk=32)
        self.assertTrue(hawaii in us.top_regions())
        self.assertTrue(us in Country.objects.top_countries())
        us.num_people = 100000
        us.save()
        self.assertEquals(us, Country.objects.top_countries()[0])

    def test_portfolio_site(self):
        p = PortfolioSite.objects.get(pk=1)
        self.assertEquals(p.__unicode__(),
            u'cheese-shop <http://example.org/>')

    def test_country_site(self):
        cs = CountrySite.objects.get(pk=1)
        self.assertEquals(cs.__unicode__(),
            u'django AT <http://example.org/>')

    def test_django_person(self):
        dave = DjangoPerson.objects.get(pk=1)
        louis = DjangoPerson.objects.get(pk=2)
        self.assertEquals(dave.__unicode__(),
            u'Dave Brubeck')
        self.assertEquals(dave.irc_nick(), 'davieboy')
        self.assertEquals(louis.irc_nick(), '<none>')
        self.assertTrue(dave.irc_tracking_allowed())
        self.assertEquals(dave.get_nearest(), [louis])
        self.assertEquals(louis.location_description_html(),
            'Paris, France')
        self.assertEquals(louis.get_absolute_url(), '/satchmo/')
