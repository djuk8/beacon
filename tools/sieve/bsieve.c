/* bsieve.c v2 -- persistent bucket sieve, memory-disciplined (C, 2026-09-09 night).
 * v1 lessons (measured on box1 beside production): 48-B records + random appends into thousands of bucket vectors
 * + P private 48-MB bitmaps per block = memory-bound at 3-4 s/ring. v2: 24-B packed records, STAGED pushes (per-bucket
 * write buffers flushed as sequential copies), landings emitted to per-chunk buffers and applied to ONE shared bitmap
 * in a chunk-owner pass (no atomics, no private bitmaps). Same math, same kills; referee + identity gated.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef __int128 i128;

/* ---------- packed record: 3 x uint64 ----------
   w0 = p (36 bits) | i (11 bits, <<36) | a0+2048 (12 bits, <<47)
   w1 = t (44 bits) | b0 (12 bits, <<44)
   w2 = a1 (40 bits)          b1 recomputed from the determinant: a0*b1 - a1*b0 = -p  ->  b1 = (a1*b0 - p) / a0   */
typedef struct { uint64_t w0, w1, w2; } rec_t;
static inline rec_t rec_pack(uint64_t p, int64_t t, int32_t i, int32_t a0, int64_t a1, int32_t b0) {
    rec_t r; r.w0 = p | ((uint64_t)(uint32_t)i << 36) | ((uint64_t)(uint32_t)(a0 + 2048) << 47);
    r.w1 = (uint64_t)t | ((uint64_t)(uint32_t)b0 << 44); r.w2 = (uint64_t)a1; return r; }
#define R_P(r)  ((r).w0 & ((1ULL << 36) - 1))
#define R_I(r)  ((int32_t)(((r).w0 >> 36) & 2047))
#define R_A0(r) ((int32_t)(((r).w0 >> 47) & 4095) - 2048)
#define R_T(r)  ((int64_t)((r).w1 & ((1ULL << 44) - 1)))
#define R_B0(r) ((int32_t)(((r).w1 >> 44) & 4095))
#define R_A1(r) ((int64_t)(r).w2)

static inline uint64_t mulmod(uint64_t a, uint64_t b, uint64_t p) { return (uint64_t)(((__uint128_t)a * b) % p); }
static inline void fk_reduce(int64_t p, int64_t s, int64_t W, int32_t *A0, int64_t *A1, int32_t *B0, int64_t *B1) {
    int64_t a0 = -p, a1 = 0, b0 = s, b1 = 1;
    for (;;) {
        if (-a0 >= W && b0 >= W) { if (-a0 >= b0) { int64_t q = (-a0) / b0; a0 += q * b0; a1 += q * b1; } else { int64_t q = b0 / (-a0); b0 += q * a0; b1 += q * a1; } continue; }
        if (-a0 >= W) { int64_t q = (-a0 - W) / b0 + 1; a0 += q * b0; a1 += q * b1; break; }
        if (b0 >= W)  { int64_t q = (b0 - W) / (-a0) + 1; b0 += q * a0; b1 += q * a1; break; }
        break;
    }
    *A0 = (int32_t)a0; *A1 = a1; *B0 = (int32_t)b0; *B1 = b1;
}

static int64_t first_hit(int64_t a, int64_t m, int64_t l, int64_t r) {
    if (l == 0) return 0;
    if (a == 0) return -1;
    int64_t x0 = (l + a - 1) / a;                    /* first multiple of a reaching l without wrapping */
    if (a * x0 <= r) return x0;
    /* need k>=1 wraps: a*x = l + k*m + d (0<=d<=r-l)  =>  (k*m) mod a in [(-r) mod a, (-l) mod a] */
    int64_t ma = m % a;
    int64_t lo = ((-r) % a + a) % a, hi = ((-l) % a + a) % a;
    int64_t k = -1;
    if (r - l + 1 >= a) k = 1;                        /* arc covers all residues */
    else if (lo <= hi) k = first_hit(ma, a, lo, hi);
    else {                                            /* wrapped arc: two pieces, take the smaller k */
        int64_t k1 = first_hit(ma, a, lo, a - 1), k2 = first_hit(ma, a, 0, hi);
        if (k1 < 0) k = k2; else if (k2 < 0) k = k1; else k = k1 < k2 ? k1 : k2;
    }
    if (k < 0) return -1;
    if (k == 0) k = 1;                                /* k=0 would be a direct hit, already excluded */
    i128 num = (i128)k * m + l;
    return (int64_t)((num + a - 1) / a);
}

static int64_t fm_next_hit(int64_t a, int64_t p, int64_t off, int64_t T, int64_t i0, int64_t I) {
    int64_t c = (int64_t)(((__int128)a * i0 + off) % p);
    int64_t lo = ((-c) % p + p) % p, hi = ((T - 1 - c) % p + p) % p, y;
    if (T >= p) y = 0;
    else if (lo <= hi) y = first_hit(a, p, lo, hi);
    else { int64_t y1 = first_hit(a, p, lo, p - 1), y2 = first_hit(a, p, 0, hi);
           y = (y1 < 0) ? y2 : (y2 < 0) ? y1 : (y1 < y2 ? y1 : y2); }
    if (y < 0) return -1;
    int64_t i = i0 + y; return i < I ? i : -1;
}


