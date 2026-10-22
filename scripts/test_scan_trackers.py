import copy
import importlib.util
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('scanner', Path(__file__).with_name('scan_trackers.py'))
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)

PATH = 'Open/2026/10/CNL_22102026_AGN_WEB.htm'
AGENDA = scanner.BASE + PATH.replace('_WEB.htm', '.HTM')
SOURCE = 'https://ecouncil.lanecove.nsw.gov.au/trim/GenDocLink.asp?RecId=80371/26'
ROW = '<tr><td><span>Resolution</span> Tracker</td><td><a href="' + SOURCE + '">PDF</a></td></tr>'
INDEX = ('<input type="hidden" name="__VIEWSTATE" value="abc">'
         '<select name="ctl00$MainContent$ddlYear"><option value="2026" selected>2026</option></select>'
         '<a href="' + PATH + '">Agenda</a>')


class FakeFetcher:
    def __init__(self, agenda='<html>Council<table>' + ROW + '</table></html>'):
        self.agenda = agenda

    def get(self, url, fields=None):
        return (INDEX if url == scanner.BASE else self.agenda).encode(), url


class ScannerTests(unittest.TestCase):
    def test_proxy_timeout_is_reported_and_host_deferred_without_hiding_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            fetcher=scanner.Fetcher(temp)
            def timeout(command, **kwargs):
                Path(command[command.index('--output')+1]).write_bytes(b'upstream connect error or disconnect/reset before headers. reset reason: connection timeout')
                return subprocess.CompletedProcess(command,22,'503\n'+SOURCE,'')
            with patch.object(scanner.subprocess,'run',side_effect=timeout) as run:
                with self.assertRaisesRegex(scanner.FetchError,'proxy upstream connection timed out'):
                    fetcher.get(SOURCE)
                with self.assertRaisesRegex(scanner.FetchError,'not checked: host deferred'):
                    fetcher.get(SOURCE.replace('80371','7554'))
                self.assertEqual(run.call_count,1)
                self.assertNotIn('lanecove.infocouncil.biz',fetcher.unreachable)

    def test_origin_503_is_not_misclassified_as_proxy_timeout(self):
        with tempfile.TemporaryDirectory() as temp:
            fetcher=scanner.Fetcher(temp)
            def unavailable(command, **kwargs):
                Path(command[command.index('--output')+1]).write_bytes(b'<html>Service Unavailable</html>')
                return subprocess.CompletedProcess(command,22,'503\n'+SOURCE,'')
            with patch.object(scanner.subprocess,'run',side_effect=unavailable):
                with self.assertRaises(scanner.FetchError) as error:fetcher.get(SOURCE)
                self.assertFalse(error.exception.upstream_timeout)
                self.assertFalse(fetcher.unreachable)

    def test_successful_fetch_preserves_verified_redirect_url(self):
        with tempfile.TemporaryDirectory() as temp:
            fetcher=scanner.Fetcher(temp)
            def ok(command, **kwargs):
                Path(command[command.index('--output')+1]).write_bytes(b'content')
                return subprocess.CompletedProcess(command,0,'200\n'+SOURCE,'')
            with patch.object(scanner.subprocess,'run',side_effect=ok):
                self.assertEqual(fetcher.get(SOURCE),(b'content',SOURCE))

    def test_all_agenda_variants_including_extraordinary(self):
        extra = PATH.replace('_AGN_WEB', '_AGN_AT_SUP_WEB')
        self.assertEqual(scanner.agenda_paths(INDEX + extra, 2026), [extra, PATH])
        self.assertEqual(scanner.agenda_paths(INDEX, 2025), [])

    def test_nested_layout_does_not_capture_unrelated_attachment(self):
        text = '<table><tr><td><table>' + ROW + '<tr><td>Budget</td><td><a href="https://ecouncil.lanecove.nsw.gov.au/budget.pdf">PDF</a></td></tr></table></td></tr></table>'
        self.assertEqual(scanner.attachments(text, AGENDA), [SOURCE])

    def test_multiple_trackers_are_all_retained(self):
        other = SOURCE.replace('80371', '80372')
        self.assertEqual(scanner.attachments(ROW + ROW.replace(SOURCE, other), AGENDA), [SOURCE, other])

    def test_revised_bytes_at_same_url(self):
        old = {'agenda': AGENDA, 'source': SOURCE, 'sha256': 'old'}
        self.assertEqual(scanner.classify([old], old | {'sha256': 'new'}), 'revised')
        self.assertEqual(scanner.classify([old], old), 'unchanged')

    def test_old_pdf_linked_by_new_agenda_is_not_new_edition(self):
        old = {'agenda': AGENDA, 'source': SOURCE, 'sha256': 'same'}
        self.assertEqual(scanner.classify([old], old | {'agenda': AGENDA + '?another=1'}), 'reused_pdf')

    def test_changed_attachment_requires_review(self):
        old = {'agenda': AGENDA, 'source': SOURCE, 'sha256': 'old'}
        self.assertEqual(scanner.classify([old], old | {'source': SOURCE + 'x', 'sha256': 'new'}), 'new')

    def test_wrong_selected_year_is_failure(self):
        with self.assertRaisesRegex(ValueError, 'requested year'):
            scanner.discover(FakeFetcher(), 2025)

    def test_html_extraction_error_is_failure(self):
        class ErrorFetcher:
            def get(self, url):
                return b'<html>There was an error extracting the File.</html>', url
        with self.assertRaisesRegex(ValueError, 'HTML/error'):
            scanner.read_pdf(ErrorFetcher(), SOURCE)

    def test_redirect_can_not_use_non_council_host(self):
        with self.assertRaises(ValueError):
            scanner.safe_url('https://example.com/tracker.pdf')

    def test_missing_expected_attachment_is_failure(self):
        baseline = [{'date': '22102026', 'agenda': AGENDA, 'source': SOURCE, 'sha256': 'old'}]
        with tempfile.TemporaryDirectory() as temp:
            report = scanner.scan(FakeFetcher('<html>Council</html>'), [2026], baseline, Path(temp))
        self.assertIn('no recognized attachment', report['errors'][0]['error'])

    def test_missing_known_agenda_is_failure(self):
        baseline = [{'date': '22102026', 'agenda': AGENDA + '?missing', 'source': SOURCE, 'sha256': 'old'}]
        with tempfile.TemporaryDirectory() as temp, patch.object(scanner, 'read_pdf', return_value=(b'pdf', SOURCE, 1)):
            report = scanner.scan(FakeFetcher(), [2026], baseline, Path(temp))
        self.assertTrue(any('absent from index' in e['error'] for e in report['errors']))

    def test_scan_stages_revision_without_updating_baseline(self):
        baseline = [{'date': '22102026', 'agenda': AGENDA, 'source': SOURCE, 'sha256': 'old'}]
        before = copy.deepcopy(baseline)
        with tempfile.TemporaryDirectory() as temp, patch.object(scanner, 'read_pdf', return_value=(b'changed', SOURCE, 2)):
            output = Path(temp)
            report = scanner.scan(FakeFetcher(), [2026], baseline, output)
            scanner.write_report(report, output)
            self.assertTrue(report['needs_review'])
            self.assertEqual(report['documents'][0]['result'], 'revised')
            self.assertEqual(len(list(output.glob('*.pdf'))), 1)
            self.assertTrue((output / 'report.json').exists())
        self.assertEqual(baseline, before)


if __name__ == '__main__':
    unittest.main()
