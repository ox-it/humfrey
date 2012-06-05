:mod:`humfrey.elasticsearch` - ElasticSearch integration
========================================================

.. module :: humfrey.elasticsearch

``humfrey`` is able to update `ElasticSearch <http://www.elasticsearch.org/>`_ indices after updating a store. It
also includes a view for users to search the index, and which supports rudimentary faceting.

This app has a dependency on :mod:`humfrey.sparql`, and an optional dependency on :mod:`humfrey.update`.

Overview
--------

ElasticSearch provides for a hierarchy of multiple indexes, and within those various types. This app pushes data for
each store into an index of the same name, and the types are populated from named SPARQL queries, created using the
Django admin site.

Each SPARQL query is associated with one or more stores to be indexed, and zero or more update definitions after which
it will be run. It's also possible to specify a `mapping <http://www.elasticsearch.org/guide/reference/mapping/>`_ to
be PUT to the ElasticSearch server. 

Plumbing in
-----------

Add ``"humfrey.elasticsearch"`` to your :setting:`INSTALLED_APPS` setting.

.. setting :: ELASTICSEARCH_SERVER

Add an ELASTICSEARCH_SERVER variable to your settings::

   ELASTICSEARCH_SERVER = {'host': 'localhost',
                           'port': 9200}         # This is the default port

If you plan to use this app with :mod:`humfrey.update`, add the index updater to :setting:`DEPENDENT_TASKS` so that it
is executed after a store update::

   DEPENDENT_TASKS = {'humfrey.update.update': ('humfrey.elasticsearch.update_indexes_after_dataset_update')}

Include the :class:`~humfrey.elasticsearch.views.SearchView` in your urlconf::

   from django.conf.urls.defaults import patterns, url
   from humfrey.elasticsearch import views as elasticsearch_views

   urlpatterns = patterns('',
       url(r'^search/$', elasticsearch_views.SearchView.as_view(), name='search'),
   )

Writing SPARQL queries for the indexes
--------------------------------------

The queries you write should result in a resultset (i.e. they are SELECT queries), which are transformed into chunks
of JSON which are then fed to ElasticSearch. How you name your variables is important in the following ways:

* Variable names are split on underscores, which result in nested JSON objects. For example, a variable of
  ``?occupant_label`` will result in ``{"occupant": {"label": "..."}}``.
* Variable names with a final part of ``uri`` (e.g. ``?uri``, ``?occupant_uri``) are treated as the URI for a thing
  and used in links in the output of :class:`~humfrey.elasticsearch.views.SearchView`, and are used to merge results
  to create the final JSON object.
* A variable called ``?description`` will be used 
* You can specify that certain keys are repeatable as a whitespace-delimited list in the ``groups`` field of the
  index. For example, if ``occupant`` is repeatable then you'll get ``{"occupant": [{"label": "..."}, ...]}``. 

Generally an indexing query will focus on one type of thing in your store (e.g. spatial things, organisations, vending
machines):

.. code-block :: sparql

   SELECT * WHERE {
       ?type_uri rdfs:subClassOf* org:Organization .
       OPTIONAL { ?type_uri rdfs:label ?type_label } .
       ?uri a ?type_uri .
       ...
   }

This will specify a resultset like:

+------------------------+---------------------+---------------------------------+
| ?type_uri              | ?type_label         | ?uri                            |
+========================+=====================+=================================+
| org:Organization       | organization        | http://example.org/id/something |
+------------------------+---------------------+---------------------------------+
| org:FormalOrganization | formal organization | http://example.org/id/acme-corp |
+------------------------+---------------------+---------------------------------+

Which in turn will result in the following two JSON objects being indexed:

.. code-block :: javascript

   {"uri": "http://example.org/id/something",
    "type": {"uri": "org:Organization",
             "label": "organization"}}

   {"uri": "http://example.org/id/something",
    "type": {"uri": "org:Organization",
             "label": "organization"}}



API reference
-------------

.. class :: humfrey.elasticsearch.views.SearchView

   .. attribute :: index_name
   
      Defaults to 