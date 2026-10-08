"""Offline release helpers; no experiment collection entry point."""
from pathlib import Path
import hashlib, json, socket, sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'analysis'), str(ROOT/'manuscript')]

def offline():
    def blocked(*args, **kwargs):
        raise RuntimeError('Network access is disabled in the offline release workflow')
    socket.socket.connect = blocked
    socket.create_connection = blocked

def read(path): return json.loads(Path(path).read_text(encoding='utf8'))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path, obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf8')

def compare(actual, expected, path='', differences=None, tolerance=1e-8):
    differences=[] if differences is None else differences
    if isinstance(expected,dict):
        if not isinstance(actual,dict): differences.append({'path':path,'kind':'type'})
        else:
            for key in sorted(set(actual)|set(expected)):
                p=path+'.'+key
                if key not in actual or key not in expected: differences.append({'path':p,'kind':'missing key'})
                else: compare(actual[key],expected[key],p,differences,tolerance)
    elif isinstance(expected,list):
        if not isinstance(actual,list) or len(actual)!=len(expected): differences.append({'path':path,'kind':'list shape'})
        else:
            for i,(a,b) in enumerate(zip(actual,expected)): compare(a,b,f'{path}[{i}]',differences,tolerance)
    elif isinstance(expected,(int,float)) and not isinstance(expected,bool):
        if not isinstance(actual,(int,float)) or abs(actual-expected)>tolerance:
            differences.append({'path':path,'actual':actual,'expected':expected})
    elif actual != expected: differences.append({'path':path,'actual':actual,'expected':expected})
    return differences
