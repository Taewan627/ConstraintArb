"""Offline submission artifacts. No runner, model client, or analysis is invoked.

Run from any directory: python manuscript/build_submission.py
Section sources remain authoritative; only generated blocks in IV are replaced.
All statistical estimates/CIs are copied from frozen JSON, not recomputed.
"""
from pathlib import Path
import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parents[1]
M = ROOT / 'manuscript'
G = M / 'generated'
F = M / 'figures'
SHORT = {'gpt-5.6-sol':'SOL','qwen3.8-flash':'QWN','deepseek-v4-pro':'DSP',
         'deepseek-v4.1-flash':'DSF','gemini-3.8-flash':'GEM','glm-5.3':'GLM','claude-sonnet-5.5':'SON'}
SOURCES = {}

def read(path):
    p = ROOT / path
    SOURCES[path] = hashlib.sha256(p.read_bytes()).hexdigest()
    return p.read_text(encoding='utf-8')

def load(path):
    return json.loads(read(path))

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip()+'\n', encoding='utf-8', newline='\n')

def dump(path, obj):
    write(path, json.dumps(obj, indent=2, ensure_ascii=False))

def table(headers, rows):
    esc = lambda v: str(v).replace('|', '\\|').replace('\n', '<br>')
    return '\n'.join(['| '+' | '.join(headers)+' |', '| '+' | '.join(['---']*len(headers))+' |'] +
                     ['| '+' | '.join(map(esc,r))+' |' for r in rows])

def section(text, heading):
    match = re.search(r'^## '+re.escape(heading)+r'[^\n]*\n(.*?)(?=^## |\Z)', text, re.M|re.S)
    if not match:
        raise ValueError(heading)
    return match.group(1).strip()

def model_tables():
    rows = []
    # Only executed main phases; void NB calls remain visible as metadata.
    for p in sorted((ROOT/'runs/raw').glob('*/manifest.json')):
        man = load(p.relative_to(ROOT).as_posix())
        phase = man['phase']
        if phase not in ['P2','S2_G','S2_X','S2_REC','S3A_G','S3A_N','S3A_REC','S3B_G','S3B_X','S3B_REC','S3B_CTRL',
                         'S3C_G','S3C_REP','S3C_N1','S3C_NB','S3C_NC']:
            continue
        counts = defaultdict(Counter)
        raw = p.parent/'trials.jsonl'
        if raw.exists():
            raw_text = read(raw.relative_to(ROOT).as_posix())
            for line in raw_text.splitlines():
                item = json.loads(line)
                provider = (item.get('raw_provider_response') or {}).get('provider')
                if provider:
                    counts[item['model']][provider] += 1
        for name, cfg in man['models'].items():
            if name not in SHORT: continue
            # Some manifests list configured but unselected models; do not imply execution.
            executed = any(json.loads(line)['model']==name for line in raw_text.splitlines()) if raw.exists() else False
            if not executed: continue
            extra = cfg.get('extra_body', {})
            routing = extra.get('provider', {})
            seed = cfg.get('send_seed', True)  # src/model_client.py::_openai default
            rows.append({'abbreviation':SHORT[name], 'model':name,'requested_identifier':cfg['model'],
                         'developer':'Not explicitly recorded', 'registry_namespace':cfg['model'].split('/')[0],
                         'phase':phase,'run_id':man['run_id'],'manifest':p.relative_to(ROOT).as_posix(),
                         'max_tokens':cfg.get('max_tokens'),'temperature':cfg.get('temperature'),
                         'reasoning':extra.get('reasoning','Not explicitly set'), 'send_seed':seed,
                         'routing':routing or 'Default (unpinned)', 'observed_provider_attempt_counts':dict(sorted(counts[name].items()))})
    read('src/model_client.py')
    dump(G/'model_routing.json', rows)
    detailed = []
    for r in rows:
        detailed.append([r['abbreviation'],r['phase'],r['run_id'],r['requested_identifier'],r['max_tokens'],
                        json.dumps(r['reasoning']), 'sent' if r['send_seed'] else 'logged, not sent',
                        json.dumps(r['routing']), '; '.join(f'{k}: {v}' for k,v in r['observed_provider_attempt_counts'].items()) or 'No returned provider metadata'])
    write(G/'model_routing_supplement.md', '# Supplement S1. Executed model and routing records\n\n'+
          'Extracted from frozen run manifests and raw provider metadata. Counts include returned API attempts, including format retries; '
          'they are not scored-trial denominators. Requested identifiers are not assertions of verified model weights. '
          'Developer legal entities are not recorded in these manifests; registry namespaces are reported without inferring corporate metadata. '
          'Seed sending uses the recorded switch or the frozen client default; acceptance/determinism is not established.\n\n'+
          table(['Model','Phase/condition','Run','Exact requested ID','Token cap','Explicit reasoning setting','Seed','Routing','Observed providers (attempts)'],detailed))
    compact=[]
    for name, short in SHORT.items():
        rs=[r for r in rows if r['model']==name]
        ids=sorted(set(r['requested_identifier'] for r in rs))
        phases=', '.join(r['phase'] for r in rs)
        settings='; '.join(sorted(set(f"{r['phase']}: {r['max_tokens']}" for r in rs)))
        compact.append([short,'; '.join('`'+i+'`' for i in ids),rs[0]['registry_namespace'],phases,
                        ', '.join(str(i) for i in sorted(set(r['max_tokens'] for r in rs))),
                        'medium' if short=='SOL' else 'not explicitly set',
                        'logged, not sent (S3B-A1)' if short=='GEM' else 'sent; acceptance not established',
                        'Relace, no fallback: 3a, 3b CTRL, 3c; default: 1–2' if short=='DSP' else 'default selection'])
    return (table(['Model','Exact requested identifier','Developer metadata¹','Executed phases','Token cap²','Reasoning','Seed','Routing'],compact)+
           '\n\n¹ Registry namespace only; developer entity not explicitly recorded. ² Phase-level limits and observed provider attempt counts are in Supplement S1. '
           'G = graph-only; X = explicit; REC = forked recognition; N/N1 = original cue; CTRL = generic deliberation; REP = restatement; NB/NC = cue variants. '
           'DSP NB produced only void transport failures; DSP NC was not run. Requested ID retains the recorded revision suffix.')

