import datetime

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

from object_permissions import get_users_any
from object_permissions.views.permissions import view_permissions

from humfrey.update.models import UpdateDefinition, UpdateLog, UpdateLogRecord
from humfrey.update.forms import UpdateDefinitionForm, UpdatePipelineFormset

class IndexView(HTMLView):
    @method_decorator(login_required)
    def get(self, request):
        definitions = UpdateDefinition.objects.all().order_by('title')
        definitions = [d for d in definitions if d.can_view(request.user)]

        context = {
            'update_definitions': definitions,
            #'update_queue': map(self.unpack, client.lrange(UpdateDefinition.UPDATE_QUEUE, 0, 100)),
        }

        return self.render(request, context, 'update/index')

class DefinitionDetailView(HTMLView):
    def common(self, request, slug=None):
        if slug:
            obj = get_object_or_404(UpdateDefinition, slug=slug)
        else:
            obj = UpdateDefinition(owner=request.user)

        form = UpdateDefinitionForm(request.POST or None, instance=obj)
        pipelines = UpdatePipelineFormset(request.POST or None, instance=obj)

        return {
            'object': obj,
            'form': form,
            'pipelines': pipelines,
        }

    @method_decorator(login_required)
    def get(self, request, slug=None):
        context = self.common(request, slug)
        if not context['object'].can_view(request.user):
            raise PermissionDenied

        return self.render(request, context, 'update/definition-detail')

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
        context = self.common(request, slug)
        if not context['object'].can_change(request.user):
            raise PermissionDenied
        form, pipelines = context['form'], context['pipelines']

        if not (form.is_valid() and pipelines.is_valid()):
            return self.render(request, context, 'update/definition-detail')

        form.save()
        pipelines.save()

        if not slug:
            for perm in ('view', 'change', 'execute', 'delete'):
                if not request.user.has_perm('update.%s_updatedefinition' % perm):
                    getattr(form.instance, '%s_users' % perm).add(request.user)

        return HttpResponseSeeOther(form.instance.get_absolute_url())

    @method_decorator(login_required)
    def delete(self, request, slug=None):
        if not slug:
            raise Http404
        obj = get_object_or_404(UpdateDefinition, slug=slug)

        if obj.can_delete(request.user):
            obj.delete()
            return self.render(request, {'object': obj}, 'update/definition-deleted')
        else:
            raise PermissionDenied

    def execute(self, request, slug=None):
        if not slug:
            raise Http404
        obj = get_object_or_404(UpdateDefinition, slug=slug)

        if not obj.can_execute(request.user):
            raise PermissionDenied

        try:
            update_log = obj.queue('web', request.user)
        except UpdateDefinition.AlreadyQueued:
            context = {'status_code': 409,
                       'success': False,
                       'object': obj}
        else:
            context = {'success': True,
                       'object': obj,
                       'update_log': update_log}
        return self.render(request, context, 'update/definition-queued')


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
        if not definition.can_view:
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
        if not definition.can_view:
            raise PermissionDenied
        log = get_object_or_404(definition.update_log, id=id)
        context = {
            'definition': definition,
            'log': log,
        }
        return self.render(request, context, 'update/log-detail')
