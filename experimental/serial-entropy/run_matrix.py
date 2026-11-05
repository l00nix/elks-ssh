#!/usr/bin/env python3
"""MIT. Run independent disposable emulator cases, with bounded concurrency."""
import argparse
import concurrent.futures
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser()
for n in ['image','mfs','probe','out']:p.add_argument('--'+n,type=Path,required=True)
p.add_argument('--jobs',type=int,choices=range(1,5),default=3)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
cases=[(m,None) for m in ['healthy','stale-session','stale-counter','replay','source-failure','corrupt','busy','bad-counter','bad-mode','bad-device']]
cases += [('short',n) for n in range(60)]
def run(case):
 mode,n=case;name=mode if n is None else 'short-%02d'%n
 out=a.out/name;out.mkdir(parents=True,exist_ok=True)
 command=[sys.executable,str(Path(__file__).with_name('qemu_probe.py')),'--mode',mode]
 for key in ['image','mfs','probe']:command += ['--'+key,str(getattr(a,key))]
 command+=['--out',str(out)]
 if n is not None:command+=['--short-bytes',str(n)]
 with (out/'run.txt').open('w') as log:
  proc=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=150)
 data=json.loads((out/'result.json').read_text())
 print(name,data['status'],flush=True)
 return {'case':name,'exit':proc.returncode,'result':data}
with concurrent.futures.ThreadPoolExecutor(max_workers=a.jobs) as pool:results=list(pool.map(run,cases))
summary={'passed':all(r['exit']==0 and r['result']['status']=='passed' for r in results),'cases':results,'real_hardware':False}
(a.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print('ALL PASSED',summary['passed'])
raise SystemExit(0 if summary['passed'] else 1)