PREREGS=[('1','docs/prereg_pilot.md','8. Decision rule','1. Primary question','7. Statistical analysis','planned at outset'),
         ('2','docs/prereg_stage2.md','6. Decision rule','1. Question','4. Primary quantities','decision-mapped follow-up'),
         ('3a','docs/prereg_stage3a.md','5. Decision rule','2. Questions','4. Quantities','adaptive after Stage 2'),
         ('3b','docs/prereg_stage3b.md','5. Decision rule','1. Questions','4. Quantities','breadth mapped; CTRL adaptively added before data'),
         ('3c','docs/prereg_stage3c.md','5. Decision rules','1. Questions','4. Quantities','adaptive after Stage 3b')]

def rule_tables():
    rows=[]; blocks=[]; mappings=[]
    for stage,path,rule,q,est,status in PREREGS:
        txt=read(path); rules=section(txt,rule)
        mappings.append({'stage':stage,'source':path,'sha256':SOURCES[path],'question_verbatim':section(txt,q),
                         'estimand_verbatim':section(txt,est),'decision_rule_verbatim':rules,'temporal_status':status})
        rows.append([stage,section(txt,q),section(txt,est),rules,status+'; completed'])
        blocks.append(f'## Stage {stage}\n\nSource: `{path}`; SHA-256 `{SOURCES[path]}`.\n\nQuestion:\n\n{section(txt,q)}\n\nQuantities:\n\n{section(txt,est)}\n\nFrozen rules and mapping (verbatim):\n\n{rules}\n')
    text=read('docs/prereg_stage3d.md')
    rows.append(['3d','Alternative-provider deployment follow-up','No observations','Not applied: pre-registered, deferred under S3D-A1','infrastructure-motivated; not run'])
    dump(G/'classification_rules.json', mappings)
    write(G/'classification_rules_supplement.md','# Supplement S2. Frozen stage rules\n\n'+
          'Order of classifications, inequalities, integrity gates and next-step mappings are reproduced without revision. '
          'Stage 1 recognition was unavailable under A2; Stage 3c missing-cell treatment follows S3C-A1. Stage 3d contributes no evidence.\n\n'+'\n'.join(blocks))
    # All rules remain available in the main review draft; template conversion may move detail to S2.
    return table(['Stage','Primary question (verbatim)','Primary quantity (verbatim)','Integrity, ordered thresholds and mapping (verbatim)','Status / anticipation'],rows)

