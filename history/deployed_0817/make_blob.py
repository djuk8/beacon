#!/usr/bin/env python3
"""Write screen.blob for screen_kernel, matched to (D, z_s). MUST match the C header.
Usage: python3 make_blob.py --digits 400 --zs 1e6   [--out screen.blob]"""
import argparse, math
import numpy as np, gmpy2
LN10=math.log(10)
def primes_upto(n):
    s=np.ones(n+1,bool); s[:2]=False
    for i in range(2,int(n**0.5)+1):
        if s[i]: s[i*i::i]=False
    return np.flatnonzero(s).astype(np.int64)
ap=argparse.ArgumentParser()
ap.add_argument("--digits",type=int,required=True)
ap.add_argument("--zs",type=float,required=True)
ap.add_argument("--out",default="screen.blob")
a=ap.parse_args()
D=a.digits; ZS=int(a.zs); L=D*LN10; W=int(10*L)
PR=primes_upto(ZS)
cum=np.cumsum(np.log(PR.astype(float)))
i=int(np.searchsorted(cum,(D-8)*LN10)); zd=int(PR[i-1]) if cum[min(i,len(cum)-1)]>(D-8)*LN10 else int(PR[i])
design=PR[PR<=zd]; P=gmpy2.mpz(1)
for p in design: P*=int(p)
offs=PR[(PR>zd)&(PR<=W)]
pd=PR[(PR>zd)&(PR<=ZS)]
Pmod=np.array([int(P%int(p)) for p in pd],np.int64)
tau=float(np.exp(np.sum(np.log1p(-1.0/pd))))
q=1.7810724179901979*math.log(ZS)/L
wv=np.zeros(W+1); wv[offs]=np.exp(-q*tau*(np.arange(len(offs))+1.0))
with open(a.out,"wb") as f:
    np.array([len(pd)],np.int64).tofile(f); pd.tofile(f); Pmod.tofile(f)
    np.array([W],np.int64).tofile(f); wv.tofile(f)
print(f"wrote {a.out}: D={D} zd={zd} z_s={ZS:.0e} np={len(pd)} W={W} "
      f"(blob {8*(1+2*len(pd)+1+W+1)/1e6:.1f} MB)")
