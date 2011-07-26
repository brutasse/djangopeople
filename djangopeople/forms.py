from django import forms
from django.conf import settings
from django.core.mail import send_mail
from django.db.models import ObjectDoesNotExist
from django.forms.forms import BoundField
from django.forms.widgets import PasswordInput
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

from tagging.forms import TagField
from tagging.utils import edit_string_for_tags

from djangopeople import utils
from djangopeople.constants import SERVICES, IMPROVIDERS
from djangopeople.groupedselect import GroupedChoiceField
from djangopeople.models import (DjangoPerson, Country, Region, User,
                                 RESERVED_USERNAMES)


def region_choices():
    # For use with GroupedChoiceField
    regions = list(Region.objects.select_related().order_by('country', 'name'))
    groups = [(False, (('', '---'),))]
    current_country = False
    current_group = []
    
    for region in regions:
        if region.country.name != current_country:
            if current_group:
                groups.append((current_country, current_group))
                current_group = []
            current_country = region.country.name
        current_group.append((region.code, region.name))
    if current_group:
        groups.append((current_country, current_group))
        current_group = []
    
    return groups

def not_in_the_atlantic(self):
    if self.cleaned_data.get('latitude', '') and self.cleaned_data.get('longitude', ''):
        lat = self.cleaned_data['latitude']
        lon = self.cleaned_data['longitude']
        
        if 43 < lat < 45 and -39 < lon < -33:
            raise forms.ValidationError("Drag and zoom the map until the crosshair matches your location")
    return self.cleaned_data['location_description']

class SignupForm(forms.Form):
    def __init__(self, *args, **kwargs):
        # Dynamically add the fields for IM providers / external services
        if 'openid' in kwargs:
            self.openid = True
            kwargs.pop('openid')
        else:
            self.openid = False

        super(SignupForm, self).__init__(*args, **kwargs)
        self.service_fields = []
        for shortname, name, icon in SERVICES:
            field = forms.URLField(
                max_length=255, required=False, label=name
            )
            self.fields['service_' + shortname] = field
            self.service_fields.append({
                'label': name,
                'shortname': shortname,
                'id': 'service_' + shortname,
                'icon': icon,
                'field': BoundField(self, field, 'service_' + shortname),
            })

        self.improvider_fields = []
        for shortname, name, icon in IMPROVIDERS:
            field = forms.CharField(
                max_length=50, required=False, label=name
            )
            self.fields['im_' + shortname] = field
            self.improvider_fields.append({
                'label': name,
                'shortname': shortname,
                'id': 'im_' + shortname,
                'icon': icon,
                'field': BoundField(self, field, 'im_' + shortname),
            })

    # Fields for creating a User object
    username = forms.RegexField('^[a-zA-Z0-9]+$', min_length=3, max_length=30)
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput, required=False)
    password2 = forms.CharField(widget=forms.PasswordInput, required=False)

    # Fields for creating a DjangoPerson profile
    bio = forms.CharField(widget=forms.Textarea, required=False)
    blog = forms.URLField(required=False)

    country = forms.ChoiceField(choices = [('', '')] + [
        (c.iso_code, c.name) for c in Country.objects.all()
    ])
    latitude = forms.FloatField(min_value=-90, max_value=90)
    longitude = forms.FloatField(min_value=-180, max_value=180)
    location_description = forms.CharField(max_length=50)

    region = GroupedChoiceField(required=False, choices=region_choices())

    privacy_search = forms.ChoiceField(
        choices = (
            ('public',
             'Allow search engines to index my profile page (recommended)'),
            ('private', "Don't allow search engines to index my profile page"),
        ), widget = forms.RadioSelect, initial='public'
    )
    privacy_email = forms.ChoiceField(
        choices = (
            ('public', 'Anyone can see my e-mail address'),
            ('private', 'Only logged-in users can see my e-mail address'),
            ('never', 'No one can ever see my e-mail address'),
        ), widget = forms.RadioSelect, initial='private'
    )
    privacy_im = forms.ChoiceField(
        choices = (
            ('public', 'Anyone can see my IM details'),
            ('private', 'Only logged-in users can see my IM details'),
        ), widget = forms.RadioSelect, initial='private'
    )
    privacy_irctrack = forms.ChoiceField(
        choices = (
            ('public', 'Keep track of the last time I was seen on IRC (requires your IRC nick)'),
            ('private', "Don't record the last time I was seen on IRC"),
        ), widget = forms.RadioSelect, initial='public'
    )
    looking_for_work = forms.ChoiceField(
        choices = (
            ('', 'Not looking for work at the moment'),
            ('freelance', 'Looking for freelance work'),
            ('full-time', 'Looking for full-time work'),
        ), required=False #, widget = forms.RadioSelect, initial=''
    )

    skilltags = TagField(required=False)

    # Upload a photo is a separate page, because if validation fails we 
    # don't want to tell them to upload it all over again
    #   photo = forms.ImageField(required=False)

    # Fields used to create machinetags

    # Validation
    def clean_password1(self):
        "Only required if NO openid set for this form"
        if not self.openid and not self.cleaned_data.get('password1', ''):
            raise forms.ValidationError('Password is required')
        return self.cleaned_data['password1']

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1', '')
        password2 = self.cleaned_data.get('password2', '')
        if password1.strip() and password1 != password2:
            raise forms.ValidationError('Passwords must match')
        return self.cleaned_data['password2']

    def clean_username(self):
        already_taken = 'That username is unavailable'
        username = self.cleaned_data['username'].lower()

        # No reserved usernames, or anything that looks like a 4 digit year 
        if username in RESERVED_USERNAMES or (len(username) == 4 and username.isdigit()):
            raise forms.ValidationError(already_taken)

        try:
            user = User.objects.get(username = username)
        except User.DoesNotExist:
            pass
        else:
            raise forms.ValidationError(already_taken)

        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        try:
            user = User.objects.get(email = email)
        except User.DoesNotExist:
            pass
        else:
            raise forms.ValidationError('That e-mail is already in use')
        return email

    def clean_region(self):
        # If a region is selected, ensure it matches the selected country
        if self.cleaned_data['region']:
            try:
                region = Region.objects.get(
                    code = self.cleaned_data['region'],
                    country__iso_code = self.cleaned_data['country']
                )
            except ObjectDoesNotExist:
                raise forms.ValidationError(
                    'The region you selected does not match the country'
                )
        return self.cleaned_data['region']

    clean_location_description = not_in_the_atlantic