def est(path, keys, label, stage, condition):
    d=load(path); v=d
    for key in keys: v=v[key]
    return {'label':label,'stage':stage,'condition':condition,'estimate':v['estimate'],'ci95':v['ci95'],
            'source':path,'pointer':'/'+ '/'.join(keys),'sha256':SOURCES[path]}

def figure_data():
    f3=[]
    for name in SHORT:
        if name in ['gpt-5.6-sol','qwen3.8-flash','deepseek-v4-pro']:
            for arm,field in [('Explicit','delta_explicit'),('Graph-only','delta_graph')]:
                f3.append(est('analysis/stage2/results.json',[field,'per_model',name],SHORT[name],'2',arm))
        else:
            for arm,field in [('Explicit','delta_x'),('Graph-only','delta_g')]:
                f3.append(est('analysis/stage3b/results.json',['new_models',name,field],SHORT[name],'3b',arm))
    f4=[]
    for arm,field,stage in [('G','delta_g3a_ns0','3a subset'),('CTRL','delta_ctrl','3b'),('N1','delta_n3a_ns0','3a subset')]:
        f4.append(est('analysis/stage3b/results.json',['deepseek_v4_pro',field],'DSP',stage,arm))
    for name in ['deepseek-v4-pro','deepseek-v4.1-flash']:
        for arm in ['G','REP','N1','NB','NC']:
            f4.append(est('analysis/stage3c/results.json',['per_model',name,'arms',arm,'delta'],SHORT[name],'3c',arm))
    a=load('data/scenarios/v2/S2-T01-A_HIGH-n0.json');b=load('data/scenarios/v2/S2-T01-B_HIGH-n0.json')
    aa=copy.deepcopy(a);bb=copy.deepcopy(b)
    # Verify node content/topology unchanged except update flags, not entire scenario metadata.
    for sc in [aa,bb]:
        for node in sc['nodes']: node.pop('update',None)
    assert aa['nodes']==bb['nodes'] and a['constraints']==b['constraints'] and a['editable']==b['editable']
    d={'figure1':{'sources':['src/feasibility_solver.py','src/validator.py','src/repair_cost.py','manuscript/04_section3_benchmark.md','manuscript/05_section4_protocol.md'],
                  'type':'design schematic; no empirical observations'},
       'figure2':{'A_HIGH':a,'B_HIGH':b,'type':'existing T01 fan scenario; schematic omits locked background nodes'},
       'figure3':f3,'figure4':f4}
    for p in d['figure1']['sources']: read(p)
    dump(G/'figure_source_data.json',d)
    return d

def save(fig,name):
    F.mkdir(exist_ok=True)
    fig.savefig(F/(name+'.pdf'),bbox_inches='tight',metadata={'CreationDate':None,'ModDate':None})
    fig.savefig(F/(name+'.png'),bbox_inches='tight',dpi=300)
    plt.close(fig)

def box(ax,x,y,w,h,text,fill='white',size=9):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.02',facecolor=fill,edgecolor='black',lw=.9))
    ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=size)

def arrow(ax,x,y,xx,yy,style='-'):
    ax.annotate('',xy=(xx,yy),xytext=(x,y),arrowprops={'arrowstyle':'->','lw':1,'linestyle':style})

