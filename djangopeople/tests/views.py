from datetime import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import mail
from django.core.urlresolvers import reverse
from django.middleware.common import CommonMiddleware
from django.test import TestCase
from django.test.client import RequestFactory


from django_openidauth.models import associate_openid
from django_openidconsumer.util import OpenID

from djangopeople.models import (Country, DjangoPerson)
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

    def test_login_redirect(self):
        url = reverse('login')

        data = {'username': 'daveb',
                'password': '123456',
                'next': reverse('redirect_to_logged_in_user_profile')}
        
        response = self.client.post(url, data, follow=True)
        self.assertRedirects(response, reverse('user_profile', args=['daveb']))

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
