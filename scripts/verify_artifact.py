"""Verify release hashes, solver certifications and all saved final scored trials."""
import csv, json
from common import ROOT, offline, read, sha, dump
offline()
import feasibility_solver, validator

def main():
    failures=[]; checked_files=0
    for entry in read(ROOT/'data/export_provenance.json')['source_records']:
        if sha(ROOT/entry['path'])!=entry['sha256']: failures.append(entry['path']+': hash mismatch')
        checked_files+=1
    manifest=ROOT/'RELEASE_MANIFEST.json'
    if manifest.exists():
        for path,digest in read(manifest)['sha256'].items():
            if sha(ROOT/path)!=digest: failures.append(path+': release hash mismatch')
    scenarios={}; solver_checks=0
    for folder in ['handbuilt','generated','v2']:
        for path in sorted((ROOT/'data/scenarios'/folder).glob('*.json')):
            s=read(path); scenarios[s['scenario_id']]=s
            result=feasibility_solver.solve(s)
            for key,value in s['expected'].items():
                if key in result and result[key]!=value: failures.append(path.name+': solver '+key)
            if not result['valid_for_pilot']: failures.append(path.name+': invalid certification')
            solver_checks+=1
    expected={}
    for path in sorted((ROOT/'data/trials').glob('*/*_trials.csv')):
        for row in csv.DictReader(path.open(encoding='utf8')):
            key=(row['phase'],row['trial_id'])
            if key in expected: failures.append(str(key)+': duplicate trial')
            expected[key]=row
    def same(value, text):
        if value is None: return text==''
        if isinstance(value,bool): return text.lower()==str(value).lower()
        if isinstance(value,(int,float)):
            try: return abs(float(text)-value)<1e-10
            except ValueError: return False
        return str(value)==text
    scored=0; fields=0; seen=set()
    for line in (ROOT/'data/scoring_inputs.jsonl').read_text(encoding='utf8').splitlines():
        record=json.loads(line); key=(record['phase'],record['trial_id'])
        if key in seen: failures.append(str(key)+': duplicate scoring input')
        seen.add(key); row=expected[key]
        lm={int(k):v for k,v in record['label_to_identity'].items()}
        function=validator.validate_decision if record['task']=='decision' else validator.validate_recognition
        result=function(scenarios[record['scenario_id']],lm,record['parsed'])
        for field,value in result.items():
            fields+=1
            if field not in row or not same(value,row[field]): failures.append(str(key)+': scoring '+field)
        scored+=1
    if seen!=set(expected): failures.append('Trial coverage mismatch')
    report={'status':'PASS' if not failures else 'FAIL','source_files_verified':checked_files,
            'solver_scenarios':solver_checks,'saved_trials_rescored':scored,'scored_fields':fields,
            'network':'disabled','failures':failures}
    dump(ROOT/'output/artifact_verification.json',report)
    print(json.dumps(report,indent=2))
    if failures: raise SystemExit(1)

if __name__=='__main__': main()
