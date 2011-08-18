import rdflib
from rdflib import URIRef
import types

from django.shortcuts import render_to_response
from django.template import RequestContext
from django_conneg.decorators import renderer
from django.utils.feedgenerator import RssUserland091Feed, Rss201rev2Feed, Atom1Feed, rfc2822_date
from django.http import HttpResponse

from humfrey.utils.views import EndpointView
from humfrey.utils.resource import Resource
from humfrey.utils.namespaces import NS


_DATE_PROPERTIES = [ NS['dcterms'] + "created", "http://purl.org/openorg/vacancy/created" ]
_TITLE_PROPERTIES = [ NS['rdfs'] + "label",
                      NS['skos'] + "prefLabel"]
_DESCRIPTION_PROPERTIES = [ NS['dcterms'] + "description", "http://purl.org/openorg/vacancy/description"]
_LINK_PROPERTIES = [ NS['rdfs'] + "seeAlso"]

def extractFeedDetails(request):
    title = "debug empty title"
    desc = "debug empty description"
    link = "http://www.debug.com/example/link"
    print request
    if 'feedtitle' in request.GET:
        title = request.GET['feedtitle']
    if 'feeddescription' in request.GET:
        desc = request.GET['feeddescription']       
    if 'feedlink' in request.GET:
        link = request.GET['feedlink']       
    return (title, desc, link)
class FeedView(EndpointView):
                             
    # obj._DESCRIPTION_PROPERTIES
    # obj._LABEL_PROPERTIES

    @renderer(format='rss1', mimetypes=('application/rss+xml',), name='RSS 0.9 Feed')
    def render_rss1(self, request, context, template_name):
        (title, desc, link) = extractFeedDetails(request)
        feed = RssUserland091Feed(title, link, desc)
        return self.renderGeneralFeed(request, context, template_name, feed)    
    
    @renderer(format='rss2', mimetypes=('application/rss+xml',), name='RSS 2.01 Feed')
    def render_rss2(self, request, context, template_name):
        (title, desc, link) = extractFeedDetails(request)
        feed = Rss201rev2Feed(title, link, desc)
        return self.renderGeneralFeed(request, context, template_name, feed)
    
    @renderer(format='atom', mimetypes=('application/atom+xml',), name='Atom Feed')
    def render_atom(self, request, context, template_name):
        (title, desc, link) = extractFeedDetails(request)
        feed = Atom1Feed(title, link, desc)
        return self.renderGeneralFeed(request, context, template_name, feed)
    
    def renderGeneralFeed(self, request, context, template_name, feed):
        graph = context['graph']
        subjects = set(graph.subjects())
        rssItems = []
        for subject in subjects:
            if isinstance(subject, rdflib.URIRef):
            #grab a creation date, label and description!
                subjectDict = {}
                for (predicate, object) in graph.predicate_objects(subject):
                    predicate = unicode(predicate)
                    object = unicode(object)
                    if predicate in _DATE_PROPERTIES:
                        subjectDict['date'] = object
                    if predicate in _TITLE_PROPERTIES:
                        subjectDict['title'] = object
                    if predicate in _DESCRIPTION_PROPERTIES:
                        subjectDict['description'] = object
                    if predicate in _LINK_PROPERTIES:
                        subjectDict['link'] = object
                    # TO DO: add any other desired properties for the RSS feed!
                if 'description' not in subjectDict:
                    subjectDict['description'] = ""
                if 'link' not in subjectDict:
                    subjectDict['link'] = "http://www.no.link.found"
                if  ('title' in subjectDict):
                    rssItems.append(subjectDict)
        print rssItems
        feed.add_root_elements = add_root_elements
        setattr(feed, add_root_elements.__name__, types.MethodType(add_root_elements, feed))
        for item in rssItems:
            feed.add_item(item['title'], item['link'], item['description'])
        return HttpResponse(feed.writeString('utf-8'))
        
        

"""This is a nasty workaround for the (known) bug in Django: 
https://code.djangoproject.com/ticket/14202
This is the troublesome method with a correction, 
and must be assigned to the relevant feed class before use!""" 
def add_root_elements(self, handler):
        handler.addQuickElement(u"title", self.feed['title'])
        handler.addQuickElement(u"link", self.feed['link'])
        handler.addQuickElement(u"description", self.feed['description'])
        # handler.addQuickElement(u"atom:link", None, {u"rel": u"self", u"href": self.feed['feed_url']})
        if self.feed['language'] is not None:
            handler.addQuickElement(u"language", self.feed['language'])
        for cat in self.feed['categories']:
            handler.addQuickElement(u"category", cat)
        if self.feed['feed_copyright'] is not None:
            handler.addQuickElement(u"copyright", self.feed['feed_copyright'])
        handler.addQuickElement(u"lastBuildDate", rfc2822_date(self.latest_post_date()).decode('utf-8'))
        if self.feed['ttl'] is not None:
            handler.addQuickElement(u"ttl", self.feed['ttl'])
        