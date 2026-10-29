'use strict';
const app = document.querySelector('#app');
const announcement = document.querySelector('#announcement');
const reducedMedia = matchMedia('(prefers-reduced-motion: reduce)');
const finePointer = matchMedia('(hover: hover) and (pointer: fine)');
const mobileLayout = matchMedia('(max-width: 760px)');
const REFERENCE_DATE = '2026-10-22';
const META = Object.fromEntries(ISSUES.map(issue=>[issue.id,issue.meta]));
const paths = {
  search:'m20 20-4.6-4.6M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0',
  arrow:'M5 12h14m-6-6 6 6-6 6', back:'M19 12H5m6-6-6 6 6 6',
  external:'M7 17 17 7M7 7h10v10', close:'m6 6 12 12M6 18 18 6',
  building:'M4 21V8h16v13M2 21h20M8 8V3h8v5M8 12h1m6 0h1m-8 4h1m6 0h1m-5 5v-4h2v4',
  council:'M3 9h18L12 3 3 9ZM6 12v5m6-5v5m6-5v5M4 18h16M2 21h20',
  community:'M15 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2m20 0v-2a4 4 0 0 0-3-3.87M15 3.13a4 4 0 0 1 0 7.75M12 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
  road:'m8 3-4 18M16 3l4 18M12 3v3m0 4v4m0 4v3',
  leaf:'M20 4C9 2 3 8 5 15c2 7 13 7 15-11ZM5 20 16 9',
  decision:'m6 5 5-3 7 10-5 3ZM3 16l8-6m1 11h10m-8-3h6',
  update:'M12 19V5m-6 6 6-6 6 6M4 20h16',
  wait:'M12 7v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  done:'m6 12 4 4 8-8M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  check:'M7 3h10l3 3v15H4V3h3m1 5h8m-8 4h8m-8 4h5',
  pointer:'m5 3 14 9-7 1-3 7Z', info:'M12 11v6m0-10v1M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0',
  spark:'m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4Z'
};
const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name]||paths.update}"/></svg>`;
const escapeText = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const formatDate = (date,short=false) => new Intl.DateTimeFormat('en-AU',{day:'numeric',month:short?'short':'long',year:'numeric',timeZone:'Australia/Sydney'}).format(new Date(date+'T12:00:00+11:00'));
const issueUrl = id => `${location.pathname}?issue=${encodeURIComponent(id)}`;
const homeUrl = () => location.pathname;
const readStorage = key => {try{return localStorage.getItem(key);}catch{return null;}};
const saveStorage = (key,value) => {try{localStorage.setItem(key,String(value));}catch{}};
let manualReduction = readStorage('lanecove-reduce-motion')==='true';
let query = '';
const CATEGORIES = [...new Set(ISSUES.map(issue=>issue.category))].sort((a,b)=>a.localeCompare(b));
let selectedCategories = new Set(CATEGORIES);
let activeIssue = null;
let selectedIndex = -1;
let cleanupView = () => {};
let cleanupTiles = () => {};
let routeGeneration = 0;
let routeViewportWidth = window.innerWidth;
let lastFocusIssue = null;
let collectionScroll = 0;
let cleanupRouteMotion = () => {};
function motionEnabled(){return !manualReduction&&!reducedMedia.matches;}
function pointerMotionEnabled(){return motionEnabled()&&finePointer.matches;}
function updateMotionControl(){
  document.documentElement.classList.toggle('reduce-motion',manualReduction||reducedMedia.matches);
  const button=document.querySelector('#motion-toggle');
  button.setAttribute('aria-pressed',String(manualReduction||reducedMedia.matches));
  button.disabled=reducedMedia.matches;
  button.title=reducedMedia.matches?'Motion is reduced by your device preference.':'';
  button.querySelector('span:last-child').textContent=manualReduction||reducedMedia.matches?'Motion reduced':'Reduce motion';
  window.dispatchEvent(new Event('tracker-motion-change'));
}
function shadeForDate(date){
  const days=Math.max(0,Math.floor((Date.parse(REFERENCE_DATE)-Date.parse(date))/86400000));
  if(days<=30)return {background:'oklch(.36 .065 188)',ink:'oklch(.99 0 0)',days};
  if(days<=90)return {background:'oklch(.50 .07 188)',ink:'oklch(.99 0 0)',days};
  if(days<=180)return {background:'oklch(.84 .035 188)',ink:'oklch(.255 .027 188)',days};
  return {background:'oklch(.94 .018 188)',ink:'oklch(.255 .027 188)',days};
}
function tilePalette(issue){const shade=shadeForDate(META[issue.id].latest);return `--tile-bg:${shade.background};--tile-ink:${shade.ink}`;}
function sourceLink(edition,pages,label='Read the original Council document'){
  const doc=TRACKERS[edition];
  return `<a href="${escapeText(doc.url)}" target="_blank" rel="noopener">${escapeText(label)} (PDF) ${icon('external')}<span class="sr-only">; opens in a new tab</span></a>`;
}
function routeIssue(){
  const hash=location.hash.slice(1),parameter=new URLSearchParams(location.search).get('issue');
  return ISSUES.find(issue=>issue.id===hash)||ISSUES.find(issue=>issue.id===parameter)||null;
}
function announce(text){announcement.textContent=text;}
function focusHeading(){document.querySelector('#page-heading')?.focus({preventScroll:true});}
function renderCategoryFilter(){
  return `<details class="category-filter" id="category-filter"><summary><span>Categories</span><span id="category-selection">All selected</span></summary><div class="category-panel"><div class="category-actions"><button type="button" id="select-categories">Select all</button><button type="button" id="deselect-categories">Deselect all</button></div><fieldset><legend class="sr-only">Issue categories</legend>${CATEGORIES.map((category,index)=>`<label for="category-${index}"><input type="checkbox" id="category-${index}" value="${escapeText(category)}" ${selectedCategories.has(category)?'checked':''} aria-controls="issue-grid"><span>${escapeText(category)}</span></label>`).join('')}</fieldset></div></details>`;
}
function updateCategoryControls(){
  document.querySelectorAll('.category-panel input').forEach(input=>{input.checked=selectedCategories.has(input.value);});
  document.querySelector('#category-selection').textContent=selectedCategories.size===CATEGORIES.length?'All selected':selectedCategories.size===0?'None selected':`${selectedCategories.size} of ${CATEGORIES.length} selected`;
  document.querySelector('#select-categories').disabled=selectedCategories.size===CATEGORIES.length;
  document.querySelector('#deselect-categories').disabled=selectedCategories.size===0;
}
function bindCategoryFilter(){
  document.querySelectorAll('.category-panel input').forEach(input=>input.addEventListener('change',()=>{
    cancelRouteMotion();input.checked?selectedCategories.add(input.value):selectedCategories.delete(input.value);renderTiles();
  }));
  document.querySelector('#select-categories').addEventListener('click',()=>{cancelRouteMotion();selectedCategories=new Set(CATEGORIES);renderTiles();});
  document.querySelector('#deselect-categories').addEventListener('click',()=>{cancelRouteMotion();selectedCategories.clear();renderTiles();});
}
function renderHome(focus=false){
  cleanupView();cleanupTiles();activeIssue=null;selectedIndex=-1;
  document.title='Lane Cove Council Resolution Tracker';
  app.innerHTML=`<div class="page-width"><section class="landing-intro" aria-labelledby="page-heading"><h1 id="page-heading" tabindex="-1">Follow updates from Council’s Resolution Tracker</h1><p class="tracker-freshness"><span>Updated for each Council meeting</span><span>Latest tracker: <time datetime="${REFERENCE_DATE}">${formatDate(REFERENCE_DATE)}</time></span></p></section><div class="search-area"><label for="issue-search">Find an issue</label><div class="search-field">${icon('search')}<input id="issue-search" type="search" name="issue-search" autocomplete="off" placeholder="Try lifts, food bins or Karilla Avenue" value="${escapeText(query)}" aria-controls="issue-grid"><button type="button" class="clear-search" id="clear-search" ${query?'':'hidden'}>Clear</button></div>${renderCategoryFilter()}</div><section class="collection" aria-labelledby="collection-heading"><div class="collection-heading"><h2 id="collection-heading">All issues <span id="result-count"></span></h2><div class="recency-key"><span class="shade-key" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span>Darker = more recently updated</span></div></div><div class="issue-grid" id="issue-grid"></div></section></div>`;
  const search=document.querySelector('#issue-search');
  search.addEventListener('input',()=>{cancelRouteMotion();query=search.value;renderTiles();});
  document.querySelector('#clear-search').addEventListener('click',clearSearch);
  bindCategoryFilter();
  renderTiles();
  cleanupView=()=>{};
  if(focus){focusHeading();window.scrollTo({top:0,behavior:'instant'});}
}
function clearSearch(){cancelRouteMotion();query='';document.querySelector('#issue-search').value='';renderTiles();document.querySelector('#issue-search').focus();}
function resetFilters(){selectedCategories=new Set(CATEGORIES);clearSearch();}
function filterIssues(issues,search,categories){
  const words=search.trim().toLocaleLowerCase('en-AU').split(/\s+/).filter(Boolean);
  return issues.filter(issue=>{
    if(!categories.has(issue.category))return false;
    const haystack=[issue.title,issue.short,issue.category,issue.nav,META[issue.id].description,issue.summary,issue.resolutions,...issue.events.map(item=>item.title)].join(' ').toLocaleLowerCase('en-AU');
    const numbers=[...issue.resolutions.split(' → '),...(issue.aliases||[])];
    return words.every(word=>/^\d+\/\d{4}$/.test(word)?numbers.some(number=>number===word||number.split('/')[0].split('+').some(minute=>minute+'/'+number.split('/')[1]===word)):haystack.includes(word));
  }).sort((a,b)=>META[b.id].latest.localeCompare(META[a.id].latest));
}
function renderTiles(){
  cleanupTiles();
  const issues=filterIssues(ISSUES,query,selectedCategories);
  updateCategoryControls();
  document.querySelector('#clear-search').hidden=!query;
  document.querySelector('#result-count').textContent=`${issues.length} ${issues.length===1?'issue':'issues'}`;
  const grid=document.querySelector('#issue-grid');
  grid.innerHTML=issues.length?issues.map(issue=>{
    const meta=META[issue.id];
    return `<a href="${issueUrl(issue.id)}" class="tile-link" data-issue="${issue.id}" aria-label="${escapeText(issue.short)}. ${escapeText(issue.nav.replace(/\.$/,''))}. Latest update ${formatDate(meta.latest)}. Open issue history."><article class="issue-tile" style="${tilePalette(issue)}"><div class="tile-sheen" aria-hidden="true"></div><div class="tile-top"><span class="tile-symbol">${icon(meta.symbol)}</span><span>${escapeText(issue.category)}</span></div><h3>${escapeText(issue.short)}</h3><p class="tile-description">${escapeText(issue.nav)}</p><div class="tile-bottom"><p>Updated <time datetime="${meta.latest}">${formatDate(meta.latest,true)}</time></p><span class="tile-arrow">${icon('external')}</span></div></article></a>`;
  }).join(''):`<div class="empty-results"><h3>${selectedCategories.size===0?'No categories selected.':'No issues match your search and categories.'}</h3><p>Select a category or change your search.</p><button type="button" id="reset-results">Show all issues</button></div>`;
  grid.querySelector('#reset-results')?.addEventListener('click',resetFilters);
  grid.querySelectorAll('[data-issue]').forEach(link=>link.addEventListener('click',event=>{
    if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
    event.preventDefault();navigateTo(ISSUES.find(issue=>issue.id===link.dataset.issue),event.detail>0?link:null);
  }));
  cleanupTiles=attachTileMotion(grid);
  announce(`${issues.length} ${issues.length===1?'issue':'issues'} found`);
}
function resolutionBadge(issue,number,label){
  const keys=issue.resolutions.split(' → '),colour=Math.max(0,keys.indexOf(number))%5;
  return `<span class="resolution-tag resolution-color-${colour}">${escapeText(label||'Minute item '+number)}</span>`;
}
function renderResolutionTags(issue,item){
  if(issue.resolutions.split(' → ').length<2)return '';
  const numbers=[...new Set(item.entries.map(entry=>entry.resolution))];
  return `<span class="resolution-tags">${numbers.map(number=>resolutionBadge(issue,number)).join('')}</span>`;
}
function renderDesktopUpdates(issue){
  const labels=META[issue.id].labels;
  return `<ol class="desktop-updates" aria-label="Updates, newest first">${issue.events.map((item,index)=>`<li class="desktop-update" id="update-row-${index}"><button type="button" class="update-row" id="row-${index}" data-index="${index}" aria-expanded="false" aria-controls="update-reader"><time datetime="${item.date}">${formatDate(item.date,true)}</time><span class="row-title">${escapeText(labels[index]||item.title)}</span><span class="row-toggle" aria-hidden="true">+</span></button></li>`).reverse().join('')}</ol>`;
}
function renderDetail(issue,focus=false){
  cleanupView();cleanupTiles();activeIssue=issue;selectedIndex=-1;
  const meta=META[issue.id];
  document.title=issue.short+' · Lane Cove Council Resolution Tracker';
  app.innerHTML=`<div class="page-width detail-page"><div class="back-row"><a href="${homeUrl()}" data-home>${icon('back')}All issues</a><span>${escapeText(issue.category)}</span></div><section class="detail-hero" style="${tilePalette(issue)}" aria-labelledby="page-heading"><div class="tile-sheen" aria-hidden="true"></div><div class="hero-heading"><h1 id="page-heading" tabindex="-1">${escapeText(issue.title)}</h1></div><p class="hero-description">${escapeText(meta.description)}</p><dl class="hero-meta"><div><dt>First appeared</dt><dd><time datetime="${meta.first}">${formatDate(meta.first,true)}</time></dd></div><div><dt>Latest update</dt><dd><time datetime="${meta.latest}">${formatDate(meta.latest,true)}</time></dd></div><div><dt>Status</dt><dd class="hero-status">${icon(issue.tone==='amber'?'wait':'update')}${escapeText(meta.status)}</dd></div></dl></section><section class="story-section" aria-labelledby="timeline-heading"><div class="story-heading"><div><h2 id="timeline-heading">Update history</h2><p class="desktop-timeline-hint">Select a dot or an update below.</p><p class="mobile-timeline-hint">Select a dated update to read the details.</p></div>${issue.events.length>12?`<div class="update-picker"><label for="update-picker">Choose an update</label><select id="update-picker"><option value="">Choose an update</option>${issue.events.map((item,index)=>`<option value="${index}">${formatDate(item.date,true)}</option>`).join('')}</select></div>`:''}</div><div class="timeline-viewport" id="timeline-viewport"><div class="timeline-scale" aria-hidden="true"></div><svg class="timeline-guides" aria-hidden="true"></svg><ol class="timeline-rail">${issue.events.map((item,index)=>`<li class="timeline-point"><button type="button" class="update-button" id="update-${index}" aria-expanded="false" aria-controls="update-reader" data-index="${index}"><span class="dot-ripple" aria-hidden="true"></span><span class="node-dot" aria-hidden="true"></span><span class="node-copy"><time class="node-date" datetime="${item.date}">${formatDate(item.date,true)}</time><span class="node-label">${escapeText(meta.labels[index]||item.title)}</span>${renderResolutionTags(issue,item)}</span></button></li>`).join('')}</ol></div>${renderDesktopUpdates(issue)}<div class="detail-reader-slot" id="reader-slot"><div class="reader-placeholder" id="reader-placeholder">${icon('pointer')}Select an update to read the summary and Council’s original wording.</div><section class="update-reader" id="update-reader" aria-labelledby="reader-heading" hidden></section></div><details class="issue-context"><summary>How Council records this issue &amp; source documents</summary><div class="context-body"><p>Council’s Resolution Tracker lists numbered minute items and their status. This page includes the minute items and available tracker updates for this issue. Several records on the same date share a dot; their original wording stays separate.</p><p>${escapeText(issue.caution)}</p><p>The outlined labels identify the minute item each update belongs to. Numbers combine Council’s minute item number with the meeting year, so minute item 159 from 2024 appears as 159/2024. The same outline colour follows a minute item throughout this page.</p><p>Minute item references on this page: ${escapeText(issue.resolutions)}.</p>${(issue.extraSources||[]).map(source=>`<p><a href="${escapeText(source.url)}" target="_blank" rel="noopener">${escapeText(source.label)}<span class="sr-only">; opens in a new tab</span></a></p>`).join('')}${issue.extraSource?`<p>${escapeText(issue.extraSource.note)}</p><a href="${escapeText(issue.extraSource.url)}" target="_blank" rel="noopener">${escapeText(issue.extraSource.label)}<span class="sr-only">; opens in a new tab</span></a>`:''}<details class="monthly-checks"><summary>All tracker entries (${issue.checks.length})</summary><p>Each entry below is a row from a Council tracker. Repeated comments, the reported status and target date are retained. A missing entry does not confirm that work finished.</p>${issue.checks.map(renderCheck).join('')}</details></div></details></section></div>`;
  document.querySelector('#update-picker')?.addEventListener('change',event=>{if(event.target.value!=='')selectUpdate(Number(event.target.value),false,true);});
  document.querySelectorAll('.update-button,.update-row').forEach(button=>{
    button.addEventListener('click',event=>selectUpdate(Number(button.dataset.index),event.detail===0,button.classList.contains('update-button')));
    if(!button.classList.contains('update-button'))return;
    button.addEventListener('keydown',event=>{
      if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End'].includes(event.key))return;
      event.preventDefault();
      const direction=mobileLayout.matches?-1:1;
      let next=Number(button.dataset.index)+(event.key==='ArrowRight'||event.key==='ArrowDown'?direction:-direction);
      if(event.key==='Home')next=mobileLayout.matches?issue.events.length-1:0;
      if(event.key==='End')next=mobileLayout.matches?0:issue.events.length-1;
      next=Math.max(0,Math.min(issue.events.length-1,next));
      const target=document.querySelector(`#update-${next}`);target.focus({preventScroll:!mobileLayout.matches});
    });
  });
  cleanupView=attachTimeline();
  if(!mobileLayout.matches)selectUpdate(issue.events.length-1);
  if(focus){focusHeading();window.scrollTo({top:0,behavior:'instant'});}
}
function placeReader(){
  const reader=document.querySelector('#update-reader');if(!reader)return;
  const parent=selectedIndex<0?document.querySelector('#reader-slot'):mobileLayout.matches?document.querySelector(`#update-${selectedIndex}`).parentElement:document.querySelector(`#update-row-${selectedIndex}`);
  parent.appendChild(reader);
}
function renderCheck(id){
  const row=RECORDS[id],doc=TRACKERS[row.edition];
  return `<div class="monthly-row"><time datetime="${doc.iso}">${formatDate(doc.iso,true)}</time><div><strong>Minute item ${escapeText(row.key)} · ${escapeText(row.status)}</strong>${row.sourceIdentifier?`<p>${escapeText(row.sourceIdentifier)}; matched using the report title and meeting date.</p>`:''}<p>Target date in this edition: ${escapeText(row.target||'Not given')}.</p><details class="source-row"><summary>Read the complete tracker entry</summary><p>${escapeText(row.title)}</p><h4>Council resolution</h4><blockquote>${escapeText(row.resolution)}</blockquote><h4>Officer comments</h4><blockquote>${escapeText(row.comments||'No comment recorded.')}</blockquote></details>${sourceLink(row.edition,row.pages,'View this tracker')}</div></div>`;
}
function renderReaderEntry(entry,multiple=false){
  const evidence=VERBATIM[entry.evidence];
  return `<div class="reader-entry">${multiple?`<h4>${escapeText(entry.title)}</h4>`:''}<p class="ai-label">${resolutionBadge(activeIssue,entry.resolution,(entry.kind==='decision'?'New minute item ':'Update on minute item ')+entry.resolution)}<span>AI summary</span></p><p class="ai-summary">${escapeText(entry.text)}</p>${evidence.dateNote?`<p class="source-date-note">${escapeText(evidence.dateNote)}</p>`:''}<div class="source-actions"><details class="exact-wording"><summary>Read the exact Council wording</summary><p class="verbatim-label">${escapeText(evidence.label)}</p><blockquote>${escapeText(evidence.text)}</blockquote><p class="wording-note">Original wording and punctuation; PDF line breaks have been normalised.</p>${evidence.versions?.length?`<details class="earlier-wording"><summary>Wording in earlier trackers (${evidence.versions.length})</summary>${evidence.versions.map(version=>`<p>${sourceLink(version.edition,version.pages,TRACKERS[version.edition].label)}</p><blockquote>${escapeText(version.text)}</blockquote>`).join('')}</details>`:''}</details><div class="reader-source">${sourceLink(evidence.edition,evidence.pages)}</div></div></div>`;
}
function scrollToUpdateRow(index){
  document.querySelector(`#update-row-${index}`)?.scrollIntoView({block:'nearest',behavior:motionEnabled()?'smooth':'instant'});
}
function selectUpdate(index,keyboard=false,fromTimeline=false){
  if(index===selectedIndex){
    if(fromTimeline&&!mobileLayout.matches)scrollToUpdateRow(index);else closeUpdate();
    return;
  }
  selectedIndex=index;const item=activeIssue.events[index],reader=document.querySelector('#update-reader');
  const entries=item.entries;
  const picker=document.querySelector('#update-picker');if(picker)picker.value=String(index);
  document.querySelectorAll('.update-button,.update-row').forEach(button=>{
    const expanded=Number(button.dataset.index)===index;button.setAttribute('aria-expanded',String(expanded));
    const toggle=button.querySelector('.row-toggle');if(toggle)toggle.textContent=expanded?'−':'+';
  });
  reader.innerHTML=`<div class="reader-top"><span class="reader-kind">${entries.length===1&&entries[0].kind==='decision'?'Council minute item':'Council update'} <span aria-hidden="true">·</span> ${formatDate(item.date,true)}${entries.length>1?` · ${entries.length} records`:''}</span><button type="button" class="close-update" aria-label="Close this update">${icon('close')}</button></div><h3 id="reader-heading" tabindex="-1">${entries.length>1?formatDate(item.date):escapeText(item.title)}</h3>${entries.map(entry=>renderReaderEntry(entry,entries.length>1)).join('')}`;
  reader.hidden=false;document.querySelector('#reader-placeholder').hidden=true;placeReader();
  reader.querySelector('.close-update').addEventListener('click',()=>closeUpdate(true));
  if(motionEnabled()&&!keyboard)reader.animate([{opacity:.45,transform:'translateY(5px)'},{opacity:1,transform:'translateY(0)'}],{duration:180,easing:'cubic-bezier(.23,1,.32,1)'});
  if(keyboard)reader.querySelector('#reader-heading').focus({preventScroll:true});
  if(fromTimeline&&!mobileLayout.matches)scrollToUpdateRow(index);
  announce(`Opened update ${mobileLayout.matches?activeIssue.events.length-index:index+1} of ${activeIssue.events.length}: ${item.title}`);
}
function closeUpdate(restoreFocus=false){
  const previous=selectedIndex;selectedIndex=-1;
  const picker=document.querySelector('#update-picker');if(picker)picker.value='';
  const reader=document.querySelector('#update-reader');reader.hidden=true;placeReader();
  document.querySelector('#reader-placeholder').hidden=false;
  document.querySelectorAll('.update-button,.update-row').forEach(button=>{button.setAttribute('aria-expanded','false');const toggle=button.querySelector('.row-toggle');if(toggle)toggle.textContent='+';});
  if(restoreFocus&&previous>=0)document.querySelector(mobileLayout.matches?`#update-${previous}`:`#row-${previous}`).focus({preventScroll:true});
  announce('Update closed');
}
// Keep the overview proportional to elapsed time; desktop update text lives in the list below.
function timelineGeometry(dates,width,fontScale){
  const padding=16,usable=width-padding*2;
  const first=new Date(dates[0]+'T00:00:00Z'),last=new Date(dates.at(-1)+'T00:00:00Z');
  const start=Date.UTC(first.getUTCFullYear(),first.getUTCMonth(),1);
  const end=Date.UTC(last.getUTCFullYear(),last.getUTCMonth()+1,1);
  return {start,end,axisY:43*fontScale,height:80*fontScale,
    positions:dates.map(date=>padding+(Date.parse(date)-start)/(end-start)*usable)};
}
// Change actual reading/tab order while retaining each event's chronological index.
function orderTimelinePoints(rail,newestFirst){
  const points=[...rail.querySelectorAll('.timeline-point')].sort((a,b)=>Number(a.querySelector('.update-button').dataset.index)-Number(b.querySelector('.update-button').dataset.index));
  const ordered=newestFirst?[...points].reverse():points;
  if(ordered.some((point,index)=>rail.children[index]!==point))ordered.forEach(point=>rail.appendChild(point));
  rail.setAttribute('aria-label',newestFirst?'Updates, newest first':'Updates, oldest first');
  return points;
}
function layoutTimeline(){
  const viewport=document.querySelector('#timeline-viewport');
  if(!viewport||!activeIssue)return;
  const points=orderTimelinePoints(viewport.querySelector('.timeline-rail'),mobileLayout.matches);
  if(mobileLayout.matches){viewport.style.height='';return;}
  const scale=viewport.querySelector('.timeline-scale'),guides=viewport.querySelector('.timeline-guides');
  const width=viewport.clientWidth,padding=16;
  const fontScale=parseFloat(getComputedStyle(document.documentElement).fontSize)/18;
  const geometry=timelineGeometry(activeIssue.events.map(event=>event.date),width,fontScale);
  const first=new Date(geometry.start),last=new Date(geometry.end-1);
  viewport.style.height=geometry.height+'px';viewport.style.setProperty('--axis-y',geometry.axisY+'px');
  points.forEach((point,index)=>{
    const x=geometry.positions[index];
    const hitWidth=Math.max(4,Math.min(28,x-(geometry.positions[index-1]??-Infinity),(geometry.positions[index+1]??Infinity)-x));
    point.style.setProperty('--dot-hit',hitWidth+'px');
    point.style.setProperty('--event-x',x+'px');point.style.setProperty('--dot-y',geometry.axisY+'px');
    point.querySelector('.update-button').title=formatDate(activeIssue.events[index].date,true)+' · '+activeIssue.events[index].title;
  });
  const monthCount=(last.getUTCFullYear()-first.getUTCFullYear())*12+last.getUTCMonth()-first.getUTCMonth()+1;
  const step=Math.max(1,Math.ceil(monthCount*70*fontScale/(width-padding*2)));
  const ticks=[];
  for(let month=0;month<monthCount;month+=step){
    const date=new Date(Date.UTC(first.getUTCFullYear(),first.getUTCMonth()+month,1));
    const x=padding+(date.getTime()-geometry.start)/(geometry.end-geometry.start)*(width-padding*2);
    const label=new Intl.DateTimeFormat('en-AU',{month:'short',year:'numeric',timeZone:'UTC'}).format(date);
    ticks.push(`<span class="month-tick" style="left:${x}px">${escapeText(label)}</span>`);
  }
  scale.innerHTML=ticks.join('');
  guides.setAttribute('viewBox',`0 0 ${width} ${geometry.height}`);
  guides.innerHTML=`<path class="time-axis" d="M${padding} ${geometry.axisY}H${width-padding}"/>`;
}
function attachTimeline(){
  const viewport=document.querySelector('#timeline-viewport');
  const cleanupRipples=attachDotRipples(viewport);
  let previousMobile=mobileLayout.matches;
  const onLayout=()=>{
    layoutTimeline();
    if(previousMobile!==mobileLayout.matches){
      previousMobile=mobileLayout.matches;
      if(!previousMobile&&selectedIndex<0)selectUpdate(activeIssue.events.length-1);
    }
    placeReader();
  };
  const observer=new ResizeObserver(onLayout);observer.observe(viewport);
  mobileLayout.addEventListener('change',onLayout);layoutTimeline();
  return ()=>{cleanupRipples();observer.disconnect();mobileLayout.removeEventListener('change',onLayout);};
}
// Each dot draws a fresh 1–1.3 second interval after every pulse starts.
function attachDotRipples(viewport){
  const controller=new AbortController(),options={signal:controller.signal},timers=new Map();
  const rings=[...viewport.querySelectorAll('.dot-ripple')];
  let visible=false,active=false;
  rings.forEach(ring=>ring.addEventListener('animationend',()=>ring.classList.remove('is-rippling'),options));
  function schedule(ring){
    timers.set(ring,setTimeout(()=>{
      timers.delete(ring);
      if(!active)return;
      ring.classList.add('is-rippling');schedule(ring);
    },1000+Math.random()*300));
  }
  function stop(){
    timers.forEach(timer=>clearTimeout(timer));timers.clear();
    rings.forEach(ring=>ring.classList.remove('is-rippling'));
  }
  function sync(){
    const next=visible&&!mobileLayout.matches&&motionEnabled()&&!document.hidden;
    if(next===active)return;
    active=next;viewport.classList.toggle('dot-hints-active',active);
    if(active)rings.forEach(schedule);else stop();
  }
  const observer=new IntersectionObserver(entries=>{
    visible=entries.some(entry=>entry.isIntersecting);sync();
  });
  observer.observe(viewport);
  window.addEventListener('tracker-motion-change',sync,options);
  mobileLayout.addEventListener('change',sync,options);
  document.addEventListener('visibilitychange',sync,options);
  return ()=>{active=false;stop();observer.disconnect();controller.abort();viewport.classList.remove('dot-hints-active');};
}
function attachTileMotion(grid){
  const controller=new AbortController(),options={signal:controller.signal},states=[];
  grid.querySelectorAll('.tile-link').forEach(link=>{
    const card=link.querySelector('.issue-tile'),sheen=card.querySelector('.tile-sheen');
    const state={x:0,y:0,tx:0,ty:0,lift:0,targetLift:0,frame:0,time:0,rectangle:null};states.push({card,sheen,state});
    function tick(time){
      if(!pointerMotionEnabled()||document.hidden){reset();return;}
      const dt=state.time?Math.min((time-state.time)/1000,1/30):1/60;state.time=time;
      const alpha=1-Math.pow(1-.12,dt*60);
      state.x+=(state.tx-state.x)*alpha;state.y+=(state.ty-state.y)*alpha;state.lift+=(state.targetLift-state.lift)*alpha;
      card.style.transform=`translateY(${-state.lift.toFixed(2)}px) rotateX(${(-state.y*3.5).toFixed(3)}deg) rotateY(${(state.x*4).toFixed(3)}deg)`;
      sheen.style.transform=`translate(${(state.x*14-15).toFixed(2)}%,${(state.y*7-5).toFixed(2)}%)`;
      if(Math.abs(state.x-state.tx)+Math.abs(state.y-state.ty)+Math.abs(state.lift-state.targetLift)>.015)state.frame=requestAnimationFrame(tick);
      else{state.frame=0;state.time=0;if(!state.targetLift){card.style.transform='';sheen.style.transform='';}}
    }
    function run(){if(!state.frame)state.frame=requestAnimationFrame(tick);}
    function reset(){cancelAnimationFrame(state.frame);Object.assign(state,{x:0,y:0,tx:0,ty:0,lift:0,targetLift:0,frame:0,time:0});card.style.transform='';sheen.style.transform='';}
    link.addEventListener('pointerenter',event=>{if(event.pointerType==='touch'||!pointerMotionEnabled())return;state.rectangle=link.getBoundingClientRect();state.targetLift=7;run();},options);
    link.addEventListener('pointermove',event=>{if(event.pointerType==='touch'||!pointerMotionEnabled()||!state.rectangle)return;state.tx=Math.max(-1,Math.min(1,((event.clientX-state.rectangle.left)/state.rectangle.width-.5)*2));state.ty=Math.max(-1,Math.min(1,((event.clientY-state.rectangle.top)/state.rectangle.height-.5)*2));run();},options);
    link.addEventListener('pointerleave',()=>{state.tx=0;state.ty=0;state.targetLift=0;run();},options);
    link.addEventListener('focusin',reset,options);
    window.addEventListener('tracker-motion-change',reset,options);
    document.addEventListener('visibilitychange',()=>{if(document.hidden)reset();},options);
  });
  return ()=>{controller.abort();states.forEach(({card,sheen,state})=>{cancelAnimationFrame(state.frame);card.style.transform='';sheen.style.transform='';});};
}
function tileIsVisible(node){const rect=node.getBoundingClientRect();return rect.bottom>0&&rect.top<innerHeight&&rect.right>0&&rect.left<innerWidth;}
const tileFlightPose = index => `translate(${index%2?160:-160}px,-65px) rotate(${index%2?7:-7}deg)`;
function cancelRouteMotion(){cleanupRouteMotion();cleanupRouteMotion=()=>{};}
function cloneSurface(node){
  const clone=node.cloneNode(true);
  [clone,...clone.querySelectorAll('[id],[aria-controls],[aria-labelledby]')].forEach(element=>{
    element.removeAttribute('id');element.removeAttribute('aria-controls');element.removeAttribute('aria-labelledby');
  });
  clone.style.removeProperty('view-transition-name');clone.style.transform='none';clone.style.margin='0';
  return clone;
}
function flipPose(rect,native,angle,z=0){
  return `translate3d(${rect.left+rect.width/2-native.width/2}px,${rect.top+rect.height/2-native.height/2}px,${z}px) rotateY(${angle}deg) scale(${rect.width/native.width},${rect.height/native.height})`;
}
async function navigateTo(issue,origin=null){
  const generation=++routeGeneration;
  cancelRouteMotion();
  routeViewportWidth=window.innerWidth;
  const previousIssue=activeIssue,returning=!issue&&!!previousIssue;
  const source=issue?origin?.querySelector('.issue-tile'):returning?document.querySelector('.detail-hero'):null;
  const animate=!!origin&&!!source&&motionEnabled()&&typeof source.animate==='function';
  lastFocusIssue=issue?.id||previousIssue?.id||lastFocusIssue;
  if(issue&&!previousIssue)collectionScroll=window.scrollY;
  const render=()=>{
    history.pushState(null,'',issue?issueUrl(issue.id):homeUrl());
    // Measure the return target at its final scroll position, without a trip to the top.
    issue?renderDetail(issue):renderHome();
    if(issue)window.scrollTo({top:0,behavior:'instant'});
    if(!issue){
      window.scrollTo({top:collectionScroll,behavior:'instant'});
      const selected=document.querySelector(`[data-issue="${lastFocusIssue}"]`);
      if(selected){
        const rect=selected.getBoundingClientRect();
        if(rect.top<16||rect.bottom>innerHeight-16)window.scrollTo({top:Math.max(0,window.scrollY+rect.top-(innerHeight-rect.height)/2),behavior:'instant'});
      }
    }
  };
  if(!animate){render();if(issue)focusHeading();else document.querySelector(`[data-issue="${lastFocusIssue}"]`)?.focus({preventScroll:true});return;}
  const rootStyle=getComputedStyle(document.documentElement);
  const easeOut=rootStyle.getPropertyValue('--ease-out').trim(),easeMove=rootStyle.getPropertyValue('--ease-in-out').trim();
  const sourceRect=source.getBoundingClientRect(),sourceClone=cloneSurface(source);
  const departingTiles=issue?[...document.querySelectorAll('.tile-link')].filter(link=>link!==origin&&tileIsVisible(link)).map(link=>({rect:link.getBoundingClientRect(),clone:cloneSurface(link)})):[];
  cleanupTiles();
  const scene=document.createElement('div');scene.className='flip-scene';scene.setAttribute('aria-hidden','true');scene.inert=true;
  // Keep the perspective camera fixed while mobile browser controls change height.
  scene.style.width=window.innerWidth+'px';scene.style.height=window.innerHeight+'px';
  const animations=[],staged=new Map();let cleaned=false,expectedScrollY=0;
  const onScroll=()=>{if(Math.abs(window.scrollY-expectedScrollY)>1)cleanup();};
  const stage=(node,property='opacity')=>{
    if(!node)return;
    if(!staged.has(node))staged.set(node,{opacity:node.style.opacity,visibility:node.style.visibility,inert:node.inert});
    node.style[property]=property==='visibility'?'hidden':'0';node.inert=true;
  };
  const reveal=node=>{
    const original=staged.get(node);if(!original)return;
    node.style.opacity=original.opacity;node.style.visibility=original.visibility;node.inert=original.inert;
  };
  const cleanup=()=>{
    if(cleaned)return;cleaned=true;
    window.removeEventListener('scroll',onScroll);
    animations.forEach(animation=>animation.cancel());
    staged.forEach((_,node)=>reveal(node));scene.remove();
    if(generation===routeGeneration&&document.activeElement===document.body){
      if(issue)focusHeading();else document.querySelector(`[data-issue="${lastFocusIssue}"]`)?.focus({preventScroll:true});
    }
  };
  cleanupRouteMotion=cleanup;
  try{
    render();expectedScrollY=window.scrollY;
    window.addEventListener('scroll',onScroll,{passive:true});
    const destination=issue?document.querySelector('.detail-hero'):document.querySelector(`[data-issue="${previousIssue.id}"] .issue-tile`);
    if(!destination)return;
    const destinationRect=destination.getBoundingClientRect(),destinationClone=cloneSurface(destination);
    stage(destination,'visibility');
    const supporting=issue?[document.querySelector('.back-row'),document.querySelector('.story-section'),document.querySelector('.site-footer')]:[document.querySelector('.landing-intro'),document.querySelector('.search-area'),document.querySelector('.collection-heading'),document.querySelector('.site-footer'),...[...document.querySelectorAll('.tile-link')].filter(link=>link.dataset.issue!==previousIssue.id&&tileIsVisible(link))];
    supporting.forEach(node=>stage(node));
    const addFace=(clone,rect)=>{
      const face=document.createElement('div');face.className='flip-face';face.style.width=rect.width+'px';face.style.height=rect.height+'px';
      clone.style.width=rect.width+'px';clone.style.height=rect.height+'px';clone.style.minHeight=rect.height+'px';face.appendChild(clone);scene.appendChild(face);
      const reflection=document.createElement('span');reflection.className='flip-reflection';clone.appendChild(reflection);
      animations.push(reflection.animate([{transform:'translateX(-125%)',opacity:0},{transform:'translateX(0)',opacity:.8,offset:.5},{transform:'translateX(125%)',opacity:0}],{duration:620,easing:easeMove,fill:'both'}));
      return face;
    };
    const front=addFace(sourceClone,sourceRect),back=addFace(destinationClone,destinationRect);
    document.body.appendChild(scene);
    const middle={left:(sourceRect.left+destinationRect.left)/2,top:(sourceRect.top+destinationRect.top)/2-12,width:(sourceRect.width+destinationRect.width)/2,height:(sourceRect.height+destinationRect.height)/2};
    const direction=returning?-1:1;
    const frontTurn=front.animate([
      {transform:flipPose(sourceRect,sourceRect,0)},
      {transform:flipPose(middle,sourceRect,direction*90,48),offset:.5},
      {transform:flipPose(destinationRect,sourceRect,direction*180)}
    ],{duration:620,easing:easeMove,fill:'both'});
    const backTurn=back.animate([
      {transform:flipPose(sourceRect,destinationRect,-direction*180)},
      {transform:flipPose(middle,destinationRect,-direction*90,48),offset:.5},
      {transform:flipPose(destinationRect,destinationRect,0)}
    ],{duration:620,easing:easeMove,fill:'both'});
    animations.push(frontTurn,backTurn);
    departingTiles.forEach(({rect,clone},index)=>{
      const flight=document.createElement('div');flight.className='flip-flight';Object.assign(flight.style,{left:rect.left+'px',top:rect.top+'px',width:rect.width+'px',height:rect.height+'px'});flight.appendChild(clone);scene.appendChild(flight);
      animations.push(flight.animate([{opacity:1,transform:'translate(0,0) rotate(0deg)'},{opacity:0,transform:tileFlightPose(index)}],{duration:230,easing:easeOut,fill:'forwards'}));
    });
    await Promise.allSettled([frontTurn.finished,backTurn.finished]);
    if(generation!==routeGeneration||cleaned)return;
    reveal(destination);
    // Paint the real surface beneath the final frame before dropping its animated copy.
    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    if(generation!==routeGeneration||cleaned)return;
    scene.remove();
    const arrivals=supporting.filter(Boolean).map((node,index)=>{
      const tileArrival=!issue&&node.classList.contains('tile-link');
      const animation=node.animate(!tileArrival?[
        {opacity:0,transform:'translateY(12px)'},{opacity:1,transform:'translateY(0)'}
      ]:[{opacity:0,transform:tileFlightPose(index)},{opacity:1,transform:'translate(0,0) rotate(0deg)'}],{duration:tileArrival?230:180,delay:tileArrival?((index-4)%4)*40:Math.min(index,2)*30,easing:easeOut,fill:'backwards'});
      node.style.opacity=staged.get(node).opacity;
      animation.finished.then(()=>{if(generation===routeGeneration&&!cleaned)reveal(node);},()=>{});
      return animation;
    });
    animations.push(...arrivals);
    await Promise.allSettled(arrivals.map(animation=>animation.finished));
    if(generation===routeGeneration){if(issue)focusHeading();else document.querySelector(`[data-issue="${lastFocusIssue}"]`)?.focus({preventScroll:true});}
  }finally{
    cleanup();if(cleanupRouteMotion===cleanup)cleanupRouteMotion=()=>{};
  }
}
document.addEventListener('click',event=>{
  const home=event.target.closest('[data-home]');
  if(!home||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
  event.preventDefault();navigateTo(null,event.detail>0?home:null);
});
function handleHistory(){++routeGeneration;cancelRouteMotion();const issue=routeIssue();issue?renderDetail(issue,true):renderHome(true);}
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&activeIssue&&selectedIndex>=0)closeUpdate(true);});
window.addEventListener('popstate',handleHistory);
function handleRouteResize(){
  // Browser bars and the on-screen keyboard resize height without changing card layout.
  if(Math.abs(window.innerWidth-routeViewportWidth)>1)cancelRouteMotion();
  routeViewportWidth=window.innerWidth;
}
window.addEventListener('resize',handleRouteResize,{passive:true});
window.addEventListener('tracker-motion-change',()=>{if(!motionEnabled())cancelRouteMotion();});
window.addEventListener('hashchange',()=>{if(ISSUES.some(issue=>issue.id===location.hash.slice(1)))handleHistory();});
document.querySelector('#motion-toggle').addEventListener('click',()=>{manualReduction=!manualReduction;saveStorage('lanecove-reduce-motion',manualReduction);updateMotionControl();announce(motionEnabled()?'Motion enabled':'Motion reduced');});
reducedMedia.addEventListener('change',updateMotionControl);
document.querySelector('#text-size').addEventListener('click',event=>{
  cancelRouteMotion();
  const enabled=document.documentElement.classList.toggle('large-text');event.currentTarget.setAttribute('aria-pressed',String(enabled));event.currentTarget.querySelector('.size-label').textContent=enabled?'Standard text':'Larger text';event.currentTarget.setAttribute('aria-label',enabled?'Standard text':'Larger text');saveStorage('lanecove-large-text',enabled);layoutTimeline();announce(enabled?'Larger text enabled':'Standard text enabled');
});
if(readStorage('lanecove-large-text')==='true')document.querySelector('#text-size').click();
updateMotionControl();
document.querySelector('#library-links').innerHTML=Object.entries(TRACKERS).sort((a,b)=>b[1].iso.localeCompare(a[1].iso)).map(([id,doc])=>sourceLink(id,[],doc.label)).join('');
document.querySelector('#source-count').textContent=`Source documents reviewed (${Object.keys(TRACKERS).length})`;
const initial=routeIssue();initial?renderDetail(initial):renderHome();
