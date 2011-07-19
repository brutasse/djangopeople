from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import mail
from django.core.urlresolvers import reverse
from django.middleware.common import CommonMiddleware
from django.test import TestCase
from django.test.client import RequestFactory

from tagging.utils import edit_string_for_tags

from django_openidauth.models import associate_openid
from django_openidconsumer.util import OpenID

from djangopeople.models import (Country, CountrySite, DjangoPerson, Region,
                                 PortfolioSite)
from djangopeople.views import signup, openid_whatnext


def prepare_request(request, openid=True):
    """
    Given a raw request coming from a RequestFactory, process it
    using the middleware and (if openid is True) attach an openid to it
    """
    if openid:
        request.openid = OpenID('http://foo.example.com/', 1302206357)
    for m in (CommonMiddleware, SessionMiddleware):
        m().process_request(request)
    return request


class DjangoPeopleTest(TestCase):
    fixtures = ['test_data']

    def test_simple_pages(self):
        """Simple pages with no action"""
        names = ['index', 'about', 'recent']
        for name in names:
            url = reverse(name)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)

    def test_login(self):
        url = reverse('login')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = {'username': 'foo',
                'password': 'bar'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)

        User.objects.create_user('foo', 'test@example.com', 'bar')
        response = self.client.post(url, data, follow=True)
        self.assertEqual(response.status_code, 404)  # Missing DjangoPerson
        self.assertEqual(len(response.redirect_chain), 1)

        response = self.client.get(reverse('logout'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.redirect_chain), 1)
        self.assertTrue('log in' in response.content)

        self.client.logout()
        data['next'] = reverse('about')
        response = self.client.post(url, data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('<h1>About Django People</h1>' in response.content)

    def test_recover_account(self):
        url = reverse('recover')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        expected = '<label for="id_username">Username'
        self.assertTrue(expected in response.content)

        data = {'username': 'foo'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('That was not a valid username' in response.content)

        user = User.objects.create_user('foo', 'test@example.com', 'bar')
        DjangoPerson.objects.create(user=user,
                                    country=Country.objects.get(pk=1),
                                    latitude=0,
                                    longitude=0,
                                    location_description='Somewhere')
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('An e-mail has been sent' in response.content)
        self.assertEqual(len(mail.outbox), 1)

        content = mail.outbox[0].body
        url = content.split('\n\n')[2]
        url = url.replace('http://djangopeople.net', '')
        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.redirect_chain), 1)
        self.assertTrue('<h1>Change your password</h1>' in response.content)

    def test_signup(self):
        url = reverse('signup')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = {
            'username': 'testuser',
            'email': 'foo@example.com',
            'first_name': 'Test',
            'last_name': 'User',
            'latitude': '45',
            'longitude': '2',
            'country': 'FR',
            'location_description': 'Somewhere',
            'privacy_search': 'public',
            'privacy_email': 'private',
            'privacy_im': 'private',
            'privacy_irctrack': 'public',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 3)

        data['password1'] = 'secret'
        data['password2'] = 'othersecret'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 3)

        data['password2'] = 'secret'
        response = self.client.post(url, data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 4)
        self.assertEqual(len(response.redirect_chain), 1)

        # Logged in users go back to the homepage
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.client.session.flush()

        # Registration with an OpenID shouldn't ask for a password
        factory = RequestFactory()
        request = prepare_request(factory.get(url))
        response = signup(request)
        response.render()
        self.assertTrue('foo.example.com' in response.content)

        del data['password1']
        del data['password2']
        data['username'] = 'meh'
        data['email'] = 'other@example.com'
        request = prepare_request(factory.post(url, data))
        response = signup(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'],
                         reverse('user_profile', args=['meh']))
        self.assertEqual(User.objects.count(), 5)
        self.assertEqual(DjangoPerson.objects.count(), 4)

    def test_whatnext(self):
        """Redirection after a successful openid login"""
        url = reverse('openid_whatnext')

        # No openid -> homepage
        response = self.client.get(url)
        self.assertRedirects(response, reverse('index'))

        # Anonymous user, openid -> signup
        factory = RequestFactory()
        request = prepare_request(factory.get(url))
        response = openid_whatnext(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('signup'))

        user = User.objects.create_user('testuser', 'foo@example.com', 'pass')
        DjangoPerson.objects.create(
            user=user,
            country=Country.objects.get(pk=1),
            latitude=44,
            longitude=2,
            location_description='Somewhere',
        )
        associate_openid(user, 'http://foo.example.com/')

        # Anonymous user, openid + assoc. with an existing user -> profile
        response = openid_whatnext(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'],
                         reverse('user_profile', args=['testuser']))

        # Authenticated user -> openid associations
        self.client.login(username='testuser', password='pass')
        request = prepare_request(factory.get(url))
        request.session = self.client.session
        response = openid_whatnext(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('openid_associations'))

    def test_search(self):
        url = reverse('search')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # search with too short string
        data = {'q': 'ab'}
        response = self.client.get(url, data)
        self.assertContains(response, 'Terms must be three or more characters')

        # search non-existent user
        data = {'q': 'Santa'}
        response = self.client.get(url, data)
        self.assertContains(response, 'No users found.')

        # search and find (first_name)
        data = {'q': 'Dave'}
        response = self.client.get(url, data)
        self.assertContains(response, '<span class="family-name">'
                                      'Brubeck</span>')

        # search and find (username)
        data = {'q': 'DaveB'}
        response = self.client.get(url, data)
        self.assertContains(response, '<span class="family-name">'
                                      'Brubeck</span>')

        # search and find (last_name)
        data = {'q': 'brubec'}
        response = self.client.get(url, data)
        self.assertContains(response, '1 result')
        self.assertContains(response,
                            '<span class="family-name">Brubeck</span>')

    def test_skill_cloud(self):
        url = reverse('skill_cloud')
        response = self.client.get(url)
        linux_url = reverse('skill_detail', args=['linux'])
        self.assertContains(response, linux_url)

    def test_skill_detail(self):
        url = reverse('skill_detail', args=['jazz'])
        response = self.client.get(url)
        self.assertContains(response, '1 Django Person mention this skill')
        self.assertContains(response,
                            '<span class="family-name">Brubeck</span')

        url = reverse('skill_detail', args=['xxx'])
        response = self.client.get(url)
        self.assertEquals(response.status_code, 404)

    def test_country_skill_cloud(self):
        url = reverse('country_skill_cloud', args=['at'])
        response = self.client.get(url)

        python_url = reverse('country_skill', args=['at', 'python'])
        self.assertContains(response, python_url)
        self.assertContains(response, 'img/flags/at.gif')

        url = reverse('country_skill_cloud', args=['xy'])
        response = self.client.get(url)
        self.assertEquals(response.status_code, 404)

    def test_country_skill(self):
        url = reverse('country_skill', args=['at', 'python'])
        response = self.client.get(url)
        self.assertContains(response, 'Dave Brubeck')
        self.assertContains(response, '1 Django Person mention this skill')

    def test_country_looking_for(self):
        url = reverse('country_looking_for', args=['at', 'full-time'])
        response = self.client.get(url)
        self.assertContains(response, 'Austria, seeking full-time work')
        self.assertTrue('Dave Brubeck' in response.content)

        url = reverse('country_looking_for', args=['fr', 'freelance'])
        response = self.client.get(url)
        self.assertContains(response, 'France, seeking freelance work')

    def test_country_detail(self):
        url = reverse('country_detail', args=['at'])
        response = self.client.get(url)
        self.assertContains(response, 'Austria')
        self.assertContains(response, '1 Django person')
        self.assertContains(response, 'Dave')

        url = reverse('country_detail', args=['xy'])
        response = self.client.get(url)
        self.assertEquals(response.status_code, 404)

    def test_sites(self):
        url = reverse('country_sites', args=['at'])
        response = self.client.get(url)
        self.assertContains(response, 'Sites in Austria')
        self.assertContains(response, 'Dave')
        self.assertContains(response, 'cheese-shop')

    def test_user_profile(self):
        url = reverse('user_profile', args=['daveb'])
        response = self.client.get(url)
        self.assertContains(response, 'Django projects Dave has '
                                      'contributed to')
        self.assertContains(response, 'Brubeck')
        self.assertContains(response, 'jazz')
        self.assertContains(response, 'cheese-shop')
        self.assertContains(response, 'full-time')
        self.assertContains(response, 'Vienna, Austria')

    def test_irc_active(self):
        url = reverse('irc_active')
        response = self.client.get(url)
        self.assertContains(response, 'Active on IRC in the past hour')
        self.assertContains(response, 'No one is currently active')

        # update dave's irc time
        dave = DjangoPerson.objects.get(pk=1)
        dave.last_active_on_irc = datetime.now()
        dave.save()

        response = self.client.get(url)
        self.assertContains(response, 'Dave Brubeck')
        self.assertContains(response, '1 person')

    def test_irc_lookup(self):
        url = reverse('irc_lookup', args=['nobody'])
        response = self.client.get(url)
        self.assertContains(response, 'no match')

        url = reverse('irc_lookup', args=['davieboy'])
        response = self.client.get(url)
        self.assertContains(response,
            'Dave Brubeck, Vienna, Austria, Austria, http://testserver/daveb/')

    def test_irc_redirect(self):
        url = reverse('irc_redirect', args=['nobody'])
        response = self.client.get(url)
        self.assertContains(response, 'no match')

        url = reverse('irc_redirect', args=['davieboy'])
        response = self.client.get(url)
        self.assertRedirects(response, 'http://testserver/daveb/')

    def test_irc_spotted(self):
        url = reverse('irc_spotted', args=['nobody'])

        data = {'sekrit': 'wrong password', }
        response = self.client.post(url, data)
        self.assertContains(response, 'BAD_SEKRIT')

        data = {'sekrit': settings.API_PASSWORD, }
        response = self.client.post(url, data)
        self.assertContains(response, 'NO_MATCH')

        url = reverse('irc_spotted', args=['davieboy'])
        data = {'sekrit': settings.API_PASSWORD, }
        response = self.client.post(url, data)
        self.assertContains(response, 'FIRST_TIME_SEEN')

        response = self.client.post(url, data)
        self.assertContains(response, 'TRACKED')

