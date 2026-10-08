"""Rebuild 165 manuscript mappings and export nine frozen scientific tables."""
import csv, json, runpy, shutil, tempfile
from pathlib import Path
from common import ROOT, offline, read, dump
offline()

def main():
    (ROOT/'output').mkdir(exist_ok=True)
    expected=read(ROOT/'manuscript/generated/results_values.json')
    with tempfile.TemporaryDirectory() as temp:
        work=Path(temp)
        shutil.copytree(ROOT/'analysis',work/'analysis',ignore=shutil.ignore_patterns('__pycache__'))
        (work/'manuscript').mkdir()
        for name in ['build_results.py','06_section5_results.tmpl.md']:
            shutil.copy2(ROOT/'manuscript'/name,work/'manuscript'/name)
        runpy.run_path(str(work/'manuscript/build_results.py'))
        actual=read(work/'manuscript/generated/results_values.json')
        if actual!=expected: raise RuntimeError('Frozen 165-mapping mismatch')
        shutil.copy2(work/'manuscript/06_section5_results.md',ROOT/'output/Results.md')
        dump(ROOT/'output/results_values.json',actual)
    tables=read(ROOT/'data/tables.json')
    for table in tables:
        target=ROOT/'output/tables'/('Table_'+table['number']+'.csv')
        target.parent.mkdir(exist_ok=True)
        with target.open('w',encoding='utf8',newline='') as stream:
            writer=csv.writer(stream); writer.writerow(table['headers']); writer.writerows(table['rows'])
    report={'status':'PASS','mappings_verified':len(actual),'tables_exported':len(tables),
            'scope':'Frozen-result formatting and table export; use reanalyse.py for empirical statistical recalculation.',
            'network':'disabled'}
    dump(ROOT/'output/results_reproduction.json',report)
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
