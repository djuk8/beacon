#!/usr/bin/env python3
"""patch_nogec.py -- add a compile-time switch FERMAT_GEC to g1_fermat_v3.cu (edits the given file IN PLACE, asserts every anchor).
FERMAT_GEC=1 (default): unchanged. FERMAT_GEC=0: the same base-2 ladder with no Gerbicz-Li bookkeeping and no span verification;
the ladder arithmetic is untouched, so verdicts are byte-identical by construction (the gate checks it anyway).
Build:  nvcc ... -DFERMAT_GEC=0 -o g1_nogec g1_fermat_v3.cu      Gate: verdict identity vs the GEC build (--skip-inject for G2)."""
import sys
p = sys.argv[1]; s = open(p).read(); n = 0
def rep(old, new):
    global s, n
    c = s.count(old); assert c == 1, f"anchor found {c} times: {old[:60]!r}"; s = s.replace(old, new); n += 1
if "FERMAT_GEC" in s: print("already patched"); sys.exit(0)
rep("#include <stdio.h>\n", "#ifndef FERMAT_GEC\n#define FERMAT_GEC 1   /* 0 = no Gerbicz-Li check (v3.5): same ladder, same verdicts, ~12% less arithmetic */\n#endif\n#include <stdio.h>\n")
rep("      if(chunk_in_blk==J) {                    /* block boundary */", "      if(FERMAT_GEC && chunk_in_blk==J) {      /* block boundary (compiled out with FERMAT_GEC=0) */")
rep("    if(blk_in_span>0) {                        /* final partial span */", "    if(FERMAT_GEC && blk_in_span>0) {          /* final partial span (compiled out with FERMAT_GEC=0) */")
open(p, "w").write(s); print(f"patched {p}: {n} edits")
