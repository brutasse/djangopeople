
import datetime
import hashlib
import operator
import os
import re
import smtplib

from cStringIO import StringIO
from PIL import Image

from django.conf import settings
from django.contrib import auth
from django.core.urlresolvers import reverse
from django.db import transaction
from django.db.models import Q, F
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.translation import ugettext_lazy as _
from django.views import generic

from djangopeople import utils
from djangopeople.constants import (MACHINETAGS_FROM_FIELDS,
                                    IMPROVIDERS_DICT, SERVICES_DICT)
from djangopeople.forms import (SkillsForm, SignupForm, PhotoUploadForm,
                                PortfolioForm, BioForm, LocationForm,
                                FindingForm, AccountForm, LostPasswordForm,
                                PasswordForm)
from djangopeople.models import (DjangoPerson, Country, User, Region,
                                 PortfolioSite)

from django_openidauth.models import associate_openid, UserOpenID

from tagging.models import Tag, TaggedItem
#from tagging.views import tagged_object_list
from tagging.utils import calculate_cloud, get_tag

from machinetags.utils import tagdict
from machinetags.models import MachineTaggedItem

from django.views.generic.list_detail import object_list


NOTALPHA_RE = re.compile('[^a-zA-Z0-9]')


@utils.simple_decorator
def must_be_owner(view):
    def inner(request, *args, **kwargs):
        if 'username' in kwargs:
            if not request.user or request.user.is_anonymous() \
               or request.user.username != kwargs['username']:
                return HttpResponseForbidden('Not allowed')
        else:
            if not request.user or request.user.is_anonymous() \
                or request.user.username != args[0]:
                return HttpResponseForbidden('Not allowed')
        return view(request, *args, **kwargs)
    return inner


