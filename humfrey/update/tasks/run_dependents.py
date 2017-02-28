from celery import shared_task

from humfrey.signals import update_completed
from humfrey.update.models import UpdateDefinition, UpdateDefinitionAlreadyQueued

@shared_task(name='humfrey.update.run_dependents')
def run_dependents(sender, update_definition, store_graphs, when, **kwargs):
    """
    Runs dataset updates when updates they depend upon have completed.
    """
    
    update_definitions = UpdateDefinition.objects.filter(depends_on=update_definition)
    
    return
    for update_definition in update_definitions:
        try:
            update_definition.queue()
        except UpdateDefinitionAlreadyQueued:
            pass
        
update_completed.connect(run_dependents.delay)
