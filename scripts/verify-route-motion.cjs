const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('dist/app.js','utf8');
const navigate=source.slice(source.indexOf('async function navigateTo('),source.indexOf("document.addEventListener('click',event=>{",source.indexOf('async function navigateTo(')));
const resize=source.slice(source.indexOf('function handleRouteResize(){'),source.indexOf("window.addEventListener('resize',handleRouteResize"));
(async()=>{
 const calls=[],selected={getBoundingClientRect:()=>({top:360,bottom:455,height:95}),focus:o=>calls.push(['focusTile',o.preventScroll])};
 const context={routeGeneration:0,routeViewportWidth:429,activeIssue:{id:'market-square'},lastFocusIssue:null,collectionScroll:3200,innerHeight:838,
  window:{innerWidth:429,innerHeight:838,scrollY:0,scrollTo:o=>{calls.push(['scroll',o.top]);context.window.scrollY=o.top;}},
  document:{querySelector:selector=>selector.includes('data-issue')?selected:{}},history:{pushState:()=>{}},
  cancelRouteMotion:()=>calls.push(['cancel']),motionEnabled:()=>true,homeUrl:()=> '/',issueUrl:id=>'?issue='+id,
  renderHome:focus=>calls.push(['home',focus]),renderDetail:(issue,focus)=>calls.push(['detail',focus]),focusHeading:()=>calls.push(['heading'])};
 vm.createContext(context);vm.runInContext(navigate+'\n'+resize,context);
 await context.navigateTo(null);
 assert.deepEqual(calls.filter(c=>c[0]==='scroll'),[['scroll',3200]],'Returning restores the collection directly, without an intermediate scroll to zero');
 assert.ok(calls.some(c=>c[0]==='home'&&c[1]===undefined),'Return rendering does not focus/scroll the landing heading');
 assert.ok(calls.some(c=>c[0]==='focusTile'&&c[1]===true),'Reduced/keyboard navigation preserves tile focus without scrolling');
 calls.length=0;context.window.innerHeight=890;context.handleRouteResize();
 assert.equal(calls.filter(c=>c[0]==='cancel').length,0,'Mobile height changes must not abort a flip');
 context.window.innerWidth=768;context.handleRouteResize();
 assert.equal(calls.filter(c=>c[0]==='cancel').length,1,'A width/breakpoint change cancels safely');
 calls.length=0;context.activeIssue=null;
 await context.navigateTo({id:'food-scraps'});
 assert.deepEqual(calls.filter(c=>c[0]==='scroll'),[['scroll',0]],'Opening still scrolls to the detail header exactly once');
 assert.ok(calls.some(c=>c[0]==='heading'),'Nonanimated opening still focuses its heading');
 console.log('Route motion checks passed: direct scroll restoration, height-only resize, width cancellation and keyboard/reduced-motion focus.');
})().catch(e=>{console.error(e);process.exitCode=1;});
