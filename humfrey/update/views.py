import datetime
import httplib

from django.conf import settings
from django.http import Http404, HttpResponseBadRequest
from django.views.generic.base import View
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from django_conneg.views import HTMLView, JSONView
from django_conneg.http import HttpResponseSeeOther

from guardian.shortcuts import get_objects_for_user, get_perms, assign_perm

from humfrey.update.models import UpdateDefinition, UpdateLog, UpdateLogRecord, UpdateDefinitionAlreadyQueued
from humfrey.update.forms import UpdateDefinitionForm, UpdatePipelineFormset

class IndexView(HTMLView):
    @method_decorator(login_required)
    def get(self, request):
        definitions = get_objects_for_user(request.user, 'update.view_updatedefinition')

        context = {
            'update_definitions': definitions,
            #'update_queue': map(self.unpack, client.lrange(UpdateDefinition.UPDATE_QUEUE, 0, 100)),
        }

        return self.render(request, context, 'update/index')

class DefinitionDetailView(HTMLView):
    template_name = 'update/definition-detail'

    def common(self, request, slug=None):
        if slug:
            obj = get_object_or_404(UpdateDefinition, slug=slug)
            perms = get_perms(request.user, obj)
        else:
            obj = UpdateDefinition(owner=request.user)
            perms = ['view_updatedefinition', 'change_updatedefinition']

        form = UpdateDefinitionForm(request.POST or None, instance=obj)
        pipelines = UpdatePipelineFormset(request.POST or None, instance=obj)

        self.context.update({
            'object': obj,
            'form': form,
            'pipelines': pipelines,
            'perms': perms,
        })

    @method_decorator(login_required)
    def get(self, request, slug=None):
        self.common(request, slug)
        if 'view_updatedefinition' not in self.context['perms']:
            raise PermissionDenied
        return self.render()

    @method_decorator(login_required)
    def post(self, request, slug=None):
        action = request.POST.get('action', '').lower()
        if action == 'delete':
            return self.delete(request, slug)
        elif action == 'execute':
            return self.execute(request, slug)
        elif action in ('', 'create', 'update'):
            return self.update(request, slug)
        else:
            return HttpResponseBadRequest("action must empty or missing, 'delete', 'execute' or 'update'")

    def update(self, request, slug=None):
        self.common(request, slug)
        if 'change_updatedefinition' not in self.context['perms']:
            raise PermissionDenied
        form, pipelines = self.context['form'], self.context['pipelines']

        if not (form.is_valid() and pipelines.is_valid()):
            return self.render()

        form.save()
        pipelines.save()

        if not slug:
            for perm in ('view', 'change', 'execute', 'delete'):
                if not request.user.has_perm('update.%s_updatedefinition' % perm):
                    getattr(form.instance, '%s_users' % perm).add(request.user)

        return HttpResponseSeeOther(form.instance.get_absolute_url())

    @method_decorator(login_required)
    def delete(self, request, slug=None):
        self.common(request, slug)
        if 'delete_updatedefinition' in self.context['perms']:
            self.context['object'].delete()
            return self.render(template_name='update/definition-deleted')
        else:
            raise PermissionDenied

    def execute(self, request, slug=None):
        obj = get_object_or_404(UpdateDefinition, slug=slug)
        self.context.update({
            'object': obj,
            'perms': get_perms(request.user, obj),
        })
        if 'execute_updatedefinition' not in self.context['perms']:
            raise PermissionDenied

        try:
            update_log = self.context['object'].queue('web', request.user)
        except UpdateDefinitionAlreadyQueued:
            self.context.update({'status_code': httplib.CONFLICT,
                                 'success': False})
        else:
            self.context.update({'status_code': httplib.ACCEPTED,
                                 'success': True,
                                 'update_log': update_log})
        return self.render(template_name='update/definition-queued')


class UpdateLogView(HTMLView, JSONView):
    _json_indent = 2

    def simplify(self, value):
        if isinstance(value, UpdateDefinition):
            return self.simplify({'_url': value.get_absolute_url(),
                                  'slug': value.slug,
                                  'title': value.title})
        elif isinstance(value, UpdateLog):
            return self.simplify({'_url': value.get_absolute_url(),
                                  'id': value.id,
                                  'forced': value.forced,
                                  'trigger': value.trigger,
                                  'log_level': value.log_level,
                                  'records': list(value.records)})
        elif isinstance(value, UpdateLogRecord):
            return self.simplify(value.record)
        else:
            return super(UpdateLogView, self).simplify(value)

class UpdateLogListView(UpdateLogView):
    @method_decorator(login_required)
    def get(self, request, slug):
        definition = get_object_or_404(UpdateDefinition, slug=slug)
        if not request.user.has_perm('update_view_updatedefinition', definition):
            raise PermissionDenied
        context = {
            'definition': definition,
            'logs': list(definition.update_log.all().order_by('-id')),
        }
        return self.render(request, context, 'update/log-list')

class UpdateLogDetailView(UpdateLogView):
    @method_decorator(login_required)
    def get(self, request, slug, id):
        definition = get_object_or_404(UpdateDefinition, slug=slug)
        if not request.user.has_perm('update_view_updatedefinition', definition):
            raise PermissionDenied
        log = get_object_or_404(definition.update_log, id=id)
        context = {
            'definition': definition,
            'log': log,
        }
        return self.render(request, context, 'update/log-detail')
