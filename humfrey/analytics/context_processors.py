from django.conf import settings

def google_analytics(context):
    google_analytics = getattr(settings, 'GOOGLE_ANALYTICS', None)
    if google_analytics:
        return {
            'google_analytics': google_analytics,
        }
    else:
        return {}

