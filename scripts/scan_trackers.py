#!/usr/bin/env python3
"""Read-only discovery proof: reports new/revised Council PDFs; never edits site data."""
import argparse
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlencode, urljoin, urlsplit, quote, unquote, urldefrag
from zoneinfo import ZoneInfo

from pypdf import PdfReader

BASE = 'https://lanecove.infocouncil.biz/'
ROOT = Path(__file__).resolve().parents[1]
AGENDA = re.compile(r'Open/(\d{4})/\d{2}/CNL_(\d{8})_AGN[A-Z_]*_WEB\.htm', re.I)
HOSTS = {'lanecove.infocouncil.biz', 'ecouncil.lanecove.nsw.gov.au'}


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.hidden, self.selected, self.rows, self.stack = {}, {}, [], []
        self.select = None
        self.section, self.blocks, self.paragraph, self.loose = 'document', {}, None, []
        self.anchor = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'a' and re.fullmatch(r'PDF2_ReportName_\d+', a.get('name', '')):
            self.section = a['name']
        if tag in ('p', 'h1', 'h2', 'h3', 'h4') and not self.stack:
            self.paragraph = []
        if tag == 'input' and a.get('type') == 'hidden' and a.get('name'):
            self.hidden[a['name']] = a.get('value', '')
        if tag == 'select':
            self.select = a.get('name')
        if tag == 'option' and 'selected' in a:
            self.selected[self.select] = a.get('value')
        if tag == 'tr':
            if self.stack:
                self.stack[-1]['nested'] = True
            self.stack.append({'text': [], 'links': [], 'nested': False, 'section': self.section})
        if tag == 'a' and a.get('href'):
            metadata = ' '.join([a.get('title', ''), a.get('aria-label', ''), unquote(a['href'])])
            if self.stack:
                self.stack[-1]['links'].append(a['href'])
                self.stack[-1]['text'].append(metadata)
            else:
                self.anchor = {'text': [metadata], 'links': [a['href']], 'section': self.section}
                self.loose.append(self.anchor)

    def handle_data(self, text):
        if self.paragraph is not None and not self.stack:
            self.paragraph.append(text)
        if self.anchor is not None:
            self.anchor['text'].append(text)
        if self.stack:
            self.stack[-1]['text'].append(text)

    def handle_endtag(self, tag):
        if tag == 'a':
            self.anchor = None
        if tag in ('p', 'h1', 'h2', 'h3', 'h4') and self.paragraph is not None:
            self.blocks.setdefault(self.section, []).append(' '.join(self.paragraph))
            self.paragraph = None
        if tag == 'select':
            self.select = None
        if tag == 'tr' and self.stack:
            row = self.stack.pop()
            if not row['nested']:
                self.rows.append(row)


def safe_url(url):
    url = quote(html.unescape(url), safe=':/%?=&+#')
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in HOSTS or parts.username:
        raise ValueError(f'Unexpected source URL: {url}')
    return url


class FetchError(RuntimeError):
    """Safe actionable failure details without dumping response headers or credentials."""
    def __init__(self, url, status, exit_code, upstream_timeout=False, deferred=False):
        self.url, self.status, self.exit_code = url, status, exit_code
        self.upstream_timeout, self.deferred = upstream_timeout, deferred
        detail = 'proxy upstream connection timed out before origin response headers' if upstream_timeout else 'HTTPS request failed'
        if deferred: detail = 'not checked: host deferred after ' + detail
        super().__init__(f'{detail}; HTTP {status}; curl exit {exit_code}; {url}')


def strong_etag(value):
    return isinstance(value, str) and re.fullmatch(r'"[\x21\x23-\x7e\x80-\xff]*"', value) is not None


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(data)
        name = temporary.name
    try:
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


