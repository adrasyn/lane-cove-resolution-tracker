const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const sources = fs.readFileSync(path.join(root, 'dist/sources.js'), 'utf8');
const trackers = vm.runInNewContext(sources + '\nTRACKERS');
// A temporary document download folder can vanish while the permanent record remains valid.
assert.equal(trackers['20082026'].url, 'https://ecouncil.lanecove.nsw.gov.au/trim/GenDocLink.asp?RecId=62016/26');
for (const [edition, doc] of Object.entries(trackers)) {
  assert.equal(doc.url, doc.record, `${edition} must link to the permanent Council record`);
  assert.match(doc.url, /^https:\/\/ecouncil\.lanecove\.nsw\.gov\.au\/trim\/GenDocLink\.asp\?RecId=/i);
}
// Execute the actual link renderer with page metadata still present in the catalogue.
const app = fs.readFileSync(path.join(root, 'dist/app.js'), 'utf8');
const renderer = app.match(/^function sourceLink\([^]*?^}/m)[0];
const render = vm.runInNewContext(renderer + '\nsourceLink', {
  TRACKERS: trackers, escapeText: text => String(text).replaceAll('&', '&amp;'), icon: () => ''
});
const html = render('20082026', [2]);
assert.match(html, /href="https:\/\/ecouncil\.lanecove\.nsw\.gov\.au\/trim\/GenDocLink\.asp\?RecId=62016\/26"/);
assert.ok(!html.includes('#page='), 'Council redirect links must not promise a PDF page jump');
console.log(`Source link regression checks passed for ${Object.keys(trackers).length} tracker editions.`);
