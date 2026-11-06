#!/usr/bin/env python3
"""Run public Ed25519 fixtures in a disposable FAT ELKS guest; no NIC or secrets."""
import argparse,hashlib,json,re,shutil,socket,subprocess,tempfile,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--image',type=Path,required=True);p.add_argument('--probe',type=Path,required=True);p.add_argument('--fixtures',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--timeout',type=int,default=1800);a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result={'status':'failed','real_hardware':False,'cpu':'486','image_sha256':sha(a.image),'probe_sha256':sha(a.probe),'fixtures_sha256':sha(a.fixtures)}
transcript=bytearray();proc=None
try:
 with tempfile.TemporaryDirectory(prefix='edcompact-') as td:
  t=Path(td);disk=t/'disk.img';shutil.copyfile(a.image,disk)
  opts=subprocess.check_output(['mtype','-i',str(disk),'::/bootopts'])+b'\nconsole=ttyS0,19200 3\n';assert len(opts)<=1023
  (t/'bootopts').write_bytes(opts)
  for source,dest in [(t/'bootopts','::/bootopts'),(a.probe,'::/bin/edcheck'),(a.fixtures,'::/edcases')]:subprocess.run(['mcopy','-o','-i',str(disk),str(source),dest],check=True)
  serial=t/'serial'
  with (a.out/'qemu.log').open('w') as log:
   proc=subprocess.Popen(['qemu-system-i386','-machine','pc','-cpu','486','-accel','tcg,one-insn-per-tb=on','-m','16M','-display','none','-monitor','none','-nic','none','-serial',f'unix:{serial},server=on,wait=off','-drive',f'file={disk},format=raw,if=ide','-boot','c'],stdout=log,stderr=log)
   end=time.monotonic()+10
   while not serial.exists():
    if time.monotonic()>end or proc.poll() is not None:raise RuntimeError('QEMU start failed')
    time.sleep(.05)
   with socket.socket(socket.AF_UNIX) as c:
    c.connect(str(serial));c.settimeout(.2)
    def receive(pattern,timeout=30):
     data=bytearray();end=time.monotonic()+timeout
     while time.monotonic()<end:
      try:chunk=c.recv(8192)
      except socket.timeout:continue
      if not chunk:raise RuntimeError('Guest disconnected')
      data.extend(chunk);transcript.extend(chunk);(a.out/'serial.txt').write_bytes(transcript)
      if re.search(pattern,data):return bytes(data)
     raise RuntimeError('Guest timed out')
    receive(rb'login:');c.sendall(b'root\r');receive(rb'# ')
    start=time.monotonic();c.sendall(b'edcheck /edcases; echo EDCHECK=$?\r')
    data=receive(rb'\r?\nEDCHECK=(\d+)\r?\n',a.timeout)
    match=re.search(rb'RESULT PASS checks=(\d+) failures=0 accepted=(\d+)',data)
    if not match or b'FAIL' in data or b'STACK' in data or b'EDCHECK=0' not in data:raise RuntimeError('Probe failed')
    result.update(status='passed',checks=int(match[1]),accepted=int(match[2]),host_seconds=round(time.monotonic()-start,3))
    c.sendall(b'ps; echo CLEANUP=$?\r');state=receive(rb'\r?\nCLEANUP=0\r?\n')
    result['no_probe_remaining']=not any(b'edcheck ' in line for line in state.splitlines() if re.match(rb'\s*\d+\s',line))
    if not result['no_probe_remaining']:raise RuntimeError('Probe remains')
except Exception as e:result.update(status='failed',error=str(e))
finally:
 if proc and proc.poll() is None:
  proc.terminate()
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
 result['original_image_unchanged']=sha(a.image)==result['image_sha256']
 if not result['original_image_unchanged']:result['status']='failed'
 (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2));raise SystemExit(result['status']!='passed')
