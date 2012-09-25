import datetime
import operator
import re

from django.contrib import auth
from django.core import signing
from django.core.urlresolvers import reverse
from django.db import transaction
from django.db.models import Q, F
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.views import generic

from password_reset.views import Recover
from tagging.models import Tag, TaggedItem
from tagging.utils import calculate_cloud, get_tag

from . import utils
from .constants import (MACHINETAGS_FROM_FIELDS,
                                    IMPROVIDERS_DICT, SERVICES_DICT)
from .forms import (SkillsForm, SignupForm, PortfolioForm, BioForm,
                    LocationForm, FindingForm, AccountForm, PasswordForm,
                    DeletionRequestForm, AccountDeletionForm)
from .models import DjangoPerson, Country, User, Region, PortfolioSite

from ..django_openidauth.models import associate_openid, UserOpenID
from ..machinetags.utils import tagdict
from ..machinetags.models import MachineTaggedItem

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
            'home': True,
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


def redirect_to_logged_in_user_profile(request):
    if request.user.is_authenticated():
        url = reverse('user_profile', kwargs={'username': request.user})
    else:
        url = reverse('index')
    return redirect(url)


def logout(request):
    auth.logout(request)
    request.session['openids'] = []
    return redirect(reverse('index'))


class RecoverView(Recover):
    search_fields = ['username']
recover = RecoverView.as_view()


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
        user = User.objects.create(**creation_args)
        if form.cleaned_data.get('password1'):
            user.set_password(form.cleaned_data['password1'])
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


class CleverPaginator(object):
    """
    A paginator that triggers pagination only if the 2nd page is
    worth displaying.
    """
    paginate_by = 100

    def get_count(self):
        raise NotImplementedError

    def get_paginate_by(self, queryset):
        count = self.get_count()
        if count > self.paginate_by * 1.5:
            return self.paginate_by
        return count


class CountryView(CleverPaginator, generic.ListView):
    template_name = 'country.html'
    context_object_name = 'people_list'

    def get_queryset(self):
        self.country = get_object_or_404(
            Country,
            iso_code=self.kwargs['country_code'].upper()
        )
        self.all_people = self.country.djangoperson_set.select_related(
                'country', 'user'
        ).order_by('user__first_name', 'user__last_name')
        return self.all_people

    def get_count(self):
        return self.country.num_people

    def get_context_data(self, **kwargs):
        context = super(CountryView, self).get_context_data(**kwargs)
        context.update({
            'regions': self.country.top_regions(),
            'country': self.country,
            'people_list': self.all_people,
        })
        return context
country = CountryView.as_view()


class RegionView(CleverPaginator, generic.ListView):
    template_name = 'country.html'

    def get_queryset(self):
        self.region = get_object_or_404(
            Region,
            country__iso_code=self.kwargs['country_code'].upper(),
            code=self.kwargs['region_code'].upper(),
        )
        self.all_people = self.region.djangoperson_set.select_related(
            'user', 'country',
        ).order_by('user__first_name', 'user__last_name')
        return self.all_people

    def get_count(self):
        return self.region.num_people

    def get_context_data(self, **kwargs):
        context = super(RegionView, self).get_context_data(**kwargs)
        context.update({
            'country': self.region,
            'people_list': self.all_people,
        })
        return context
region = RegionView.as_view()


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
            'people_list': self.object.get_nearest(),
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
            'first_name': self.object.user.first_name,
            'last_name': self.object.user.last_name,
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


class TaggedObjectList(generic.ListView):
    related_tags = False
    related_tag_counts = True
    select_related = False

    def get_queryset(self):
        self.tag_instance = get_tag(self.kwargs['tag'])
        if self.tag_instance is None:
            raise Http404(
                _('No Tag found matching "%s".') % self.kwargs['tag']
            )
        queryset = TaggedItem.objects.get_by_model(self.model,
                                                   self.tag_instance)
        if self.select_related:
            queryset = queryset.select_related(*self.select_related)
        filter_args = self.get_extra_filter_args()
        if filter_args:
            queryset = queryset.filter(**filter_args)
        return queryset

    def get_extra_filter_args(self):
        return {}

    def get_context_data(self, **kwargs):
        kwargs.update({
            'tag': self.kwargs['tag'],
        })
        if self.related_tags:
            kwargs['related_tags'] = Tag.objects.related_for_model(
                self.tag_instance,
                self.model,
                counts=self.related_tag_counts
            )
        ctx = super(TaggedObjectList, self).get_context_data(**kwargs)
        return ctx


class Skill(TaggedObjectList):
    model = DjangoPerson
    related_tags = True
    template_name = 'skill.html'
    context_object_name = 'people_list'
    select_related = ['user', 'country']
skill = Skill.as_view()


class CountrySkill(TaggedObjectList):
    model = DjangoPerson
    related_tags = True
    template_name = 'skill.html'
    context_object_name = 'people_list'

    def get_context_data(self, **kwargs):
        kwargs['country'] = Country.objects.get(
            iso_code=self.kwargs['country_code'].upper()
        )
        return super(CountrySkill, self).get_context_data(**kwargs)

    def get_extra_filter_args(self):
        filters = super(CountrySkill, self).get_extra_filter_args()
        filters['country__iso_code'] = self.kwargs['country_code'].upper()
        return filters
country_skill = CountrySkill.as_view()


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
            last_active_on_irc__gt=(timezone.now() -
                                    datetime.timedelta(hours=1))
        ).order_by('-last_active_on_irc')
        # Filter out the people who don't want to be tracked (inefficient)
        return [r for r in results if r.irc_tracking_allowed()]
irc_active = IRCActiveView.as_view()


class RequestFormMixin(object):
    def get_form_kwargs(self):
        kwargs = super(RequestFormMixin, self).get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs


class DeletionRequestView(RequestFormMixin, generic.FormView):
    form_class = DeletionRequestForm
    template_name = 'delete_account_request.html'

    def form_valid(self, form):
        form.save()
        return redirect(reverse('delete_account_next',
                                args=[self.request.user.username]))
delete_account_request = must_be_owner(DeletionRequestView.as_view())


class DeletionNext(generic.TemplateView):
    template_name = 'delete_account_next.html'
delete_account_next = must_be_owner(DeletionNext.as_view())


class AccountDeletionView(RequestFormMixin, generic.FormView):
    form_class = AccountDeletionForm
    template_name = 'delete_account.html'

    def dispatch(self, request, *args, **kwargs):
        try:
            self.key = signing.loads(kwargs['key'], max_age=3600,
                                     salt='delete_account')
        except signing.SignatureExpired:
            return redirect(reverse('delete_account_request',
                                    args=[request.user.username]))
        except signing.BadSignature:
            raise Http404
        return super(AccountDeletionView, self).dispatch(request, *args,
                                                         **kwargs)

    def form_valid(self, form):
        form.save()
        return redirect(reverse('delete_account_done',
                                args=[self.request.user.username]))

    def get_context_data(self, **kwargs):
        ctx = super(AccountDeletionView, self).get_context_data(**kwargs)
        ctx['key'] = self.kwargs['key']
        return ctx
delete_account = must_be_owner(AccountDeletionView.as_view())


class DeletionDone(generic.TemplateView):
    template_name = 'delete_account_done.html'

    def dispatch(self, request, *args, **kwargs):
        if User.objects.filter(username=kwargs['username']).exists():
            raise Http404
        return super(DeletionDone, self).dispatch(request, *args, **kwargs)
delete_account_done = DeletionDone.as_view()
