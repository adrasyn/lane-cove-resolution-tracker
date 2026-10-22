"""Reproducible catalogue: 2026 membership, complete available row history and dated notes."""
import collections,datetime as dt,json,pathlib,re,hashlib
ROOT=pathlib.Path(__file__).resolve().parent
SITE=ROOT.parent/'dist'
flat=lambda s:' '.join(s.split())
fingerprint=lambda s:re.sub(r'[^a-z0-9]','',s.lower())
iso=lambda ed:ed[4:]+'-'+ed[2:4]+'-'+ed[:2]
load=lambda p:json.loads(p.read_text())
CATEGORY_SYMBOLS={'Council & governance':'council','Community & services':'community'}
# Related decisions are grouped explicitly; nothing is joined solely by a title match.
GROUPS=[
 ('market-square',['224/2025','290/2025','45/2026','130/2026']),
 ('karilla-avenue',['254/2024','53/2026']),
 ('food-scraps',['60/2025','185/2025','71/2026']),
 ('community-e-shuttle',['158/2024','81/2026']),
 ('st-leonards-return-and-earn',['257/2024','192/2026']),
 ('pacific-highway-2-4',['201/2025','72/2026']),
 ('civic-centre-piano',['239/2025','23/2026']),
 ('st-leonards-road-names',['234/2025','29/2026']),
 ('aquatic-centre-electrification',['223/2025','137/2026']),
 ('local-environment-plan-review',['158/2025','270/2025']),
 ('children-and-families-strategy',['267/2025','103/2026']),
 ('galuwa-food-and-events',['259/2025','97/2026']),
 ('pottery-green-drainage',['258/2025','303/2025']),
 ('rotary-peace-poles',['299/2025','135/2026']),
 ('dog-facilities',['283/2025','30/2026']),
 ('code-of-meeting-practice',['293/2025','117/2026']),
 ('austin-crescent-3',['28/2026','224/2026']),
 ('austin-crescent-1',['77/2026','223/2026']),
 ('ev-charging-policy',['25/2026','79/2026']),
 ('sustainability-action-plan',['24/2026','80/2026']),
 ('asset-and-reserves-policies',['74/2026','84/2026','134/2026']),
 ('budget-2026-27',['73/2026','132/2026']),
 ('greenwich-road-177-183',['54/2026','95/2026','110/2026']),
 ('habitat-logs-and-biodiversity',['48/2026','70/2026','141/2026']),
 ('third-party-revenue',['44/2026','166/2026']),
 ('affordable-housing-policy',['111/2026','190/2026']),
 ('fire-safety-policy',['113/2026','191/2026']),
 ('civic-art-collection-policy',['107/2026','188/2026']),
 ('planning-agreements-policy',['106/2026','185/2026']),
 ('st-leonards-south-areas-22-23',['96/2026','156/2026']),
 ('community-engagement',['148/2025','133/2026','181/2026']),
 ('burns-bay-reserve-masterplan',['165/2026','228/2026','229/2026']),
 ('data-breach-policy',['157/2026','216/2026']),
 ('vacant-development-sites',['126/2026','225/2026']),
 ('safe-phone-initiative',['8/2026','222/2026']),
 ('watercraft-storage-policy',['82/2026','164/2026']),
 ('anglo-road-closure',['155/2025','230/2026']),
 ('st-leonards-contributions',['159/2025','27/2026']),
 ('climate-emergency-plan',['251/2024','189/2026']),
 ('pride-community-grants',['196/2025','298/2025','58/2026']),
 ('domestic-violence-prevention',['287/2025','57/2026']),
 ('e-bike-safety',['129/2026','175/2026']),
 ('canberra-avenue',['145/2025','289/2025']),
 ('lgnsw-conference-2026',['163/2026','217/2026']),
 ('advisory-committee-appointments',['201/2026','202/2026','203/2026']),
 ('mayor-and-deputy-mayor-election',['198/2026','199/2026','200/2026'])
]

