import unittest, tempfile, os

from django.test.simple import DjangoTestSuiteRunner, build_suite, reorder_suite
from django.test import TestCase as DjangoTestCase
from django.test._doctest import DocTestCase
from django.db.models import get_app, get_apps
from django.db import transaction, connections, DEFAULT_DB_ALIAS

class HumfreyTestSuiteRunner(DjangoTestSuiteRunner):
    def __init__(self, *args, **kwargs):
        for connection in connections.all():
            connection.settings_dict.update({
                'ENGINE': 'django.db.backends.sqlite3',
                'SUPPORTS_TRANSACTIONS': False,
            })
        self.temporary_database_name = tempfile.mktemp()
        super(HumfreyTestSuiteRunner, self).__init__(*args, **kwargs)
        
#===============================================================================
    def setup_databases(self, **kwargs):
        pass
#        for connection in connections.all():
#            connection.settings_dict.update({
#                'ENGINE': 'sqlite3',
#                'DATABASE': self.temporary_database_name,
#                'SUPPORTS_TRANSACTIONS': False,
#            })
#            print connection.settings_dict
# 
    def teardown_databases(self, old_config, **kwargs):
        pass
# #        os.unlink(self.temporary_database_name)
#===============================================================================
    
    def run_suite(self, suite, **kwargs):
        for connection in connections.all():
            connection.settings_dict.update({
                'ENGINE': 'django.db.backends.sqlite3',
                'SUPPORTS_TRANSACTIONS': False,
            })

        if '--junit' in sys.argv:
            import junit
            with open('../xmlresults.xml', 'w') as report:
                result = junitxml.JUnitXmlResult(report)
                result.startTestRun()
                suite.run(result)
                result.stopTestRun()
            return result
        else:
            return super(HumfreyTestSuiteRunner, self).run_suite(suite, **kwargs)
        
    def build_suite(self, test_labels, extra_tests=None, **kwargs):

        suite = super(HumfreyTestSuiteRunner, self).build_suite(test_labels, extra_tests=None, **kwargs)
        suite._tests[:] = [tc for tc in suite._tests if
                           not isinstance(tc, (DjangoTestCase, DocTestCase)) and
                           not type(tc).__module__.startswith('django.')]
        return suite
    
#===============================================================================
# 244                for app in get_apps():
# 245                    suite.addTest(build_suite(app))
# 246    
# 247            if extra_tests:
# 248                for test in extra_tests:
# 249                    suite.addTest(test)
# 250    
# 251            return reorder_suite(suite, (TestCase,))
#    
#===============================================================================
