from __future__ import unicode_literals

import os
from urllib.parse import unquote_plus, urlsplit

from django.conf import settings
from django.forms import ModelForm, URLField
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.generic.detail import SingleObjectTemplateResponseMixin
from django.views.generic.edit import (ModelFormMixin, ProcessFormView,
                                       UpdateView)
from library.django_superform import ModelFormField
from s3direct.widgets import S3DirectWidget


class FormSetForm(ModelForm):
    parent_instance_field = ''

    def __init__(self, parent_instance=None,
                 get_formset=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent_instance = parent_instance
        self.formset = get_formset and get_formset()

    def save(self, commit):
        setattr(self.instance, self.parent_instance_field, self.parent_instance)
        return super().save(commit)

    def full_clean(self):
        super().full_clean()
        # NOTE: Ignore parent instance foreign key error as we save ourselves
        if self._errors.get(self.parent_instance_field):
            self._errors.pop(self.parent_instance_field)


class NestedModelFormField(ModelFormField):
    def get_instance(self, form, name):
        if form._meta.model != self.form_class._meta.model:
            raise ValueError('Field model must be same as the form model')
        return form.instance


class GetParamAsFormDataMixin(SingleObjectTemplateResponseMixin,
                              ModelFormMixin, ProcessFormView):
    # mixin to be used with CreateView or UpdateView
    def get(self, request, *args, **kwargs):
        if request.GET:
            # form data included in GET request, use it to initialize form
            form_class = self.get_form_class()
            form = form_class(request.GET)

            if isinstance(self, UpdateView):
                self.object = self.get_object()
            else:
                # self is CreateView, no associated object
                self.object = None
            return self.render_to_response(self.get_context_data(form=form))
        # no form data, fallback to default
        return super().get(request, *args, **kwargs)


class FieldDataMixin(object):
    def get_field_value(self, field_name):
        if self.is_bound:
            # get value from boundfield
            return self[field_name].value()
        else:
            # use initial value
            return self.initial.get(field_name)


class FileS3UploadWidget(S3DirectWidget):
    # modified from S3DirectWidget source
    # change file_name to exclude query and fragment
    def render(self, name, value, **kwargs):
        file_url = value or ''
        csrf_cookie_name = getattr(settings, 'CSRF_COOKIE_NAME', 'csrftoken')

        ctx = {
            'policy_url': reverse('s3direct'),
            'signing_url': reverse('s3direct-signing'),
            'dest': self.dest,
            'name': name,
            'csrf_cookie_name': csrf_cookie_name,
            'file_url': file_url,
            'file_name': os.path.basename(unquote_plus(
                urlsplit(file_url).path)),
        }

        return mark_safe(
            render_to_string(os.path.join('s3direct', 's3direct-widget.tpl'),
                             ctx))


class FileS3UploadField(URLField):
    def __init__(self, **kwargs):
        self.dest = kwargs.pop('dest', 'document')
        self.widget = FileS3UploadWidget(dest=self.dest)

        super().__init__(**kwargs)

    def clean(self, value):
        url = super().clean(value)
        if url:
            # extract file name from full url
            bucket = settings.AWS_STORAGE_BUCKET_NAME
            file_dir = settings.S3DIRECT_DESTINATIONS[self.dest]['key']
            if file_dir[-1] != '/':
                file_dir += '/'
            file_name = url.split(bucket, maxsplit=1)[1]
            file_name = file_name.split(file_dir, maxsplit=1)[1]
            return file_name
        return ''
