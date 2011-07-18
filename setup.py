from distutils.core import setup
from distutils.command.install import INSTALL_SCHEMES
import os

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

print data_files

setup(
    name='humfrey',
    description='A Django-based RESTful linked data frontend for SPARQL endpoints.',
    author='Oxford University Computing Services',
    author_email='opendata@oucs.ox.ac.uk',
    version='0.1',
    packages=packages,
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
    data_files=data_files,

)
