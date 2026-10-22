"""Stage seven-column PDF extraction for review; never change accepted site data.
Ported from the research extractor. PDF cell boundaries keep comments separate
from resolutions; warnings require visual source review, not automatic acceptance.
"""
import argparse,datetime,json,pathlib,re,hashlib
import pdfplumber

def parse_document(source, path):
 edition=source['date'];path=pathlib.Path(path);records=[];warnings=[];current=None;canonical=None
 with pdfplumber.open(path) as pdf:
  for page_no,page in enumerate(pdf.pages,1):
   tables=page.find_tables()
   if not tables:
    warnings.append({'page':page_no,'warning':'No table found'});continue
   page_words=page.extract_words(extra_attrs=['fontname'])
   table=max(tables,key=lambda t:(t.bbox[2]-t.bbox[0])*(t.bbox[3]-t.bbox[1]))
   extracted=table.extract()
   if canonical is None:
    for row,values in zip(table.rows,extracted):
     actual=[(cell,value) for cell,value in zip(row.cells,values) if cell is not None]
     if len(actual)==7 and re.fullmatch(r'[\d, &\s]+',(actual[0][1] or '').strip()) and re.search(r'\d{1,2}/\d{1,2}/\d{4}',re.sub(r'\s+','',actual[3][1] or '')):
      canonical=[actual[0][0][0]]+[cell[2] for cell,value in actual];break
   if canonical is None:raise ValueError('No canonical columns '+edition)
   for row,values in zip(table.rows,extracted):
    cols=['']*7;bold_comment_lines=[]
    for cell,value in zip(row.cells,values):
     if cell is None or not value:continue
     x=(cell[0]+cell[2])/2
     idx=next((i for i in range(7) if canonical[i]-2<=x<=canonical[i+1]+2),None)
     if idx is not None:
      cols[idx]+=('\n' if cols[idx] else '')+value.strip()
      if idx==6:
       lines={}
       for word in page_words:
        if cell[0]<=word['x0'] and word['x1']<=cell[2]+1 and cell[1]<=word['top'] and word['bottom']<=cell[3]+1 and 'bold' in word['fontname'].lower():
         line=next((y for y in lines if abs(y-word['top'])<2),word['top']);lines.setdefault(line,[]).append(word)
       bold_comment_lines+=[' '.join(w['text'] for w in sorted(ws,key=lambda w:w['x0'])) for y,ws in sorted(lines.items())]
    if not any(cols):continue
    if ('Minute' in cols[0] or cols[0]=='No' or cols[1]=='Report Title' or cols[2]=='Item Resolution' or (cols[3] in ['Council','Meeting','Council\nMeeting','Council Meeting'] and not re.fullmatch(r'\d+',cols[0]))):continue
    number=cols[0].strip().lstrip('\\')
    if not number and cols[1] and cols[2] and re.search(r'\d{1,2}/\d{1,2}/\d{4}',re.sub(r'\s+','',cols[3])):
     match=re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})',re.sub(r'\s+','',cols[3]));d,m,y=match.groups();meeting=f'{y}-{m.zfill(2)}-{d.zfill(2)}'
     key='unnumbered-'+meeting+'-'+hashlib.sha256(' '.join(cols[1].split()).encode()).hexdigest()[:6]
     current={'key':key,'minute':None,'minutes':[],'meeting':meeting,'title':cols[1],'resolution':cols[2],'target':cols[4],'status':cols[5],'comments':cols[6],'pages':[page_no],'edition':edition,'commentHeadings':bold_comment_lines}
     records.append(current);warnings.append({'warning':'Unnumbered source decision','key':key,'page':page_no,'title':cols[1]});continue
    if re.fullmatch(r'[\d, &\s]+',number) and re.search(r'\d',number):
     match=re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})',re.sub(r'\s+','',cols[3]))
     if not match:
      warnings.append({'page':page_no,'warning':'Numeric row without meeting date','columns':cols});current=None;continue
     d,m,y=match.groups();meeting=f'{y}-{m.zfill(2)}-{d.zfill(2)}'
     numbers=list(dict.fromkeys(int(n) for n in re.findall(r'\d+',number)))
     current={'key':f'{"+".join(map(str,numbers))}/{y}','minute':numbers[0],'minutes':numbers,'meeting':meeting,'title':cols[1],'resolution':cols[2],'target':cols[4],'status':cols[5],'comments':cols[6],'pages':[page_no],'edition':edition,'commentHeadings':bold_comment_lines}
     records.append(current)
    elif current:
     current['commentHeadings']+=bold_comment_lines
     for i,key in [(1,'title'),(2,'resolution'),(6,'comments')]:
      if cols[i]:current[key]+=('\n' if current[key] else '')+cols[i]
     for i,key in [(3,'meeting'),(4,'target'),(5,'status')]:
      if cols[i] and key!='meeting' and not current[key]:current[key]=cols[i]
     if any(cols[i] for i in [1,2,6]) and page_no not in current['pages']:current['pages'].append(page_no)
    elif any(cols):warnings.append({'page':page_no,'warning':'Orphan continuation','columns':cols})
 keys=[r['key'] for r in records]
 if len(keys)!=len(set(keys)):warnings.append({'warning':'Duplicate keys','keys':[k for k in set(keys) if keys.count(k)>1]})
 for record in records:
  record['title']=' '.join(record['title'].split())
  record['status']=' '.join(record['status'].split())
  if record['status'].lower() not in ['completed','in progress','outstanding','inprogress']:
   warnings.append({'warning':'Unexpected status','key':record['key'],'status':record['status']})
 if not records:raise ValueError('No tracker records extracted')
 return {'source':source,'records':records,'warnings':warnings}

def stage_document(document, directory):
 """Verify scan metadata and bytes before staging a proposed row file."""
 datetime.datetime.strptime(document['date'],'%d%m%Y')
 digest=document['sha256']
 if not re.fullmatch(r'[a-f0-9]{64}',digest):raise ValueError('Invalid PDF SHA-256')
 path=directory/(digest+'.pdf')
 if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('PDF hash differs from scan report')
 source={k:document[k] for k in ['date','agenda','source','pdf_url','pages']}
 with pdfplumber.open(path) as pdf:
  if len(pdf.pages)!=source['pages']:raise ValueError('PDF page count differs from scan report')
 return parse_document(source,path)

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--report',type=pathlib.Path,default=pathlib.Path('scan-output/report.json'))
 parser.add_argument('--output',type=pathlib.Path,default=pathlib.Path('scan-output/proposed'))
 args=parser.parse_args()
 report=json.loads(args.report.read_text())
 if report['errors']:raise ValueError('Resolve scan errors before extracting proposed changes')
 args.output.mkdir(parents=True,exist_ok=True)
 seen=set();warnings=0
 for document in report['documents']:
  if document['result'] not in ['new','revised']:continue
  identity=(document['date'],document['sha256'])
  if identity in seen:continue
  seen.add(identity)
  result=stage_document(document,args.report.parent)
  # Retain different revisions of an edition; never overwrite one with another.
  target=args.output/(document['date']+'-'+document['sha256']+'-rows.json')
  target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
  warnings+=len(result['warnings'])
  print(f'{target}: {len(result["records"])} rows; {len(result["warnings"])} warnings')
 print('Proposals only: accepted catalogue, baseline and website were not changed.')
 return 2 if warnings else 0

if __name__=='__main__':raise SystemExit(main())
