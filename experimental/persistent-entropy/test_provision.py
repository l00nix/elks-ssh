#!/usr/bin/env python3
"""MIT. Host provisioning safety tests; never publish secret-bearing records."""
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from fixture import initial, record
from provision import create_bundle, validate

HELPER = Path(os.environ['ELKSSH_SEED_HELPER']).resolve()


class ProvisionTests(unittest.TestCase):
    def test_upstream_initialization_matches_independent_public_oracle(self):
        result = subprocess.run([str(HELPER)], input=bytes(range(48)),
                                capture_output=True, check=True)
        self.assertEqual(result.stdout, record(*initial()))
        self.assertFalse(result.stderr)

    def test_incomplete_and_excess_seed_refuse_without_output(self):
        for n in (0, 1, 47, 49, 96):
            with self.subTest(length=n):
                result = subprocess.run([str(HELPER)], input=bytes(n),
                                        capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(result.stdout)

    def test_fresh_recovery_material_and_private_modes(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp)/'initial', Path(temp)/'recovery'
            create_bundle(a, HELPER)
            create_bundle(b, HELPER)
            self.assertTrue((a/'state').read_bytes() != (b/'state').read_bytes(),
                            'Fresh bundles unexpectedly match')
            for directory in (a, b):
                validate((directory/'state').read_bytes())
                self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
                for name in ('state', 'COMPLETE.json'):
                    self.assertEqual(stat.S_IMODE((directory/name).stat().st_mode), 0o600)

    def test_existing_bundle_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)/'bundle'
            create_bundle(directory, HELPER)
            before = (directory/'state').read_bytes()
            with self.assertRaises(FileExistsError):
                create_bundle(directory, HELPER)
            self.assertTrue((directory/'state').read_bytes() == before,
                            'Existing bundle changed')

    def test_symlink_destination_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/'target'; target.mkdir()
            link = Path(temp)/'bundle'; link.symlink_to(target)
            with self.assertRaises(FileExistsError):
                create_bundle(link, HELPER)
            self.assertEqual(list(target.iterdir()), [])

    def test_host_random_source_failure_leaves_no_usable_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)/'bundle'
            with mock.patch('provision.os.urandom', side_effect=OSError('source failure')):
                with self.assertRaises(OSError):
                    create_bundle(directory, HELPER)
            self.assertEqual(list(directory.iterdir()), [])

    def test_helper_failure_leaves_no_usable_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)/'bundle'
            result = subprocess.CompletedProcess([], 1, b'private data', b'private data')
            with mock.patch('provision.subprocess.run', return_value=result):
                with self.assertRaisesRegex(RuntimeError, '^Provisioning helper failed; bundle is incomplete$'):
                    create_bundle(directory, HELPER)
            self.assertEqual(list(directory.iterdir()), [])

    def test_invalid_record_leaves_no_usable_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)/'bundle'
            result = subprocess.CompletedProcess([], 0, bytes(1024), b'')
            with mock.patch('provision.subprocess.run', return_value=result):
                with self.assertRaises(ValueError):
                    create_bundle(directory, HELPER)
            self.assertEqual(list(directory.iterdir()), [])

    def test_flush_failure_never_marks_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)/'bundle'
            with mock.patch('provision.os.fsync', side_effect=OSError('write failure')):
                with self.assertRaises(OSError):
                    create_bundle(directory, HELPER)
            self.assertFalse((directory/'COMPLETE.json').exists())
            with self.assertRaises(FileExistsError):
                create_bundle(directory, HELPER)

    def test_cli_reports_status_without_record_and_refuses_reuse(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)/'bundle'
            command = [sys.executable, str(Path(__file__).with_name('provision.py')),
                       '--output', str(directory), '--helper', str(HELPER)]
            first = subprocess.run(command, capture_output=True)
            self.assertEqual(first.returncode, 0)
            self.assertEqual(first.stdout, b'Private experimental bundle created. Not installed; not SSH-ready.\n')
            self.assertFalse(first.stderr)
            second = subprocess.run(command, capture_output=True)
            self.assertEqual(second.returncode, 1)
            self.assertFalse(second.stdout)
            self.assertEqual(second.stderr, b'Bundle creation failed. Do not use an incomplete bundle; existing files were not replaced.\n')


if __name__ == '__main__':
    unittest.main()
