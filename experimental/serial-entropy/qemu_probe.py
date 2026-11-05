#!/usr/bin/env python3
"""MIT. Disposable MINIX fixture; no physical ports or secret-byte logging."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from provider import Provider

p=argparse.ArgumentParser()
for name in ['image','mfs','probe','out']:p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--mode',choices=['healthy','short','stale-session','stale-counter','replay','source-failure','corrupt','busy','bad-counter','bad-mode','bad-device'],default='healthy')
p.add_argument('--short-bytes',type=int,choices=range(60),default=59)
p.add_argument('--daemon',action='store_true',help='Check daemon entropy startup with deliberately absent host key')
p.add_argument('--keygen',action='store_true',help='Validate an ephemeral guest-generated key without saving its private bytes')
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
if a.daemon and a.keygen:p.error('Choose daemon or keygen, not both')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result={'status':'failed','mode':a.mode,'short_bytes':a.short_bytes if a.mode=='short' else None,
        'daemon':a.daemon,'keygen':a.keygen,'image_sha256':sha(a.image),'probe_sha256':sha(a.probe),'real_hardware':False}
transcript=bytearray();stop=threading.Event();provider=Provider();provider_error=[];sequences=[]
try:
 with tempfile.TemporaryDirectory(prefix='esh-ep-') as directory:
  temp=Path(directory);disk=temp/'disk.img';shutil.copyfile(a.image,disk)
  def mfs(*args):return subprocess.check_output([str(a.mfs),str(disk),*map(str,args)])
  opts=mfs('cat','/bootopts')+b'\nconsole=ttyS0,19200 3\n';assert len(opts)<=1023
  (temp/'bootopts').write_bytes(opts);mfs('cp',temp/'bootopts','/bootopts')
  mfs('mkdir','/root/ssh1105');mfs('cp',a.probe,'/bin/eprobe')
  provider.bootstrap(temp/'bootstrap')
  for name in ['esession','ecounter']:mfs('cp',temp/'bootstrap'/name,'/root/ssh1105/'+name)
  serial=temp/'serial';entropy=temp/'entropy'
  with (a.out/'qemu.log').open('w') as log:
   proc=subprocess.Popen(['qemu-system-i386','-machine','pc','-cpu','486','-accel','tcg,one-insn-per-tb=on',
        '-m','16M','-display','none','-monitor','none','-nic','none',
        '-serial',f'unix:{serial},server=on,wait=off','-serial',f'unix:{entropy},server=on,wait=off',
        '-drive',f'file={disk},format=raw,if=ide','-boot','c'],stdout=log,stderr=log)
   try:
    end=time.monotonic()+10
    while not serial.exists() or not entropy.exists():
     if time.monotonic()>end or proc.poll() is not None:raise RuntimeError('QEMU startup failed')
     time.sleep(.05)
    def serve():
     try:
      with socket.socket(socket.AF_UNIX) as link:
       link.connect(str(entropy));link.settimeout(.2);pending=bytearray();first=None
       while not stop.is_set():
        try:chunk=link.recv(128)
        except socket.timeout:continue
        if not chunk:return
        pending.extend(chunk)
        while len(pending)>=24:
         request=bytes(pending[:24]);del pending[:24]
         if a.mode=='source-failure':return
         response=provider.answer(request);sequences.append(provider.last)
         if a.mode=='short':response=response[:a.short_bytes]
         elif a.mode=='stale-session':response=response[:4]+bytes([response[4]^1])+response[5:]
         elif a.mode=='stale-counter':response=response[:20]+bytes(4)+response[24:]
         elif a.mode=='corrupt':response=response[:24]+bytes([response[24]^1])+response[25:]
         elif a.mode=='replay':
          if first is None:first=response
          else:response=first
         link.sendall(response)
     except Exception as exc:
      if not stop.is_set():provider_error.append(str(exc))
    thread=threading.Thread(target=serve,daemon=True);thread.start()
    with socket.socket(socket.AF_UNIX) as conn:
     conn.connect(str(serial));conn.settimeout(.2)
     def receive(pattern,timeout=45):
      data=bytearray();end=time.monotonic()+timeout
      while time.monotonic()<end:
       try:chunk=conn.recv(8192)
       except socket.timeout:continue
       if not chunk:raise RuntimeError('Guest disconnected')
       data.extend(chunk);transcript.extend(chunk)
       (a.out/'serial.txt').write_bytes(transcript)
       if re.search(pattern,data):return bytes(data)
      raise RuntimeError('Guest timed out')
     receive(rb'login:');conn.sendall(b'root\r');receive(rb'# ')
     count=0
     def command(value,expected=0,timeout=45):
      global count
      count+=1;marker=('CHECK%d='%count).encode()
      conn.sendall((value+'; echo CHECK%d=$?\r'%count).encode())
      data=receive(rb'\r?\n'+marker+rb'(\d+)\r?\n',timeout)
      if int(re.search(marker+rb'(\d+)\r?\n',data)[1])!=expected:raise RuntimeError('Unexpected exit: '+value)
      return data
     command('chmod 700 /bin/eprobe')
     command('chmod 600 /dev/ttyS1')
     command('chmod 700 /root/ssh1105')
     command('chmod 600 /root/ssh1105/esession')
     command('chmod 600 /root/ssh1105/ecounter')
     if a.mode=='bad-device':command('chmod 644 /dev/ttyS1')
     if a.mode=='busy':command('exec 9</dev/ttyS1')
     if a.mode=='bad-counter':command('echo bad > /root/ssh1105/ecounter')
     if a.mode=='bad-mode':command('chmod 644 /root/ssh1105/ecounter')
     if a.keygen:
      data=command('eprobe -t ed25519 -f /root/ssh1105/hk',0 if a.mode=='healthy' else 1,180)
      if a.mode=='healthy':
       key_output=data
       listing=command('ls -l /root/ssh1105/hk')
       assert b'-rw-------' in listing
       assert sequences==[1,2,3],sequences
       data=command('eprobe -t ed25519 -f /root/ssh1105/other',1)
       assert b'Failure reading dedicated serial entropy' in data
       command('test ! -f /root/ssh1105/other')
       result.update(private_mode_600=True,relaunch_without_bootstrap_refused=True)
      else:
       assert b'Failure reading dedicated serial entropy' in data
       command('test ! -f /root/ssh1105/hk')
       command('test ! -f /root/ssh1105/hk.pub')
       result['failure_created_no_key']=True
      command('test ! -f /dev/urandom')
     elif a.daemon:
      data=command('eprobe -F -r /root/no-key',1)
      if a.mode=='healthy':
       assert b'No hostkeys available' in data,data
       assert sequences==[1],sequences
       data=command('eprobe -F -r /root/no-key',1)
       assert b'Failure reading dedicated serial entropy' in data,data
       result['relaunch_without_bootstrap_refused']=True
      else:
       assert b'Failure reading dedicated serial entropy' in data,data
      command('test ! -f /dev/urandom')
     elif a.mode=='healthy':
      data=command('eprobe');assert b'PASS four seeds' in data
      data=command('eprobe fail');assert b'PASS refusal' in data
      assert sequences==[1,2,3,4],sequences
      result['relaunch_without_bootstrap_refused']=True
     elif a.mode=='replay':
      data=command('eprobe',1);assert b'FAIL second seed' in data
      assert sequences==[1,2],sequences
     else:
      data=command('eprobe fail');assert b'PASS refusal' in data
      assert len(sequences)==(0 if a.mode in ['source-failure','busy','bad-counter','bad-mode','bad-device'] else 1),sequences
     command('test '+('' if a.mode in ['busy','bad-device'] else '! ')+'-f /root/ssh1105/esession')
     if provider_error:raise RuntimeError(provider_error[0])
     if a.keygen and a.mode=='healthy':
      command('sync')
      stop.set();thread.join(timeout=2)
      proc.terminate();proc.wait(timeout=10)
      # Read only after QEMU exits. The mounted MINIX clean flag remains unset;
      # -f is used solely for cat on this discarded test image, never mutation.
      def read_key(path):return subprocess.check_output([str(a.mfs),'-f',str(disk),'cat',path])
      from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
      from cryptography.hazmat.primitives import serialization
      private=read_key('/root/ssh1105/hk')
      assert len(private)==83 and private[:19]==b'\x00\x00\x00\x0bssh-ed25519\x00\x00\x00\x40'
      key=Ed25519PrivateKey.from_private_bytes(private[19:51])
      public=key.public_key()
      assert public.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)==private[51:]
      public_text=public.public_bytes(serialization.Encoding.OpenSSH,serialization.PublicFormat.OpenSSH)
      assert public_text in key_output and read_key('/root/ssh1105/hk.pub').startswith(public_text+b' ')
      del private,key,public
      result['generated_key_valid']=True
     result['status']='passed'
   finally:
    stop.set()
    if 'thread' in locals():thread.join(timeout=2)
    if proc.poll() is None:proc.terminate();proc.wait(timeout=10)
except Exception as exc:result['error']=str(exc)
finally:
 result.update(sequences=sequences,provider_errors=provider_error,original_image_unchanged=sha(a.image)==result['image_sha256'])
 if not result['original_image_unchanged']:result['status']='failed'
 (a.out/'serial.txt').write_bytes(transcript);(a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(0 if result['status']=='passed' else 1)
