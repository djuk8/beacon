# 9. Reproducibility
Every find reconstructs from one small text file (k, zd, d,
fences); every number in this paper reconstructs from the public
repository plus the data deposit (DOI: [SLOT]). The repository
ships: the certified core (sigma_t1, three-anchor fingerprint at
import), the exact evaluator and pricer (selftests included), the
sieve factory, GPU kernel sources with their gate harness
(2,008,000-verdict known-answer corpus, zero mismatches; Gerbicz
error check on every production test), the gates directory
(known-answer + bit-exact equivalence + fault injection),
LINEAGE.md (per-tool SHA-256 and certifying gate), preregistration
files with dates, and the corrections ledger. deploy/kit_v1 takes
a fresh 4-GPU machine from login to a certified, self-healing
hunt in under thirty minutes. Verification chain for any claimed
gap: sieved interior = divisibility-certified composite; every
tested candidate carries a GEC-checked or PFGW verdict; finds are
re-proved with an independent library before banking; the public
notary re-proves endpoints and re-sieves the interior on
independent hardware at submission. Nothing depends on trusting
one program, one machine, or us. License: code under Apache-2.0; documents and
data under CC BY 4.0 (LICENSE, LICENSE-DOCS, NOTICE).
