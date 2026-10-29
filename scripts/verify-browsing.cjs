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
const orderPoints=productionFunction('orderTimelinePoints');
const timelinePoints=Array.from({length:3},(_,index)=>({querySelector:()=>({dataset:{index:String(index)}})}));
const selectedReader={text:'Open update'};timelinePoints[1].reader=selectedReader;
const rail={children:[...timelinePoints],attributes:{},moves:0,querySelectorAll(){return this.children;},setAttribute(name,value){this.attributes[name]=value;},appendChild(point){this.children=this.children.filter(child=>child!==point);this.children.push(point);this.moves++;}};
orderPoints(rail,true);
assert.deepEqual(rail.children,timelinePoints.slice().reverse(),'Mobile reading and tab order must put the newest update first');
assert.equal(rail.attributes['aria-label'],'Updates, newest first');
const moves=rail.moves;orderPoints(rail,true);assert.equal(rail.moves,moves,'Repeated mobile layout must not move the focused/open update');
orderPoints(rail,false);
assert.deepEqual(rail.children,timelinePoints,'Switching to desktop restores chronological axis order');
assert.equal(rail.attributes['aria-label'],'Updates, oldest first');
assert.equal(rail.children[1].reader,selectedReader,'Breakpoint changes preserve the existing inline reader');
const geometry=productionFunction('timelineGeometry');
const sample=geometry(['2026-03-01','2026-03-11','2026-03-31'],1000,1);
assert.equal(sample.positions.length,3);
assert.equal(sample.positions[0],16);
assert.ok(Math.abs((sample.positions[2]-sample.positions[1])/(sample.positions[1]-sample.positions[0])-2)<1e-9,'20 days must occupy twice the space of 10 days');
assert.ok(sample.height<120,'Desktop overview must stay compact regardless of update count');
assert.ok(sample.positions.every(x=>x>=16&&x<=984));
const yearBoundary=geometry(['2025-12-31','2026-01-01','2026-01-03'],1000,1);
assert.ok(Math.abs((yearBoundary.positions[2]-yearBoundary.positions[1])/(yearBoundary.positions[1]-yearBoundary.positions[0])-2)<1e-9);
const badge=productionFunction('resolutionBadge',{escapeText:s=>String(s)});
const tags=productionFunction('renderResolutionTags',{resolutionBadge:badge});
const renderRows=productionFunction('renderDesktopUpdates',{META:meta,escapeText:s=>String(s),formatDate:d=>d});
const square=issues.find(issue=>issue.id==='market-square');
const rows=renderRows(square);
assert.equal((rows.match(/class="update-row"/g)||[]).length,19);
assert.ok(rows.indexOf('2026-10-14')<rows.indexOf('2026-09-17'),'Latest updates must come first');
assert.ok(rows.indexOf('id="row-18"')<rows.indexOf('id="row-0"'),'Row indices must still match chronological dots');
const food=issues.find(issue=>issue.id==='food-scraps');
const foodRows=renderRows(food);
assert.ok(!foodRows.includes('resolution-tag'),'Desktop table headings must stay free of minute-item labels');
const sameDay=food.events.find(event=>event.date==='2026-10-22');
assert.equal((tags(food,sameDay).match(/class="resolution-tag /g)||[]).length,2,'A shared date must show both resolutions');
const classes=food.resolutions.split(' → ').map(number=>badge(food,number).match(/resolution-color-\d+/)[0]);
assert.equal(new Set(classes).size,4,'Each resolution within a group must have its own outline colour');
assert.equal(tags({resolutions:'1/2026'}, {entries:[{resolution:'1/2026'}]}),'','Single-resolution rows need no repeated badge');
const renderEntry=productionFunction('renderReaderEntry',{
 VERBATIM:{sample:{text:'Council source text',label:'Minute item',edition:'sample',pages:[]}},
 activeIssue:food,resolutionBadge:badge,escapeText:s=>String(s),sourceLink:()=>'<a>Source PDF</a>'
});
assert.ok(renderEntry({evidence:'sample',resolution:'60/2025',title:'Report',text:'Summary',kind:'decision'}).includes('New minute item 60/2025'));
assert.ok(renderEntry({evidence:'sample',resolution:'159/2024',title:'Update',text:'Summary',kind:'update'}).includes('Update on minute item 159/2024'));
// Exercise the actual lifecycle: visible desktop only, preferences and route cleanup.
function dotMotionHarness({mobile=false,reduced=false}={}){
 const events=new Map(),classes=new Set(),timers=new Map();let timerId=0,draw=0;
 const rings=Array.from({length:3},()=>{const names=new Set();return {classList:{add:n=>names.add(n),remove:n=>names.delete(n),contains:n=>names.has(n)},addEventListener(){}};});
 let visibility,signal,disconnected=false;
 const mobileLayout={matches:mobile,addEventListener:(name,fn)=>events.set('layout:'+name,fn)};
 const doc={hidden:false,addEventListener:(name,fn)=>events.set(name,fn)};
 const viewport={querySelectorAll:()=>rings,classList:{
  toggle:(name,on)=>on?classes.add(name):classes.delete(name),remove:name=>classes.delete(name)
 }};
 const attach=productionFunction('attachDotRipples',{
  AbortController,mobileLayout,motionEnabled:()=>!reduced,document:doc,
  Math:{random:()=>[0,.5,.99,.25][draw++%4]},
  setTimeout:(fn,delay)=>{timers.set(++timerId,{fn,delay});return timerId;},clearTimeout:id=>timers.delete(id),
  window:{addEventListener:(name,fn,options)=>{events.set(name,fn);signal=options.signal;}},
  IntersectionObserver:class{constructor(fn){visibility=fn;}observe(){}disconnect(){disconnected=true;}}
 });
 const cleanup=attach(viewport);
 return {events,rings,timers,doc,mobileLayout,cleanup,visible:on=>visibility([{isIntersecting:on}]),
  active:()=>classes.has('dot-hints-active'),reduce:on=>{reduced=on;events.get('tracker-motion-change')();},
  get signal(){return signal;},get disconnected(){return disconnected;}};
}
const ripple=dotMotionHarness();ripple.visible(true);assert.equal(ripple.active(),true);
assert.deepEqual([...ripple.timers.values()].map(timer=>timer.delay),[1000,1150,1297]);
const firstTimer=ripple.timers.entries().next().value;ripple.timers.delete(firstTimer[0]);firstTimer[1].fn();
assert.equal(ripple.rings[0].classList.contains('is-rippling'),true);
assert.equal(ripple.timers.size,3,'Every dot must independently schedule its next pulse');
assert.equal([...ripple.timers.values()].at(-1).delay,1075,'The next pulse must draw a fresh interval');
assert.ok([...ripple.timers.values()].every(timer=>timer.delay>=1000&&timer.delay<=1300));
ripple.visible(false);assert.equal(ripple.active(),false,'Off-screen timelines must stop');
assert.equal(ripple.timers.size,0);assert.ok(ripple.rings.every(ring=>!ring.classList.contains('is-rippling')));
ripple.visible(true);ripple.reduce(true);assert.equal(ripple.active(),false,'Reduce motion must stop the hint');
ripple.reduce(false);assert.equal(ripple.active(),true,'Allowing motion must restart the hint');
ripple.doc.hidden=true;ripple.events.get('visibilitychange')();assert.equal(ripple.active(),false);
ripple.doc.hidden=false;ripple.events.get('visibilitychange')();assert.equal(ripple.active(),true);
ripple.mobileLayout.matches=true;ripple.events.get('layout:change')();assert.equal(ripple.active(),false);
ripple.mobileLayout.matches=false;ripple.events.get('layout:change')();assert.equal(ripple.active(),true);
ripple.cleanup();assert.equal(ripple.timers.size,0);assert.equal(ripple.active(),false);assert.equal(ripple.signal.aborted,true);assert.equal(ripple.disconnected,true);
for(const settings of [{mobile:true},{reduced:true}]){
 const quiet=dotMotionHarness(settings);quiet.visible(true);assert.equal(quiet.active(),false);quiet.cleanup();
}
console.log('Browsing checks passed: filters, mobile timeline order, elapsed-time overview, update rows and visible desktop dot hints.');
