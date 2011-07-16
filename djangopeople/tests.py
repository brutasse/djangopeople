from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import mail
from django.core.urlresolvers import reverse
from django.middleware.common import CommonMiddleware
from django.test import TestCase
from django.test.client import RequestFactory

from django_openidauth.models import associate_openid
from django_openidconsumer.util import OpenID

from djangopeople.models import DjangoPerson, Country
from djangopeople.views import signup, openid_whatnext
from datetime import datetime
import settings


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
    fixtures = ['test_data.json']

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
        self.assertEqual(User.objects.count(), 2)

        data['password1'] = 'secret'
        data['password2'] = 'othersecret'
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 2)

        data['password2'] = 'secret'
        response = self.client.post(url, data, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 3)
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
        self.assertEqual(User.objects.count(), 4)
        self.assertEqual(DjangoPerson.objects.count(), 3)

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
        profile = DjangoPerson.objects.create(
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
        self.assertContains(response, '<span class="family-name">Brubeck</span>')

        # search and find (username)
        data = {'q': 'DaveB'}
        response = self.client.get(url, data)
        self.assertContains(response, '<span class="family-name">Brubeck</span>')

        # search and find (last_name)
        data = {'q': 'brubec'}
        response = self.client.get(url, data)
        self.assertContains(response, '1 result')
        self.assertTrue('<span class="family-name">Brubeck</span>' in response.content)

    def test_skill_cloud(self):
        url = reverse('skill_cloud')
        response = self.client.get(url)
        self.assertContains(response, '/skills/linux/')

    def test_skill_detail(self):
        url = '/skills/jazz/'
        response = self.client.get(url)
        self.assertContains(response, '1 Django Person mention this skill')
        self.assertTrue('<span class="family-name">Brubeck</span>', response.content)

        response_404 = self.client.get('/skills/xxx/')
        self.assertEquals(response_404.status_code, 404)

    def test_country_skill_cloud(self):
        url = '/at/skills/'
        response = self.client.get(url)
        self.assertContains(response, '/at/skills/python/')
        self.assertTrue('img/flags/at.gif' in response.content)

        response_404 = self.client.get('/xy/skills/')
        self.assertEquals(response_404.status_code, 404)

    def test_country_skill(self):
        url = '/at/skills/python/'
        response = self.client.get(url)
        self.assertContains(response, 'Dave Brubeck')
        self.assertTrue('1 Django Person mention this skill' in response.content)

    def test_country_looking_for(self):
        url = '/at/looking-for/full-time/'
        response = self.client.get(url)
        self.assertContains(response, 'Austria, seeking full-time work')
        self.assertTrue('Dave Brubeck' in response.content)

        url = '/fr/looking-for/freelance/'
        response = self.client.get(url)
        self.assertContains(response, 'France, seeking freelance work')

    def test_country_detail(self):
        url = '/at/'
        response = self.client.get(url)
        self.assertContains(response, 'Austria')
        self.assertTrue('1 Django person'in response.content)
        self.assertTrue('Dave' in response.content)

        response_404 = self.client.get('/xy/')
        self.assertEquals(response_404.status_code, 404)

    def test_sites(self):
        url = '/at/sites/'
        response = self.client.get(url)
        self.assertContains(response, 'Sites in Austria')
        self.assertTrue('Dave' in response.content)
        self.assertTrue('cheese-shop' in response.content)

    def test_user_profile(self):
        url = '/daveb/'
        response = self.client.get(url)
        self.assertContains(response, 'Django projects Dave has contributed to')
        self.assertTrue('Brubeck' in response.content)
        self.assertTrue('jazz' in response.content)
        self.assertTrue('cheese-shop' in response.content)
        self.assertTrue('full-time' in response.content)
        self.assertTrue('Vienna, Austria' in response.content)

    def test_irc_active(self):
        # update dave's irc time
        dave = DjangoPerson.objects.get(pk=1)
        dave.last_active_on_irc = datetime.now()
        dave.save()

        url = reverse('irc_active')
        response = self.client.get(url)
        self.assertContains(response, 'Active on IRC in the past hour')
        self.assertTrue('Dave Brubeck' in response.content)
        self.assertTrue('1 people' in response.content) #TODO fix the singular in template

    def test_irc_lookup(self):
        url = '/api/irc_lookup/nobody/'
        response = self.client.get(url)
        self.assertContains(response, 'no match')

        url = '/api/irc_lookup/davieboy/'
        response = self.client.get(url)
        self.assertContains(response,
            'Dave Brubeck, Vienna, Austria, Austria, http://testserver/daveb/')

    def test_irc_redirect(self):
        url = '/irc/nobody/'
        response = self.client.get(url)
        self.assertContains(response, 'no match')

        url = '/irc/davieboy/'
        response = self.client.get(url)
        self.assertRedirects(response, 'http://testserver/daveb/')

    def test_irc_spotted(self):
        url = '/api/irc_spotted/nobody/'

        data = {'sekrit': 'wrong password',}
        response = self.client.post(url, data)
        self.assertContains(response, 'BAD_SEKRIT')

        data = {'sekrit': settings.API_PASSWORD,}
        response = self.client.post(url, data)
        self.assertContains(response, 'NO_MATCH')

        url = '/api/irc_spotted/davieboy/'
        data = {'sekrit': settings.API_PASSWORD,}
        response = self.client.post(url, data)
        self.assertContains(response, 'FIRST_TIME_SEEN')

        response = self.client.post(url, data)
        self.assertContains(response, 'TRACKED')