def normal_status(s):
 s=flat(s).lower().rstrip('.')
 if s in ['complete','completed','competed','comleted']:return 'completed'
 return s.replace(' ','')
def normal_target(s):
 nums=re.findall(r'\d+',s)
 return tuple(map(int,nums)) if len(nums)==3 else fingerprint(s)

def records():
 docs={}
 for p in (ROOT/'structured').glob('*-rows.json'):
  doc=load(p)
  if doc['source'].get('duplicate_of'):continue
  docs[doc['source']['date']]=doc
 aliases=collections.defaultdict(set)
 for doc in docs.values():
  for row in doc['records']:
   if not row['key'].startswith('unnumbered-'):aliases[(row['meeting'],fingerprint(row['title']))].add(row['key'])
 for doc in docs.values():
  for row in doc['records']:
   if row['key'].startswith('unnumbered-'):
    candidates=aliases[(row['meeting'],fingerprint(row['title']))]
    if len(candidates)==1:row['sourceIdentifier']='Not numbered in this edition';row['key']=next(iter(candidates))
 bykey=collections.defaultdict(list)
 for ed in sorted(docs,key=iso):
  for row in docs[ed]['records']:bykey[row['key']].append(row)
 members={k for k,rows in bykey.items() if any(r['edition'].endswith('2026') for r in rows)}
 return docs,bykey,members

