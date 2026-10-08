"""Regenerate the four paper figures from the original project plotting code."""
import json
from common import ROOT, offline, read, dump, compare
offline()
import build_submission

def main():
    build_submission.F=ROOT/'output/figures'
    actual=build_submission.figure_data()
    expected=read(ROOT/'manuscript/generated/figure_source_data.json')
    differences=compare(actual,expected)
    if differences: raise RuntimeError(str(differences))
    build_submission.figures(actual)
    report={'status':'PASS','figure_source_data':'matches frozen reference','figures_regenerated':4,
            'network':'disabled','scope':'Frozen estimates and confidence intervals; no commercial-model collection.'}
    dump(ROOT/'output/figures_reproduction.json',report)
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