def figures(d):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False})
    fig,ax=plt.subplots(figsize=(10,4));ax.set(xlim=(0,10),ylim=(0,4));ax.axis('off')
    for x,w,title,fill in [(0.1,4.6,'Section III: benchmark instrument','#f0f0f0'),(4.9,5,'Section IV: execution and estimation','white')]:
        ax.add_patch(Rectangle((x,.12),w,3.65,facecolor=fill,edgecolor='black',linestyle='--',lw=.8));ax.text(x+.12,3.55,title,fontsize=10,weight='bold')
    for x,text in [(.3,'Scenario /\ncontent graph'),(1.8,'Exhaustive\nsolver\ncertification'),(3.25,'Cost condition /\nprompt\nconstruction')]: box(ax,x,2.1,1.2,.8,text,size=8)
    arrow(ax,1.5,2.5,1.8,2.5);arrow(ax,3,2.5,3.25,2.5)
    box(ax,5.1,2.1,1.4,.8,'LLM decision\n(patch)',size=8)
    box(ax,5.1,.5,1.4,.8,'Forked recognition\nprobe\n(separate call)',size=8)
    arrow(ax,4.45,2.5,5.1,2.5);arrow(ax,4.45,2.2,5.1,.9,style='--')
    box(ax,6.85,2.1,1.3,.8,'Deterministic\npatch validator',size=8);arrow(ax,6.5,2.5,6.85,2.5)
    box(ax,6.85,.5,1.3,.8,'Deterministic\nprobe scoring',size=8);arrow(ax,6.5,.9,6.85,.9)
    box(ax,8.5,2.1,1.1,.8,'Behavioural\nsacrifice A/B',size=8);arrow(ax,8.15,2.5,8.5,2.5)
    box(ax,8.5,.5,1.1,.8,'Estimands /\nintervals',size=8);arrow(ax,9.05,2.1,9.05,1.3);arrow(ax,8.15,.9,8.5,.9)
    ax.text(.35,.5,'Solver / validator definitions: III\nStage-specific calls, retries and inference: IV',fontsize=8)
    save(fig,'fig1_pipeline')

    fig,axes=plt.subplots(1,2,figsize=(10,4.2))
    for ax,cond in zip(axes,['A_HIGH','B_HIGH']):
        sc=d['figure2'][cond];ax.set(xlim=(0,5),ylim=(0,4.8));ax.axis('off');ax.set_title(cond,weight='bold')
        box(ax,1.35,3.45,2.3,.8,'T: Roots Beneath Varn\nGoal: completable in Act 1',size=8)
        for side,x,label in [('A',.1,'N_A: Iron Seal'),('B',2.65,'N_B: Pell the Scout')]:
            c=sc['constraints'][side]; deps=[n for n in sc['nodes'] if n.get('mirrors')==c['node']+'.'+c['field']]
            assert len(deps)==8
            n=sum(n['update']=='manual' for n in deps)
            node_text=label+'\n'+('location: Act 2' if side=='A' else 'unlock: Act 2')+f'\nConstraint {side}: retain this field'
            box(ax,x,2.0,2.25,.7,node_text,size=8);arrow(ax,x+1.125,2.7,2.5,3.45)
            # Exactly eight squares: hatch manual, empty engine; indices preserve identity.
            for i,node in enumerate(deps):
                xx=x+.08+i*.27
                ax.add_patch(Rectangle((xx,1.08),.21,.3,facecolor='white',edgecolor='black',hatch='////' if node['update']=='manual' else None,lw=.7))
                arrow(ax,x+1.125,2.0,xx+.105,1.38)
            ax.text(x+1.125,.85,f'8 dependents: {n} manual, {8-n} engine',ha='center',fontsize=8)
            ax.text(x+1.125,.5,'Relaxation: 1 direct field edit',ha='center',fontsize=8)
        ax.text(2.5,.13,'Equal priority; same editable fields and graph topology',ha='center',fontsize=8)
        ax.text(2.5,3.08,'requires_any: either branch suffices',ha='center',fontsize=8,bbox={'facecolor':'white','edgecolor':'none','pad':1})
    fig.text(.5,.01,'Hatched = manual repair; empty = engine update. Only update flags are exchanged between conditions.',ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.04,1,1));save(fig,'fig2_forced_sacrifice')

    fig,ax=plt.subplots(figsize=(7.2,4.5))
    order=['SOL','QWN','DSP','GEM','GLM','SON','DSF']
    for y,label in enumerate(order):
        for arm,off,marker,fill in [('Explicit',-.14,'s','white'),('Graph-only',.14,'o','black')]:
            r=next(r for r in d['figure3'] if r['label']==label and r['condition']==arm)
            v=r['estimate']; lo,hi=r['ci95'];ax.errorbar(v,y+off,xerr=[[v-lo],[hi-v]],fmt=marker,color='black',mfc=fill,mec='black',capsize=3,ms=5,label=arm if y==0 else None)
    ax.set(yticks=range(7),yticklabels=[l+' (Stage '+next(r['stage'] for r in d['figure3'] if r['label']==l)+')' for l in order],
           xlim=(-1.04,1.08),xticks=[-1,-.5,0,.5,1],xlabel='Cost utilisation Δ (risk difference)')
    ax.axvline(0,color='.6',ls=':',lw=.8);ax.invert_yaxis();ax.legend(loc='lower left',frameon=False);fig.tight_layout();save(fig,'fig3_explicit_graph')

    fig,axes=plt.subplots(1,3,figsize=(10,4.5),sharex=True)
    panels=[('DSP: cross-stage CTRL',[r for r in d['figure4'] if r['stage']!='3c']),
            ('DSP: same-stage 3c',[r for r in d['figure4'] if r['stage']=='3c' and r['label']=='DSP']),
            ('DSF: same-stage 3c',[r for r in d['figure4'] if r['stage']=='3c' and r['label']=='DSF'])]
    for ax,(title,rows) in zip(axes,panels):
        for y,r in enumerate(rows):
            if r['estimate'] is None:
                ax.text(.05,y,'NOT EVALUABLE',fontsize=8,ha='left',va='center',transform=ax.get_yaxis_transform())
            else:
                v=r['estimate'];lo,hi=r['ci95'];ax.errorbar(v,y,xerr=[[v-lo],[hi-v]],fmt='o',color='black',mfc='white' if r['condition'] in ['G','CTRL','REP'] else 'black',capsize=3,ms=5)
        labels=[r['condition']+ (' (3a)' if r['stage']=='3a subset' else ' (3b)' if r['stage']=='3b' else '') for r in rows]
        ax.set(yticks=range(len(rows)),yticklabels=labels,xlim=(-1.04,1.08),xticks=[-1,0,1],ylim=(4.7,-.7),xlabel='Cost utilisation Δ')
        ax.set_title(title,fontsize=10);ax.axvline(0,color='.6',ls=':',lw=.8)
    fig.text(.5,.01,'95% template-cluster bootstrap CIs. Cross-stage CTRL contrasts use matched name-set-0 subsets.',ha='center',fontsize=8)
    fig.tight_layout(rect=(0,.04,1,1));save(fig,'fig4_controls_cues')

