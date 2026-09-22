#include "bsieve.c"
static uint64_t rng3 = 0xABCDEF0123456789ULL; static uint64_t xr3(void) { rng3 ^= rng3 << 13; rng3 ^= rng3 >> 7; rng3 ^= rng3 << 17; return rng3; }
static int isp3(int64_t n) { if (n < 2) return 0; for (int64_t d = 2; d * d <= n; d++) if (n % d == 0) return 0; return 1; }
int main(int argc, char **argv) {
    int trials = argc > 1 ? atoi(argv[1]) : 3; int bad = 0; long land = 0;
    for (int tr = 0; tr < trials; tr++) {
        int64_t T = 200000, hi = 1568, NB = 4, nq = 40; int64_t qd[64], PEd[64]; int cnt = 0;
        while (cnt < nq) { int64_t p = 2000000000LL + (int64_t)(xr3() % 8000000000ULL); if (isp3(p)) { qd[cnt] = p; PEd[cnt] = (int64_t)(xr3() % (uint64_t)p); cnt++; } }
        /* sort primes ascending (init assumes qd[nq-1] is the max) */
        for (int i = 0; i < nq; i++) for (int j = i + 1; j < nq; j++) if (qd[j] < qd[i]) { int64_t t = qd[i]; qd[i] = qd[j]; qd[j] = t; t = PEd[i]; PEd[i] = PEd[j]; PEd[j] = t; }
        int64_t k0 = 59416000000001LL;
        bsieve_t *S = bsieve_init(qd, PEd, nq, k0, T, hi, (int)(qd[nq-1] / T) + 3);
        size_t BW = S->BW; uint64_t *bits = malloc((size_t)T * BW * 8);
        for (int b = 0; b < NB; b++) {
            memset(bits, 0xFF, (size_t)T * BW * 8); bsieve_block(S, bits);
            /* expected kills: for each t and prime, j = -(k0+2t)*pe mod p in [-hi, hi]?  (p > 2hi: at most one j) */
            for (int64_t tt = 0; tt < T; tt++) {
                int64_t t = (int64_t)b * T + tt;
                for (int q = 0; q < nq; q++) {
                    uint64_t p = (uint64_t)qd[q], pe = (uint64_t)PEd[q] % p;
                    uint64_t n0 = (uint64_t)(((__uint128_t)(uint64_t)((k0 + 2 * t) % (int64_t)p) * pe) % p);   /* n0(t) mod p */
                    int64_t j = (int64_t)((p - n0) % p); if (j > (int64_t)hi) j -= (int64_t)p;               /* j in (-p, hi] */
                    if (j >= -hi && j <= hi && (j & 1) == 0) {                                                 /* even j only */
                        int64_t i = j / 2 + S->Sh; int alive = (bits[(size_t)tt * BW + (i >> 6)] >> (i & 63)) & 1; land++;
                        if (alive) { bad++; if (bad <= 4) fprintf(stderr, "MISSED KILL tr=%d blk=%d t=%ld j=%ld p=%lu\n", tr, b, (long)t, (long)j, (unsigned long)p); }
                    }
                }
            }
        }
        /* and no extra kills: count alive bits vs expected T*I - kills */
        free(bits);
    }
    printf("large-p referee (p in 2e9..1e10, T=200k, 4 blocks): %d trials, %ld expected landings, missed %d -> %s\n", trials, land, bad, bad ? "FAIL" : "PASS");
    return bad != 0;
}