/* ---------- buckets with staged pushes ---------- */
enum { STAGE = 64 };                                   /* records staged per bucket before a sequential flush */
typedef struct { rec_t *v; size_t n, cap; rec_t st[STAGE]; uint8_t sn; } bucket_t;
typedef struct {
    int64_t T, Tc, I, Sh, k0; size_t nb; bucket_t *bk; int64_t cur; size_t BW; int64_t applied;
    /* per-block landing buffers by chunk (filled by sieve, applied by owner pass) */
    uint32_t **lb; size_t *ln, *lc; int nch;
    const int32_t *tmap;     /* optional: block-local t -> compact row (-1 = window not hunted); NULL = rows are t */
} bsieve_t;
static inline void bflush(bucket_t *b) {
    if (b->n + b->sn > b->cap) { size_t nc = b->cap ? b->cap * 2 : 1024; while (nc < b->n + b->sn) nc *= 2; b->v = realloc(b->v, nc * sizeof(rec_t)); if (!b->v) abort(); b->cap = nc; }
    memcpy(b->v + b->n, b->st, (size_t)b->sn * sizeof(rec_t)); b->n += b->sn; b->sn = 0;
}
static inline void bpush(bsieve_t *S, const rec_t *r) {
    bucket_t *b = &S->bk[(size_t)((uint64_t)R_T(*r) / (uint64_t)S->T) % S->nb];
    b->st[b->sn++] = *r; if (b->sn == STAGE) bflush(b);
}
static inline void bnext(rec_t *r, int64_t I) {
    int64_t x = R_I(*r), y = R_T(*r); int32_t a0 = R_A0(*r), b0 = R_B0(*r); int64_t a1 = R_A1(*r);
    int64_t b1 = ((i128)a1 * b0 - (i128)R_P(*r)) / a0;                /* determinant: a0*b1 - a1*b0 = -p */
    if (x >= -(int64_t)a0)   { x += a0;      y += a1; }
    else if (x < I - b0)     { x += b0;      y += b1; }
    else                     { x += a0 + b0; y += a1 + b1; }
    r->w0 = (r->w0 & ~(2047ULL << 36)) | ((uint64_t)(uint32_t)x << 36);
    r->w1 = (r->w1 & ~((1ULL << 44) - 1)) | (uint64_t)y;
}
bsieve_t *bsieve_init(const int64_t *qd, const int64_t *PEd, int64_t nq, int64_t k0, int64_t T, int64_t hi, int max_ahead) {
    bsieve_t *S = calloc(1, sizeof *S); S->T = T; S->Tc = 4096; S->Sh = hi / 2; S->I = 2 * S->Sh + 1; S->k0 = k0; S->nb = (size_t)max_ahead;
    S->bk = calloc(S->nb, sizeof(bucket_t)); S->BW = (size_t)((S->I + 63) / 64); S->cur = 0;
    S->nch = (int)((T + S->Tc - 1) / S->Tc); S->lb = calloc(S->nch, sizeof(uint32_t *)); S->ln = calloc(S->nch, sizeof(size_t)); S->lc = calloc(S->nch, sizeof(size_t));
    for (int64_t q = 0; q < nq; q++) {
        uint64_t p = (uint64_t)qd[q], pe = (uint64_t)PEd[q] % p; uint64_t B = (2 * pe) % p; if (!B) continue;
        uint64_t inv2 = (p + 1) / 2, k0m = (uint64_t)(k0 % (int64_t)p);
        uint64_t i0 = (uint64_t)(((uint64_t)S->Sh % p + p - mulmod(mulmod(k0m, pe, p), inv2, p)) % p);
        uint64_t sp = p - pe;
        int64_t t = fm_next_hit((int64_t)sp, (int64_t)p, (int64_t)i0, S->I, 0, (int64_t)p);
        if (t < 0) continue;
        int32_t i = (int32_t)((i0 + (__uint128_t)(uint64_t)t * sp) % p);
        int32_t a0, b0; int64_t a1, b1; fk_reduce((int64_t)p, (int64_t)sp, S->I, &a0, &a1, &b0, &b1);
        if ((uint64_t)t / (uint64_t)T >= S->nb) { fprintf(stderr, "bsieve: prime %lu first landing %ld beyond ring\n", (unsigned long)p, (long)t); abort(); }
        rec_t r = rec_pack(p, t, i, a0, a1, b0); bpush(S, &r);
    }
    for (size_t b = 0; b < S->nb; b++) bflush(&S->bk[b]);
    return S;
}
/* phase 1: sieve block S->cur -> landing buffers (no bitmap access). */
void bsieve_emit(bsieve_t *S) {
    int64_t base = S->cur * S->T, lim = base + S->T;
    bucket_t *b = &S->bk[(size_t)S->cur % S->nb]; bflush(b);
    rec_t *v = b->v; size_t n = b->n; b->v = NULL; b->n = b->cap = 0;
    for (int c = 0; c < S->nch; c++) S->ln[c] = 0;
    for (size_t e = 0; e < n; e++) {
        rec_t r = v[e];
        while (R_T(r) < lim) {
            uint32_t tl = (uint32_t)(R_T(r) - base); int c = (int)(tl / S->Tc);
            if (S->ln[c] == S->lc[c]) { S->lc[c] = S->lc[c] ? S->lc[c] * 2 : 8192; S->lb[c] = realloc(S->lb[c], S->lc[c] * 4); if (!S->lb[c]) abort(); }
            S->lb[c][S->ln[c]++] = (tl << 11) | (uint32_t)R_I(r);
            bnext(&r, S->I);
        }
        bpush(S, &r);
    }
    free(v); S->cur++;
}
/* phase 2: apply this sieve's landing buffer for chunk c to bits (caller guarantees one writer per chunk) */
void bsieve_apply_chunk(bsieve_t *S, int c, uint64_t *bits) {
    uint32_t *q = S->lb[c]; size_t m = S->ln[c];
    for (size_t e = 0; e < m; e++) { uint32_t tl = q[e] >> 11, ii = q[e] & 2047; int64_t r = S->tmap ? S->tmap[tl] : (int64_t)tl; if (r < 0) continue; bits[(size_t)r * S->BW + (ii >> 6)] &= ~(1ULL << (ii & 63)); }
    S->applied += m; S->ln[c] = 0;
}
void bsieve_block(bsieve_t *S, uint64_t *bits) { bsieve_emit(S); for (int c = 0; c < S->nch; c++) bsieve_apply_chunk(S, c, bits); }

