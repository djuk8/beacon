/* fk_walk.c -- Franke-Kleinjung lattice enumeration for the linear-form sieve (C, 2026-09-08).
 * Landings of prime p in the block are the lattice points (t, i), 0 <= t < T, 0 <= i < I, with
 *     t == tc + i*s  (mod p),   0 < s < p,  p > T.
 * Reduce the basis {(-p,0),(s,1)} of L0 = {(t,i): t == i*s mod p} to (a0,a1),(b0,b1) with
 *     -T < a0 <= 0 <= b0 < T  and  b0 - a0 >= T,
 * then from any lattice point (x,y) with 0 <= x < T the next point with larger y and 0 <= x' < T is
 *     x >= -a0 : (x,y)+(a0,a1)     x < T - b0 : (x,y)+(b0,b1)     else : (x,y)+(a0+b0, a1+b1).
 * The first point is found with the existing first-hit primitive (once per prime). */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

static inline void fk_reduce(int64_t p, int64_t s, int64_t T, int64_t *A0, int64_t *A1, int64_t *B0, int64_t *B1) {
    /* Basis {(-p,0),(s,1)} of L0 = {(t,i): t == i*s (mod p)}, 0 < s < p, p > T.
       Euclid on the t-coordinates: while both |a0| and b0 are >= T reduce the larger by the smaller (full quotient);
       the final step uses the MINIMAL quotient that brings the coordinate under T, which guarantees b0 - a0 >= T. */
    int64_t a0 = -p, a1 = 0, b0 = s, b1 = 1;
    for (;;) {
        if (-a0 >= T && b0 >= T) {
            if (-a0 >= b0) { int64_t q = (-a0) / b0; a0 += q * b0; a1 += q * b1; }
            else           { int64_t q = b0 / (-a0); b0 += q * a0; b1 += q * a1; }
            continue;
        }
        if (-a0 >= T) { int64_t q = (-a0 - T) / b0 + 1; a0 += q * b0; a1 += q * b1; break; }   /* b0 < T: -a0' in [T-b0, T) */
        if (b0 >= T)  { int64_t q = (b0 - T) / (-a0) + 1; b0 += q * a0; b1 += q * a1; break; }  /* -a0 < T: b0' in [T+a0, T) */
        break;
    }
    if (!(-T < a0 && a0 <= 0 && 0 <= b0 && b0 < T && b0 - a0 >= T && a1 >= 1 && b1 >= 1)) {
        fprintf(stderr, "fk_reduce: postcondition failed p=%ld s=%ld T=%ld -> a=(%ld,%ld) b=(%ld,%ld)\n", (long)p, (long)s, (long)T, (long)a0, (long)a1, (long)b0, (long)b1); abort();
    }
    *A0 = a0; *A1 = a1; *B0 = b0; *B1 = b1;
}

/* enumerate all landings; call cb(t, i, ctx) for each; returns count. first point via linear search here
   (the production version uses fm_next_hit). */
typedef void (*fk_cb)(int64_t t, int64_t i, void *ctx);
int64_t fk_enumerate(int64_t p, int64_t s, int64_t tc, int64_t T, int64_t I, fk_cb cb, void *ctx) {
    int64_t a0, a1, b0, b1; fk_reduce(p, s, T, &a0, &a1, &b0, &b1);
    /* first point: smallest i in [0, I) with (tc + i*s) mod p < T -- brute here (referee harness) */
    int64_t x = -1, y = -1;
    for (int64_t i = 0; i < I; i++) { int64_t t = (tc + (__int128)i * s) % p; if (t < T) { x = t; y = i; break; } }
    if (y < 0) return 0;
    int64_t n = 0;
    while (y < I) {
        cb(x, y, ctx); n++;
        if (x >= -a0)         { x += a0; y += a1; }            /* high region: a valid (x' in [0, T+a0)), b not */
        else if (x < T - b0)  { x += b0; y += b1; }            /* low region: b valid (x' in [b0, T)), a not */
        else                  { x += a0 + b0; y += a1 + b1; }  /* middle [T-b0, -a0): only a+b lands (x' in [T+a0, b0)) */
    }
    return n;
}

/* ---- referee: brute force vs FK on random (p, s, tc), T in {20000, 240000}, I = 1569 ---- */
typedef struct { int64_t *buf; int64_t n, cap; } vec_t;
static void push(int64_t t, int64_t i, void *ctx) { vec_t *v = ctx; if (v->n == v->cap) { v->cap = v->cap ? 2*v->cap : 1024; v->buf = realloc(v->buf, v->cap * 2 * sizeof(int64_t)); } v->buf[2*v->n] = t; v->buf[2*v->n+1] = i; v->n++; }
static int cmp2(const void *A, const void *B) { const int64_t *a = A, *b = B; if (a[1] != b[1]) return a[1] < b[1] ? -1 : 1; return a[0] < b[0] ? -1 : (a[0] > b[0]); }
static uint64_t rng = 88172645463325252ULL; static uint64_t xr(void) { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return rng; }
static int is_prime(int64_t n) { if (n < 2) return 0; for (int64_t d = 2; d * d <= n; d++) if (n % d == 0) return 0; return 1; }
int main(int argc, char **argv) {
    int64_t trials = argc > 1 ? atoll(argv[1]) : 2000, I = 1569, bad = 0, tot = 0;
    for (int64_t tr = 0; tr < trials; tr++) {
        int64_t T = (tr & 1) ? 240000 : 20000;
        int64_t p; do { p = 1000003 + (int64_t)(xr() % 99000000); } while (!is_prime(p));
        int64_t s = 1 + (int64_t)(xr() % (p - 1)), tc = (int64_t)(xr() % p);
        vec_t fk = {0}, br = {0};
        fk_enumerate(p, s, tc, T, I, push, &fk);
        for (int64_t i = 0; i < I; i++) { int64_t t = (tc + (__int128)i * s) % p; for (; t < T; t += p) push(t, i, &br); }
        qsort(fk.buf, fk.n, 2 * sizeof(int64_t), cmp2); qsort(br.buf, br.n, 2 * sizeof(int64_t), cmp2);
        int ok = fk.n == br.n; for (int64_t e = 0; ok && e < fk.n * 2; e++) ok = fk.buf[e] == br.buf[e];
        if (!ok) { bad++; if (bad <= 5) fprintf(stderr, "MISMATCH p=%ld s=%ld tc=%ld T=%ld: fk %ld vs brute %ld\n", (long)p, (long)s, (long)tc, (long)T, (long)fk.n, (long)br.n); }
        tot += br.n; free(fk.buf); free(br.buf);
    }
    printf("fk referee: %ld trials, %ld landings, mismatches %ld -> %s\n", (long)trials, (long)tot, (long)bad, bad ? "FAIL" : "PASS");
    return bad != 0;
}