CAPTIONS={
1:('fig1_pipeline','ConstraintArb pipeline. The benchmark instrument specifies the graph, declared edit space, solver certification and deterministic scorers (Section III). The protocol specifies stage-specific calls and inference (Section IV). The recognition probe is a separate forked call; its score is not a patch sacrifice and does not establish the latent representation during the decision.'),
2:('fig2_forced_sacrifice','Representative frozen T01 fan template (name set 0). T becomes available if either N_A or N_B is available. Constraint A retains the Iron Seal location; Constraint B retains the Pell the Scout unlock. Both have equal priority and relaxing either requires one direct field edit. Each side retains eight dependents: the high-cost side has eight manual entries, the low-cost side one manual and seven engine entries. A_HIGH/B_HIGH exchange only update flags; topology and locked background nodes are unchanged. Locked background nodes are omitted from the schematic. Certification is conditional on the declared edit space.'),
3:('fig3_explicit_graph','Explicit and graph-only cost utilisation across seven models, copied from frozen Stage-2 and Stage-3b results. Squares denote explicit reports; circles graph-only decisions; lines are 95% template-cluster bootstrap intervals. The full theoretical risk-difference range is shown. Five models retain high utilisation; DSP and DSF differ. Stages, selection and serving configurations differ across models; this is not a population or provider-independent comparison. Degenerate empirical bootstrap intervals do not establish zero uncertainty about deployment behaviour.'),
4:('fig4_controls_cues','Controls and dependent-directed cues in the affected models. Left: DSP generic control from Stage 3b compared with matched Stage-3a name-set-0 G/N1 subsets, a cross-stage contrast. Middle/right: same-stage Stage-3c G, REP and cue arms; concurrent means collected within that stage, not simultaneous/interleaved trials. DSP NB/NC are NOT EVALUABLE after provider withdrawal and have no plotted estimates. DSF provider mixtures differed between arms. Points and 95% intervals are Δ, not cue-effect estimates; G3 remains PARTIAL.')}

