#!/usr/bin/env python3
"""MIT. Explicit physical daemon startup/restart test; deliberately no host key.
Each iteration starts a new host provider and provisions fresh public metadata.
No SSH listener, secret key provisioning, seed bytes or seed hashes in evidence.
"""
import argparse
from ftplib import FTP
from io import BytesIO
import json
from pathlib import Path
import re
import subprocess
import sys
import telnetlib
import time

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--host',required=True)
p.add_argument('--device',required=True)
p.add_argument('--out',required=True,type=Path)
p.add_argument('--rounds',type=int,default=10,choices=range(1,31))
p.add_argument('--baud',type=int,choices=[300,1200,2400,9600],default=1200)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
results=[];transcript=bytearray();provider=None
with telnetlib.Telnet(a.host,23,10) as t:
 t.read_until(b'login: ',10);t.write(b'root\r\n');assert t.read_until(b'# ',10).endswith(b'# ')
 count=0
 def command(value):
  global count
  count+=1;marker=('RESTART%d='%count).encode()
  t.write(value.encode()+b'; echo '+marker+b'$?\r\n')
  data=bytearray();end=time.monotonic()+40
  while time.monotonic()<end:
   chunk=t.read_until(b'\n',.5);data.extend(chunk);transcript.extend(chunk)
   (a.out/'telnet.txt').write_bytes(transcript)
   found=re.search(rb'\r?\n'+marker+rb'(\d+)\r?\n',data)
   if found:return bytes(data),int(found[1])
  raise RuntimeError('Target command timed out')
 listing,rc=command('ls -l /dev/ttyS0');assert rc==0
 permissions=re.search(rb'c([rwx-]{9})\s',listing)[1]
 original=sum(1<<(8-i) for i,c in enumerate(permissions) if c!=45)
 try:
  assert command('chmod 600 /dev/ttyS0')[1]==0
  for n in range(a.rounds):
   session=a.out/('session-%02d'%n);logpath=a.out/('provider-%02d.txt'%n)
   with logpath.open('w') as log:
    provider=subprocess.Popen([sys.executable,str(Path(__file__).with_name('provider.py')),'--device',a.device,'--bootstrap',str(session),'--baud',str(a.baud)],stdout=log,stderr=log)
    try:
     end=time.monotonic()+10
     while 'READY:' not in logpath.read_text():
      if provider.poll() is not None or time.monotonic()>end:raise RuntimeError('Provider failed startup')
      time.sleep(.1)
     with FTP(a.host,timeout=15) as ftp:
      ftp.login('root','')
      for name in ['esession','ecounter']:
       data=(session/name).read_bytes();target='/root/ssh1105/'+name
       ftp.storbinary('STOR '+target,BytesIO(data));back=BytesIO();ftp.retrbinary('RETR '+target,back.write)
       assert back.getvalue()==data
     assert command('chmod 600 /root/ssh1105/esession')[1]==0
     assert command('chmod 600 /root/ssh1105/ecounter')[1]==0
     start=time.monotonic()
     output,rc=command('/root/ssh1105/sshdiag -F -r /root/no-key')
     stages=re.findall(rb'diagnostic: stage (\d+) refused',output)
     passed=rc==1 and b'No hostkeys available' in output
     result={'round':n+1,'reached_hostkey_loading':passed,'exit':rc,'host_seconds':round(time.monotonic()-start,3),'refused_stages':[int(x) for x in stages]}
     results.append(result);print(json.dumps(result),flush=True)
    finally:
     if provider.poll() is None:provider.terminate()
     provider.wait(timeout=5);provider=None
   (a.out/'result.json').write_text(json.dumps({'cases':results,'all_passed':all(r['reached_hostkey_loading'] for r in results),'real_hardware':True,'ssh_login':False},indent=2)+'\n')
  command('ps');command('netstat')
 finally:
  if provider is not None and provider.poll() is None:provider.terminate();provider.wait(timeout=5)
  command('rm -f /root/ssh1105/esession /root/ssh1105/ecounter')
  command('chmod %03o /dev/ttyS0'%original)
  t.write(b'exit\r\n')
raise SystemExit(0 if all(r['reached_hostkey_loading'] for r in results) else 1)
