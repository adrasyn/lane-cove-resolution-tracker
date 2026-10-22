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
const geometry=productionFunction('timelineGeometry');
const sample=geometry(['2026-03-01','2026-03-11','2026-03-31'],1000,1);
assert.equal(sample.positions.length,3);
assert.equal(sample.positions[0],16);
assert.ok(Math.abs((sample.positions[2]-sample.positions[1])/(sample.positions[1]-sample.positions[0])-2)<1e-9,'20 days must occupy twice the space of 10 days');
assert.ok(sample.height<120,'Desktop overview must stay compact regardless of update count');
assert.ok(sample.positions.every(x=>x>=16&&x<=984));
const yearBoundary=geometry(['2025-12-31','2026-01-01','2026-01-03'],1000,1);
assert.ok(Math.abs((yearBoundary.positions[2]-yearBoundary.positions[1])/(yearBoundary.positions[1]-yearBoundary.positions[0])-2)<1e-9);
const renderRows=productionFunction('renderDesktopUpdates',{META:meta,escapeText:s=>String(s),formatDate:d=>d});
const square=issues.find(issue=>issue.id==='market-square');
const rows=renderRows(square);
assert.equal((rows.match(/class="update-row"/g)||[]).length,19);
assert.ok(rows.indexOf('2026-10-14')<rows.indexOf('2026-09-17'),'Latest updates must come first');
assert.ok(rows.indexOf('id="row-18"')<rows.indexOf('id="row-0"'),'Row indices must still match chronological dots');
// Exercise the production animation lifecycle with controllable visibility and motion preferences.
function dotMotionHarness({mobile=false,reduced=false}={}){
 const mobileLayout={matches:mobile,addEventListener:(name,fn)=>events.set('layout:'+name,fn)};
 const events=new Map(),timers=new Map(),played=[];let visibility,disconnected=false,signal;
 const rings=Array.from({length:3},()=>({
  animate:(frames,timing)=>{const animation={frames,timing,cancelled:false,finished:new Promise(()=>{}),cancel(){this.cancelled=true;}};played.push(animation);return animation;}
 }));
 // Each dot gets its own pointer handler, just as it does in the browser.
 rings.forEach((ring,index)=>ring.closest=()=>({addEventListener:(name,fn,options)=>{events.set('hover:'+index,fn);signal=options.signal;}}));
 const doc={documentElement:{},hidden:false,addEventListener:(name,fn)=>events.set(name,fn)};
 const attach=productionFunction('attachDotRipples',{
  AbortController,mobileLayout,motionEnabled:()=>!reduced,pointerMotionEnabled:()=>!reduced,
  document:doc,window:{addEventListener:(name,fn)=>events.set(name,fn)},
  getComputedStyle:()=>({getPropertyValue:()=> 'cubic-bezier(.23,1,.32,1)'}),
  setTimeout:(fn,delay)=>{timers.set(1,{fn,delay});return 1;},clearTimeout:id=>timers.delete(id),
  IntersectionObserver:class{constructor(fn){visibility=fn;}observe(){}disconnect(){disconnected=true;}}
 });
 const cleanup=attach({querySelectorAll:()=>rings});
 return {events,timers,played,doc,mobileLayout,cleanup,visible:()=>visibility([{isIntersecting:true}]),
  get signal(){return signal;},get disconnected(){return disconnected;}};
}
const ripple=dotMotionHarness();ripple.visible();
assert.equal(ripple.timers.get(1).delay,900,'Hint waits for the card transition');
ripple.timers.get(1).fn();
assert.equal(ripple.played.length,3);
assert.deepEqual(ripple.played.map(animation=>animation.timing.delay),[0,40,80]);
assert.ok(ripple.played.every(animation=>!animation.timing.iterations),'Hints must not loop');
ripple.events.get('tracker-motion-change')();
assert.ok(ripple.played.every(animation=>animation.cancelled),'Reduce motion must stop running hints');
ripple.cleanup();assert.equal(ripple.signal.aborted,true);assert.equal(ripple.disconnected,true);
for(const settings of [{mobile:true},{reduced:true}]){
 const quiet=dotMotionHarness(settings);quiet.visible();quiet.events.get('hover:0')({pointerType:'mouse'});
 assert.equal(quiet.timers.size,0);assert.equal(quiet.played.length,0);quiet.cleanup();
}
const departing=dotMotionHarness();departing.visible();departing.cleanup();
assert.equal(departing.timers.size,0,'Leaving the page must cancel the pending hint');
console.log('Browsing checks passed: filters, elapsed-time overview, update rows and cancellable desktop dot hints.');
