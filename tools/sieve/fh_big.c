#include "bsieve.c"
static uint64_t rng2 = 0x1234567887654321ULL; static uint64_t xr2(void) { rng2 ^= rng2 << 13; rng2 ^= rng2 >> 7; rng2 ^= rng2 << 17; return rng2; }
static int isp2(int64_t n) { if (n < 2) return 0; for (int64_t d = 2; d * d <= n; d++) if (n % d == 0) return 0; return 1; }
int main(int argc, char **argv) {
    int trials = argc > 1 ? atoi(argv[1]) : 50, bad = 0; int64_t W = 1569;
    for (int tr = 0; tr < trials; tr++) {
        int64_t p; do { p = 2000000000LL + (int64_t)(xr2() % 8000000000ULL); } while (!isp2(p));
        int64_t s = 1 + (int64_t)(xr2() % (uint64_t)(p - 1)), off = (int64_t)(xr2() % (uint64_t)p);
        int64_t y_fh = fm_next_hit(s, p, off, W, 0, p);
        int64_t y_br = -1; for (int64_t y = 0; y < p; y++) { int64_t x = (int64_t)(((__int128)s * y + off) % p); if (x < W) { y_br = y; break; } }
        if (y_fh != y_br) { bad++; if (bad <= 4) fprintf(stderr, "MISMATCH p=%ld s=%ld off=%ld: fm_next_hit %ld vs brute %ld\n", (long)p, (long)s, (long)off, (long)y_fh, (long)y_br); }
    }
    printf("fm_next_hit at p in (2e9, 1e10): %d trials, mismatches %d -> %s\n", trials, bad, bad ? "FAIL" : "PASS"); return bad != 0;
}
