import unittest
from pathlib import Path
from update_preflight import validate_binding, validate_runtime


class PreflightTests(unittest.TestCase):
    config = {'location': 'local', 'repository': 'adrasyn/lane-cove-resolution-tracker', 'branch': 'main'}
    remote = 'https://github.com/adrasyn/lane-cove-resolution-tracker.git'

    def test_local_binding_and_explicit_future_cloud_switch(self):
        validate_binding(self.config, 'local', self.remote, 'main', '')
        validate_binding(dict(self.config, location='cloud'), 'cloud', self.remote, 'main', '')

    def test_stale_cloud_schedule_cannot_process_local_configuration(self):
        with self.assertRaisesRegex(ValueError, 'Execution location'):
            validate_binding(self.config, 'cloud', self.remote, 'main', '')

    def test_local_runtime_cannot_be_selected_from_cloud_or_another_checkout(self):
        config = dict(self.config, localBinding={'platform': 'darwin', 'checkout': '~/tracker-checkout'})
        expected = Path('~/tracker-checkout').expanduser()
        validate_runtime(config, 'local', 'darwin', expected)
        for platform, checkout in [('linux', expected), ('darwin', expected / 'another')]:
            with self.subTest(platform=platform), self.assertRaisesRegex(ValueError, 'configured Mac checkout'):
                validate_runtime(config, 'local', platform, checkout)

    def test_wrong_checkout_or_unfinished_work_cannot_publish(self):
        for remote, branch, dirty in [(self.remote + '-other', 'main', ''),
                                      (self.remote, 'review', ''), (self.remote, 'main', ' M dist/data.js')]:
            with self.subTest(remote=remote, branch=branch, dirty=dirty), self.assertRaises(ValueError):
                validate_binding(self.config, 'local', remote, branch, dirty)
