import os
import tempfile
import unittest

from django.test.simple import DjangoTestSuiteRunner, build_suite, reorder_suite
from django.test.runner import DiscoverRunner
from django.test import TestCase as DjangoTestCase
from django.test._doctest import DocTestCase
from django.db.models import get_app, get_apps
from django.db import transaction, connections, DEFAULT_DB_ALIAS
from django.utils.importlib import import_module
from django.conf import settings


class HumfreyTestSuiteRunner(DiscoverRunner):
    def run_suite(self, suite, **kwargs):
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

    _ignore_test_modules = [
       'django.contrib.auth.tests',
       'django.contrib.auth.tests.context_processors',
       'django.contrib.auth.tests.decorators',
       'django.contrib.auth.tests.signals',
       'django.contrib.auth.tests.views',
       'django_conneg.tests.basic_auth_middleware',
       'object_permissions.tests.backend',
       'object_permissions.tests.groups',
       'object_permissions.tests.permissions',
    ]
    _ignore_test_modules.extend(getattr(settings, 'IGNORE_TEST_MODULES', ()))
    
    def _filter_suite(self, suite):
        tests = []
        for testcase in suite._tests:
            if type(testcase).__module__ in self._ignore_test_modules:
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
    
    
try:
    from django_jenkins.runner import CITestSuiteRunner
except ImportError:
    pass
else:
    class HumfreyJenkinsTestSuiteRunner(HumfreyTestSuiteRunner, CITestSuiteRunner):
        def run_suite(self, suite, **kwargs):
            return super(HumfreyTestSuiteRunner, self).run_suite(suite, **kwargs)

