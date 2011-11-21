import datetime

from django.conf import settings
from django.http import Http404, HttpResponseBadRequest
from django.views.generic.base import View
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404

from django_conneg.views import HTMLView, JSONView, TextView
from django_conneg.http import HttpResponseSeeOther

from humfrey.utils.views import RedisView, AuthenticatedView
from humfrey.update.longliving.uploader import Uploader
from humfrey.update.longliving.updater import Updater

from humfrey.update.models import UpdateDefinition
from humfrey.update.forms import UpdateDefinitionForm, UpdatePipelineFormset

class IndexView(HTMLView, RedisView, AuthenticatedView):

    def get(self, request):
        client = self.get_redis_client()

        definitions = UpdateDefinition.objects.all().order_by('title')
        definitions = [d for d in definitions if d.can_view(request.user)]

        context = {
            'update_definitions': definitions,
            'update_queue': map(self.unpack, client.lrange(UpdateDefinition.UPDATE_QUEUE, 0, 100)),
            'upload_queue': map(self.unpack, client.lrange(Uploader.QUEUE_NAME, 0, 100)),
        }

        return self.render(request, context, 'update/index')

class DefinitionDetailView(HTMLView, AuthenticatedView):
    def common(self, request, slug=None):
        if slug:
            obj = get_object_or_404(UpdateDefinition, slug=slug)
        else:
            obj = UpdateDefinition()

        form = UpdateDefinitionForm(request.POST or None, instance=obj)
        pipelines = UpdatePipelineFormset(request.POST or None, instance=obj)

        return {
            'object': obj,
            'form': form,
            'pipelines': pipelines,
        }

    def get(self, request, slug=None):
        context = self.common(request, slug)
        if not context['object'].can_view(request.user):
            raise PermissionDenied

        return self.render(request, context, 'update/definition-detail')

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
            obj.queue('web', request.user)
        except UpdateDefinition.AlreadyQueued:
            context = {'status_code': 409,
                       'success': False,
                       'object': obj}
        else:
            context = {'success': True,
                       'object': obj}
        return self.render(request, context, 'update/definition-queued')
