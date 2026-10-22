#!/usr/bin/env python3
"""Read-only discovery proof: reports new/revised Council PDFs; never edits site data."""
import argparse
import datetime as dt
import hashlib
import html
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlencode, urljoin, urlsplit, quote
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
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'input' and a.get('type') == 'hidden' and a.get('name'):
            self.hidden[a['name']] = a.get('value', '')
        if tag == 'select':
            self.select = a.get('name')
        if tag == 'option' and 'selected' in a:
            self.selected[self.select] = a.get('value')
        if tag == 'tr':
            if self.stack:
                self.stack[-1]['nested'] = True
            self.stack.append({'text': [], 'links': [], 'nested': False})
        if tag == 'a' and a.get('href') and self.stack:
            self.stack[-1]['links'].append(a['href'])

    def handle_data(self, text):
        if self.stack:
            self.stack[-1]['text'].append(text)

    def handle_endtag(self, tag):
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


class Fetcher:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.cookies = self.directory / 'cookies'

    def get(self, url, fields=None):
        url = safe_url(url)
        output = self.directory / 'response'
        command = ['curl', '--fail', '--silent', '--show-error', '--location',
                   '--proto', '=https', '--proto-redir', '=https',
                   '--connect-timeout', '20', '--max-time', '90', '--retry', '2',
                   '--retry-delay', '2', '--max-filesize', '52428800',
                   '--cookie', str(self.cookies), '--cookie-jar', str(self.cookies),
                   '--output', str(output), '--write-out', '%{url_effective}', url]
        if fields is not None:
            form = self.directory / 'form'
            form.write_text(urlencode(fields))
            command += ['--data-binary', '@' + str(form)]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        safe_url(result.stdout.strip())
        return output.read_bytes(), result.stdout.strip()


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


def attachments(text, agenda):
    links = set()
    for row in Page(text).rows:
        if re.search(r'Resolution\s+Tracker', ' '.join(row['text']), re.I):
            for link in row['links']:
                if 'gendoclink' in link.lower() or urlsplit(link).path.lower().endswith('.pdf'):
                    links.add(safe_url(urljoin(agenda, link)))
    return sorted(links)


def read_pdf(fetcher, source):
    data, final = fetcher.get(source)
    if not data.startswith(b'%PDF-'):
        match = re.search(r'location\.replace\(\s*[\'"]([^\'"]+)[\'"]', data.decode('utf-8-sig', errors='replace'), re.I)
        if not match:
            raise ValueError('Attachment is HTML/error content, not a PDF or known Council redirect')
        data, final = fetcher.get(safe_url(urljoin(final, match[1])))
    if not data.startswith(b'%PDF-'):
        raise ValueError('Council attachment did not resolve to PDF bytes')
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted or not len(reader.pages):
        raise ValueError('PDF is encrypted or has no pages')
    sample = '\n'.join(p.extract_text() or '' for p in reader.pages[:2])
    if not re.search(r'Resolution\s+Tracker', sample, re.I):
        raise ValueError('PDF text does not identify a Resolution Tracker; manual inspection required')
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
                links = attachments(text, agenda)
                record['attachments'] = links
                known = [d for d in baseline if d['agenda'].lower() == agenda.lower()]
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
    return report


def write_report(report, output):
    pending = [d for d in report['documents'] if d['result'] != 'unchanged']
    report['needs_review'] = bool(pending or report['errors'])
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Council tracker scan', '', f"Checked: {report['checked_at']}", '',
             f"Agendas checked: {len(report['agendas'])}. PDFs checked: {len(report['documents'])}.",
             f"Changes requiring review: {len(pending)}. Errors: {len(report['errors'])}.", '',
             'Site data and the accepted baseline were not modified.', '']
    for document in pending:
        lines += [f"- **{document['result']}** — {document['date']}: [Council PDF]({document['pdf_url']})",
                  f"  SHA-256: `{document['sha256']}`"]
    for error in report['errors']:
        lines.append('- ERROR: ' + json.dumps(error))
    (output / 'summary.md').write_text('\n'.join(lines) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    year = dt.datetime.now(ZoneInfo('Australia/Sydney')).year
    parser.add_argument('--years', nargs='+', type=int, default=[year - 1, year])
    parser.add_argument('--baseline', type=Path, default=ROOT / 'monitor/baseline.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'scan-output')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    baseline = json.loads(args.baseline.read_text())['documents']
    with tempfile.TemporaryDirectory() as temp:
        report = scan(Fetcher(temp), sorted(set(args.years)), baseline, args.output)
    write_report(report, args.output)
    print((args.output / 'summary.md').read_text())
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
