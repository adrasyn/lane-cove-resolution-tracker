import copy
import hashlib
import json
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

    def get(self, url, fields=None, **kwargs):
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
            def get(self, url, **kwargs):
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

    def test_renamed_row_found_by_item_scoped_attachment_reference(self):
        text = ('<a name="PDF2_ReportName_1"></a><p>The Resolution Tracker [AT-2] is updated.</p>'
                '<table><tr><td>AT&#8209;1</td><td>Snapshot</td><td><a href="snapshot.pdf">View</a></td></tr>'
                '<tr><td>AT&#8209;2</td><td>Monthly action list</td><td><a href="' + SOURCE + '">View</a></td></tr></table>'
                '<a name="PDF2_ReportName_2"></a><table><tr><td>AT-2</td><td>Police minutes</td><td><a href="police.pdf">View</a></td></tr></table>')
        self.assertEqual(scanner.attachments(text, AGENDA), [SOURCE])

    def test_variants_and_filename_metadata_find_candidates(self):
        for label in ['Council resolutions progress report', 'Outstanding Council resolutions', 'Council Action Register']:
            self.assertEqual(scanner.attachments(ROW.replace('Resolution</span> Tracker', label + '</span>'), AGENDA), [SOURCE])
        self.assertEqual(scanner.attachments('<tr><td><a title="Resolution tracking register" href="'+SOURCE+'">Download</a></td></tr>', AGENDA), [SOURCE])

    def test_ambiguous_reference_and_unrecognized_pattern_fail_visibly(self):
        ambiguous='<p>Resolution Tracker [AT-2]</p><table><tr><td>AT-2</td><td><a href="a.pdf">View</a><a href="b.pdf">View</a></td></tr></table>'
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            scanner.attachments(ambiguous, AGENDA)
        with self.assertRaisesRegex(ValueError, 'unrecognized|recognized'):
            scanner.attachments('<p>Council resolution monitoring matrix</p><a href="file.pdf">View</a>', AGENDA)

    def test_tracker_reference_in_other_item_does_not_select_unrelated_row(self):
        text='<a name="PDF2_ReportName_1"></a><p>Resolution Tracker [AT-2]</p><a name="PDF2_ReportName_2"></a><tr><td>AT-2</td><td><a href="police.pdf">View</a>Police minutes</td></tr>'
        with self.assertRaisesRegex(ValueError, 'recognized'):
            scanner.attachments(text, AGENDA)

    def test_unrelated_external_pdf_is_ignored_but_tracker_external_pdf_is_error(self):
        text=ROW+'<tr><td>Budget</td><td><a href="https://example.com/budget.pdf">View</a></td></tr><a href="https://example.com/police.pdf">Police minutes</a>'
        self.assertEqual(scanner.attachments(text,AGENDA),[SOURCE])
        with self.assertRaisesRegex(ValueError,'Unexpected source URL'):
            scanner.attachments('<tr><td>Resolution Tracker</td><td><a href="https://example.com/tracker.pdf">View</a></td></tr>',AGENDA)

    def test_ordinary_resolution_prose_does_not_imply_tracker_attachment(self):
        prose='<p>To respond to a Council Resolution regarding the development and implementation of a community strategy.</p><p>The subsequent Resolution to reject all tenders registered an interest.</p>'
        self.assertEqual(scanner.attachments(prose,AGENDA),[])

    def test_explicit_tracker_row_takes_priority_over_incorrect_narrative_number(self):
        # Actual February 2026 narrative says AT-1; its attachment table says AT-2.
        text='<p>Council’s Resolution Tracker is included at AT-1.</p><table><tr><td>AT-1 Snapshot</td><td><a href="snapshot.pdf">View</a></td></tr><tr><td>AT-2 Resolution Tracker</td><td><a href="'+SOURCE+'">View</a></td></tr></table>'
        diagnostics=[]
        self.assertEqual(scanner.attachments(text,AGENDA,[SOURCE],diagnostics=diagnostics),[SOURCE])
        self.assertTrue(diagnostics)

    def test_one_matched_tracker_does_not_hide_another_missing_tracker(self):
        second=SOURCE.replace('80371','80372')
        with self.assertRaisesRegex(ValueError,'missing|Missing|recognized'):
            scanner.attachments(ROW,AGENDA,[SOURCE,second])
        text='<p>Resolution Tracker [AT-2]</p><p>Outstanding Council resolutions [AT-3]</p><tr><td>AT-2 Resolution Tracker</td><td><a href="'+SOURCE+'">View</a></td></tr>'
        with self.assertRaisesRegex(ValueError,'missing|Missing|recognized'):
            scanner.attachments(text,AGENDA)

    def test_historical_general_tracker_database_mention_does_not_require_attachment(self):
        text='<a name="PDF2_ReportName_1"></a><p>The introduction of a new Council Resolution Tracker database.</p><a name="PDF2_ReportName_2"></a>'+ROW
        self.assertEqual(scanner.attachments(text,AGENDA),[SOURCE])

    def test_monthly_snapshot_with_unrecognized_attachment_name_requires_review(self):
        text='<a name="PDF2_ReportName_1"></a><p>Subject: Council Snapshot November 2026</p><tr><td>AT-2 Action outcomes matrix</td><td><a href="'+SOURCE+'">View</a></td></tr>'
        with self.assertRaisesRegex(ValueError,'unrecognized|recognized'):
            scanner.attachments(text,AGENDA)

    def test_actual_word_agenda_excerpt_survives_renamed_row_without_other_pdfs(self):
        text=(Path(__file__).parent/'fixtures/october-attachment-context.html').read_text()
        renamed=text.replace('Resolution Tracker for 22 October 2026 Council meeting','Monthly action list')
        self.assertEqual(scanner.attachments(renamed,AGENDA),[SOURCE])

    def test_tracker_title_in_ordinary_report_is_not_sufficient_pdf_validation(self):
        class Reader:
            is_encrypted=False
            pages=[type('Page', (), {'extract_text': lambda self:'Council Resolution Tracker mentioned in a budget report'})()]
        class Fetch:
            def get(self, url, **kwargs):return b'%PDF-fake',url
        with patch.object(scanner, 'PdfReader', return_value=Reader()):
            with self.assertRaisesRegex(ValueError, 'columns|structure'):
                scanner.read_pdf(Fetch(),SOURCE)

