from django import forms
from django.contrib.auth.forms import UserChangeForm
from django.db.models import Count
from django.forms import EmailField, model_to_dict
from django.forms.widgets import RadioSelect
from django.http import HttpResponse
from django.views import generic
from django_filters import CharFilter, NumberFilter
from library.django_superform import ForeignKeyFormField, SuperModelForm
from material import Layout, Row
from material.frontend.views import (DetailModelView, ListModelView,
                                     ModelViewSet, UpdateModelView)
from polls.models import User

from ...utils import ListFilterView, SearchAndFilterSet, get_html_list


class AccountForm(UserChangeForm):
    email = EmailField(required=True)

    layout = Layout(
        'username',
        'email',
        'password',
        Row('first_name', 'last_name'),
        'groups',
        'user_permissions',
        'is_active',
        Row('is_staff', 'is_superuser'),
        Row('date_joined', 'last_login'),
    )


class UserForm(SuperModelForm):
    account = ForeignKeyFormField(AccountForm)

    layout = Layout(
        'account',
        'group',
        Row('subs_start', 'subs_expire'),
        'followed_users'
    )

    form_widgets = {'group': RadioSelect}

    class Meta:
        model = User
        fields = ['group', 'subs_start', 'subs_expire',
                  'followed_users']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance:
            self.initial = model_to_dict(self.instance)

            account_queryset = self.instance.account
            self.initial["account"] = account_queryset


class UserUpdateView(UpdateModelView):
    def get_form_class(self):
        return UserForm


class UserDetailView(DetailModelView):
    def get_object_data(self):
        user = super().get_object()

        # Account fields
        account = user.account

        account_fields = [
            'username', 'email',  # 'password',
            'first_name', 'last_name',
            'is_active', 'is_staff', 'is_superuser',
            'date_joined', 'last_login',
        ]
        for field in account_fields:
            attr = getattr(account, field, '')
            if attr:
                yield (field.replace('_', ' ').title(), attr)

        auth_groups = account.groups.all()
        html_list = get_html_list(auth_groups)
        yield ('Auth Groups', html_list or None)

        user_permissions = account.user_permissions.all()
        html_list = get_html_list(user_permissions)
        yield ('User Permissions', html_list or None)

        # Polls fields
        account_name = User._meta.get_field('account')
        account_name = account_name.verbose_name.title()
        group_name = User._meta.get_field('group')
        group_name = group_name.verbose_name.title()
        for item in super().get_object_data():
            if item[0] == account_name:
                continue
            elif item[0] == group_name:
                yield ('Polls Group', item[1])
            else:
                yield item

        # M2M field
        followed_users = user.followed_users.order_by('account__username')
        if len(followed_users):
            html_list = get_html_list(followed_users)
            yield ('Followed Users', html_list)

        # Reverse relation
        followed_question = user.question_follows.order_by('question_text')
        html_list = get_html_list(followed_question)
        yield ('Followed Question', html_list or 'None')

        # Relational data
        question_rel = user.questionfollower_set
        notify_time = question_rel.filter(notify_time__isnull=False)
        notify_time = notify_time.values_list('notify_time', flat=True)
        html_list = get_html_list(notify_time)
        yield ('Question Notify Times', html_list or 'None')


class UserFilterForm(forms.Form):
    layout = Layout('search',
                    'group',
                    'account__username',
                    'min_follower_count')


class UserFilter(SearchAndFilterSet):
    search_fields = ['account__username', 'group']

    account__username = CharFilter(lookup_expr='icontains',
                                   label='Name contains')

    min_follower_count = NumberFilter(field_name='user_followed',
                                      method='filter_count_gte',
                                      label='Minimum follower count')

    def filter_count_gte(self, queryset, name, value):
        qs = queryset.annotate(name_count=Count(name))
        return qs.filter(name_count__gte=value)

    class Meta:
        model = User
        fields = {'group': ['exact']}
        form = UserFilterForm


class UserListView(ListModelView, ListFilterView):
    list_display = ['name', 'group', 'followers_list']
    filterset_class = UserFilter


class UserViewSet(ModelViewSet):
    model = User
    update_view_class = UserUpdateView
    detail_view_class = UserDetailView
    list_view_class = UserListView


class PasswordChangeView(generic.View):
    def get(self, request, *args, **kwargs):
        return HttpResponse('Form for changing password')


class PasswordChangeDoneView(generic.View):
    def get(self, request, *args, **kwargs):
        return HttpResponse('Password changed!')