/* ---------------- referee: brute force kills on random small progressions vs bsieve (T=1000, I=101, p<=200003) ---------------- */
#ifdef BS_REFEREE
static uint64_t rng = 0x9E3779B97F4A7C15ULL; static uint64_t xr(void) { rng ^= rng << 13; rng ^= rng >> 7; rng ^= rng << 17; return rng; }
static int isp(int64_t n) { if (n < 2) return 0; for (int64_t d = 2; d * d <= n; d++) if (n % d == 0) return 0; return 1; }
int main(int argc, char **argv) {
    int trials = argc > 1 ? atoi(argv[1]) : 200; int bad = 0; long tot = 0;
    for (int tr = 0; tr < trials; tr++) {
        int64_t T = 500 + (int64_t)(xr() % 1500), hi = 20 + (int64_t)(xr() % 300); hi -= hi & 1;   /* even hi */
        int nq = 40; int64_t qd[64], PEd[64]; int cnt = 0;
        while (cnt < nq) { int64_t p = 1009 + (int64_t)(xr() % 200000); if (isp(p)) { qd[cnt] = p; PEd[cnt] = (int64_t)(xr() % p); cnt++; } }
        int64_t k0 = (int64_t)(xr() % 1000000) | 1; int NB = 4;
        int64_t pmax = 0; for (int q = 0; q < nq; q++) if (qd[q] > pmax) pmax = qd[q];
        int nbk = (int)(pmax / T) + 3;                      /* ring in BLOCKS: gaps up to ~p rows when sp is small */
        bsieve_t *S = bsieve_init(qd, PEd, nq, k0, T, hi, nbk);
        size_t BW = S->BW; uint64_t *bits = malloc((size_t)T * BW * 8);
        for (int b = 0; b < NB; b++) {
            memset(bits, 0xFF, (size_t)T * BW * 8);
            bsieve_block(S, bits);
            for (int64_t tt = 0; tt < T; tt++) {                       /* brute: a bit is dead iff ANY prime kills it */
                int64_t t = (int64_t)b * T + tt;
                for (int64_t i = 0; i < S->I; i++) {
                    int64_t j = 2 * (i - S->Sh); int dead = 0;
                    for (int q = 0; q < nq && !dead; q++) {
                        uint64_t p = (uint64_t)qd[q], pe = (uint64_t)PEd[q] % p; if ((2 * pe) % p == 0) continue;
                        __int128 val = ((__int128)((k0 + 2 * t) % (int64_t)p) * (int64_t)pe + j) % (int64_t)p; if (val < 0) val += p;
                        dead = (val == 0);
                    }
                    int alive = (bits[(size_t)tt * BW + (i >> 6)] >> (i & 63)) & 1; tot++;
                    if (dead == alive) { if (bad < 5) fprintf(stderr, "MISMATCH tr=%d blk=%d t=%ld i=%ld dead=%d alive=%d\n", tr, b, (long)t, (long)i, dead, alive); bad++; }
                }
            }
        }
        free(bits);
    }
    printf("bsieve referee: %d trials, %ld (t,i,p) checks, mismatches %d -> %s\n", trials, tot, bad, bad ? "FAIL" : "PASS");
    return bad != 0;
}
#endif
