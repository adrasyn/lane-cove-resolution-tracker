"""Regressions for identical officer comments belonging to different minute items."""
import contextlib
import copy
import importlib.util
import io
import json
import pathlib
import shutil
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('catalogue_build', ROOT / 'catalogue/build_catalogue.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class SummaryContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Build the fixture from tracked source rows; no local generated cache is required.
        with tempfile.TemporaryDirectory() as directory:
            temporary = pathlib.Path(directory)
            shutil.copytree(ROOT / 'catalogue/structured', temporary / 'structured')
            shutil.copyfile(ROOT / 'catalogue/historical-links.json', temporary / 'historical-links.json')
            original_root = build.ROOT
            build.ROOT = temporary
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    cls.model = build.model()
            finally:
                build.ROOT = original_root

    def compile(self, edit=None, model=None):
        with tempfile.TemporaryDirectory() as directory:
            temporary = pathlib.Path(directory)
            for pattern in ['editorial-output-*.json', 'note-*.json', 'historical-minutes-verification.json']:
                for source in (ROOT / 'catalogue').glob(pattern):
                    shutil.copyfile(source, temporary / source.name)
            if edit:
                edit(temporary)
            original_root, original_site = build.ROOT, build.SITE
            build.ROOT, build.SITE = temporary, temporary
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    return build.compile_site(self.model if model is None else model)
            finally:
                build.ROOT, build.SITE = original_root, original_site

    def test_greenwich_gateway_update_does_not_name_austin_crescent(self):
        issues, evidence, _, _ = self.compile()
        issue = next(i for i in issues if i['id'] == 'greenwich-road-177-183')
        update = next(e for e in issue['events'] if e['date'] == '2026-07-14')
        self.assertNotIn('Austin', update['title'])
        self.assertIn('Gateway', update['title'])
        self.assertEqual(update['entries'][0]['resolution'], '110/2026')
        self.assertIn('Gateway determination', evidence[update['entries'][0]['evidence']]['text'])

    def test_performance_review_does_not_inherit_transport_summary(self):
        issues, _, _, _ = self.compile()
        entries = [e for i in issues for d in i['events'] for e in d['entries']
                   if e['resolution'] == '197/2026' and e['kind'] == 'update']
        self.assertTrue(entries)
        for entry in entries:
            self.assertNotIn('transport', (entry['title'] + ' ' + entry['text']).lower())

    def test_cctv_exhibition_does_not_inherit_childcare_title(self):
        issues, _, _, _ = self.compile()
        entries = [e for i in issues for d in i['events'] for e in d['entries']
                   if e['resolution'] == '186/2026' and e['kind'] == 'update']
        self.assertTrue(entries)
        for entry in entries:
            self.assertNotIn('Kindy Cove', entry['title'])

    def test_unreviewed_comments_stop_the_build(self):
        def remove_summaries(directory):
            (directory / 'note-summaries.json').write_text('[]')
        with self.assertRaises(ValueError):
            self.compile(remove_summaries)

    def test_identical_comment_on_a_new_date_requires_its_own_review(self):
        model = copy.deepcopy(self.model)
        issue = next(i for i in model['issues'] if i['id'] == 'greenwich-road-177-183')
        original = next(e for d in issue['days'] for e in d['entries']
                        if e['key'] == '110/2026' and e['type'] == 'note' and e['date'] == '2026-07-14')
        later = dict(original, date='2026-11-14')
        issue['days'].append({'date': '2026-11-14', 'entries': [later]})
        with self.assertRaises(ValueError):
            self.compile(model=model)

    def test_duplicate_summary_bindings_are_rejected(self):
        def duplicate_summary(directory):
            path = directory / 'note-summaries.json'
            records = json.loads(path.read_text())
            records.append(dict(records[0], title='A conflicting title'))
            path.write_text(json.dumps(records))
        with self.assertRaises(ValueError):
            self.compile(duplicate_summary)

    def test_summary_bound_to_different_source_text_is_rejected(self):
        def add_bad_binding(directory):
            path = directory / 'note-summaries.json'
            records = json.loads(path.read_text()) if path.exists() else []
            records.append({'minuteItem': '110/2026', 'date': '2026-07-14',
                            'sourceText': 'An unrelated comment.', 'title': 'Wrong context', 'text': 'Wrong context'})
            path.write_text(json.dumps(records))
        with self.assertRaises(ValueError):
            self.compile(add_bad_binding)


if __name__ == '__main__':
    unittest.main()