def protocol(models,rules):
    p=M/'05_section4_protocol.md';s=p.read_text(encoding='utf-8')
    for tag,title,data in [('models','Model identifiers and routing',models),('rules','Stage questions, rules and temporal status',rules)]:
        block=f'<!-- GENERATED {tag}: build_submission.py -->\n**Table [{tag}]. {title}**\n\n{data}\n<!-- END GENERATED {tag} -->'
        pattern=rf'<!-- GENERATED {tag}:.*?<!-- END GENERATED {tag} -->'
        if re.search(pattern,s,re.S): s=re.sub(pattern,lambda _:block,s,flags=re.S)
        else:
            pattern=rf'\*\*Table \[{tag}\]\.\*\*.*?\*\](?=\s*\n\n###)'
            # Existing placeholder closes with ]*; use next subsection as boundary.
            start=s.index(f'**Table [{tag}].**');end=s.index('\n### ',start)
            s=s[:start]+block+'\n'+s[end:]
    write(p,s)

TABLES={'[Table: prompt conditions]':'Table I','[Table: bias controls]':'Table II','Table [stages]':'Table III','Table [models]':'Table IV',
        'Table [rules]':'Table V','Table [amendments]':'Table VI','Table [main]':'Table VII','Table [cues]':'Table VIII','Table [robust]':'Table IX'}

def assemble():
    intro=read('manuscript/01_abstract_introduction.md')
    title=re.search(r'Title: \*\*(.*?)\*\*',intro).group(1)
    abstract=intro.split('## Abstract',1)[1].split('\n',1)[1].split('\n---',1)[0]
    abstract=re.sub(r'<!--.*?-->','',abstract,flags=re.S).strip()
    out=['<!-- GENERATED by manuscript/build_submission.py; edit section sources -->', '# '+title,'\n## Abstract\n\n'+abstract,
         '\n**Index terms:** Large language models, constraint satisfaction, structured content editing, consequence-aware arbitration, behavioural evaluation.']
    files=['01_abstract_introduction.md','03_related_work.md','04_section3_benchmark.md','05_section4_protocol.md',
           '06_section5_results.md','07_section6_discussion.md','08_section7_limitations.md','10_conclusion_availability.md']
    for name in files:
        s=read('manuscript/'+name)
        starts=list(re.finditer(r'^## (?:I|II|III|IV|V|VI|VII|VIII)\. ',s,re.M))
        if not starts: raise ValueError(name)
        s=s[starts[0].start():]
        s=s.split('\n## Reference status',1)[0].strip()
        for old,new in TABLES.items(): s=s.replace(old,new)
        s=s.replace('**Table II Biases','**Table II. Biases')
        if name=='04_section3_benchmark.md':
            s=s.replace('\n| Condition | Condition paragraph |','\n**Table I. Prompt conditions**\n\n| Condition | Condition paragraph |')
        s=re.sub(r'<!-- GENERATED.*?-->|<!-- END GENERATED.*?-->','',s)
        if name=='04_section3_benchmark.md':
            for n in [1,2]:
                asset,cap=CAPTIONS[n];s+=f'\n\n![Fig. {n}](figures/{asset}.png)\n\n**Fig. {n}.** {cap}'
        if name=='06_section5_results.md':
            for n in [3,4]:
                asset,cap=CAPTIONS[n];s+=f'\n\n![Fig. {n}](figures/{asset}.png)\n\n**Fig. {n}.** {cap}'
        out.append(s)
    out.append(read('manuscript/REFERENCES.md'))
    write(M/'constraintarb_ieee_access_full_draft.md','\n\n'.join(out))
    write(F/'captions.md','# Figure captions\n\n'+'\n\n'.join(f'**Fig. {n}.** {cap}' for n,(_,cap) in CAPTIONS.items()))
    dump(G/'submission_inputs.json',dict(sorted(SOURCES.items())))

def main():
    G.mkdir(exist_ok=True)
    read('manuscript/build_submission.py')
    models=model_tables();rules=rule_tables();protocol(models,rules)
    d=figure_data();figures(d);assemble()
    print('Built IV tables, S1/S2, four PDF/PNG figures, source mappings, and assembled manuscript. Offline only.')

if __name__=='__main__': main()
