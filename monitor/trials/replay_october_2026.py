"""Isolated historical October fixture replay; never use as a live source-health result."""
import contextlib,copy,hashlib,importlib.util,io,json,pathlib,sys,subprocess,shutil
root=pathlib.Path.cwd();sys.path.insert(0,str(root/'scripts'))
from derive_release_inventory import derive
spec=importlib.util.spec_from_file_location('build',root/'catalogue/build_catalogue.py');build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
source=root/'catalogue/structured/22102026-rows.json';original=source.read_bytes()
notes_path=root/'catalogue/note-summaries.json';notes_original=notes_path.read_bytes();notes=json.loads(notes_original)
inventory_path=root/'catalogue/release-inventory.json';inventory_original=inventory_path.read_bytes()
def model():
 with contextlib.redirect_stdout(io.StringIO()):return build.model()
# Require the isolated rehearsal branch, never the production checkout.
assert subprocess.check_output(['git','branch','--show-current'],text=True).strip()=='rehearsal/october-2026-cloud'
digest='17be031ef3f9585bedbf10d247085f5edcda251c8cb94b76963c17754117fbd4'
fixture=root/'monitor/rehearsal-sources'/(digest+'.pdf')
assert hashlib.sha256(fixture.read_bytes()).hexdigest()==digest
baseline_before=(root/'monitor/baseline.json').read_bytes()
document=next(d for d in json.loads(baseline_before)['documents'] if d['date']=='22102026')
assert document['sha256']==digest
staging=root/'work/physical-replay';staging.mkdir(parents=True,exist_ok=True)
shutil.copyfile(fixture,staging/(digest+'.pdf'))
(staging/'report.json').write_text(json.dumps({'documents':[document|{'result':'new'}],'errors':[],'fixtureOnly':True}))
subprocess.run([sys.executable,'scripts/extract_tracker_rows.py','--report',str(staging/'report.json'),'--output',str(staging/'proposed')],check=True)
extracted=staging/'proposed'/('22102026-'+digest+'-rows.json')
physical=json.loads(extracted.read_text())
assert physical==json.loads(original) and not physical['warnings']
review=json.loads((root/'monitor/trials/october-pdf-visual-review-2026-10-22.json').read_text())
assert review['humanReviewComplete'] and review['pdfSha256']==digest
assert review['overviewPages']==list(range(1,66))
full=model()
# Replay the actual historical change: withhold October, then incorporate it again.
source.unlink()
prior=model()
prior_bindings={build.note_binding(e['key'],e['date'],e['text']) for i in prior['issues'] for d in i['days'] for e in d['entries'] if e['type']=='note'}
prior_notes=[n for n in notes if build.note_binding(n['minuteItem'],n['date'],n['sourceText']) in prior_bindings]
existing={build.note_binding(n['minuteItem'],n['date'],n['sourceText']) for n in prior_notes}
for key,date,text in sorted(prior_bindings-existing):
 prior_notes.append({'minuteItem':key,'date':date,'sourceText':text,'title':'Minute item '+key+' — officer update','text':text})
notes_path.write_text(json.dumps(prior_notes))
inventory_path.write_text(json.dumps(derive()))
with contextlib.redirect_stdout(io.StringIO()):before=build.compile_site(prior)
# Keep the accepted file serialization after checking every freshly extracted field.
source.write_bytes(json.dumps(physical,ensure_ascii=False,indent=2).encode());notes_path.write_bytes(notes_original)
# Stale release inventory must reject incorporation until independently reviewed.
try:build.compile_site(full)
except ValueError as error:assert 'Release inventory differs' in str(error)
else:raise AssertionError('Unreviewed release accepted')
inventory_path.write_bytes(inventory_original)
# Write a factual, item-specific summary from its exact dated source comment.
chosen=next(n for n in notes if n['minuteItem']=='230/2026' and n['date']=='2026-10-15')
assert 'multiple steps' in chosen['sourceText']
chosen['title']='Anglo Road closure: implementation steps being explored'
chosen['text']='Staff are exploring the next steps to implement the resolution and note that several steps are required.'
notes_path.write_text(json.dumps(notes,ensure_ascii=False,indent=2)+'\n')
with contextlib.redirect_stdout(io.StringIO()):after=build.compile_site(full)
assert source.read_bytes()==original
assert (root/'monitor/baseline.json').read_bytes()==baseline_before
# Every pre-October physical row and route survives; no unrelated original quotation changes.
assert set(i['id'] for i in before[0])<=set(i['id'] for i in after[0])
for key,value in before[2].items():assert after[2][key]==value,key
assert before[3]['through']=='2026-09-24' and after[3]['through']=='2026-10-22'
# Verify issue association using explicit content, not matching officer comments.
issue=next(i for i in after[0] if i['id']=='burns-bay-reserve-masterplan')
assert all(k in issue['resolutions'] for k in ['165/2026','228/2026','229/2026'])
assert 'Masterplan' in next(r for r in physical['records'] if r['key']=='229/2026')['resolution']
report={'status':'historical real-PDF extraction/editorial/release rehearsal passed; live Council transport and scheduler binding remain blocked','replay':'actual October PDF fixture physically extracted in this cloud; no invented edition','pdfSha256':digest,'extractedRows':len(physical['records']),'extractionWarnings':physical['warnings'],'physicalFieldDifferences':[],'newMinuteItems':sorted(set(full['members'])-set(prior['members'])),'priorCoverage':before[3]['through'],'replayedCoverage':after[3]['through'],'preservedPriorPhysicalRows':len(before[2]),'priorIssues':len(before[0]),'replayedIssues':len(after[0]),'summaryBinding':{k:chosen[k] for k in ['minuteItem','date','sourceText','title','text']},'associationEvidence':'228/2026 and 229/2026 explicitly concern adoption of the Burns Bay Reserve Masterplan; retained with the earlier 165/2026 masterplan issue. No grouping from matching comments.','gates':{'staleInventoryRejected':True,'allPriorRoutesRetained':True,'allPriorPhysicalRowsEqual':True,'realPdfExtraction':True,'visualReview':True,'liveCouncilTransport':False,'schedulerEnvironmentRetained':False,'scheduleActivationAllowed':False}}
(root/'monitor/trials/isolated-october-replay-2026-10-22.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
