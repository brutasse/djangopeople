from django.contrib.auth.models import User
from django.core import mail
from django.core.urlresolvers import reverse
from django.test import TestCase
import re

from djangopeople.models import DjangoPerson, Country

RE_REQUIRED_PATTERN = re.compile(r'"errorlist"><li>This field is required.')

class DjangoPeopleTest(TestCase):

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
        self.assertTrue('<label for="id_username">Username' in response.content)

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
        self.assertTrue('<h1>Sign up as a Django Person</h1>' in response.content)

        # password length
        data = {'password1': '123',
                'password2': '123'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('Your password needs to be at least 5 characters long.' in response.content)

        # required fields and specific required fields
        data = {}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('Password is required' in response.content)
        self.assertEquals(12, len(re.findall(RE_REQUIRED_PATTERN, response.content)))

        # valid signup
        data = {'username': 'superstar',
                'first_name': 'Anna',
                'last_name': 'Salsa',
                'email': 'foo@example.com',
                'password1': 'secr3ts',
                'password2': 'secr3ts',
                'location_description': 'somewhere',
                'latitude': '48.20807976550599',
                'longitude': '16.3421630859375',
                'country': 'AT',
                'bio': 'bla bla',
                'blog': 'http://example.org/blog',
                'privacy_search': 'public',
                'privacy_email': 'private',
                'privacy_im': 'public',
                'privacy_irctrack': 'private',
                'skilltags': 'Python, Django, whitespace',
                'looking_for_work': 'freelance'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        new_user = User.objects.get(username='superstar')
        self.assertTrue(new_user.email, 'foo@example.com')
