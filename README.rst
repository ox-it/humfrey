humfrey
=======

humfrey is a Django-based RESTful linked data interface to a SPARQL endpoint.

Features
--------

* Serialization to HTML, RDF, JSON, CSV.
* Template selection based on rdf:types.
* Semantic pingback
* SPARQL rate-limiting

Documentation
-------------

Read the documentation at `humfrey.readthedocs.org <http://humfrey.readthedocs.org/>`_.

Using
-----

humfrey provides a lot of the framework you need for producing a linked data
site. You will need to produce a minimal Django project to pull it all
together. Examples include `data.ox.ac.uk <https://github.com/ox-it/dataox>`_,
`data.clarosnet.org <https://github.com/clarosnet/claros-voyager>`_, and
`opencitations.net <https://github.com/opencitations/opencitations-net>`_. In
due course we plan to provide a simple demonstration site that will run out of
the box.

It requires a backing SPARQL endpoint to run queries against. The sites listed
above use `Fuseki <http://openjena.org/wiki/Fuseki>`_, but it should work with
any endpoint. If it doesn't, raise an issue in `the GitHub issue tracker
<https://github.com/ox-it/humfrey/issues>`_.

You will also need running ``memcached`` and ``redis`` instances.

Running the test suite
----------------------

In the root of the humfrey module run::

    PYTHONPATH=.. python manage.py test --settings=humfrey.tests.settings

If using Jenkins, you can use tox or run the following::

    PYTHONPATH=.. python manage.py jenkins --settings=humfrey.tests.settings

This will produce a bunch of reports using django_jenkins, which will turn up in a ``reports`` directory.

Requirements
------------

* memcached
* redis
