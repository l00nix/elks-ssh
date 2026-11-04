#!/usr/bin/env python3
"""MIT. Regenerate public X25519 cases using the independent host backend."""
import json
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
root=Path(__file__).resolve().parents[1]
a=bytes.fromhex('77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a')
b=bytes.fromhex('5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb')
ap=bytes.fromhex('8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a')
bp=bytes.fromhex('de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f')
enc=lambda n:n.to_bytes(32,'little')
p=2**255-19
cases=[('alice-public',a,enc(9)),('bob-public',b,enc(9)),('alice-shared',a,bp),('bob-shared',b,ap),('low-zero',a,enc(0)),('low-one',a,enc(1)),('noncanon-p',a,enc(p)),('noncanon-p1',a,enc(p+1)),('noncanon-p9',a,enc(p+9)),('point-highbit',a,enc(9+2**255)),('scalar-zero',bytes(32),enc(9)),('scalar-ff',bytes([255])*32,enc(9))]
rows=[]
for name,k,u in cases:
 try: out=X25519PrivateKey.from_private_bytes(k).exchange(X25519PublicKey.from_public_bytes(u))
 except ValueError:
  assert name in ['low-zero','low-one','noncanon-p','noncanon-p1']
  out=bytes(32)  # Probe checks raw primitive; SSH must reject all-zero output.
 rows.append(dict(name=name,scalar=k.hex(),point=u.hex(),expected=out.hex()))
assert rows[0]['expected']==ap.hex() and rows[1]['expected']==bp.hex()
assert rows[2]['expected']==rows[3]['expected']=='4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742'
(root/'tests/x25519-vectors.json').write_text(json.dumps(rows,indent=2)+'\n')
text='/* Generated public vectors. Regenerate with tests/x25519_vectors.py. */\n'
text+='static const struct vector vectors[] = {\n'
for row in rows:
 text+='    {"'+row['name']+'", "'+row['scalar']+'",\n     "'+row['point']+'",\n     "'+row['expected']+'"},\n'
text+='};\n'
(root/'src/x25519-vectors.h').write_text(text)
print('Generated 12 public reference vectors')
