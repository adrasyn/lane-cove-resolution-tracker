const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const app=fs.readFileSync('dist/app.js','utf8');
const issues=vm.runInNewContext(fs.readFileSync('dist/data.js','utf8')+'\nISSUES');
const meta=Object.fromEntries(issues.map(issue=>[issue.id,issue.meta]));
function productionFunction(name,globals={}){
 const source=app.match(new RegExp('^function '+name+'\\([^]*?^}', 'm'));
 assert.ok(source,`${name} must provide the browsing behaviour`);
 return vm.runInNewContext(source[0]+'\n'+name,globals);
}
const filter=productionFunction('filterIssues',{META:meta});
const categories=new Set(issues.map(issue=>issue.category));
assert.equal(filter(issues,'',categories).length,165);
assert.equal(filter(issues,'',new Set()).length,0);
const facilities=filter(issues,'',new Set(['Facilities & places']));
assert.ok(facilities.length>0&&facilities.length<165);
assert.ok(facilities.every(issue=>issue.category==='Facilities & places'));
assert.ok(filter(issues,'market square',new Set(['Facilities & places'])).some(issue=>issue.id==='market-square'));
assert.equal(filter(issues,'market square',new Set(['Roads & transport'])).length,0);
assert.ok(filter(issues,'224/2025',categories).some(issue=>issue.id==='market-square'));
const place=productionFunction('placeTimelineLabels');
for(const width of [700,1158,1240]){
 // Close dates must stay close, even while every label gets its own readable space.
 const positions=[16,23,30,120,150,155,160,200,230,240,350,400,405,410,500,520,525,550,600];
 const heights=positions.map((_,i)=>i%3===0?80:60);
 const result=place(positions,width,138,heights,1);
 assert.equal(result.labels.length,19);
 assert.ok(result.labels.some(label=>label.side==='above'));
 assert.ok(result.labels.some(label=>label.side==='below'));
 result.labels.forEach((label,i)=>{
  assert.equal(label.x,positions[i]);
  assert.ok(label.left>=0&&label.left+138<=width);
  assert.ok(label.top>=30&&label.top+heights[i]<=result.height);
  assert.ok(label.side==='above'?label.top+heights[i]<result.axisY:label.top>result.axisY);
 });
 for(let i=0;i<result.labels.length;i++)for(let j=i+1;j<result.labels.length;j++){
  const a=result.labels[i],b=result.labels[j];
  const overlap=a.left<b.left+138&&a.left+138>b.left&&a.top<b.top+heights[j]&&a.top+heights[i]>b.top;
  assert.ok(!overlap,`Labels ${i} and ${j} must not overlap at width ${width}`);
 }
}
console.log('Browsing checks passed: category/search intersection, decision search, and complete labels above/below the timeline.');
