#!/usr/bin/env python3
"""Public deterministic vectors: Wycheproof plus independent Ed25519 reference."""
import argparse,hashlib,json,struct
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[3]
w=json.loads((root/'feasibility/vendor/wycheproof/ed25519_test.json').read_text())
records=[]
def add(id,op,msg,seed,pub,sig,expected,label,declared=None):
 assert len(sig)<=96
 records.append(dict(id=id,op=op,msg=msg,seed=seed,pub=pub,sig=sig,expected=expected,label=label,declared=declared))
for g in w['testGroups']:
 for t in g['tests']:
  expectation=1 if t['result']=='valid' else 0
  if t['result']=='acceptable' and 'MixedOrderPublicKey' in t['flags']:expectation=2
  add(t['tcId'],0,bytes.fromhex(t['msg']),bytes(32),bytes.fromhex(g['publicKey']['pk']),bytes.fromhex(t['sig']),expectation,{'source':'wycheproof','result':t['result'],'flags':t['flags']})
lengths=[0,1,2,31,32,63,64,95,96,111,112,127,128,129,191,192,255,256,1023,2048,4096]
L=2**252+27742317777372353535851937790883648493
for i,n in enumerate(lengths+list(range(64))):
 seed=hashlib.sha256(b'ELKSSH PUBLIC ED25519 FIXTURE '+str(i).encode()).digest()
 key=Ed25519PrivateKey.from_private_bytes(seed);pub=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
 msg=hashlib.shake_256(b'ELKSSH PUBLIC MESSAGE '+str(i).encode()).digest(n);sig=key.sign(msg)
 j=1000+i*5
 add(j,1,msg,seed,pub,sig,1,{'source':'cryptography','kind':'sign','length':n})
 add(j+1,0,msg,seed,pub,sig,1,{'source':'cryptography','kind':'verify','length':n})
 bad=bytearray(sig);bad[0]^=1
 add(j+2,0,msg,seed,pub,bytes(bad),0,{'kind':'tampered-R','length':n})
 high=sig[:32]+(int.from_bytes(sig[32:],'little')+L).to_bytes(32,'little')
 add(j+3,0,msg,seed,pub,high,0,{'kind':'S-plus-L','length':n})
 add(j+4,0,msg,seed,pub,sig[:-1],0,{'kind':'short-signature','length':n})
for i,n in enumerate([4097,8128,65535]):add(2000+i,2,b'',bytes(32),bytes(32),bytes(64),0,{'kind':'length-guard','length':n},declared=n)
# Explicit identity-key forgery R=B, S=1 passes naive equation for A=identity.
base=bytes.fromhex('58'+'66'*31)
for i,point in enumerate([bytes(32),(1).to_bytes(32,'little'),(2**255-20).to_bytes(32,'little'),(2**255-19).to_bytes(32,'little')]):
 for sign in [0,128]:
  b=bytearray(point);b[31]|=sign
  add(2100+i*2+(sign!=0),0,b'',bytes(32),bytes(b),base+(1).to_bytes(32,'little'),0,{'kind':'small-order-key'})
# Target subset: fixed adversarial cases plus all hash-boundary lengths;
# target-sign only selected boundaries to keep original-CPU probe bounded.
selected=[r for r in records if (r['id']<1000 and (r['expected']!=1 or r['id']<=3)) or (1000<=r['id']<1105 and r['id']%5 in [1,3,4]) or r['id']>=2000 or r['id'] in [1000,1040,1050,1060,1100]]
quick=[r for r in records if r['id'] in [1000,1001,1003,1004,2000,2002,2102]]
def write(name,rows):
 data=bytearray(b'EDC1')
 for r in rows:
  data+=struct.pack('<BHHBB',r['op'],r['id'],r['declared'] if r['declared'] is not None else len(r['msg']),len(r['sig']),r['expected'])
  data+=r['seed']+r['pub']+r['sig'].ljust(96,b'\0')+r['msg']
 (a.out/name).write_bytes(data)
 return {'cases':len(rows),'sha256':hashlib.sha256(data).hexdigest(),'labels':[{k:v for k,v in r.items() if k in ['id','op','label','expected']} for r in rows]}
manifest={name:write(name,rows) for name,rows in [('hostcases',records),('edcases',selected),('edquick',quick)]}
(a.out/'fixtures.json').write_text(json.dumps(manifest,indent=2)+'\n')
print({k:v['cases'] for k,v in manifest.items()})