class PhotoUploadForm(forms.Form):
    photo = forms.ImageField()


class SkillsForm(forms.ModelForm):
    skills = TagField(label='Change skills', required=False)

    class Meta:
        model = DjangoPerson
        fields = ()

    def __init__(self, *args, **kwargs):
        super(SkillsForm, self).__init__(*args, **kwargs)
        self.initial = {'skills': edit_string_for_tags(self.instance.skilltags)}
        
    def save(self):
        self.instance.skilltags = self.cleaned_data['skills']


class BioForm(forms.ModelForm):
    class Meta:
        model = DjangoPerson
        fields = ('bio',)

class AccountForm(forms.ModelForm):
    class Meta:
        model = DjangoPerson
        fields = ('openid_server', 'openid_delegate')

class LocationForm(forms.ModelForm):
    country = forms.ChoiceField(choices = [('', '')] + [
        (c.iso_code, c.name) for c in Country.objects.all()
    ])
    latitude = forms.FloatField(min_value=-90, max_value=90)
    longitude = forms.FloatField(min_value=-180, max_value=180)
    location_description = forms.CharField(max_length=50)

    class Meta:
        model = DjangoPerson
        fields = ('country', 'latitude', 'longitude', 'location_description',
                  'region')

    def clean_country(self):
        try:
            country = Country.objects.get(iso_code=self.cleaned_data['country'])
            return country
        except Country.DoesNotExist:
            raise forms.ValidationError(
                    'The ISO code of the country you selected is invalid.'
                )
    def clean_region(self):
        # If a region is selected, ensure it matches the selected country
        if self.cleaned_data['region']:
            try:
                region = Region.objects.get(
                    code = self.cleaned_data['region'],
                    country__iso_code = self.cleaned_data['country']
                )
            except ObjectDoesNotExist:
                raise forms.ValidationError(
                    'The region you selected does not match the country'
                )
        return self.cleaned_data['region']

    clean_location_description = not_in_the_atlantic

