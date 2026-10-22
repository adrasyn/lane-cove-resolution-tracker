const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const context={};vm.createContext(context);
for(const file of ['sources.js','data.js','evidence.js'])vm.runInContext(fs.readFileSync('dist/'+file,'utf8'),context);
const {issues,documents,evidence,rows}=vm.runInContext('({issues:ISSUES,documents:TRACKERS,evidence:VERBATIM,rows:RECORDS})',context);
const sourceDocuments=fs.readdirSync('catalogue/structured').filter(n=>n.endsWith('2026-rows.json')).map(n=>JSON.parse(fs.readFileSync('catalogue/structured/'+n,'utf8')));
const expected=new Set(sourceDocuments.flatMap(d=>d.records.map(r=>r.key)));
const represented=new Set(issues.flatMap(i=>i.resolutions.split(' → ')));
const release=JSON.parse(fs.readFileSync('catalogue/release-inventory.json','utf8'));
assert.deepEqual([...expected].sort(),release.minuteItems,'Independently reviewed 2026 inventory');
assert.deepEqual(sourceDocuments.map(d=>d.source.date).sort(),release.documents.filter(d=>d.edition.endsWith('2026')).map(d=>d.edition).sort(),'Every reviewed 2026 edition present');
const coverage=JSON.parse(fs.readFileSync('dist/coverage.json','utf8'));
assert.equal(coverage.through,release.through,'Accepted release coverage date');
assert.deepEqual([...coverage.resolutions2026].sort(),release.minuteItems);
for(const asset of ['sources.js','data.js','evidence.js','app.js']){
 const hash=require('crypto').createHash('sha256').update(fs.readFileSync('dist/'+asset)).digest('hex').slice(0,12);
 assert.ok(fs.readFileSync('dist/index.html','utf8').includes(asset+'?v='+hash),'Cache version follows accepted content');
}
assert.deepEqual([...expected].filter(k=>!represented.has(k)),[],'Every 2026 resolution has a page');
assert.equal(new Set(issues.map(i=>i.id)).size,issues.length,'Unique routes');
for(const doc of sourceDocuments)for(const row of doc.records){
 const actual=rows[doc.source.date+':'+row.key];assert.ok(actual,'Every 2026 source row is retained');
 for(const field of ['resolution','comments','status','target'])assert.equal(actual[field],row[field],`Unchanged ${field} for ${row.key}`);
}
let entries=0,days=0;
for(const issue of issues){
 const dates=Array.from(issue.events,e=>e.date);assert.deepEqual([...dates].sort(),dates,'Chronological dates');
 assert.equal(new Set(dates).size,dates.length,'One dot per date; same-day records stay inside it');
 assert.equal(issue.meta.labels.length,dates.length);
 assert.ok(dates.length>0&&issue.checks.length>0);
 for(const event of issue.events){
  assert.match(event.date,/^\d{4}-\d{2}-\d{2}$/);
  assert.ok(event.entries.length>0);days++;
  for(const entry of event.entries){
   const source=evidence[entry.evidence];assert.ok(source,'Every summary has original wording');
   assert.ok(entry.text&&entry.title&&source.text);assert.ok(documents[source.edition]);
   assert.ok(source.pages.length&&source.pages.every(p=>p>0&&p<=documents[source.edition].pages),'Valid PDF page range');entries++;
  }
 }
 for(const id of issue.checks)assert.ok(rows[id]);
}
// Regressions from actual PDF edge cases: wrapped numbers and blank minute cells.
assert.ok(rows['23042026:25/2026'],'Backslash-prefixed 25 is its own EV-policy row');
assert.ok(!rows['23042026:28/2026'].title.includes('Electric Vehicle'));
assert.ok(!rows['19062025:158/2024'].title.includes('Interaction'));
assert.ok(!rows['20022025:126/2024'].title.includes('Interaction'));
assert.ok(rows['19062025:96/2024'],'Minutes-verified blank-number Staff Interaction row is retained');
assert.equal(rows['22102026:1/2026'].meeting,'2026-09-24','Source smart-glasses identifier retained');
assert.ok(issues.find(i=>i.id==='market-square').resolutions.includes('101/2025'),'Earlier Market Square decision retained');
assert.ok(issues.find(i=>i.id==='food-scraps').resolutions.includes('159/2024'),'Earlier food-service procurement retained');
console.log(JSON.stringify({passed:true,resolutions2026:expected.size,issues:issues.length,datedUpdates:days,summaryRecords:entries,sourceRows:Object.keys(rows).length,editions:Object.keys(documents).length},null,2));
