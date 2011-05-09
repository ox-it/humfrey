from distutils.core import setup

setup(
    name='humfrey',
    description='A Django-based RESTful linked data frontend for SPARQL endpoints.',
    author='Oxford University Computing Services',
    author_email='opendata@oucs.ox.ac.uk',
    version='0.1',
    packages=['humfrey', 'humfrey.desc', 'humfrey.pingback', 'humfrey.utils', 'humfrey.settings'],
    scripts=['humfrey/pingback/bin/pingback.py'],
    license='BSD',
    long_description=open('README.txt').read(),
    classifiers=['Development Status :: 4 - Beta',
                 'Framework :: Django',
                 'Intended Audience :: Developers',
                 'License :: OSI Approved :: BSD License',
                 'Natural Language :: English',
                 'Operating System :: OS Independent',
                 'Programming Language :: Python',
                 'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
                 'Topic :: Software Development :: Libraries :: Python Modules'],
    keywords=['sparql', 'linked data', 'RDF', 'REST'],

)