class FindingForm(forms.Form):
    def __init__(self, *args, **kwargs):
        # Dynamically add the fields for IM providers / external services
        self.person = kwargs.pop('person') # So we can validate e-mail later
        super(FindingForm, self).__init__(*args, **kwargs)
        self.service_fields = []
        for shortname, name, icon in SERVICES:
            field = forms.URLField(
                max_length=255, required=False, label=name
            )
            self.fields['service_' + shortname] = field
            self.service_fields.append({
                'label': name,
                'shortname': shortname,
                'id': 'service_' + shortname,
                'icon': icon,
                'field': BoundField(self, field, 'service_' + shortname),
            })

        self.improvider_fields = []
        for shortname, name, icon in IMPROVIDERS:
            field = forms.CharField(
                max_length=50, required=False, label=name
            )
            self.fields['im_' + shortname] = field
            self.improvider_fields.append({
                'label': name,
                'shortname': shortname,
                'id': 'im_' + shortname,
                'icon': icon,
                'field': BoundField(self, field, 'im_' + shortname),
            })

    email = forms.EmailField()
    blog = forms.URLField(required=False)
    privacy_search = forms.ChoiceField(
        choices = (
            ('public',
             'Allow search engines to index my profile page (recommended)'),
            ('private', "Don't allow search engines to index my profile page"),
        ), widget = forms.RadioSelect, initial='public'
    )
    privacy_email = forms.ChoiceField(
        choices = (
            ('public', 'Anyone can see my e-mail address'),
            ('private', 'Only logged-in users can see my e-mail address'),
            ('never', 'No one can ever see my e-mail address'),
        ), widget = forms.RadioSelect, initial='private'
    )
    privacy_im = forms.ChoiceField(
        choices = (
            ('public', 'Anyone can see my IM details'),
            ('private', 'Only logged-in users can see my IM details'),
        ), widget = forms.RadioSelect, initial='private'
    )
    privacy_irctrack = forms.ChoiceField(
        choices = (
            ('public', 'Keep track of the last time I was seen on IRC (requires your IRC nick)'),
            ('private', "Don't record the last time I was seen on IRC"),
        ), widget = forms.RadioSelect, initial='public'
    )
    looking_for_work = forms.ChoiceField(
        choices = (
            ('', 'Not looking for work at the moment'),
            ('freelance', 'Looking for freelance work'),
            ('full-time', 'Looking for full-time work'),
        ), required=False #, widget = forms.RadioSelect, initial=''
    )

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(
            email = email
        ).exclude(djangoperson = self.person).count() > 0:
            raise forms.ValidationError('That e-mail is already in use')
        return email

class PortfolioForm(forms.ModelForm):

    class Meta:
        model = DjangoPerson
        fields = ()
    
    def __init__(self, *args, **kwargs):
        # Dynamically add the fields for IM providers / external services
        super(PortfolioForm, self).__init__(*args, **kwargs)
        self.portfolio_fields = []
        self.initial = {}
        num = 1
        for site in kwargs['instance'].portfoliosite_set.all():
            self.initial['title_%d' % num] = site.title
            self.initial['url_%d' % num] = site.url
            num += 1

        # Add fields
        for i in range(1, num + 3):
            url_field = forms.URLField(
                max_length=255, required=False, label='URL %d' % i
            )
            title_field = forms.CharField(
                max_length=100, required=False, label='Title %d' % i
            )
            self.fields['title_%d' % i] = title_field
            self.fields['url_%d' % i] = url_field
            self.portfolio_fields.append({
                'title_field': BoundField(self, title_field, 'title_%d' % i),
                'url_field': BoundField(self, url_field, 'url_%d' % i),
                'title_id': 'id_title_%d' % i,
                'url_id': 'id_url_%d' % i,
            })

        # Add custom validator for each url field
        for key in [k for k in self.fields if k.startswith('url_')]:
            setattr(self, 'clean_%s' % key, make_validator(key, self))

    def save(self):
        self.instance.portfoliosite_set.all().delete()
        for key in [k for k in self.cleaned_data.keys() if k.startswith('title_')]:
            title = self.cleaned_data[key]
            url = self.cleaned_data[key.replace('title_', 'url_')]
            if title.strip() and url.strip():
                self.instance.portfoliosite_set.create(title=title, url=url)


def make_validator(key, form):
    def check():
        if form.cleaned_data.get(key.replace('url_', 'title_')) and \
            not form.cleaned_data.get(key):
            raise forms.ValidationError, 'You need to provide a URL'
        return form.cleaned_data.get(key)
    return check


class LostPasswordForm(forms.Form):
    username = forms.CharField()

    def clean_username(self):
        username = self.cleaned_data['username']
        try:
            person = DjangoPerson.objects.get(user__username=username)
        except DjangoPerson.DoesNotExist:
            raise forms.ValidationError(_('That was not a valid username.'))
        self.cleaned_data['person'] = person
        return username

    def save(self):
        path = utils.lost_url_for_user(self.cleaned_data['username'])
        person = self.cleaned_data['person']
        body = render_to_string('recovery_email.txt', {
            'path': path,
            'person': person,
        })
        send_mail(
            'Django People account recovery', body,
            settings.RECOVERY_EMAIL_FROM, [person.user.email],
            fail_silently=False
        )


class PasswordForm(forms.ModelForm):
    current_password = forms.CharField(label='Current Password', widget=PasswordInput)
    password1 = forms.CharField(label='New Password', widget=PasswordInput)
    password2 = forms.CharField(label='New Password (again)', widget=PasswordInput)

    class Meta:
        model = User
        fields = ()

    def clean_current_password(self):
        if not self.instance.check_password(self.cleaned_data['current_password']):
            raise forms.ValidationError('Please submit your current password.')
        else:
            return self.cleaned_data['current_password']
        
    def clean(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 == password2:
            return self.cleaned_data
        else:
            raise forms.ValidationError('The passwords did not match.') 
    
    def save(self):
        self.instance.set_password(self.cleaned_data['password1'])
        self.instance.save()
