# -------------------------------------------------------------------------
#
#  Part of the CodeChecker project, under the Apache License v2.0 with
#  LLVM Exceptions. See LICENSE for license information.
#  SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
#
# -------------------------------------------------------------------------

""" Test cases to trim a path by using prefixes. """


import os
import tempfile
import unittest

from codechecker_report_converter.report import BugPathEvent, File, Range, \
    Report, report_file
from codechecker_report_converter.util import trim_path_prefixes


class TrimPathPrefixTestCase(unittest.TestCase):
    """
    Test cases to trim a path by using prefixes.
    """

    def test_no_prefix(self):
        test_path = '/a/b/c'
        self.assertEqual(test_path, trim_path_prefixes(test_path, None))
        self.assertEqual(test_path, trim_path_prefixes(test_path, []))
        self.assertEqual(test_path, trim_path_prefixes(test_path, ['x']))

    def test_only_root_matches(self):
        test_path = '/a/b/c'
        self.assertEqual(test_path, trim_path_prefixes(test_path, ['/']))
        self.assertEqual(test_path, trim_path_prefixes(test_path, ['/x']))

    def test_one_matches(self):
        test_path = '/a/b/c'
        self.assertEqual('b/c', trim_path_prefixes(test_path, ['/a']))
        self.assertEqual('c', trim_path_prefixes(test_path, ['/a/b']))

    def test_longest_matches(self):
        test_path = '/a/b/c'
        self.assertEqual('b/c', trim_path_prefixes(test_path, ['/a']))
        self.assertEqual('c', trim_path_prefixes(test_path, ['/a', '/a/b']))

    def test_file_path(self):
        test_path = '/a/b/c/foo.txt'
        self.assertEqual('foo.txt', trim_path_prefixes(test_path, ['/a/b/c']))

    def test_prefix_in_dir_name(self):
        test_path = '/a/b/common/foo.txt'
        self.assertEqual(test_path, trim_path_prefixes(test_path, ['/a/b/c']))
        self.assertEqual('foo.txt',
                         trim_path_prefixes(test_path, ['/a/b/common']))

    def test_prefix_in_filename(self):
        test_path = '/a/b/common.txt'
        self.assertEqual(test_path, trim_path_prefixes(test_path, ['/a/b/c']))
        self.assertEqual(test_path,
                         trim_path_prefixes(test_path, ['/a/b/common']))
        self.assertEqual('common.txt',
                         trim_path_prefixes(test_path, ['/a/b/']))

    def test_prefix_blob(self):
        test_path = '/a/b/common.txt'
        self.assertEqual('common.txt', trim_path_prefixes(test_path, ['/*/b']))
        self.assertEqual('common.txt', trim_path_prefixes(test_path, ['/a/*']))
        self.assertEqual('common.txt',
                         trim_path_prefixes(test_path, ['/*/']))
        self.assertEqual('common.txt',
                         trim_path_prefixes(test_path, ['/a/?/']))

        self.assertEqual('my_proj/x.cpp',
                         trim_path_prefixes('/home/jsmith/my_proj/x.cpp',
                                            ['/home/jsmith/']))


class FileTrimPathPersistedTestCase(unittest.TestCase):
    """
    Test cases for File.trim_path and Report.trim_path_prefixes_persisted,
    which trim the persisted (original) file paths. These are used by
    'CodeChecker analyze --trim-path-prefix' so that the paths written into the
    generated result (e.g. '.plist') files become independent of the local
    directory layout (e.g. a Bazel cache folder).
    """

    def test_file_trim_only_affects_display_path(self):
        """ File.trim() must not change the persisted original_path. """
        f = File('/path/to/your/main.cpp')
        f.trim(['/path/to/your/'])

        self.assertEqual('main.cpp', f.path)
        # The original (persisted) path must stay untouched.
        self.assertEqual('/path/to/your/main.cpp', f.original_path)

    def test_file_trim_path_affects_persisted_path(self):
        """ File.trim_path() must trim both display and persisted paths. """
        f = File('/path/to/your/main.cpp')
        f.trim_path(['/path/to/your/'])

        self.assertEqual('main.cpp', f.path)
        self.assertEqual('main.cpp', f.original_path)
        self.assertEqual('main.cpp', f.id)
        self.assertEqual('main.cpp', f.name)

    def test_file_trim_path_no_prefix(self):
        """ Without a matching prefix the path is left intact. """
        f = File('/path/to/your/main.cpp')
        f.trim_path(None)
        self.assertEqual('/path/to/your/main.cpp', f.original_path)

        f.trim_path(['/does/not/match/'])
        self.assertEqual('/path/to/your/main.cpp', f.original_path)

    def test_report_trim_path_prefixes_persisted(self):
        """
        Report.trim_path_prefixes_persisted() must trim the persisted path of
        every referenced file (the main file and all event files).
        """
        main_file = File('/path/to/your/main.cpp')
        header_file = File('/path/to/your/lib/util.h')

        report = Report(
            main_file, 7, 14, 'Division by zero', 'core.DivideZero',
            bug_path_events=[
                BugPathEvent(
                    "something", header_file, 6, 1, Range(6, 1, 6, 1))])

        report.trim_path_prefixes_persisted(['/path/to/your/'])

        self.assertEqual('main.cpp', main_file.original_path)
        self.assertEqual('lib/util.h', header_file.original_path)
        self.assertEqual(
            {'main.cpp', 'lib/util.h'}, report.original_files)


class PlistTrimPathPrefixTestCase(unittest.TestCase):
    """
    End-to-end test: a report whose paths are trimmed with
    trim_path_prefixes_persisted() must produce a '.plist' whose 'files' array
    contains the trimmed paths.
    """

    def test_plist_files_array_is_trimmed(self):
        report = Report(
            File('/path/to/your/main.cpp'), 3, 5,
            'Dereference of null pointer', 'core.NullDereference',
            report_hash='fakehash',
            bug_path_events=[
                BugPathEvent(
                    "null pointer dereference",
                    File('/path/to/your/main.cpp'), 3, 5,
                    Range(3, 5, 3, 10))])

        report.trim_path_prefixes_persisted(['/path/to/your'])

        with tempfile.TemporaryDirectory() as tmp_dir:
            plist_path = os.path.join(tmp_dir, 'report.plist')
            report_file.create(plist_path, [report])

            with open(plist_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # The trimmed path must be present ...
            self.assertIn('<string>main.cpp</string>', content)
            # ... and the original prefixed path must be gone.
            self.assertNotIn('/path/to/your/main.cpp', content)

            # Re-parsing the written plist should also yield the trimmed path.
            # Note: the plist parser resolves relative paths against the
            # plist's directory, so compare the file name only.
            reports = report_file.get_reports(plist_path)
            self.assertEqual(1, len(reports))
            self.assertEqual('main.cpp', reports[0].file.name)
            self.assertEqual(
                os.path.join(tmp_dir, 'main.cpp'),
                reports[0].file.original_path)
