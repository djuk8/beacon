#!/usr/bin/env python3
"""BEACON screen sweep -- map lift vs (screening ratio, target depth).

For each (D, target_merit, top) cell: C-screen a fixed anchor pool, select
top, run BEACON trials on the selected + a shared vanilla pool, report
per-cell lift with Poisson CI and the preregistered posterior sum.

Emits sweep_out.csv (one row per cell) for plotting the lift surface.

Usage (shredder, overnight):
  python3 sweep_screen.py --digits 400 --zs 1e6 --z 1e6 \
      --pool 300000 --vanilla 60000 \
      --merits 6,7,8,9 --tops 30000,12000,4000,1500
Each (merit x top) pair is a cell; vanilla pool is shared across all cells
at a given merit (scored once, reused).
"""
import argparse, math, os, subprocess, tempfile, time, csv
import numpy as np, gmpy2

EG=1.7810724179901979; LN10=math.log(10)
def primes_upto(n):
    s=np.ones(n+1,bool); s[:2]=False
    for i in range(2,int(n**0.5)+1):
        if s[i]: s[i*i::i]=False
    return np.flatnonzero(s).astype(np.int64)
def build_base(D,PR):
    cum=np.cumsum(np.log(PR.astype(float)))
    i=int(np.searchsorted(cum,(D-8)*LN10))
    zd=int(PR[i-1]) if cum[min(i,len(cum)-1)]>(D-8)*LN10 else int(PR[i])
    design=PR[PR<=zd]; P=gmpy2.mpz(1)
    for p in design: P*=int(p)
    return zd,design,P

def screen_c(k0,K,pd,Pmod,offs,W,wv_off,exe="./screen_kernel"):
    wv=np.zeros(W+1); wv[offs]=wv_off
    d=tempfile.mkdtemp(); blob=d+"/b"; out=d+"/o"
    with open(blob,"wb") as f:
        np.array([len(pd)],np.int64).tofile(f); pd.tofile(f); Pmod.tofile(f)
        np.array([W],np.int64).tofile(f); wv.tofile(f)
    subprocess.run([exe,blob,str(k0),str(K),out],check=True)
    sc=np.fromfile(out,np.float64); os.remove(blob); os.remove(out); os.rmdir(d)
    return sc

def trial(k,P,design,deep,rP,Wside):
    n0=int(k)*P; Wt=2*Wside+1
    alive=np.ones(Wt,bool)
    for q in design: alive[Wside%q::q]=False
    r0=(int(k)*rP)%deep; lo=(r0-Wside)%deep; med=deep<Wt
    for p,rl in zip(deep[med],lo[med]): alive[(p-rl)%p::p]=False
    idx=(deep[~med]-lo[~med])%deep[~med]; hit=idx<Wt; alive[idx[hit]]=False
    so=np.flatnonzero(alive)-Wside; order=so[np.argsort(np.abs(so),kind='stable')]
    jl=jr=None
    for j in order:
        if j==0 or (j<0 and jl is not None) or (j>0 and jr is not None): continue
        c=n0+int(j)
        if gmpy2.powmod(2,c-1,c)==1 and gmpy2.is_prime(c,25):
            if j<0: jl=int(j)
            else: jr=int(j)
            if jl is not None and jr is not None: break
    return (jr-jl if jl is not None and jr is not None else 0)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--digits",type=int,required=True)
    ap.add_argument("--zs",type=float,required=True)
    ap.add_argument("--z",type=float,required=True)
    ap.add_argument("--pool",type=int,required=True)
    ap.add_argument("--vanilla",type=int,required=True)
    ap.add_argument("--merits",required=True)
    ap.add_argument("--tops",required=True)
    ap.add_argument("--seed",type=int,default=11)
    a=ap.parse_args()
    D,ZS,Z=a.digits,int(a.zs),int(a.z); L=D*LN10; W=int(10*L)
    merits=[float(x) for x in a.merits.split(",")]
    tops=[int(x) for x in a.tops.split(",")]
    PR=primes_upto(max(Z,int(30*L),ZS)); zd,design,P=build_base(D,PR)
    offs=PR[(PR>zd)&(PR<=W)]; pd=PR[(PR>zd)&(PR<=ZS)]
    Pmod=np.array([int(P%int(p)) for p in pd],np.int64)
    tau=float(np.exp(np.sum(np.log1p(-1.0/pd)))); q=EG*math.log(ZS)/L
    wv_off=np.exp(-q*tau*(np.arange(len(offs))+1.0))
    deep=PR[(PR>zd)&(PR<=Z)]; rP=np.array([int(P%int(p)) for p in deep],np.int64); Wside=int(25*L)
    rng=np.random.default_rng(a.seed)

    # screen one big pool once; each 'top' is a nested selection from it
    k0=int(rng.integers(10**6,10**7-a.pool))
    print(f"screening pool of {a.pool:,} consecutive anchors...",flush=True)
    sc=screen_c(k0,a.pool,pd,Pmod,offs,W,wv_off)
    order=np.argsort(-sc)
    poolk=np.arange(k0,k0+a.pool)

    # vanilla pool (shared across cells): one set of trials, scored per merit
    kv=rng.integers(10**6,10**7,a.vanilla)
    print(f"running {a.vanilla:,} vanilla trials (shared)...",flush=True)
    t0=time.time(); gv=np.array([trial(int(k),P,design,deep,rP,Wside) for k in kv])
    print(f"  vanilla done ({time.time()-t0:.0f}s)",flush=True)

    rows=[]
    maxtop=max(tops)
    selk=poolk[order[:maxtop]]
    print(f"running {maxtop:,} BEACON trials on the deepest selection...",flush=True)
    t0=time.time(); gb=np.array([trial(int(k),P,design,deep,rP,Wside) for k in selk])
    print(f"  BEACON trials done ({time.time()-t0:.0f}s)",flush=True)

    for M in merits:
        G=int(M*L); sv=int((gv>=G).sum()); rV=sv/a.vanilla
        for top in tops:
            sb=int((gb[:top]>=G).sum()); rB=sb/top
            lift=rB/max(rV,1e-12)
            se=math.sqrt(1/max(sb,1)+1/max(sv,1))
            rows.append(dict(D=D,merit=M,top=top,ratio=a.pool/top,
                sB=sb,nB=top,sV=sv,nV=a.vanilla,rateB=rB,rateV=rV,
                lift=lift,ci_lo=lift*math.exp(-1.96*se),ci_hi=lift*math.exp(1.96*se)))
    with open("sweep_out.csv","w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader()
        for r in rows: w.writerow(r)
    print(f"\n{'merit':>6}{'top':>8}{'ratio':>7}{'sB':>4}{'sV':>4}{'lift':>7}{'  95% CI':>16}")
    for r in rows:
        print(f"{r['merit']:>6}{r['top']:>8}{r['ratio']:>7.0f}{r['sB']:>4}{r['sV']:>4}"
              f"{r['lift']:>7.2f}   [{r['ci_lo']:.2f},{r['ci_hi']:.2f}]")
    print("-> sweep_out.csv")

if __name__=="__main__": main()
