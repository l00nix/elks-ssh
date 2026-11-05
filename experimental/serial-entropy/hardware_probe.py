#!/usr/bin/env python3
"""MIT. Explicit PPC probe qualification. No SSH keys/listener or seed logging.
Requires an already verified eprobe at /root/ssh1105/eprobe and exclusive cable.
"""
import argparse
import binascii
import fcntl
from ftplib import FTP
from io import BytesIO
import ipaddress
import json
import os
from pathlib import Path
import re
import select
import struct
import subprocess
import telnetlib
import termios
import threading
import time
from provider import Provider

p=argparse.ArgumentParser()
p.add_argument('--host',required=True,type=ipaddress.IPv4Address)
p.add_argument('--device',required=True)
p.add_argument('--out',required=True,type=Path)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
fd=os.open(a.device,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
fcntl.ioctl(fd,termios.TIOCEXCL)
owners=subprocess.run(['lsof','-t',a.device],capture_output=True,text=True,check=True)
if set(owners.stdout.split())!={str(os.getpid())}:os.close(fd);raise RuntimeError('Serial has another owner')
old=termios.tcgetattr(fd);settings=termios.tcgetattr(fd)
settings[0]=settings[1]=settings[3]=0;settings[2]=termios.CS8|termios.CLOCAL|termios.CREAD
settings[4]=settings[5]=termios.B1200;settings[6][termios.VMIN]=settings[6][termios.VTIME]=0
termios.tcsetattr(fd,termios.TCSANOW,settings)
results=[];transcript=bytearray();counter=0
try:
 with telnetlib.Telnet(str(a.host),23,10) as t:
  t.read_until(b'login: ',10);t.write(b'root\r\n');assert t.read_until(b'# ',10).endswith(b'# ')
  def command(value,expected=0):
   global counter
   counter+=1;marker=('HWCHECK%d='%counter).encode()
   assert len(value)<65,value
   t.write(value.encode()+b'; echo '+marker+b'$?\r\n')
   data=bytearray();end=time.monotonic()+60
   while time.monotonic()<end:
    chunk=t.read_until(b'\n',1);data.extend(chunk);transcript.extend(chunk)
    (a.out/'telnet.txt').write_bytes(transcript)
    match=re.search(rb'\r?\n'+marker+rb'(\d+)\r?\n',data)
    if match:
     if int(match[1])!=expected:raise RuntimeError('Unexpected exit: '+value)
     return bytes(data)
   raise RuntimeError('Target command timed out: '+value)
  command('uname -a');command('ps')
  listing=command('ls -l /dev/ttyS0')
  permissions=re.search(rb'c([rwx-]{9})\s',listing)[1]
  original_mode=sum(1<<(8-i) for i,c in enumerate(permissions) if c!=45)
  for mode in ['silent','short-seed','short-crc','stale-session','stale-counter','corrupt','replay','bad-device','healthy','busy']:
   provider=Provider();stop=threading.Event();seen=[];errors=[];first=[None]
   termios.tcflush(fd,termios.TCIOFLUSH)
   with FTP(str(a.host),timeout=15) as ftp:
    ftp.login('root','')
    for name,data in [('esession',provider.session),('ecounter',provider.session+bytes(4))]:
     path='/root/ssh1105/'+name
     ftp.storbinary('STOR '+path,BytesIO(data));check=BytesIO();ftp.retrbinary('RETR '+path,check.write)
     if check.getvalue()!=data:raise RuntimeError('Public bootstrap readback mismatch')
   command('chmod '+('644' if mode=='bad-device' else '600')+' /dev/ttyS0')
   command('chmod 600 /root/ssh1105/esession')
   command('chmod 600 /root/ssh1105/ecounter')
   def serve():
    try:
     pending=bytearray()
     while not stop.is_set():
      if not select.select([fd],[],[],.2)[0]:continue
      pending.extend(os.read(fd,128))
      while len(pending)>=24:
       request=bytes(pending[:24]);del pending[:24]
       response=provider.answer(request);seen.append(provider.last)
       if mode=='silent':continue
       if mode=='short-seed':response=response[:55]
       elif mode=='short-crc':response=response[:59]
       elif mode in ['stale-session','stale-counter']:
        frame=bytearray(response[:56]);frame[4 if mode=='stale-session' else 23]^=1
        response=bytes(frame)+struct.pack('>I',binascii.crc32(frame))
       elif mode=='corrupt':response=response[:24]+bytes([response[24]^1])+response[25:]
       elif mode=='replay':
        if first[0] is None:first[0]=response
        else:response=first[0]
       remaining=memoryview(response)
       while remaining:
        if not select.select([],[fd],[],2)[1]:raise RuntimeError('Serial write timeout')
        n=os.write(fd,remaining)
        if n<=0:raise RuntimeError('Serial write failed')
        remaining=remaining[n:]
    except Exception as exc:errors.append(str(exc))
   thread=threading.Thread(target=serve,daemon=True);thread.start()
   began=time.monotonic()
   try:
    if mode=='busy':command('exec 9</dev/ttyS0')
    cmd='/root/ssh1105/eprobe'+('' if mode in ['healthy','replay'] else ' fail')
    data=command(cmd,1 if mode=='replay' else 0)
    if mode=='healthy':
     assert b'PASS four seeds' in data and seen==[1,2,3,4],(data,seen)
     data=command('/root/ssh1105/eprobe fail');assert b'PASS refusal' in data
     assert seen==[1,2,3,4]
    elif mode=='replay':assert b'FAIL second seed' in data and seen==[1,2],(data,seen)
    else:assert b'PASS refusal' in data and len(seen)==(0 if mode in ['busy','bad-device'] else 1),(data,seen)
    if errors:raise RuntimeError(errors[0])
    result={'case':mode,'passed':True,'sequences':seen.copy(),'host_seconds':round(time.monotonic()-began,3)}
    results.append(result);print(json.dumps(result),flush=True)
    (a.out/'result.json').write_text(json.dumps({'cases':results,'real_hardware':True,'ssh_login':False},indent=2)+'\n')
   finally:stop.set();thread.join(timeout=3)
  command('exec 9<&-')
  command('chmod %o /dev/ttyS0'%original_mode)
  command('rm /root/ssh1105/esession')
  command('rm /root/ssh1105/ecounter')
  command('ps');t.write(b'exit\r\n')
finally:
 termios.tcsetattr(fd,termios.TCSANOW,old);os.close(fd)
 (a.out/'telnet.txt').write_bytes(transcript)
print('All hardware probe cases passed; no SSH login attempted')
