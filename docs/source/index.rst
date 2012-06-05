.. humfrey documentation master file, created by
   sphinx-quickstart on Mon Jun  4 12:33:41 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to humfrey's documentation!
===================================

humfrey is a library for producing linked data front-end sites to RDF triple-stores. It builds on the `Django web
framework <http://www.djangoproject.com/>`_, allowing considerable customisation and integration into other sites.

It has the following features:

* Fully content-negotiable to various formats
* Customisable HTML representations of RDF resources
* SPARQL endpoint with rate-limiting and numerous serialization options
* Update system for pulling data from third-party sources and transforming it into RDF
* Support for maintaining ElasticSearch indexes of RDF data
* Support for multiple stores
* Producing time-stamped RDF dumps of data after an update
* Uploading dataset metadata to CKAN instances, such as `the Data Hub <http://thedatahub.org/>`_
* Thumbnailing images
* 303 redirects from resource URIs to their descriptions
* `Semantic pingback <http://aksw.org/Projects/SemanticPingBack>`_ (currently server only)

Contents:

.. toctree::
   :maxdepth: 2

   getting_started

Application reference
=====================

.. toctree::
   :glob:
   :maxdepth: 1
   
   ref/apps/*

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

