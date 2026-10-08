import os, sys, json, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

def load(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return json.load(f)

def handbuilt():
    return {os.path.basename(p)[:3]: load(os.path.relpath(p, ROOT))
            for p in sorted(glob.glob(os.path.join(ROOT, "data/scenarios/handbuilt/*.json")))}

def generated():
    return [load(os.path.relpath(p, ROOT)) for p in sorted(glob.glob(os.path.join(ROOT, "data/scenarios/generated/*.json")))]