class IndexView(generic.TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        people = DjangoPerson.objects.all().select_related()
        people = people.order_by('-id')[:100]
        ctx = super(IndexView, self).get_context_data(**kwargs)
        ctx.update({
            'people_list': people,
            'people_list_limited': people[:4],
            'total_people': DjangoPerson.objects.count(),
            'countries': Country.objects.top_countries(),
        })
        return ctx
index = IndexView.as_view()


class AboutView(generic.TemplateView):
    template_name = 'about.html'

    def get_context_data(self, **kwargs):
        ctx = super(AboutView, self).get_context_data(**kwargs)
        users = User.objects.filter(useropenid__openid__startswith='http')
        ctx.update({
            'total_people': DjangoPerson.objects.count(),
            'openid_users': users.distinct().count(),
            'countries': Country.objects.top_countries(),
        })
        return ctx
about = AboutView.as_view()


class RecentView(generic.TemplateView):
    template_name = 'recent.html'

    def get_context_data(self, **kwargs):
        ctx = super(RecentView, self).get_context_data(**kwargs)
        people = DjangoPerson.objects.all().select_related()
        ctx.update({
            'people': people.order_by('-auth_user.date_joined')[:50],
        })
        return ctx
recent = RecentView.as_view()


class ProfileRedirectView(generic.RedirectView):
    '''
    redirect to the profile page of the logged in user
    used to redirect to the profile page of the user after login
    '''

    def get_redirect_url(self):
        return reverse('user_profile', kwargs={'username': self.request.user})
redirect_to_logged_in_user_profile = ProfileRedirectView.as_view()


def logout(request):
    auth.logout(request)
    request.session['openids'] = []
    return redirect(reverse('index'))


class LostPasswordView(generic.FormView):
    form_class = LostPasswordForm
    template_name = 'lost_password.html'

    def form_valid(self, form):
        try:
            form.save()
        except smtplib.SMTPException:
            return self.render_to_response(
                self.get_context_data(
                    message=_('Could not email you a recovery link.'),
            ))
        return self.render_to_response(
            self.get_context_data(
                message=_("An e-mail has been sent with instructions for "
                          "recovering your account. Don't forget to check "
                          "your spam folder!"),
        ))
lost_password = LostPasswordView.as_view()


class LostPasswordRecoverView(generic.TemplateView):
    template_name = 'lost_password.html'

    def get(self, request, *args, **kwargs):
        username = kwargs['username']
        user = get_object_or_404(User, username=username)
        if utils.hash_is_valid(username, kwargs['days'], kwargs['hash']):
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            auth.login(request, user)
            url = reverse('edit_password', kwargs={'username': username})
            return redirect(url)
        return super(LostPasswordRecoverView, self).get(request, *args,
                                                        **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super(LostPasswordRecoverView, self).get_context_data(**kwargs)
        ctx['message'] = _('That was not a valid account recovery link')
        return ctx
lost_password_recover = LostPasswordRecoverView.as_view()


class OpenIDWhatNext(generic.RedirectView):
    """
    If user is already logged in, send them to /openid/associations/
    Otherwise, send them to the signup page
    """
    permanent = False

    def get_redirect_url(self):
        if not self.request.openid:
            return reverse('index')

        if self.request.user.is_anonymous():
            # Have they logged in with an OpenID that matches an account?
            try:
                user_openid = UserOpenID.objects.get(
                    openid=str(self.request.openid),
                )
            except UserOpenID.DoesNotExist:
                return reverse('signup')

            # Log the user in
            user = user_openid.user
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            auth.login(self.request, user)
            return reverse('user_profile', args=[user.username])
        return reverse('openid_associations')
openid_whatnext = OpenIDWhatNext.as_view()


class SignupView(generic.FormView):
    form_class = SignupForm
    template_name = 'signup.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_anonymous():
            return redirect(reverse('index'))
        return super(SignupView, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        creation_args = {
            'username': form.cleaned_data['username'],
            'email': form.cleaned_data['email'],
        }
        if form.cleaned_data.get('password1'):
            creation_args['password'] = form.cleaned_data['password1']
        user = User.objects.create(**creation_args)
        user.first_name = form.cleaned_data['first_name']
        user.last_name = form.cleaned_data['last_name']
        user.save()

        if self.request.openid:
            associate_openid(user, str(self.request.openid))

        region = None
        if form.cleaned_data['region']:
            region = Region.objects.get(
                country__iso_code=form.cleaned_data['country'],
                code=form.cleaned_data['region'],
            )

        # Now create the DjangoPerson
        person = DjangoPerson.objects.create(
            user=user,
            bio=form.cleaned_data['bio'],
            country=Country.objects.get(
                iso_code=form.cleaned_data['country'],
            ),
            region=region,
            latitude=form.cleaned_data['latitude'],
            longitude=form.cleaned_data['longitude'],
            location_description=form.cleaned_data['location_description'],
        )

        # Set up the various machine tags
        for fieldname, (namespace, predicate) in \
                MACHINETAGS_FROM_FIELDS.items():
            if fieldname in form.cleaned_data and \
                form.cleaned_data[fieldname].strip():
                value = form.cleaned_data[fieldname].strip()
                person.add_machinetag(namespace, predicate, value)

        # Finally, set their skill tags
        person.skilltags = form.cleaned_data['skilltags']

        # Log them in and redirect to their profile page
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        auth.login(self.request, user)
        self.person = person
        return super(SignupView, self).form_valid(form)

    def get_success_url(self):
        return self.person.get_absolute_url()

    def get_form_kwargs(self):
        kwargs = super(SignupView, self).get_form_kwargs()
        if self.request.openid:
            kwargs['openid'] = self.request.openid
        return kwargs

    def get_initial(self):
        initial = super(SignupView, self).get_initial()
        if self.request.openid and self.request.openid.sreg:
            sreg = self.request.openid.sreg
            first_name = ''
            last_name = ''
            username = ''
            if sreg.get('fullname'):
                bits = sreg['fullname'].split()
                first_name = bits[0]
                if len(bits) > 1:
                    last_name = ' '.join(bits[1:])
            # Find a not-taken username
            if sreg.get('nickname'):
                username = derive_username(sreg['nickname'])

            initial.update({
                'first_name': first_name,
                'last_name': last_name,
                'email': sreg.get('email', ''),
                'username': username,
            })
        return initial

    def get_context_data(self, **kwargs):
        ctx = super(SignupView, self).get_context_data(**kwargs)
        ctx.update({
            'openid': self.request.openid,
        })
        return ctx
signup = SignupView.as_view()
signup = transaction.commit_on_success(signup)


def derive_username(nickname):
    nickname = NOTALPHA_RE.sub('', nickname)
    if not nickname:
        return ''
    base_nickname = nickname
    to_add = 1
    while True:
        try:
            DjangoPerson.objects.get(user__username=nickname)
        except DjangoPerson.DoesNotExist:
            break
        nickname = base_nickname + str(to_add)
        to_add += 1
    return nickname


@must_be_owner
def upload_profile_photo(request, username):
    person = get_object_or_404(DjangoPerson, user__username=username)
    if request.method == 'POST':
        form = PhotoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Figure out what type of image it is
            image_content = request.FILES['photo'].read()
            format = Image.open(StringIO(image_content)).format
            format = format.lower().replace('jpeg', 'jpg')
            filename = hashlib.md5(image_content).hexdigest() + '.' + format
            # Save the image
            path = os.path.join(settings.MEDIA_ROOT, 'profiles', filename)
            open(path, 'w').write(image_content)
            person.photo = 'profiles/%s' % filename
            person.save()
            return redirect(reverse('upload_done', args=[username]))
    else:
        form = PhotoUploadForm()
    return render(request, 'upload_profile_photo.html', {
        'form': form,
        'person': person,
    })


@must_be_owner
def upload_done(request, username):
    "Using a double redirect to try and stop back button from re-uploading"
    return redirect(reverse('user_profile', args=[username]))


class CountryView(generic.DetailView):
    template_name = 'country.html'
    context_object_name = 'country'

    def get_object(self):
        return get_object_or_404(Country,
                                 iso_code=self.kwargs['country_code'].upper())

    def get_context_data(self, **kwargs):
        context = super(CountryView, self).get_context_data(**kwargs)
        context.update({
            'people_list': self.object.djangoperson_set.all(),
            'regions': self.object.top_regions(),
        })
        return context
country = CountryView.as_view()


class CountrySitesView(generic.ListView):
    context_object_name = 'sites'
    template_name = 'country_sites.html'

    def get_queryset(self):
        self.country = get_object_or_404(
            Country, iso_code=self.kwargs['country_code'].upper(),
        )
        return PortfolioSite.objects.select_related().filter(
            contributor__country=self.country,
        ).order_by('contributor')

    def get_context_data(self, **kwargs):
        context = super(CountrySitesView, self).get_context_data(**kwargs)
        context.update({
            'country': self.country,
        })
        return context
country_sites = CountrySitesView.as_view()


def region(request, country_code, region_code):
    region = get_object_or_404(Region,
        country__iso_code=country_code.upper(),
        code=region_code.upper()
    )
    return render(request, 'country.html', {
        'country': region,
    })


class ProfileView(generic.DetailView):
    context_object_name = 'person'
    template_name = 'profile.html'

    def get_object(self):
        person = get_object_or_404(DjangoPerson,
                                   user__username=self.kwargs['username'])
        DjangoPerson.objects.filter(pk=person.pk).update(
            profile_views=F('profile_views') + 1,
        )
        return person

    def get_context_data(self, **kwargs):
        context = super(ProfileView, self).get_context_data(**kwargs)
        mtags = tagdict(self.object.machinetags.all())

        # Set up convenient iterables for IM and services
        ims = []
        for key, value in mtags.get('im', {}).items():
            shortname, name, icon = IMPROVIDERS_DICT.get(key, ('', '', ''))
            if not shortname:
                continue  # Bad machinetag
            ims.append({
                'shortname': shortname,
                'name': name,
                'value': value,
            })
        ims.sort(lambda x, y: cmp(x['shortname'], y['shortname']))

        services = []
        for key, value in mtags.get('services', {}).items():
            shortname, name, icon = SERVICES_DICT.get(key, ('', '', ''))
            if not shortname:
                continue  # Bad machinetag
            services.append({
                'shortname': shortname,
                'name': name,
                'value': value,
            })
        services.sort(lambda x, y: cmp(x['shortname'], y['shortname']))

        # Set up vars that control privacy stuff
        privacy = {
            'show_im': (
                mtags['privacy']['im'] == 'public' or
                not self.request.user.is_anonymous()
            ),
            'show_email': (
                mtags['privacy']['email'] == 'public' or
                (not self.request.user.is_anonymous() and
                 mtags['privacy']['email'] == 'private')
            ),
            'hide_from_search': mtags['privacy']['search'] != 'public',
            'show_last_irc_activity': bool(self.object.last_active_on_irc and
                                           self.object.irc_tracking_allowed()),
        }

        # Should we show the 'Finding X' section at all?
        show_finding = (services or privacy['show_email'] or
                        (privacy['show_im'] and ims))

        context.update({
            'is_owner': self.request.user.username == self.kwargs['username'],
            'skills_form': SkillsForm(instance=self.object),
            'mtags': mtags,
            'ims': ims,
            'services': services,
            'privacy': privacy,
            'show_finding': show_finding,
        })
        return context
profile = ProfileView.as_view()


class DjangoPersonEditViewBase(generic.UpdateView):
    def get_object(self):
        return get_object_or_404(DjangoPerson,
                                 user__username=self.kwargs['username'])

    def get_success_url(self):
        return reverse('user_profile', args=[self.kwargs['username']])


class EditFindingView(DjangoPersonEditViewBase):
    form_class = FindingForm
    template_name = 'edit_finding.html'

    def get_initial(self):
        mtags = tagdict(self.object.machinetags.all())
        initial = {
            'email': self.object.user.email,
        }
        # Fill in other initial fields from machinetags
        for fieldname, (namespace, predicate) in \
                MACHINETAGS_FROM_FIELDS.items():
            initial[fieldname] = mtags[namespace][predicate]
        return initial
edit_finding = must_be_owner(EditFindingView.as_view())


class EditPortfolioView(DjangoPersonEditViewBase):
    form_class = PortfolioForm
    template_name = 'edit_portfolio.html'
edit_portfolio = must_be_owner(EditPortfolioView.as_view())


class EditAccountView(DjangoPersonEditViewBase):
    form_class = AccountForm
    template_name = 'edit_account.html'
edit_account = must_be_owner(EditAccountView.as_view())


class EditSkillsView(DjangoPersonEditViewBase):
    form_class = SkillsForm
    template_name = 'edit_skills.html'
edit_skills = must_be_owner(EditSkillsView.as_view())


class EditPassword(generic.UpdateView):
    form_class = PasswordForm
    template_name = 'edit_password.html'

    def get_object(self):
        return get_object_or_404(User, username=self.kwargs['username'])

    def get_success_url(self):
        return reverse('user_profile', args=[self.kwargs['username']])
edit_password = must_be_owner(EditPassword.as_view())


class EditBioView(DjangoPersonEditViewBase):
    form_class = BioForm
    template_name = 'edit_bio.html'
edit_bio = must_be_owner(EditBioView.as_view())


class EditLocationView(DjangoPersonEditViewBase):
    form_class = LocationForm
    template_name = 'edit_location.html'

    def get_initial(self):
        initial = super(EditLocationView, self).get_initial()
        initial.update({
            'country': self.object.country.iso_code,
        })
        return initial
edit_location = must_be_owner(EditLocationView.as_view())


class SkillCloudView(generic.TemplateView):
    template_name = 'skills.html'

    def get_context_data(self, **kwargs):
        tags = DjangoPerson.skilltags.cloud(steps=5)
        calculate_cloud(tags, 5)
        context = super(SkillCloudView, self).get_context_data(**kwargs)
        context.update({
            'tags': tags,
        })
        return context
skill_cloud = SkillCloudView.as_view()


class CountrySkillCloudView(generic.DetailView):
    context_object_name = 'country'
    template_name = 'skills.html'

    def get_object(self):
        return get_object_or_404(Country,
                                 iso_code=self.kwargs['country_code'].upper())

    def get_context_data(self, **kwargs):
        context = super(CountrySkillCloudView, self).get_context_data(**kwargs)
        tags = Tag.objects.cloud_for_model(DjangoPerson, steps=5, filters={
            'country': self.object,
        })
        calculate_cloud(tags, 5)
        context.update({
            'tags': tags,
        })
        return context
country_skill_cloud = CountrySkillCloudView.as_view()


def skill(request, tag):
    return tagged_object_list(request,
        model=DjangoPerson,
        tag=tag,
        related_tags=True,
        related_tag_counts=True,
        template_name='skill.html',
        template_object_name='people',
    )


def country_skill(request, country_code, tag):
    return tagged_object_list(request,
        model=DjangoPerson,
        tag=tag,
        related_tags=True,
        related_tag_counts=True,
        extra_filter_args={'country__iso_code': country_code.upper()},
        template_name='skill.html',
        template_object_name='people',
        extra_context={
            'country': Country.objects.get(iso_code=country_code.upper()),
        },
    )


class CountryLookingForView(generic.ListView):
    context_object_name = 'people'
    template_name = 'country_looking_for.html'

    def get_queryset(self):
        self.country = get_object_or_404(
            Country, iso_code=self.kwargs['country_code'].upper(),
        )
        ids = [
            o['object_id'] for o in MachineTaggedItem.objects.filter(
                namespace='profile',
                predicate='looking_for_work',
                value=self.kwargs['looking_for'],
            ).values('object_id')
        ]
        return DjangoPerson.objects.filter(country=self.country, id__in=ids)

    def get_context_data(self, **kwargs):
        context = super(CountryLookingForView, self).get_context_data(**kwargs)
        context.update({
            'country': self.country,
            'looking_for': self.kwargs['looking_for'],
        })
        return context
country_looking_for = CountryLookingForView.as_view()


class SearchView(generic.ListView):
    context_object_name = 'people_list'
    template_name = 'search.html'

    def get_queryset(self):
        self.q = self.request.GET.get('q', '')
        self.has_badwords = [
            w.strip() for w in self.q.split() if len(w.strip()) in (1, 2)
        ]
        if self.q:
            return self.search_people()
        return []

    def get_context_data(self, **kwargs):
        context = super(SearchView, self).get_context_data(**kwargs)
        context.update({
            'q': self.q,
            'has_badwords': self.has_badwords
        })
        return context

    def search_people(self):
        words = [w.strip() for w in self.q.split() if len(w.strip()) > 2]
        if not words:
            return []

        terms = []
        for word in words:
            terms.append(Q(
                user__username__icontains=word) |
                Q(user__first_name__icontains=word) |
                Q(user__last_name__icontains=word)
            )

        combined = reduce(operator.and_, terms)
        return DjangoPerson.objects.filter(
            combined,
        ).select_related().distinct()
search = SearchView.as_view()


class IRCActiveView(generic.ListView):
    context_object_name = 'people_list'
    template_name = 'irc_active.html'

    def get_queryset(self):
        results = DjangoPerson.objects.filter(
            last_active_on_irc__gt=(datetime.datetime.now() -
                                    datetime.timedelta(hours=1))
        ).order_by('-last_active_on_irc')
        # Filter out the people who don't want to be tracked (inefficient)
        return [r for r in results if r.irc_tracking_allowed()]
irc_active = IRCActiveView.as_view()


# Custom variant of the generic view from django-tagging
def tagged_object_list(request, model=None, tag=None, related_tags=False,
        related_tag_counts=True, extra_filter_args=None, **kwargs):
    """
    A thin wrapper around
    ``django.views.generic.list_detail.object_list`` which creates a
    ``QuerySet`` containing instances of the given model tagged with
    the given tag.

    In addition to the context variables set up by ``object_list``, a
    ``tag`` context variable will contain the ``Tag`` instance for the
    tag.

    If ``related_tags`` is ``True``, a ``related_tags`` context variable
    will contain tags related to the given tag for the given model.
    Additionally, if ``related_tag_counts`` is ``True``, each related
    tag will have a ``count`` attribute indicating the number of items
    which have it in addition to the given tag.
    """
    if model is None:
        try:
            model = kwargs['model']
        except KeyError:
            raise AttributeError(_('tagged_object_list must be called with '
                                   'a model.'))

    if tag is None:
        try:
            tag = kwargs['tag']
        except KeyError:
            raise AttributeError(_('tagged_object_list must be called with '
                                   'a tag.'))

    tag_instance = get_tag(tag)
    if tag_instance is None:
        raise Http404(_('No Tag found matching "%s".') % tag)
    queryset = TaggedItem.objects.get_by_model(model, tag_instance)
    if extra_filter_args:
        queryset = queryset.filter(**extra_filter_args)
    if 'extra_context' not in kwargs:
        kwargs['extra_context'] = {}
    kwargs['extra_context']['tag'] = tag_instance
    if related_tags:
        kwargs['extra_context']['related_tags'] = \
            Tag.objects.related_for_model(tag_instance, model,
                                          counts=related_tag_counts)
    return object_list(request, queryset, **kwargs)
