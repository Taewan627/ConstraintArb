"""Recalculate saved empirical statistics with unchanged project analysis functions."""
import argparse, json, shutil
from common import ROOT, offline, read, dump, compare
offline()
import statistical_analysis as s1
import stage2_analysis as s2
import stage3a_analysis as s3a
import stage3b_analysis as s3b
import stage3c_analysis as s3c

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage',choices=['all','stage1_p2','stage2','stage3a','stage3b','stage3c'],default='all')
    args=parser.parse_args()
    trial=lambda phase: str(next((ROOT/'data/trials'/phase).glob('*_trials.csv')))
    raw=str(ROOT/'data/attempt_metadata')
    def stage1():
        directory=ROOT/'output/stage1_p2'; directory.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/'data/trials/P2/decision_trials.csv',directory/'pilot_trials.csv')
        return s1.analyse(str(directory),2000)[0]
    functions={
      'stage1_p2':stage1,
      'stage2':lambda:s2.analyse(trial('S2_G'),trial('S2_X'),trial('S2_REC'),2000),
      'stage3a':lambda:s3a.analyse(trial('S3A_G'),trial('S3A_N'),trial('S3A_REC'),trial('S2_G'),2000,raw),
      'stage3b':lambda:s3b.analyse(trial('S3B_G'),trial('S3B_X'),trial('S3B_REC'),trial('S3B_CTRL'),trial('S3A_G'),trial('S3A_N'),2000,raw),
      'stage3c':lambda:s3c.analyse({a:trial('S3C_'+a) for a in s3c.ARMS},2000,raw)}
    summaries=[]
    for stage,function in functions.items():
        if args.stage not in ['all',stage]: continue
        print('Reanalysing '+stage+' (2000 bootstrap replicates)',flush=True)
        actual=function(); expected=read(ROOT/'analysis'/stage/'results.json')
        # Stage 1 frozen statistics use four-decimal storage. Other stages store unrounded values.
        tolerance=5e-5 if stage=='stage1_p2' else 1e-8
        differences=compare(actual,expected,tolerance=tolerance)
        dump(ROOT/'output'/stage/'results.json',actual)
        report={'stage':stage,'status':'PASS' if not differences else 'MISMATCH',
                'absolute_tolerance':tolerance,'bootstrap_replicates':2000,'differences':differences}
        dump(ROOT/'output'/stage/'comparison.json',report); summaries.append(report)
        print(json.dumps(report),flush=True)
    dump(ROOT/'output'/('reanalysis_'+args.stage+'.json'),{'network':'disabled','comparisons':summaries})
    if any(r['differences'] for r in summaries): raise SystemExit(1)

if __name__=='__main__': main()