class PersistentCacheTests(unittest.TestCase):
    """Exercise disk persistence and HTTP boundaries; only the external curl call is faked."""
    def fetch(self, work, cache, responses):
        fetcher = scanner.Fetcher(work, cache_directory=cache)
        def transfer(command, **kwargs):
            expected_url, status, body, headers, expected_etag = responses.pop(0)
            self.assertIn(expected_url, command)
            conditions=[command[i+1] for i,x in enumerate(command) if x=='--header' and command[i+1].startswith('If-None-Match:')]
            self.assertEqual(conditions, ['If-None-Match: '+expected_etag] if expected_etag else [])
            Path(command[command.index('--output')+1]).write_bytes(body)
            Path(command[command.index('--dump-header')+1]).write_text('HTTP/1.1 '+str(status)+' Test\r\n'+''.join(k+': '+v+'\r\n' for k,v in headers.items())+'\r\n')
            return subprocess.CompletedProcess(command,0,str(status)+'\n'+expected_url+'\n'+str(len(body)),'')
        return fetcher, patch.object(scanner.subprocess,'run',side_effect=transfer)

    def test_strong_etag_304_reuses_intact_bytes_across_runs_but_pending_revision_stays_pending(self):
        with tempfile.TemporaryDirectory() as t:
            cache=Path(t)/'cache';body=b'%PDF-new revision';etag='"revision-2"'
            f,m=self.fetch(Path(t)/'first',cache,[(SOURCE,200,body,{'ETag':etag},None)])
            with m:self.assertEqual(f.get(SOURCE,cache_pdf=True)[0],body)
            f,m=self.fetch(Path(t)/'second',cache,[(SOURCE,304,b'',{'ETag':etag},etag)])
            with m:data,final=f.get(SOURCE,cache_pdf=True)
            self.assertEqual(data,body);self.assertEqual(f.metrics['cacheHits'],1);self.assertEqual(f.metrics['transferredBytes'],0)
            document={'agenda':AGENDA,'source':SOURCE,'sha256':hashlib.sha256(data).hexdigest()}
            accepted=[dict(document,sha256='old accepted bytes')]
            self.assertEqual(scanner.classify(accepted,document),'revised')
            self.assertEqual(scanner.classify([],document),'new')
            self.assertEqual(accepted[0]['sha256'],'old accepted bytes')

    def test_corrupt_missing_or_mismatched_cache_fetches_without_validator(self):
        for corruption in ['blob','missing','metadata']:
            with self.subTest(corruption=corruption),tempfile.TemporaryDirectory() as t:
                cache=Path(t)/'cache';body=b'%PDF-old'
                f,m=self.fetch(Path(t)/'a',cache,[(SOURCE,200,body,{'ETag':'"old"'},None)])
                with m:f.get(SOURCE,cache_pdf=True)
                blob=next(cache.rglob('*.pdf'))
                if corruption=='blob':blob.write_bytes(b'corrupt')
                elif corruption=='missing':blob.unlink()
                else:
                    metadata=next(cache.rglob('*.json'));value=json.loads(metadata.read_text());value['url']=SOURCE+'different';metadata.write_text(json.dumps(value))
                f,m=self.fetch(Path(t)/'b',cache,[(SOURCE,200,b'%PDF-replacement',{'ETag':'"replacement"'},None)])
                with m:self.assertEqual(f.get(SOURCE,cache_pdf=True)[0],b'%PDF-replacement')
                self.assertEqual(f.metrics['cacheRepairs'],1)

    def test_redirect_does_not_forward_validator_to_new_temporary_resource(self):
        a='https://ecouncil.lanecove.nsw.gov.au/old.pdf';b=a.replace('old','new')
        with tempfile.TemporaryDirectory() as t:
            cache=Path(t)/'cache';f,m=self.fetch(Path(t)/'a',cache,[(a,200,b'%PDF-first',{'ETag':'"tag"'},None)])
            with m:f.get(a,cache_pdf=True)
            f,m=self.fetch(Path(t)/'b',cache,[(a,302,b'',{'Location':b},'"tag"'),(b,200,b'%PDF-different',{'ETag':'"tag"'},None)])
            with m:self.assertEqual(f.get(a,cache_pdf=True),(b'%PDF-different',b))
            self.assertEqual(f.metrics['cacheHits'],0)

    def test_weak_tags_last_modified_and_no_store_do_not_prove_byte_identity(self):
        for headers in [{'ETag':'W/"tag"'}, {'Last-Modified':'Thu, 15 Oct 2026 05:08:37 GMT'}, {'ETag':'"tag"','Cache-Control':'no-store'}]:
            with self.subTest(headers=headers),tempfile.TemporaryDirectory() as t:
                cache=Path(t)/'cache';f,m=self.fetch(Path(t)/'a',cache,[(SOURCE,200,b'%PDF-first',headers,None)])
                with m:f.get(SOURCE,cache_pdf=True)
                f,m=self.fetch(Path(t)/'b',cache,[(SOURCE,200,b'%PDF-second',headers,None)])
                with m:self.assertEqual(f.get(SOURCE,cache_pdf=True)[0],b'%PDF-second')
                self.assertEqual(f.metrics['cacheHits'],0)

    def test_304_without_cache_fails_and_mismatched_304_retries_unconditionally(self):
        with tempfile.TemporaryDirectory() as t:
            cache=Path(t)/'cache';f,m=self.fetch(Path(t)/'a',cache,[(SOURCE,304,b'',{'ETag':'"x"'},None)])
            with m,self.assertRaisesRegex(ValueError,'304'):f.get(SOURCE,cache_pdf=True)
            f,m=self.fetch(Path(t)/'b',cache,[(SOURCE,200,b'%PDF-old',{'ETag':'"old"'},None)])
            with m:f.get(SOURCE,cache_pdf=True)
            f,m=self.fetch(Path(t)/'c',cache,[(SOURCE,304,b'',{'ETag':'W/"old"'},'"old"'),(SOURCE,200,b'%PDF-new bytes',{'ETag':'"new"'},None)])
            with m:self.assertEqual(f.get(SOURCE,cache_pdf=True)[0],b'%PDF-new bytes')
            self.assertEqual(f.metrics['cacheHits'],0)

    def test_permanent_html_redirect_is_reresolved_and_cache_never_crosses_url_churn(self):
        a='https://ecouncil.lanecove.nsw.gov.au/a.pdf';b=a.replace('/a.pdf','/b.pdf')
        with tempfile.TemporaryDirectory() as t:
            cache=Path(t)/'cache'
            for i,url in enumerate([a,b]):
                html=('location.replace("'+url+'")').encode()
                f,m=self.fetch(Path(t)/str(i),cache,[(SOURCE,200,html,{},None),(url,200,b'%PDF-same',{'ETag':'"same"'},None)])
                with m:
                    page,final=f.get(SOURCE,cache_pdf=True);self.assertEqual(page,html)
                    data,final=f.get(url,cache_pdf=True);self.assertEqual(data,b'%PDF-same')
                self.assertEqual(f.metrics['cacheHits'],0)

    def test_changed_strong_etag_body_updates_observed_cache_without_accepting_it(self):
        with tempfile.TemporaryDirectory() as t:
            cache=Path(t)/'cache'
            f,m=self.fetch(Path(t)/'a',cache,[(SOURCE,200,b'%PDF-old',{'ETag':'"old"'},None)])
            with m:f.get(SOURCE,cache_pdf=True)
            f,m=self.fetch(Path(t)/'b',cache,[(SOURCE,200,b'%PDF-new',{'ETag':'"new"'},'"old"')])
            with m:self.assertEqual(f.get(SOURCE,cache_pdf=True)[0],b'%PDF-new')
            f,m=self.fetch(Path(t)/'c',cache,[(SOURCE,304,b'',{'ETag':'"new"'},'"new"')])
            with m:data,_=f.get(SOURCE,cache_pdf=True)
            self.assertEqual(data,b'%PDF-new')
            d={'agenda':AGENDA,'source':SOURCE,'sha256':hashlib.sha256(data).hexdigest()}
            self.assertEqual(scanner.classify([dict(d,sha256=hashlib.sha256(b'%PDF-old').hexdigest())],d),'revised')

    def test_untracked_cache_cannot_be_written_under_published_dist(self):
        with tempfile.TemporaryDirectory() as t,self.assertRaisesRegex(ValueError,'published dist'):
            scanner.Fetcher(t,cache_directory=scanner.ROOT/'dist'/'cache')

    def test_vary_cookie_does_not_reuse_session_specific_pdf(self):
        with tempfile.TemporaryDirectory() as t:
            cache=Path(t)/'cache'
            for i in range(2):
                f,m=self.fetch(Path(t)/str(i),cache,[(SOURCE,200,b'%PDF-session',{'ETag':'"tag"','Vary':'Cookie'},None)])
                with m:self.assertEqual(f.get(SOURCE,cache_pdf=True)[0],b'%PDF-session')
                self.assertEqual(f.metrics['cacheHits'],0)

    def test_cached_pending_revision_is_restaged_in_each_fresh_scan_output(self):
        class Reader:
            is_encrypted=False
            pages=[type('Page', (), {'extract_text': lambda self:'Resolution Tracker Minute No Resolution Council Meeting Target Date Status Comments'})()]
        with tempfile.TemporaryDirectory() as t:
            cache=Path(t)/'cache';accepted=[{'date':'22102026','agenda':AGENDA,'source':SOURCE,'sha256':'old accepted hash'}]
            for index,status in enumerate([200,304]):
                headers={'ETag':'"pending"'};body=b'%PDF-pending' if status==200 else b''
                responses=[(scanner.BASE,200,INDEX.encode(),{},None),(scanner.BASE,200,INDEX.encode(),{},None),(AGENDA,200,('<html>Council<table>'+ROW+'</table></html>').encode(),{},None),(SOURCE,status,body,headers,'"pending"' if status==304 else None)]
                f,m=self.fetch(Path(t)/('request'+str(index)),cache,responses);out=Path(t)/('output'+str(index));out.mkdir()
                with m,patch.object(scanner,'PdfReader',return_value=Reader()):
                    report=scanner.scan(f,[2026],accepted,out);scanner.write_report(report,out)
                self.assertFalse(report['errors']);self.assertTrue(report['needs_review'])
                self.assertEqual(report['documents'][0]['result'],'revised')
                self.assertEqual(next(out.glob('*.pdf')).read_bytes(),b'%PDF-pending')
                self.assertEqual(report['http']['cacheHits'],index)
            self.assertEqual(accepted[0]['sha256'],'old accepted hash')


if __name__ == '__main__':
    unittest.main()