MONTHS={m.lower():i for i,m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'],1)}
for m,i in list(MONTHS.items()):MONTHS[m[:3]]=i
MONTHS['sept']=9
DATE=re.compile(r'^\s*(?:(?P<day>\d{1,2})\s+(?P<month>[A-Za-z]+)\s+(?P<year>20\d{2})\b|(?P<partial>February 2024|9 June)[ \t]*$)',re.M)
def dated_notes(row):
 text=row['comments'];headings={fingerprint(h) for h in row.get('commentHeadings',[])}
 matches=[]
 for m in DATE.finditer(text):
  heading=fingerprint(m.group())
  line_end=text.find('\n',m.end());line_end=len(text) if line_end<0 else line_end
  # Only a bold PDF heading is a dated update. Dates inside a sentence are content.
  # Legacy PDFs without bold date headings fall back to date-only lines.
  previous=text[:m.start()].rstrip().split('\n')[-1] if text[:m.start()].strip() else ''
  continues_sentence=bool(re.search(r'\b(?:until|by|on|of|ending|closes|before|after|from)\s*$',previous,re.I))
  date_only=not text[m.end():line_end].strip()
  if heading in headings or (date_only and not continues_sentence):matches.append(m)
 out=[]
 def undated(body):
  if flat(body):out.append({'date':iso(row['edition']),'text':flat(body),'raw':body.strip(),'dateNote':'This note has no separate date in the PDF; the timeline uses the tracker edition date.'})
 if not matches:undated(text);return out
 undated(text[:matches[0].start()])
 for i,m in enumerate(matches):
  body=text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip()
  if not body:continue
  note=''
  if m['partial']:
   date=iso(row['edition']);note=f'Council’s date heading is “{m["partial"]}”. It does not give a complete date; the timeline uses the edition date.'
  else:
   d,month,y=m['day'],m['month'],m['year'];mn=MONTHS.get(month.lower())
   if not mn:raise ValueError('Unknown month '+m.group())
   date=dt.date(int(y),mn,int(d)).isoformat()
   if date<row['meeting'] or date>iso(row['edition']):
    note=f'Council dates this note {flat(m.group())}. That date falls outside the decision/report period; the timeline uses the edition date instead.';date=iso(row['edition'])
  out.append({'date':date,'text':flat(body),'raw':m.group().strip()+'\n'+body,'dateNote':note})
 return out

def model():
 docs,bykey,members=records();groups={i:list(keys) for i,keys in GROUPS};owner={k:i for i,ks in groups.items() for k in ks}
 # Historical links reviewed against the adopted decisions. Preserve every row, including prior policy stages.
 links=load(ROOT/'historical-links.json') if (ROOT/'historical-links.json').exists() else []
 for link in links:
  key,parent=link['key'],link['related2026Key']
  if key in members or key in owner or parent not in members:continue
  group=owner.get(parent,'resolution-'+parent.replace('/','-').replace('+','-'))
  if group not in groups:groups[group]=[parent];owner[parent]=group
  groups[group].append(key);owner[key]=group
 for key in sorted(members,key=lambda k:(bykey[k][0]['meeting'],k)):
  if key not in owner:
   group='resolution-'+key.replace('/','-').replace('+','-');groups[group]=[key];owner[key]=group
 allissues=[]
 for issueid,keys in groups.items():
  keys=[k for k in keys if k in bykey]
  if not any(k in members for k in keys):continue
  rows=sorted([r for k in keys for r in bykey[k]],key=lambda r:(iso(r['edition']),r['meeting'],r['key']))
  events=[];checks=[]
  for key in keys:
   rs=bykey[key];first=rs[0]
   # Earliest available wording avoids silently replacing an earlier adopted decision.
   events.append({'date':first['meeting'],'type':'decision','key':key,'text':flat(first['resolution']),'evidenceText':first['resolution'],'edition':first['edition'],'pages':first['pages'],'dateNote':''})
   notes=collections.defaultdict(list)
   previous=None
   for row in rs:
    checks.append(row)
    for note in dated_notes(row):
     sig=(note['date'],fingerprint(note['text']))
     if not any(fingerprint(v['text'])==sig[1] for v in notes[note['date']]):
      notes[note['date']].append({**note,'edition':row['edition'],'pages':row['pages']})
    status=flat(row['status']);target=flat(row['target'])
    if previous is not None and (normal_status(status)!=normal_status(previous['status']) or normal_target(target)!=normal_target(previous['target'])):
     date=iso(row['edition']);text=f'The tracker lists this decision as {status}.'
     if target:text+=f' Its target date is {target}.'
     if previous is not None:text=f'The tracker changes this decision’s status from {previous["status"]} to {status}.' if normal_status(status)!=normal_status(previous['status']) else f'The tracker changes this decision’s target date from {previous["target"]} to {target}.'
     events.append({'date':date,'type':'status','key':key,'text':text,'evidenceText':f'Status: {status}\nTarget Date: {target}','edition':row['edition'],'pages':row['pages'],'dateNote':'This is the date of the tracker edition, not a confirmed date that work finished.'})
    previous=row
   dated_fingerprints={fingerprint(v['text']) for vs in notes.values() for v in vs if not v['dateNote']}
   seen_undated=set()
   for date,versions in notes.items():
    versions=[v for v in versions if not ('no separate date' in v['dateNote'] and (fingerprint(v['text']) in dated_fingerprints or fingerprint(v['text']) in seen_undated))]
    if not versions:continue
    seen_undated.update(fingerprint(v['text']) for v in versions if 'no separate date' in v['dateNote'])
    chosen=versions[-1]
    events.append({'date':date,'type':'note','key':key,'text':chosen['text'],'evidenceText':chosen['raw'],'edition':chosen['edition'],'pages':chosen['pages'],'dateNote':chosen['dateNote'],'versions':versions[:-1]})
  events.sort(key=lambda e:(e['date'],{'decision':0,'note':1,'status':2}[e['type']],e['key']))
  # One dot per date; all decisions and notes for that date remain selectable inside its reader.
  days=collections.defaultdict(list)
  for event in events:days[event['date']].append(event)
  allissues.append({'id':issueid,'keys':keys,'first':iso(rows[0]['edition']),'latest':max(e['date'] for e in events),'rows':rows,'days':[{'date':d,'entries':es} for d,es in days.items()]})
 out={'members':sorted(members),'issues':allissues,'sources':{ed:doc['source'] for ed,doc in docs.items()}}
 (ROOT/'catalogue-model.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 print(len(members),'resolutions;',len(allissues),'issues;',sum(len(i['days']) for i in allissues),'dated updates;',sum(len(i['rows']) for i in allissues),'source rows')
 return out

GROUP_COPY={
 'market-square':('Market Square','Lifts, escalators & building management','Repeated lift and escalator failures affect access to Market Square. Council is seeking to improve reliability and change how the shared building is managed.'),
 'karilla-avenue':('Karilla Avenue & safer streets','Traffic calming & the 40 km/h area','A raised crossing and a 40 km/h area aim to make Lane Cove North safer. A separate study will check through-traffic on Karilla Avenue.'),
 'food-scraps':('Food scraps collection','House collections & apartment rollout','Council is introducing food-only bin collections. House collections and the later rollout to apartments have different timetables, with apartment space and bin numbers under review.'),
 'community-e-shuttle':('Community shuttle bus','Feasibility, routes & costs','Council investigated a community shuttle, including possible routes, costs and partnerships with aged care providers, before deciding how to proceed.'),
 'st-leonards-return-and-earn':('Return and Earn in St Leonards','Investigating another recycling machine','Council investigated sites for an additional Return and Earn reverse vending machine in the St Leonards area.'),
 'pacific-highway-2-4':('2–4 Pacific Highway planning agreement','Public benefits & planning agreement','A proposed planning agreement for 2–4 Pacific Highway, St Leonards, went through public exhibition and Council consideration.'),
 'civic-centre-piano':('Civic Centre grand piano hire','Piano hire fees & conditions','Council reviewed the fees and conditions for hiring the concert grand piano at the Civic Centre.'),
 'st-leonards-road-names':('New road names in St Leonards South','Naming new public roads','Council considered names for new roads in St Leonards South, including public consultation and the road-naming process.'),
 'aquatic-centre-electrification':('Aquatic Centre electric heating','Replacing gas heating at the pool','Council investigated replacing gas heating at Lane Cove Aquatic Centre with electric heating and later considered the upgrade tender.'),
 'local-environment-plan-review':('Local Environment Plan review','Planning rules, housing & sustainability','Council is reviewing the Lane Cove Local Environmental Plan, including sustainability provisions and affordable housing, and considering the planning work required.'),
 'children-and-families-strategy':('Children and Families Strategy','Services & support for local families','Council developed a strategy for children and families, sought community feedback and considered the final strategy.'),
 'galuwa-food-and-events':('Galuwa food, drinks & events','Café, catering & events lease','Council considered how food, drinks and events would operate at Galuwa Recreation Centre and the terms of the operator’s lease.'),
 'pottery-green-drainage':('Pottery Green drainage','Funding & timing of drainage works','Council considered drainage works at Pottery Green Oval, including sporting club contributions, contractor availability and the Council budget.'),
 'rotary-peace-poles':('Rotary Peace Poles','Proposed locations & community feedback','Council considered Rotary’s proposal to install Peace Poles, including locations and community feedback.'),
 'dog-facilities':('Dog facilities in Lane Cove','Review of infrastructure for dogs','Council investigated improvements to infrastructure for dogs and considered the options in a follow-up report.'),
 'code-of-meeting-practice':('Council meeting rules','Meeting code & changes to NSW rules','Council reviewed its Code of Meeting Practice and later considered changes to NSW meeting rules and their local implications.'),
 'austin-crescent-3':('3 Austin Crescent heritage listing','Proposed heritage protection','Council considered a planning proposal to add heritage protection for 3 Austin Crescent, Lane Cove, including public exhibition.'),
 'austin-crescent-1':('1 Austin Crescent heritage listing','Review of heritage protection','Council considered a planning proposal to remove heritage protection for 1 Austin Crescent, Lane Cove, including public exhibition.'),
 'ev-charging-policy':('Electric vehicle charging policy','Charging infrastructure & public feedback','Council developed an Electric Vehicle Charging Infrastructure Policy, sought public feedback and considered the final policy.'),
 'sustainability-action-plan':('Sustainability Action Plan 2026–2030','Local sustainability actions','Council reviewed the previous sustainability plan and developed, exhibited and adopted the 2026–2030 Sustainability Action Plan.'),
 'asset-and-reserves-policies':('Asset management & cash reserves','Policies for assets & restricted funds','Council sought feedback on its infrastructure asset management and restricted cash reserves documents before considering their adoption.'),
 'budget-2026-27':('Council budget for 2026–27','Budget, fees & annual work program','Council prepared, exhibited and adopted its 2026–27 budget, fees and charges, operational plan and supporting resource plans.'),
 'greenwich-road-177-183':('177–183 Greenwich Road','Planning proposal & public benefits','Council considered planning changes and a planning agreement for 177–183 Greenwich Road, including public exhibition and proposed public benefits.'),
 'habitat-logs-and-biodiversity':('Habitat logs & urban biodiversity','Reusing logs & creating wildlife habitat','Council investigated salvaging logs from tree work and other ways to create wildlife habitat in local public spaces.'),
 'third-party-revenue':('Council revenue managed by others','Review of third-party arrangements','Council requested a review of revenue collected or managed by third parties and considered the resulting report.'),
 'affordable-housing-policy':('Affordable Housing Policy','Proposed approach to affordable housing','Council developed and exhibited an Affordable Housing Policy before considering the policy after public feedback.'),
 'fire-safety-policy':('Fire Safety Policy','Council’s approach to fire safety','Council developed and exhibited a Fire Safety Policy before considering its adoption.'),
 'civic-art-collection-policy':('Civic Art Collection Policy','Managing Council’s art collection','Council reviewed the policy for its civic art collection, sought public feedback and considered the final policy.'),
 'planning-agreements-policy':('Planning Agreements Policy','Rules for negotiating public benefits','Council reviewed its Planning Agreements Policy, sought public feedback and considered its adoption.'),
 'st-leonards-south-areas-22-23':('St Leonards South: Areas 22 & 23','Changes to the planning agreement','Council considered a planning agreement and later variations for Areas 22 and 23 in the St Leonards South precinct.'),
 'community-engagement':('Community consultation & communication','How Council seeks resident feedback','Council reviewed how it consults and communicates with residents, including community engagement policies and digital communication strategies.'),
 'burns-bay-reserve-masterplan':('Burns Bay Reserve masterplan','Future improvements to the reserve','Council exhibited the Burns Bay Reserve masterplan and considered its separate parts after public feedback.'),
 'data-breach-policy':('Data Breach Response Policy','How Council responds to data breaches','Council developed and exhibited a policy for responding to data breaches before considering its adoption.'),
 'vacant-development-sites':('Maintenance of vacant development sites','Sediment run-off & site appearance','Council investigated measures to manage sediment run-off and the appearance of vacant development sites, then considered a follow-up report.'),
 'safe-phone-initiative':('Domestic violence safe phones','Support for the DV Safe Phone initiative','Council considered supporting DV Safe Phone, including collecting and promoting donated phones for people affected by domestic violence.'),
 'watercraft-storage-policy':('Small Watercraft Storage Policy','Storage of boats & other small watercraft','Council developed and exhibited a policy for storing small watercraft before considering its adoption.'),
 'anglo-road-closure':('Anglo Road closure & proposed sale','Road closure, access & sale conditions','Council is considering the closure and sale of Anglo Road in St Leonards, including development requirements, public access and the road closure process.'),
 'st-leonards-contributions':('St Leonards South developer contributions','Infrastructure funding & contributions plan','Council reviewed developer contributions for St Leonards South infrastructure, including valuations, public exhibition, IPART review and adoption of the amended contributions plan.'),
 'climate-emergency-plan':('Climate Emergency Plan','Emissions targets & local climate actions','Council reviewed its climate emergency reporting and emissions targets, then developed a new climate plan for public consultation.'),
 'pride-community-grants':('Pride & inclusive community grants','Grant rules, applications & funding','Council developed a pilot Pride celebration grant program and later considered the Inclusive Communities Grant Program and funding applications.'),
 'domestic-violence-prevention':('Domestic & family violence prevention','Council strategy, training & local support','Council considered a domestic and family violence prevention strategy, staff training, local resources and participation in a local government prevention program.'),
 'e-bike-safety':('E-bike safety','Education, shared-bike parking & enforcement','Council considered safety education and advocacy for e-bikes, followed by shared-bike parking standards, enforcement and community feedback.'),
 'canberra-avenue':('Canberra Avenue closure & planning agreement','Road closure timing, access & developer works','Council considered closing part of Canberra Avenue in St Leonards South, the timing and trial arrangements, and related changes to Silver Pond Investments’ planning agreement works and payments.'),
 'lgnsw-conference-2026':('2026 Local Government NSW conference','Council motions, attendance & voting delegates','Council considered who would attend and vote at the 2026 Local Government NSW conference and the motions it would submit for debate.'),
 'advisory-committee-appointments':('Committee representatives for 2026–28','Councillor appointments to committees','Council appointed councillor representatives to internal committees and external organisations for September 2026 to September 2028. Each appointment decision is recorded separately below.'),
 'mayor-and-deputy-mayor-election':('Mayor & Deputy Mayor elections','Election outcomes & voting method','Council elected the Mayor and Deputy Mayor and decided the voting method for the Deputy Mayor election.')
}

TIMELINE_LABELS={'market-square':{
 '2025-05-22':'Maintenance review requested','2025-05-28':'Workshop scheduled','2025-07-24':'Review task completed',
 '2025-10-23':'Lift failure report requested','2025-11-10':'Meeting arranged','2025-12-03':'December report prepared','2025-12-11':'Report received',
 '2026-02-11':'Weekly reports continue','2026-02-19':'Reporting tasks completed','2026-03-11':'Toilets upgrade completed','2026-03-19':'Management advice requested',
 '2026-04-15':'Advice being prepared','2026-05-13':'Region Group meeting scheduled','2026-06-08':'Advice report prepared','2026-06-18':'Manager search approved',
 '2026-07-16':'Manager duties discussed','2026-08-12':'No new update','2026-09-17':'Maintenance tender first','2026-10-14':'Quote documents awaited'}}

def compile_site(m):
 editorial={}
 for name in ['editorial-output-0.json','editorial-output-1.json','editorial-output-history.json']:
  if (ROOT/name).exists():editorial.update(load(ROOT/name))
 note_editorial={}
 note_original=load(ROOT/'note-editorial-input.json')
 for index in range(2):
  path=ROOT/f'note-output-{index}.json'
  if path.exists():
   for key,val in load(path).items():note_editorial[fingerprint(note_original[int(key)]['text'])]=val
 if (ROOT/'note-output-extra.json').exists():note_editorial.update(load(ROOT/'note-output-extra.json'))
 rawrows={};evidence={};issues=[];missing_notes={};missing_decisions={}
 for item in m['issues']:
  rows=item['rows'];keys=item['keys'];latest_by_key={}
  for row in rows:
   rowid=row['edition']+':'+row['key'];rawrows[rowid]=row;latest_by_key[row['key']]=row
  lead=next((editorial[k] for k in keys if k in editorial),None)
  if not lead:raise ValueError('Missing editorial '+str(keys))
  short,nav,description=GROUP_COPY.get(item['id'],(lead['short'],lead['description'],lead['description']))
  if len(nav)>120:nav=nav[:117].rsplit(' ',1)[0]+'…'
  if item['id']=='market-square':status='Still waiting'
  elif item['id']=='karilla-avenue':status='Partly delivered'
  elif item['id']=='food-scraps':status='Rolling out in phases'
  else:
   states=[normal_status(row['status']) for row in latest_by_key.values()]
   status='Completed' if all(s=='completed' for s in states) else 'In progress' if any(s.startswith('inprogress') for s in states) else 'Outstanding' if 'outstanding' in states else flat(rows[-1]['status'])
   if len(keys)>1 and status=='Completed':status='Tasks marked Completed'
  events=[]
  for day in item['days']:
   entries=[]
   for idx,e in enumerate(day['entries']):
    eid=item['id']+':'+day['date']+':'+str(idx)
    if e['type']=='decision':
     copy=editorial.get(e['key'])
     if not copy:
      missing_decisions[e['key']]={'key':e['key'],'resolution':e['text'],'title':latest_by_key[e['key']]['title']}
      copy={'title':latest_by_key[e['key']]['title'],'decisionSummary':e['text']}
     title=copy['title'];text=copy['decisionSummary'];kind='decision';label=f'Resolution {e["key"]} — Council wording'
    elif e['type']=='note':
     copy=note_editorial.get(fingerprint(e['text']))
     if not copy:
      missing_notes[fingerprint(e['text'])]={'key':e['key'],'text':e['text']}
      sentences=re.split(r'(?<=[.!?])\s+',e['text'])
      copy={'title':sentences[0] if len(sentences[0])<=65 else 'Council update','text':e['text']}
     title,text=copy['title'],copy['text'];kind='update';label=f'Resolution {e["key"]} — officer comment'
    else:
     title='Target date changed' if 'target date from' in e['text'] else 'Tracker status changed'
     text=e['text'];kind='update';label=f'Resolution {e["key"]} — tracker status and target date'
    evidence[eid]={'text':e['evidenceText'],'label':label,'edition':e['edition'],'pages':e['pages'],'dateNote':e['dateNote'],'versions':[{'text':v['raw'],'edition':v['edition'],'pages':v['pages']} for v in e.get('versions',[])]}
    entries.append({'title':title,'text':text,'kind':kind,'evidence':eid,'resolution':e['key']})
   # Status and target changes use reporting dates; the date stays visible and never implies completion of a whole issue.
   event={'date':day['date'],'title':entries[0]['title'],'text':' '.join(e['text'] for e in entries),'entries':entries}
   if len(entries)>1:event['title']+=f' (+{len(entries)-1})'
   events.append(event)
  context=[]
  verification=[v for v in load(ROOT/'historical-minutes-verification.json') if any(k in keys for k in v['sourceKeys'])] if (ROOT/'historical-minutes-verification.json').exists() else []
  if '67+68/2024' in keys:context.append('The tracker reproduces the foreshadowed Children and Families motion. The adopted minutes confirm the strategy decision as 67/2024 and the separate childcare tender/report decision as 68/2024.')
  if item['id']=='market-square':context.append('Earlier report and advice tasks were marked Completed. The later task to appoint a manager remains In Progress; a completed report does not confirm that the lifts are reliable.')
  if '1/2026' in keys:context.append('The October PDF labels the 24 September smart-glasses decision “1”. This site preserves that source identifier rather than silently replacing it.')
  if any(k in keys for k in ['28/2026','77/2026']):context.append('The report title says Austin Crescent, while the resolution text says Austin Street. The Council wording below is preserved as published.')
  if '199/2023' in keys:context.append('The tracker labels the October 2023 Canberra Avenue closure decision 199/2023. The adopted minutes identify it as 200/2023; 199 is a procedural motion. The original tracker wording is retained.')
  if any(k.endswith('/2023') for k in keys):context.append('The September 2023 tracker attachment is unavailable from Council’s official link. December 2023 links to the same PDF as November. Available later records retain some earlier dated comments; no missing update has been invented.')
  if any(normal_status(r['status'])=='notified' for r in latest_by_key.values()):context.append('Council’s latest available label is “Notified”. This site does not interpret that label as confirmation that the underlying work is finished.')
  issue={'id':item['id'],'short':short,'title':short,'category':lead['category'],'nav':nav,'summary':description,'status':status,'tone':'green' if 'Completed' in status else 'amber','resolutions':' → '.join(keys),'caution':' '.join(context) or 'The status shown is the latest available status for each decision. A decision disappearing from later trackers is not evidence that work finished. A completed report or policy task may still lead to further work.','meta':{'first':item['first'],'latest':item['latest'],'status':status,'symbol':CATEGORY_SYMBOLS.get(lead['category'],lead['symbol']),'description':description,'labels':[TIMELINE_LABELS.get(item['id'],{}).get(e['date'],e['title']) for e in events]},'events':events,'checks':[r['edition']+':'+r['key'] for r in sorted(rows,key=lambda r:(iso(r['edition']),r['key']),reverse=True)]}
  issue['aliases']=[k for v in verification for k in v.get('canonicalKeys',[])]
  issue['extraSources']=[{'url':v['minutes_pdf']+'#page='+str(v['pages'][0]),'label':'Adopted minutes: '+v['meeting']+' (pages '+', '.join(map(str,v['pages']))+')'} for v in verification]
  issues.append(issue)
 if missing_decisions:(ROOT/'missing-decision-editorial.json').write_text(json.dumps(missing_decisions,ensure_ascii=False,indent=2))
 (ROOT/'missing-note-editorial.json').write_text(json.dumps(missing_notes,ensure_ascii=False,indent=2))
 trackers={}
 for ed,s in sorted(m['sources'].items(),key=lambda kv:iso(kv[0])):
  if s.get('duplicate_of'):continue
  date=dt.date.fromisoformat(iso(ed))
  trackers[ed]={'iso':date.isoformat(),'label':f'{date.day} {date.strftime("%B %Y")}','url':s['source'],'record':s['source'],'pages':s['pages']}
 def js(name,variable,value):
  (SITE/name).write_text('// Generated from official Council tracker PDFs; see coverage.json.\nconst '+variable+' = '+json.dumps(value,ensure_ascii=False,separators=(',',':'))+';\n')
 js('sources.js','TRACKERS',trackers);js('data.js','ISSUES',issues);js('evidence.js','VERBATIM',evidence)
 with (SITE/'evidence.js').open('a') as f:f.write('const RECORDS = '+json.dumps(rawrows,ensure_ascii=False,separators=(',',':'))+';\n')
 coverage={'through':'2026-10-22','scope':'Every resolution appearing in an available 2026 Resolution Tracker, with related earlier decisions and all available dated comments and tracker rows.','resolutions2026':m['members'],'issues':len(issues),'datedUpdates':sum(len(i['events']) for i in issues),'sourceRows':len(rawrows),'editionsReviewed':len(trackers),'editions2026':[ed for ed in trackers if ed.endswith('2026')],'groups':{i['id']:i['resolutions'].split(' → ') for i in issues},'gaps':[{'edition':'21092023','reason':'Official attachment returns an extraction error; agenda PDF links it but does not embed it.'},{'edition':'07122023','reason':'Agenda links the identical November tracker; not counted as a new snapshot.'}],'method':'Each source row is extracted by physical table columns. Dated officer comments are combined across editions; repeated wording is deduplicated. Status/target changes are dated to publication. Multiple records on a date share one dot but keep separate summaries and original wording.'}
 (SITE/'coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2))
 print('Compiled',len(issues),'issues;',len(missing_decisions),'decision summaries and',len(missing_notes),'note summaries pending')
 return issues,evidence,rawrows,coverage

if __name__=='__main__':
 m=model()
 compile_site(m)
