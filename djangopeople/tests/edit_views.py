from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase

from tagging.utils import edit_string_for_tags

from djangopeople.models import (DjangoPerson, Country)


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

    def test_edit_password_permission(self):
        '''
        logged in user can only edit his own password
        '''
        url_edit_password = reverse('edit_password', args=['daveb'])

        # user can edit his own password
        response = self.client.get(url_edit_password)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(url_edit_password)
        self.assertEqual(response.status_code, 200)

        # user can't edit passwords of other users
        url_edit_password = reverse('edit_password', args=['satchmo'])
        response = self.client.get(url_edit_password)
        self.assertEqual(response.status_code, 403)
        response = self.client.post(url_edit_password)
        self.assertEqual(response.status_code, 403)

    def test_edit_password(self):
        '''
        test editing passwords
        '''
        url_edit_password = reverse('edit_password', args=['daveb'])
        url_profile = reverse('user_profile', args=['daveb'])

        response = self.client.get(url_edit_password)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'edit_password.html')
        
        u = User.objects.get(username='daveb')
        self.assertTrue(u.check_password('123456'))

        response = self.client.post(url_edit_password,
                                    {'current_password': '123456',
                                     'password1': 'foo',
                                     'password2': 'foo'})

        self.assertRedirects(response, url_profile)
        u = User.objects.get(username='daveb')
        self.assertTrue(u.check_password('foo'))

    
    def test_edit_password_form_current_password_error(self):
        '''
        test form error messages when current password is invalid
        '''
        url_edit_password = reverse('edit_password', args=['daveb'])

        response = self.client.post(url_edit_password,
                                    {'current_password': 'invalid pw',
                                     'password1': 'foo1',
                                     'password2': 'foo'})

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'current_password', 'Please submit your current password.')

    def test_edit_password_form_error_fields_required(self):
        '''
        test form error messages when form fields are empty
        '''
        url_edit_password = reverse('edit_password', args=['daveb'])

        response = self.client.post(url_edit_password, {'password1': 'foo1'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'password2', 'This field is required.')

        response = self.client.post(url_edit_password, {'password2': 'foo1'})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'password1', 'This field is required.')

        response = self.client.post(url_edit_password, {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'password1', 'This field is required.')
        self.assertFormError(response, 'form', 'password2', 'This field is required.')

    def test_edit_password_form_error_different_passwords(self):
        '''
        test form error message when user submits two different
        passwords
        '''
        url_edit_password = reverse('edit_password', args=['daveb'])

        u = User.objects.get(username='daveb')
        self.assertTrue(u.check_password('123456'))

        # two passwords aren't the same
        response = self.client.post(url_edit_password, {'password1': 'foo1',
                                                        'password2': 'foo'})

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', None, 'The passwords did not match.')

        u = User.objects.get(username='daveb')
        self.assertTrue(u.check_password('123456'))