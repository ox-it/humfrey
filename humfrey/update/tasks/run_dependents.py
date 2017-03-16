from celery import shared_task
from django.dispatch import receiver

from humfrey.signals import update_completed
from humfrey.update.models import UpdateDefinition, UpdateDefinitionAlreadyQueued


@shared_task(name='humfrey.update.run_dependents')
def run_dependents(update_definition_id):
    """
    Runs dataset updates when updates they depend upon have completed.
    """

    update_definitions = UpdateDefinition.objects.filter(depends_on__pk=update_definition_id)
    
    for update_definition in update_definitions:
        try:
            update_definition.queue()
        except UpdateDefinitionAlreadyQueued:
            pass


@receiver(update_completed)
def update_completed_receiver(sender, update_definition_id, **kwargs):
    run_dependents.delay(update_definition_id)
