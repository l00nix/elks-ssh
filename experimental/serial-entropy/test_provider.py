# MIT. Protocol/state tests; no physical device is opened.
import unittest
import struct
from provider import Provider

class Protocol(unittest.TestCase):
    def request(self, p, sequence):
        return b'ESQ1' + p.session + struct.pack('>I',sequence)
    def test_fresh_and_replay(self):
        p=Provider();a=p.answer(self.request(p,1));b=p.answer(self.request(p,3))
        self.assertEqual(len(a),60);self.assertNotEqual(a[24:56],b[24:56])
        for n in [0,1,2,3]:
            with self.assertRaises(ValueError):p.answer(self.request(p,n))
    def test_session_restart(self):
        first=Provider();second=Provider()
        with self.assertRaises(ValueError):second.answer(self.request(first,1))
    def test_framing(self):
        p=Provider()
        for data in [b'',self.request(p,1)[:-1],b'BAD!'+self.request(p,1)[4:],self.request(p,1)+b'x']:
            with self.assertRaises(ValueError):p.answer(data)
        self.assertEqual(p.requests,0)
    def test_source_failure_consumes_sequence(self):
        p=Provider();p.source=lambda n: b'x'*31
        with self.assertRaises(RuntimeError):p.answer(self.request(p,1))
        with self.assertRaises(ValueError):p.answer(self.request(p,1))
    def test_repeated_output(self):
        p=Provider();p.source=lambda n:b'x'*n;p.answer(self.request(p,1))
        with self.assertRaises(RuntimeError):p.answer(self.request(p,2))
    def test_limit(self):
        p=Provider();p.requests=1024
        with self.assertRaises(ValueError):p.answer(self.request(p,1))

if __name__=='__main__':unittest.main()
