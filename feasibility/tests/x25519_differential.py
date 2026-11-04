#!/usr/bin/env python3
"""MIT. Deterministic public inputs; compare three C variants to host X25519."""
import ctypes,hashlib,json,subprocess
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey,X25519PublicKey
root=Path(__file__).resolve().parents[1]
out=root/'build/x25519-host';out.mkdir(parents=True,exist_ok=True)
functions={}
for name,extra in [('baseline',[]),('m15-0',['-DUSE_BEARSSL','-DBR_SLOW_MUL15=0']),('m15-1',['-DUSE_BEARSSL','-DBR_SLOW_MUL15=1'])]:
 cmd=['cc','-shared','-fPIC','-Os','-std=c99','-Wall','-Wextra','-fwrapv','-DBR_NO_ARITH_SHIFT=1']+extra
 cmd+=['-Ivendor/bearssl/inc','-Ivendor/bearssl/src','-Itests/shim','-Ivendor/dropbear/src','tests/x25519_api.c']
 cmd+=['vendor/bearssl/src/ec/ec_c25519_m15.c','vendor/bearssl/src/codec/ccopy.c'] if extra else ['vendor/dropbear/src/curve25519.c']
 cmd+=['-o',str(out/(name+'.so'))]
 subprocess.run(cmd,cwd=root,check=True)
 lib=ctypes.CDLL(str(out/(name+'.so')));fn=lib.probe_x25519
 fn.argtypes=[ctypes.c_void_p]*3;fn.restype=ctypes.c_int;functions[name]=fn
checks=0
for i in range(128):
 key=hashlib.sha256(('public-x25519-scalar-%d'%i).encode()).digest()
 point=hashlib.sha256(('public-x25519-point-%d'%i).encode()).digest()
 expected=X25519PrivateKey.from_private_bytes(key).exchange(X25519PublicKey.from_public_bytes(point))
 # Include ignored scalar bits and the ignored high point bit.
 variants=[(key,point),(bytes([key[0]^7])+key[1:31]+bytes([key[31]^192]),point[:31]+bytes([point[31]^128]))]
 for k,p in variants:
  for name,fn in functions.items():
   result=ctypes.create_string_buffer(32)
   assert fn(result,k,p)==1 and result.raw==expected,(name,i)
   checks+=1
print(json.dumps({'status':'passed','public_input_pairs':256,'backend_comparisons':checks,'reference':'cryptography X25519','checks':'deterministic public inputs, scalar clamping, ignored point bit','hardware':False},indent=2))