class EditViewTest(TestCase):
    fixtures = ['test_data']

    def setUp(self):
        super(EditViewTest, self).setUp()
        self.client.login(username='daveb', password='123456')

    def test_edit_skill_permission(self):
        '''
        logged in user can only edit his own skills
        '''
        url_edit_skills = reverse('edit_skills', args=['daveb'])
        response = self.client.get(url_edit_skills)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url_edit_skills)
        self.assertEqual(response.status_code, 302)

        url_edit_skills = reverse('edit_skills', args=['satchmo'])
        response = self.client.get(url_edit_skills)
        self.assertEqual(response.status_code, 403)
        response = self.client.post(url_edit_skills)
        self.assertEqual(response.status_code, 403)

    def test_add_skills(self):
        '''
        test adding skills
        '''
        url_edit_skills = reverse('edit_skills', args=['daveb'])
        
        p = DjangoPerson.objects.get(user__username='daveb')
        self.assertEqual(len(p.skilltags), 3)
        self.assertTrue('jazz' in edit_string_for_tags(p.skilltags))
        self.assertTrue('linux' in edit_string_for_tags(p.skilltags))
        self.assertTrue('python' in edit_string_for_tags(p.skilltags))
        
        skills = '%s django'%(edit_string_for_tags(p.skilltags))
        self.client.post(url_edit_skills, {'skills': skills})

        p = DjangoPerson.objects.get(user__username='daveb')
        self.assertEqual(len(p.skilltags), 4)
        self.assertTrue('jazz' in edit_string_for_tags(p.skilltags))
        self.assertTrue('linux' in edit_string_for_tags(p.skilltags))
        self.assertTrue('python' in edit_string_for_tags(p.skilltags))
        self.assertTrue('django' in edit_string_for_tags(p.skilltags))

    def test_delete_skill(self):
        '''
        test deleting skills
        '''
        url_edit_skills = reverse('edit_skills', args=['daveb'])
        
        p = DjangoPerson.objects.get(user__username='daveb')
        self.assertEqual(len(p.skilltags), 3)
        self.assertTrue('jazz' in edit_string_for_tags(p.skilltags))
        self.assertTrue('linux' in edit_string_for_tags(p.skilltags))
        self.assertTrue('python' in edit_string_for_tags(p.skilltags))

        # delete jazz skill
        skills = 'linux python'
        self.client.post(url_edit_skills, {'skills': skills})
        p = DjangoPerson.objects.get(user__username='daveb')
        self.assertEqual(len(p.skilltags), 2)
        self.assertTrue('linux' in edit_string_for_tags(p.skilltags))
        self.assertTrue('python' in edit_string_for_tags(p.skilltags))
        self.assertFalse('jazz' in edit_string_for_tags(p.skilltags))
        
        # delete all skills
        response = self.client.post(url_edit_skills, {'skills': ''})
        p = DjangoPerson.objects.get(user__username='daveb')

        self.assertEqual(len(p.skilltags), 0)
        self.assertEqual(edit_string_for_tags(p.skilltags), '')

    def test_edit_account_permission(self):
        '''
        logged in user can only edit his own account
        '''
        url_edit_account = reverse('edit_account', args=['daveb'])
        response = self.client.get(url_edit_account)
        self.assertEqual(response.status_code, 200)

        url_edit_account = reverse('edit_account', args=['satchmo'])
        response = self.client.get(url_edit_account)
        self.assertEqual(response.status_code, 403)

    def test_edit_account(self):
        '''
        add and change openid
        '''
        url_profile = reverse('user_profile', args=['daveb'])
        url_edit_account = reverse('edit_account', args=['daveb'])

        p = DjangoPerson.objects.get(user__username='daveb')
        self.assertEqual(p.openid_server, u'')
        self.assertEqual(p.openid_delegate, u'')
        
        response = self.client.post(url_edit_account,
                                    {'openid_server': 'example.com',
                                     'openid_delegate': 'fooBar.com'})

        self.assertRedirects(response, url_profile)

        p = DjangoPerson.objects.get(user__username='daveb')
        self.assertEqual(p.openid_server, 'http://example.com/')
        self.assertEqual(p.openid_delegate, 'http://fooBar.com/')

        # test display openid change form (with initial data)
        response = self.client.get(url_edit_account)
        self.assertContains(response, '<input type="text" name="openid_server" '
                                      'value="http://example.com/" '
                                      'id="id_openid_server" />')
        self.assertContains(response, '<input type="text" '
                                      'name="openid_delegate" '
                                      'value="http://fooBar.com/" '
                                      'id="id_openid_delegate" />')

        # test change openid settings
        response = self.client.post(url_edit_account,
                                    {'openid_server': 'google.com',
                                     'openid_delegate': 'foo.com'})

        p = DjangoPerson.objects.get(user__username='daveb')
        self.assertEqual(p.openid_server, 'http://google.com/')
        self.assertEqual(p.openid_delegate, 'http://foo.com/')
        
    def test_edit_account_form_error(self):
        '''
        check AccountForm error messages
        '''
        
        p = DjangoPerson.objects.get(user__username='daveb')
        self.assertEqual(p.openid_server, u'')
        self.assertEqual(p.openid_delegate, u'')
        
        url_edit_account = reverse('edit_account', args=['daveb'])
        response = self.client.post(url_edit_account,
                                    {'openid_server': 'example',
                                     'openid_delegate': 'fooBar'})

        self.assertEqual(response.status_code, 200)

        self.assertFormError(response, 'form', 'openid_server',
                             'Enter a valid URL.')
        self.assertFormError(response, 'form', 'openid_delegate',
                             'Enter a valid URL.')
        
        p = DjangoPerson.objects.get(user__username='daveb')
        self.assertEqual(p.openid_server, u'')
        self.assertEqual(p.openid_delegate, u'')

    def test_change_portfolio_entry(self):
        url_profile = reverse('user_profile', args=['daveb'])
        url_edit_portfolio = reverse('edit_portfolio', args=['daveb'])
        response = self.client.get(url_profile)
        self.assertContains(response, '<li><a href="http://example.org/" '
                                      'class="url" rel="nofollow"><cite>'
                                      'cheese-shop</cite></a></li>')

        # test change existing portfolio entry
        response = self.client.post(url_edit_portfolio,
                                    {'title_1': 'chocolate shop',
                                     'url_1': 'cs.org'}, follow=True)
        self.assertRedirects(response, url_profile)
        self.assertNotContains(response, '<li><a href="http://example.org/" '
                                         'class="url" rel="nofollow"><cite>'
                                         'cheese-shop</cite></a></li>')
        self.assertContains(response, '<li><a href="http://cs.org/" class="url'
                                      '" rel="nofollow"><cite>chocolate shop'
                                      '</cite></a></li>')

    def test_remove_portfolio_entry(self):
        # test remove existing portfolio entry
        url_profile = reverse('user_profile', args=['daveb'])
        url_edit_portfolio = reverse('edit_portfolio', args=['daveb'])
        response = self.client.post(url_edit_portfolio,
                                    {'title_1': '', 'url_1': ''}, follow=True)
        self.assertRedirects(response, url_profile)
        self.assertNotContains(response, '<li><a href="http://example.org/" '
                                         'class="url" rel="nofollow"><cite>'
                                         'cheese-shop</cite></a></li>')
        self.assertNotContains(response, '<li><a href="cs.org/" class="url" '
                                         'rel="nofollow"><cite>chocolate shop'
                                         '</cite></a></li>')
        self.assertContains(response, 'Add some sites')

    def test_add_portfolio_entry(self):
        # test add new portfolio entry

        url_profile = reverse('user_profile', args=['daveb'])
        url_edit_portfolio = reverse('edit_portfolio', args=['daveb'])
        response = self.client.post(url_edit_portfolio,
                                    {'title_1': 'chocolate shop',
                                     'url_1': 'cs.org'},
                                    follow=True)
        self.assertRedirects(response, url_profile)
        self.assertNotContains(response, 'Add some sites')
        self.assertContains(response, '<li><a href="http://cs.org/" class="url'
                                      '" rel="nofollow"><cite>chocolate shop'
                                      '</cite></a></li>')

    def test_portfolio_form_url_error(self):
        # test portfolio edit form
        url_edit_portfolio = reverse('edit_portfolio', args=['daveb'])
        response = self.client.get(url_edit_portfolio)
        self.assertContains(response, '<input id="id_title_1" type="text" '
                                      'name="title_1" value="cheese-shop" '
                                      'maxlength="100" />')
        self.assertContains(response, '<input id="id_url_1" type="text" '
                                      'name="url_1" value="http://example.org/'
                                      '" maxlength="255" />')
        self.assertContains(response, '<input id="id_title_2" type="text" '
                                      'name="title_2" maxlength="100" />')
        self.assertContains(response, '<input id="id_url_2" type="text" '
                                      'name="url_2" maxlength="255" />')

        # test form error messages
        response = self.client.post(url_edit_portfolio,
                                    {'title_1': 'chocolate shop',
                                     'url_1': 'no url'},
                                    follow=True)

        self.assertFormError(response, 'form', 'url_1', 'Enter a valid URL.')

    def test_edit_other_user(self):
        # test editing another users portfolio

        # add new user
        user = User.objects.create_user('testuser', 'foo@example.com', 'pass')
        DjangoPerson.objects.create(
            user=user,
            country=Country.objects.get(pk=1),
            latitude=44,
            longitude=2,
            location_description='Somewhere',
        )

        url_profile = reverse('user_profile', args=['testuser'])
        url_edit_portfolio = reverse('edit_portfolio', args=['testuser'])

        # no Add some sites link for user daveb on testuser's profile page
        response = self.client.get(url_profile)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Add some sites')

        # daveb can't add sites to testuser's portfolio
        response = self.client.post(url_edit_portfolio,
                                    {'title_1': 'chocolate shop',
                                     'url_1': 'cs.org'}, follow=True)
        self.assertEqual(response.status_code, 403)

        response = self.client.get(url_profile)
        self.assertNotContains(response, '<li><a href="http://cs.org/" class="'
                                         'url" rel="nofollow"><cite>chocolate '
                                         'shop </cite></a></li>')


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
