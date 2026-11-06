"""MIT. Test-only SSH agent returning deliberately invalid signatures.
A caller supplies a disposable fixture key. No real ssh-agent is used or read.
Protocol: draft-miller-ssh-agent-13, identity list and sign request subset.
"""
import os,socket,struct,threading
from cryptography.hazmat.primitives import serialization

def string(b):return struct.pack('>I',len(b))+b

def take(b):
 if len(b)<4:raise ValueError('Short agent string')
 n=struct.unpack('>I',b[:4])[0]
 if n>len(b)-4:raise ValueError('Truncated agent string')
 return b[4:4+n],b[4+n:]

class InvalidSignatureAgent:
 def __init__(self,path,key,mode):
  self.path=str(path);self.key=key;self.mode=mode
  raw=key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
  self.blob=string(b'ssh-ed25519')+string(raw)
  self.signatures=0;self.error=None;self.stop=threading.Event()
 def __enter__(self):
  self.server=socket.socket(socket.AF_UNIX);self.server.bind(self.path);os.chmod(self.path,0o600)
  self.server.listen(1);self.server.settimeout(.2)
  self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start();return self
 def read(self,c,n):
  b=bytearray()
  while len(b)<n and not self.stop.is_set():
   try:p=c.recv(n-len(b))
   except socket.timeout:continue
   if not p:return None
   b.extend(p)
  return bytes(b) if len(b)==n else None
 def run(self):
  try:
   while not self.stop.is_set():
    try:c,_=self.server.accept()
    except socket.timeout:continue
    with c:
     c.settimeout(.2)
     while not self.stop.is_set():
      h=self.read(c,4)
      if h is None:break
      n=struct.unpack('>I',h)[0]
      if not 1<=n<=65536:raise ValueError('Agent frame bound')
      b=self.read(c,n)
      if b is None:break
      response=b'\x05'
      if b[0]==11:
       response=b'\x0c'+struct.pack('>I',1)+string(self.blob)+string(b'public test fixture')
      elif b[0]==13:
       blob,rest=take(b[1:]);message,flags=take(rest)
       if blob!=self.blob or flags!=bytes(4):raise ValueError('Unexpected signing request')
       sig=self.key.sign(message)
       if self.mode=='tampered-R':sig=bytes([sig[0]^1])+sig[1:]
       elif self.mode=='S-plus-L':
        order=2**252+27742317777372353535851937790883648493
        sig=sig[:32]+(int.from_bytes(sig[32:],'little')+order).to_bytes(32,'little')
       elif self.mode=='short':sig=sig[:-1]
       else:raise ValueError('Unsupported mutation')
       self.signatures+=1
       response=b'\x0e'+string(string(b'ssh-ed25519')+string(sig))
      c.sendall(string(response))
  except Exception as e:
   if not self.stop.is_set():self.error=str(e)
 def __exit__(self,*args):
  self.stop.set();self.thread.join(timeout=2);self.server.close()
  try:os.unlink(self.path)
  except FileNotFoundError:pass
  if self.thread.is_alive():raise RuntimeError('Fixture agent did not stop')
