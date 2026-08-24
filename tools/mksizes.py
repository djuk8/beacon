#!/usr/bin/env python3
"""mksizes.py -- write the G2S1 sizes sidecar for g1_fermat_v3 --ee from one or more manifests (bin order).
usage: mksizes.py out.sizes.bin a.manifest.json [b.manifest.json ...]"""
import sys, json, struct
out = sys.argv[1]; sizes = []
for m in sys.argv[2:]: sizes += [int(s) for s in json.load(open(m))["sizes"]]
with open(out, "wb") as f: f.write(struct.pack("<II", 0x31533247, len(sizes)) + struct.pack(f"<{len(sizes)}I", *sizes))
print(f"{out}: {len(sizes)} ks, {sum(sizes)} candidates")