class Fetcher:
    def __init__(self, directory, cache_directory=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.cookies = self.directory / 'cookies'
        self.cache = Path(cache_directory) if cache_directory is not None else None
        if self.cache and self.cache.resolve().is_relative_to((ROOT / 'dist').resolve()):
            raise ValueError('HTTP cache must be outside the published dist directory')
        self.unreachable = {}
        self.metrics = dict(requests=0, conditionalRequests=0, transferredBytes=0,
                            pdfDownloads=0, pdfTransferredBytes=0, cacheHits=0,
                            cachedBytesReused=0, cacheRepairs=0, fullPdfWithoutStrongValidator=0)
        self.diagnostics = []

    def cache_path(self, url):
        return self.cache / 'resources' / (hashlib.sha256(url.encode()).hexdigest()+'.json')

    def cached(self, url):
        if self.cache is None or not self.cache_path(url).exists(): return None
        try:
            entry = json.loads(self.cache_path(url).read_text())
            if entry['url'] != url or not strong_etag(entry['etag']) or not re.fullmatch('[0-9a-f]{64}', entry['sha256']):
                raise ValueError('cache binding/validator mismatch')
            data = (self.cache / 'blobs' / (entry['sha256']+'.pdf')).read_bytes()
            if len(data) != entry['size'] or hashlib.sha256(data).hexdigest() != entry['sha256'] or not data.startswith(b'%PDF-'):
                raise ValueError('cached byte integrity mismatch')
            return entry, data
        except (OSError, ValueError, KeyError, TypeError):
            self.metrics['cacheRepairs'] += 1
            self.diagnostics.append({'url': url, 'event': 'invalid cache; unconditional fetch required'})
            self.cache_path(url).unlink(missing_ok=True)
            return None

    @staticmethod
    def reusable(headers):
        # Only one fixed representation is requested. Never retain cookies/raw headers.
        vary = {x.strip().lower() for x in headers.get('vary', '').split(',') if x.strip()}
        return (strong_etag(headers.get('etag')) and 'no-store' not in headers.get('cache-control', '').lower()
                and vary <= {'accept-encoding'} and headers.get('content-encoding', 'identity').lower() == 'identity')

    def remember(self, url, data, headers):
        if self.cache is None: return
        if not data.startswith(b'%PDF-') or not self.reusable(headers):
            self.cache_path(url).unlink(missing_ok=True)
            return
        digest = hashlib.sha256(data).hexdigest()
        atomic_write(self.cache / 'blobs' / (digest+'.pdf'), data)
        entry = {'url': url, 'etag': headers['etag'], 'sha256': digest, 'size': len(data)}
        atomic_write(self.cache_path(url), (json.dumps(entry)+'\n').encode())

    def request(self, url, fields=None, etag=None):
        host = urlsplit(url).hostname
        if host in self.unreachable:
            failure = self.unreachable[host]
            raise FetchError(url, failure.status, failure.exit_code, True, deferred=True)
        output, header_file = self.directory / 'response', self.directory / 'headers'
        output.unlink(missing_ok=True)
        header_file.unlink(missing_ok=True)
        # Redirects are followed explicitly: a validator must never reach another resource.
        command = ['curl', '--fail-with-body', '--silent', '--show-error',
                   '--proto', '=https', '--connect-timeout', '20', '--max-time', '90',
                   '--retry', '2', '--retry-delay', '2', '--max-filesize', '52428800',
                   '--cookie', str(self.cookies), '--cookie-jar', str(self.cookies),
                   '--header', 'Accept-Encoding: identity', '--header', 'Cache-Control: no-cache',
                   '--dump-header', str(header_file), '--output', str(output),
                   '--write-out', '%{http_code}\n%{url_effective}\n%{size_download}', url]
        if etag:
            command += ['--header', 'If-None-Match: '+etag]
            self.metrics['conditionalRequests'] += 1
        if fields is not None:
            form = self.directory / 'form'
            form.write_text(urlencode(fields))
            command += ['--data-binary', '@' + str(form)]
        self.metrics['requests'] += 1
        result = subprocess.run(command, capture_output=True, text=True)
        metadata = result.stdout.strip().splitlines()
        status = metadata[0] if metadata else 'unknown'
        body = output.read_bytes() if output.exists() else b''
        # curl-reported response body bytes; excludes headers/TLS and may omit retry overhead.
        transferred = int(float(metadata[2])) if len(metadata)>2 and re.fullmatch(r'\d+(?:\.\d+)?', metadata[2]) else len(body)
        self.metrics['transferredBytes'] += transferred
        if body.startswith(b'%PDF-'):
            if not result.returncode and status == '200': self.metrics['pdfDownloads'] += 1
            self.metrics['pdfTransferredBytes'] += transferred
        if result.returncode:
            upstream = status == '503' and b'upstream connect error' in body and b'connection timeout' in body
            failure = FetchError(url, status if status.isdigit() else 'unknown', result.returncode, upstream)
            if upstream: self.unreachable[host] = failure
            raise failure
        if len(metadata)<2 or not status.isdigit(): raise ValueError('Malformed HTTPS fetch metadata')
        if safe_url(metadata[1]) != url:
            raise ValueError('Unexpected implicit redirect; resource validator binding is not safe')
        headers = {}
        if header_file.exists():
            raw = header_file.read_text(encoding='iso-8859-1').replace('\r\n', '\n')
            block = re.split(r'(?m)^HTTP/\S+ [^\n]*\n', raw)[-1]
            for line in block.splitlines():
                name, sep, value = line.partition(':')
                if sep:
                    key = name.lower().strip()
                    headers[key] = headers[key]+', '+value.strip() if key in headers else value.strip()
        return int(status), body, headers

    def get(self, url, fields=None, cache_pdf=False):
        url = safe_url(urldefrag(url)[0])
        for redirect in range(9):
            stored = self.cached(url) if cache_pdf and fields is None else None
            etag = stored[0]['etag'] if stored else None
            status, data, headers = self.request(url, fields, etag)
            if status in (301, 302, 303, 307, 308):
                if 'location' not in headers: raise ValueError('Redirect has no Location')
                url = safe_url(urldefrag(urljoin(url, headers['location']))[0])
                if status in (301, 302, 303): fields = None
                continue
            if status == 304:
                # If-None-Match uses weak comparison. Demand the same STRONG tag on the
                # response before treating our exact SHA-256 bytes as current.
                valid = stored and headers.get('etag') == etag and self.reusable(headers)
                checked = self.cached(url) if valid else None
                if checked and checked[0] == stored[0]:
                    self.metrics['cacheHits'] += 1
                    self.metrics['cachedBytesReused'] += len(checked[1])
                    return checked[1], url
                if not stored: raise ValueError('Unexpected 304 without intact conditional cache')
                self.diagnostics.append({'url': url, 'event': '304 cannot verify exact bytes; unconditional retry'})
                status, data, headers = self.request(url, fields)
            if status != 200: raise ValueError(f'Unexpected HTTP {status}; attachment was not verified')
            if cache_pdf and fields is None:
                if data.startswith(b'%PDF-') and not self.reusable(headers):
                    self.metrics['fullPdfWithoutStrongValidator'] += 1
                self.remember(url, data, headers)
            return data, url
        raise ValueError('Too many Council redirects')


def agenda_paths(text, year):
    return sorted({m.group(0) for m in AGENDA.finditer(text) if int(m[1]) == year})


def discover(fetcher, year):
    data, _ = fetcher.get(BASE)
    page = Page(data.decode('utf-8-sig'))
    if not page.hidden.get('__VIEWSTATE'):
        raise ValueError('Council index no longer has the expected search form')
    fields = page.hidden | {
        'ctl00$MainContent$ddlCommittee': '14',
        'ctl00$MainContent$ddlYear': str(year),
        'ctl00$MainContent$ddlMonth': '0',
        'ctl00$MainContent$btnView': 'View',
    }
    data, _ = fetcher.get(BASE, fields)
    text = data.decode('utf-8-sig')
    page = Page(text)
    if page.selected.get('ctl00$MainContent$ddlYear') != str(year):
        raise ValueError(f'Council index did not select requested year {year}')
    paths = agenda_paths(text, year)
    if not paths:
        raise ValueError(f'No Council agendas found for {year}; investigate rather than report no changes')
    return paths


# Names vary; require Council/resolution context, not a generic "action" attachment.
TRACKER = re.compile(r'(?:resolutions?\s+(?:tracker|tracking(?:\s+register)?|register|progress|action)|'
                     r'outstanding\s+(?:council\s+)?resolutions?|council\s+action\s+register|'
                     r'(?:implementation|progress|status)\s+(?:of|on)\s+(?:council\s+)?resolutions?)', re.I)
SUSPECT = re.compile(r'\b(?:(?:council\s+)?resolutions?\s+(?:monitor(?:ing)?|matrix|tracking)|council\s+action\s+monitor(?:ing)?)\b', re.I)
AT = re.compile(r'\bAT\s*-\s*(\d+)\b', re.I)


def normalized(text):
    return re.sub(r'\s+', ' ', html.unescape(text).translate(str.maketrans('‐‑‒–—_', '------'))).strip()


def attachments(text, agenda, known_sources=(), diagnostics=None):
    page = Page(text)
    references, expected, mentioned = {}, set(), False
    for section, paragraphs in page.blocks.items():
        for paragraph in paragraphs:
            paragraph = normalized(paragraph)
            match = TRACKER.search(paragraph)
            if match:
                mentioned = True
                nearby = paragraph[max(0, match.start()-45):match.end()+120]
                numbers = set(AT.findall(nearby))
                if len(numbers) > 1:
                    raise ValueError('Ambiguous tracker attachment references in agenda item')
                if numbers:
                    expected.add(section)
                    references.setdefault(section, set()).update(numbers)
            elif SUSPECT.search(paragraph) or re.match(r'^subject:\s*council snapshot\b', paragraph, re.I):
                expected.add(section)
    diagnostics = diagnostics if diagnostics is not None else []
    # Explicit attachment identity outranks an inconsistent narrative AT number.
    # February 2026's source narrative says AT-1, but the tracker row is AT-2.
    explicit, known_sections = {}, set()
    for row in page.rows + page.loose:
        label = normalized(' '.join(row['text']))
        row_known = set(urljoin(agenda, x) for x in row['links']) & set(known_sources)
        if row_known: known_sections.add(row['section'])
        if TRACKER.search(label) or row_known:
            explicit.setdefault(row['section'], set()).update(AT.findall(label))
    for section, numbers in list(references.items()):
        if (section in known_sections and len(numbers) == 1 and len(explicit.get(section, set())) == 1
                and numbers.isdisjoint(explicit[section])):
            # A reviewed existing source provides the extra identity evidence needed
            # to resolve February's erroneous AT-1 narrative without fetching Snapshot.
            diagnostics.append({'agenda': agenda, 'event': 'Narrative AT reference differs from known explicitly identified tracker attachment; explicit row used', 'section': section})
            references[section] = set()
    links, matched, ref_links = set(), set(), {}
    for row in page.rows + page.loose:
        label = normalized(' '.join(row['text']))
        section = row['section']
        candidates = {urljoin(agenda, link) for link in row['links']
                      if 'gendoclink' in link.lower() or urlsplit(link).path.lower().endswith('.pdf')}
        nums = set(AT.findall(label)) & references.get(section, set())
        named = bool(TRACKER.search(label))
        known = bool(candidates & set(known_sources))
        if not (named or known or nums):
            if SUSPECT.search(label): expected.add(section)
            continue
        expected.add(section)
        candidates = {safe_url(link) for link in candidates}
        if len(candidates) > 1:
            raise ValueError('Ambiguous tracker attachment: multiple document links in one candidate')
        if candidates:
            matched.add(section)
            links.update(candidates)
            for number in nums:
                ref_links.setdefault((section, number), set()).update(candidates)
    if any(len(values) > 1 for values in ref_links.values()):
        raise ValueError('Ambiguous tracker attachment: item reference maps to different documents')
    missing_refs = [(section, number) for section, numbers in references.items() for number in numbers
                    if not ref_links.get((section, number))]
    if missing_refs or set(known_sources) - links:
        raise ValueError('Missing expected tracker: no recognized attachment for one or more required documents/references')
    if expected - matched or (mentioned and not links):
        raise ValueError('Expected/mentioned or unrecognized tracker pattern has no recognized attachment link')
    return sorted(links)


def read_pdf(fetcher, source):
    data, final = fetcher.get(source, cache_pdf=True)
    if not data.startswith(b'%PDF-'):
        match = re.search(r'location\.replace\(\s*[\'"]([^\'"]+)[\'"]', data.decode('utf-8-sig', errors='replace'), re.I)
        if not match:
            raise ValueError('Attachment is HTML/error content, not a PDF or known Council redirect')
        data, final = fetcher.get(safe_url(urljoin(final, match[1])), cache_pdf=True)
    if not data.startswith(b'%PDF-'):
        raise ValueError('Council attachment did not resolve to PDF bytes')
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted or not len(reader.pages):
        raise ValueError('PDF is encrypted or has no pages')
    sample = '\n'.join(p.extract_text() or '' for p in reader.pages[:2])
    sample = normalized(sample)
    if not TRACKER.search(sample):
        raise ValueError('PDF text does not identify a Resolution Tracker; manual inspection required')
    if not all(re.search(pattern, sample, re.I) for pattern in
               [r'minute\s+(?:item\s+)?(?:no|number)', r'resolution', r'council\s+meeting', r'target\s+date', r'status', r'(?:officer\s+)?comments?']):
        raise ValueError('Tracker PDF table structure/columns not recognized; manual inspection required')
    return data, final, len(reader.pages)


def classify(baseline, document):
    exact = [d for d in baseline if d['agenda'].lower() == document['agenda'].lower()
             and d['source'].lower() == document['source'].lower()]
    if exact:
        return 'unchanged' if any(d['sha256'] == document['sha256'] for d in exact) else 'revised'
    if any(d['sha256'] == document['sha256'] for d in baseline):
        return 'reused_pdf'
    return 'new'


def scan(fetcher, years, baseline, output):
    report = {'checked_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'years': years,
              'agendas': [], 'documents': [], 'errors': []}
    seen = set()
    for year in years:
        try:
            paths = discover(fetcher, year)
        except Exception as error:
            report['errors'].append({'year': year, 'error': str(error)})
            continue
        for path in paths:
            agenda = urljoin(BASE, re.sub(r'_WEB\.htm$', '.HTM', path, flags=re.I))
            seen.add(agenda.lower())
            record = {'url': agenda}
            report['agendas'].append(record)
            try:
                raw, _ = fetcher.get(agenda)
                text = raw.decode('utf-8-sig')
                if '<html' not in text.lower() or 'council' not in text.lower():
                    raise ValueError('Unexpected agenda response')
                known = [d for d in baseline if d['agenda'].lower() == agenda.lower()]
                record['discoveryDiagnostics'] = []
                links = attachments(text, agenda, [d['source'] for d in known], record['discoveryDiagnostics'])
                record['attachments'] = links
                if not links and (known or re.search(r'Resolution\s+Tracker', html.unescape(re.sub('<[^>]+>', ' ', text)), re.I)):
                    raise ValueError('Expected/mentioned tracker has no recognized attachment link')
                for source in links:
                    data, url, pages = read_pdf(fetcher, source)
                    document = {'date': re.search(r'CNL_(\d{8})', path)[1], 'agenda': agenda,
                                'source': source, 'pdf_url': url, 'pages': pages,
                                'sha256': hashlib.sha256(data).hexdigest()}
                    document['result'] = classify(baseline, document)
                    if document['result'] != 'unchanged':
                        (output / (document['sha256'] + '.pdf')).write_bytes(data)
                    report['documents'].append(document)
            except Exception as error:
                report['errors'].append({'agenda': agenda, 'error': str(error)})
    for document in baseline:
        if int(document['date'][-4:]) in years and document['agenda'].lower() not in seen:
            report['errors'].append({'agenda': document['agenda'], 'error': 'Known agenda absent from index'})
    report['http'] = dict(getattr(fetcher, 'metrics', {}))
    report['httpDiagnostics'] = list(getattr(fetcher, 'diagnostics', []))
    return report


def write_report(report, output):
    pending = [d for d in report['documents'] if d['result'] != 'unchanged']
    report['needs_review'] = bool(pending or report['errors'])
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Council tracker scan', '', f"Checked: {report['checked_at']}", '',
             f"Agendas checked: {len(report['agendas'])}. PDFs checked: {len(report['documents'])}.",
             f"Changes requiring review: {len(pending)}. Errors: {len(report['errors'])}.", '',
             'Site data and the accepted baseline were not modified.', '']
    metrics = report.get('http', {})
    if metrics:
        lines += [f"HTTP: {metrics['requests']} requests; {metrics['pdfDownloads']} full PDF downloads; {metrics['cacheHits']} validated cache hits.",
                  f"Curl-reported payload (excludes headers/TLS; retry overhead may be omitted): {metrics['transferredBytes']} bytes ({metrics['pdfTransferredBytes']} PDF bytes); cached PDF bytes reused: {metrics['cachedBytesReused']}.", '']
    for document in pending:
        lines += [f"- **{document['result']}** — {document['date']}: [Council PDF]({document['pdf_url']})",
                  f"  SHA-256: `{document['sha256']}`"]
    for agenda in report['agendas']:
        for diagnostic in agenda.get('discoveryDiagnostics', []):
            lines.append('- DISCOVERY: ' + json.dumps(diagnostic))
    for error in report['errors']:
        lines.append('- ERROR: ' + json.dumps(error))
    (output / 'summary.md').write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    year = dt.datetime.now(ZoneInfo('Australia/Sydney')).year
    parser.add_argument('--years', nargs='+', type=int, default=[year - 1, year])
    parser.add_argument('--baseline', type=Path, default=ROOT / 'monitor/baseline.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'scan-output')
    parser.add_argument('--cache-dir', type=Path, default=ROOT / '.tracker-http-cache', help='Persistent observed HTTP bytes, separate from the accepted baseline')
    parser.add_argument('--no-cache', action='store_true', help='Fetch every resource without conditional caching')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    baseline = json.loads(args.baseline.read_text())['documents']
    with tempfile.TemporaryDirectory() as temp:
        report = scan(Fetcher(temp, cache_directory=None if args.no_cache else args.cache_dir), sorted(set(args.years)), baseline, args.output)
    write_report(report, args.output)
    print((args.output / 'summary.md').read_text())
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
