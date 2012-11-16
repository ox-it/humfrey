from __future__ import with_statement, absolute_import

try:
    import sharepoint
except ImportError:
    pass
else:
    import logging
    
    from lxml import etree
    
    from humfrey.update.transform.base import Transform
    from humfrey.update.tasks.retrieve import get_opener
    
    logger = logging.getLogger(__name__)

    class SharePointLists(Transform):
        def __init__(self, site_url, **kwargs):
            self.site_url = site_url
            self.kwargs = kwargs

        def execute(self, transform_manager):
            opener = get_opener(self.site_url, transform_manager.opener)
            site = sharepoint.SharePointSite(self.site_url, opener)
            
            with transform_manager('xml')  as f:
                xml = site.lists.as_xml(**self.kwargs)
                f.write(etree.tostring(xml))
                return f.name
