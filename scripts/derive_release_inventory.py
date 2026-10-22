"""Independently inventory accepted physical rows; write a review candidate, never approve it."""
import argparse, datetime, hashlib, json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def derive(catalogue=ROOT/'catalogue'):
 documents=[];keys=set();row_count=0
 for path in sorted((catalogue/'structured').glob('*-rows.json')):
  data=json.loads(path.read_text());source=data['source']
  if source.get('duplicate_of'):continue
  if int(source['date'][-4:])>2026:raise ValueError('New-year membership scope requires explicit review before deriving a release')
  documents.append({'edition':source['date'],'rows':len(data['records']),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
  row_count+=len(data['records'])
  if source['date'].endswith('2026'):keys.update(r['key'] for r in data['records'])
 through=max(datetime.datetime.strptime(d['edition'],'%d%m%Y').date() for d in documents).isoformat()
 return {'schemaVersion':1,'through':through,'membershipPolicy':'Retain every minute item appearing in a 2026 tracker and related historical decisions; new 2027 scope requires review.','minuteItems':sorted(keys),'documents':documents,'physicalRows':row_count}
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output',type=pathlib.Path,required=True)
 args=parser.parse_args()
 if args.output.resolve()==ROOT/'catalogue/release-inventory.json':parser.error('Write a separate review candidate, then inspect and accept the diff')
 args.output.parent.mkdir(parents=True,exist_ok=True)
 args.output.write_text(json.dumps(derive(),indent=2)+'\n')
