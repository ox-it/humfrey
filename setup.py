from distutils.core import setup
from distutils.command.install import INSTALL_SCHEMES
import os

from humfrey import __version__, source_homepage

#################################
# BEGIN borrowed from Django #
# licensed under the BSD #
# http://www.djangoproject.com/ #
#################################

def fullsplit(path, result=None):
    """
Split a pathname into components (the opposite of os.path.join) in a
platform-neutral way.
"""
    if result is None:
        result = []
    head, tail = os.path.split(path)
    if head == '':
        return [tail] + result
    if head == path:
        return result
    return fullsplit(head, [tail] + result)

# Tell distutils to put the data_files in platform-specific installation
# locations. See here for an explanation:
# http://groups.google.com/group/comp.lang.python/browse_thread/thread/35ec7b2fed36eaec/2105ee4d9e8042cb
for scheme in INSTALL_SCHEMES.values():
    scheme['data'] = scheme['purelib']

# Compile the list of packages available, because distutils doesn't have
# an easy way to do this.
packages, data_files = [], []
root_dir = os.path.dirname(__file__)
if root_dir != '':
    os.chdir(root_dir)

for dirpath, dirnames, filenames in os.walk('humfrey'):
    # Ignore dirnames that start with '.'
    dirnames[:] = [dirname for dirname in dirnames if not dirname.startswith('.')]
    if '__init__.py' in filenames:
        packages.append('.'.join(fullsplit(dirpath)))
    elif filenames:
        data_files.append([dirpath, [os.path.join(dirpath, f) for f in filenames]])

#################################
# END borrowed from Django      #
#################################


# Idea borrowed from http://cburgmer.posterous.com/pip-requirementstxt-and-setuppy
install_requires, dependency_links = [], []
for line in open('requirements.txt'):
    line = line.strip()
    if line.startswith('-e'):
        dependency_links.append(line[2:].strip())
    elif line:
        install_requires.append(line)


setup(
    name='humfrey',
    description='A Django-based RESTful linked data frontend for SPARQL endpoints.',
    author='IT Services, University of Oxford',
    author_email='opendata@oucs.ox.ac.uk',
    version=__version__,
    packages=packages,
    license='BSD',
    url=source_homepage,
    long_description=open('README.rst').read(),
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
    data_files=data_files,
    install_requires=install_requires,
    dependency_links=dependency_links,
)
