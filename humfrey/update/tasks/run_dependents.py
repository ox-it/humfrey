from celery.task import task

from humfrey.update.models import UpdateDefinition

@task(name='humfrey.update.run_dependents')
def run_dependents(update_log, graphs, updated):
    """
    Runs dataset updates when updates they depend upon have completed.
    """
    
    update_definitions = UpdateDefinition.objects.filter(depends_on=update_log.update_definition)
    for update_definition in update_definitions:
        update_definition.queue()