import os
import tempfile
import unittest

from django.test.simple import DjangoTestSuiteRunner, build_suite, reorder_suite
from django.test import TestCase as DjangoTestCase
from django.test._doctest import DocTestCase
from django.db.models import get_app, get_apps
from django.db import transaction, connections, DEFAULT_DB_ALIAS
from django.utils.importlib import import_module
from django.conf import settings

from django_jenkins.runner import CITestSuiteRunner

class HumfreyTestSuiteRunner(DjangoTestSuiteRunner):
    def __init__(self, *args, **kwargs):
        for connection in connections.all():
            connection.settings_dict.update({
                'ENGINE': 'django.db.backends.sqlite3',
                'SUPPORTS_TRANSACTIONS': False,
            })
        self.temporary_database_name = tempfile.mktemp()
        super(HumfreyTestSuiteRunner, self).__init__(*args, **kwargs)
        
    def setup_databases(self, **kwargs):
        pass
    def teardown_databases(self, old_config, **kwargs):
        pass
    
    def run_suite(self, suite, **kwargs):
        for connection in connections.all():
            connection.settings_dict.update({
                'ENGINE': 'django.db.backends.sqlite3',
                'SUPPORTS_TRANSACTIONS': False,
            })

        if os.environ.get('HUMFREY_JUNIT_TEST'):
            import junitxml
            report_filename = os.path.join(os.path.dirname(__file__), '..', 'xmlresults.xml')
            with open(report_filename, 'w') as report:
                result = junitxml.JUnitXmlResult(report)
                result.startTestRun()
                suite.run(result)
                result.stopTestRun()
            return result
        else:
            return super(HumfreyTestSuiteRunner, self).run_suite(suite, **kwargs)
    
    def _filter_suite(self, suite):
        tests = []
        for testcase in suite._tests:
            if isinstance(testcase, (DjangoTestCase, DocTestCase)):
                continue
            if type(testcase).__module__.startswith('django.'):
                continue
            if isinstance(testcase, unittest.TestSuite):
                self._filter_suite(testcase)
                if testcase._tests:
                    tests.append(testcase)
            else:
                tests.append(testcase)
        suite._tests = tests
        
    def build_suite(self, test_labels, extra_tests=None, **kwargs):
        suite = super(HumfreyTestSuiteRunner, self).build_suite(test_labels, extra_tests=None, **kwargs)
        for module_name in getattr(settings, 'EXTRA_TEST_MODULES', ()):
            suite.addTests(unittest.findTestCases(import_module(module_name)))
        self._filter_suite(suite)
        return suite
    
    
class HumfreyJenkinsTestSuiteRunner(HumfreyTestSuiteRunner, CITestSuiteRunner):
    def run_suite(self, suite, **kwargs):
        return super(HumfreyTestSuiteRunner, self).run_suite(suite, **kwargs)

