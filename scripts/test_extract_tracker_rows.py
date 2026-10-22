"""Provenance gates for staging PDF rows, without accepting them into the site."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import extract_tracker_rows as extractor


class ExtractionProvenanceTests(unittest.TestCase):
    def test_invalid_hash_cannot_select_a_file_outside_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, 'Invalid PDF SHA-256'):
                extractor.stage_document({'date': '22102026', 'sha256': '../outside'}, Path(temp))

    def test_modified_download_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as temp:
            digest = hashlib.sha256(b'original').hexdigest()
            (Path(temp) / (digest + '.pdf')).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                extractor.stage_document({'date': '22102026', 'sha256': digest}, Path(temp))

    def test_page_count_must_match_scanned_document(self):
        with tempfile.TemporaryDirectory() as temp:
            digest = hashlib.sha256(b'PDF fixture').hexdigest()
            (Path(temp) / (digest + '.pdf')).write_bytes(b'PDF fixture')
            document = dict(date='22102026', sha256=digest, agenda='agenda',
                            source='source', pdf_url='pdf', pages=2)
            opened = MagicMock()
            opened.__enter__.return_value.pages = [object()]
            with patch.object(extractor.pdfplumber, 'open', return_value=opened):
                with self.assertRaisesRegex(ValueError, 'page count differs'):
                    extractor.stage_document(document, Path(temp))

    def test_scan_errors_stop_staging(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / 'report.json'
            report.write_text(json.dumps({'errors': ['missing agenda'], 'documents': []}))
            output = Path(temp) / 'proposed'
            with patch('sys.argv', ['extract', '--report', str(report), '--output', str(output)]):
                with self.assertRaisesRegex(ValueError, 'Resolve scan errors'):
                    extractor.main()
            self.assertFalse(output.exists())

    def test_revisions_are_separate_and_warnings_prevent_clean_exit(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / 'report.json'
            documents = [dict(date='22102026', sha256=digest * 64, result='revised')
                         for digest in ['a', 'b']]
            report.write_text(json.dumps({'errors': [], 'documents': documents}))
            output = Path(temp) / 'proposed'
            proposed = {'records': [{'key': '110/2026'}], 'warnings': ['source needs review']}
            with patch.object(extractor, 'stage_document', return_value=proposed):
                with patch('sys.argv', ['extract', '--report', str(report), '--output', str(output)]):
                    self.assertEqual(extractor.main(), 2)
            self.assertEqual(len(list(output.glob('*-rows.json'))), 2)
            self.assertEqual(json.loads(report.read_text())['documents'], documents)


if __name__ == '__main__':
    unittest.main()
