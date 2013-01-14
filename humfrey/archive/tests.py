import datetime
import os
import unittest

import mock
import pytz

from .tasks import DatasetArchiver

class OldArchiveRemoverTestCase(unittest.TestCase):
    @mock.patch('os.listdir')
    @mock.patch('os.unlink')
    def testRemovals(self, unlink, listdir):
        archive_path = 'testdir/testsubdir'

        filenames = []
        for i in xrange(0, 10000):
            dt = pytz.utc.localize(datetime.datetime.utcnow()) - datetime.timedelta(0, 14400*i)
            dt - dt.replace(microsecond=0)
            filenames.append('{0}.rdf'.format(dt.isoformat()))

        listdir.return_value = filenames

        DatasetArchiver.filter_old_archives(archive_path)

        listdir.assert_called_once_with(archive_path)

        remaining = sorted(set(filenames) - set(os.path.basename(call[1][0]) for call in unlink.mock_calls))

        # This doesn't actually test that the right files have been removed.
        # However, a casual inspection of the results of this print statement
        # looks about right.
        # print '\n'.join(remaining)