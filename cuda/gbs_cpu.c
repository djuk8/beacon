/* gbs_cpu.c -- CPU twin of cuda/gbs.cu v8.56 (same ctypes API, same arithmetic, the three kernels as serial loops).
 * Purpose: gates. (1) gbsd.py runs end to end on a machine without a GPU (--gpu-api gbs_cpu.so): rings, selection, packing, state.
 * (2) On the box it is the GPU's referee: gate_856.sh demands GPU rings == CPU-twin rings, byte for byte. Not a production path.
 * Every kernel body is a line-for-line copy of gbs.cu with the thread index turned into a loop index; atomicAnd -> &= (the kill set
 * is order-independent). gbs_create COPIES every input (the GPU version uploads copies; gbsd.py frees/reuses its arrays after create).
 * Build: gcc -O3 -march=native -shared -fPIC -o gbs_cpu.so gbs_cpu.c */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct { uint64_t w0, w1, w2; } rec_t;                    /* bsieve.c v2 packed record */
#define R_P(r)  ((r).w0 & ((1ULL << 36) - 1))
#define R_I(r)  ((int32_t)(((r).w0 >> 36) & 2047))
#define R_A0(r) ((int32_t)(((r).w0 >> 47) & 4095) - 2048)
#define R_T(r)  ((int64_t)((r).w1 & ((1ULL << 44) - 1)))
#define R_B0(r) ((int32_t)(((r).w1 >> 44) & 4095))
#define R_A1(r) ((int64_t)(r).w2)

typedef struct {
    int64_t T, I, Sh, BW, k0; int64_t nrec; rec_t *rec; uint64_t *bits; int64_t cur;
    int nsm; int64_t *sp, *spe, *spc; uint64_t *mask; int64_t *moff;
    int64_t nmed; int64_t *mp, *mtc, *mstep;
    uint64_t *wheel;
    int64_t S;
} gbs_t;

static inline int coprime2310(int64_t k) { return (k % 3) && (k % 5) && (k % 7) && (k % 11); }   /* k odd always */

/* K_A: row init + wheel + small-prime masks (one GPU thread per row) */
static void k_rows(gbs_t *G, int64_t tbase) {
    const int64_t T = G->T, Sh = G->Sh, BW = G->BW, k0 = G->k0, S = G->S;
    for (int64_t row = 0; row < T; row++) {
        uint64_t *w = G->bits + row * BW; int64_t t = tbase + row; int64_t k = k0 + S * t;
        if (!coprime2310(k)) { for (int64_t x = 0; x < BW; x++) w[x] = 0; continue; }
        for (int64_t x = 0; x < BW; x++) w[x] = G->wheel[x];
        for (int q = 0; q < G->nsm; q++) {
            int64_t p = G->sp[q], e = G->spe[q]; if (p == 2) continue; int64_t r;
            if ((2 * e) % p == 0) r = Sh % p; else { int64_t f = (S == 2) ? e : ((S / 2) % p) * e % p; r = (G->spc[q] - (t % p) * f) % p; if (r < 0) r += p; }
            const uint64_t *mk = G->mask + G->moff[q] + r * BW;
            for (int64_t x = 0; x < BW; x++) w[x] &= ~mk[x];
        }
    }
}
/* K_B: medium primes (one GPU thread per (prime, i)) */
static void k_medium(gbs_t *G, int64_t tbase) {
    const int64_t T = G->T, I = G->I, BW = G->BW;
    for (int64_t q = 0; q < G->nmed; q++) {
        int64_t p = G->mp[q];
        for (int64_t i = 0; i < I; i++) {
            int64_t x = (G->mtc[q] + (i * (G->mstep[q] % p)) % p + p - (tbase % p)) % p;     /* absolute t_i = tc + i*step (mod p); block row = t - tbase */
            for (int64_t tt = x; tt < T; tt += p) G->bits[tt * BW + (i >> 6)] &= ~(1ULL << (i & 63));
        }
    }
}
/* K_C: deep primes (one GPU thread per record) */
static void k_deep(gbs_t *G, int64_t tbase) {
    const int64_t T = G->T, I = G->I, BW = G->BW, lim = tbase + T;
    for (int64_t q = 0; q < G->nrec; q++) {
        rec_t r = G->rec[q]; int64_t t = R_T(r); if (t >= lim) continue;
        int64_t x = R_I(r); int32_t a0 = R_A0(r), b0 = R_B0(r); int64_t a1 = R_A1(r); int64_t p = (int64_t)R_P(r);
        int64_t b1 = (a1 * (int64_t)b0 - p) / a0;                                              /* exact: a0*b1 - a1*b0 = -p */
        while (t < lim) {
            G->bits[(t - tbase) * BW + (x >> 6)] &= ~(1ULL << (x & 63));
            if (x >= -(int64_t)a0)   { x += a0;      t += a1; }
            else if (x < I - b0)     { x += b0;      t += b1; }
            else                     { x += a0 + b0; t += a1 + b1; }
        }
        r.w0 = (r.w0 & ~(2047ULL << 36)) | ((uint64_t)(uint32_t)x << 36);
        r.w1 = (r.w1 & ~((1ULL << 44) - 1)) | (uint64_t)t;
        G->rec[q] = r;
    }
}

void *gbs_create(int dev, int64_t T, int64_t hi, int64_t k0, const rec_t *records, int64_t nrec,
                 int nsm, const int64_t *sp, const int64_t *spe, const int64_t *spc, const uint64_t *mask, const int64_t *moff, int64_t mask_words,
                 int64_t nmed, const int64_t *mp, const int64_t *mtc, const int64_t *mstep, const uint64_t *wheel) {
    (void)dev;
    gbs_t *G = (gbs_t *)calloc(1, sizeof *G); if (!G) return NULL;
    G->T = T; G->Sh = hi / 2; G->I = 2 * G->Sh + 1; G->BW = (G->I + 63) / 64; G->k0 = k0; G->nrec = nrec; G->nsm = nsm; G->nmed = nmed; G->S = 2;
    #define CP(dst, src, n, ty) do { (dst) = (ty *)malloc((size_t)(n) * sizeof(ty) + 16); if (!(dst)) return NULL; if ((n) > 0) memcpy((dst), (src), (size_t)(n) * sizeof(ty)); } while (0)
    CP(G->rec, records, nrec, rec_t);
    G->bits = (uint64_t *)malloc((size_t)T * G->BW * 8); if (!G->bits) return NULL;
    CP(G->sp, sp, nsm, int64_t); CP(G->spe, spe, nsm, int64_t); CP(G->spc, spc, nsm, int64_t); CP(G->mask, mask, mask_words, uint64_t); CP(G->moff, moff, nsm, int64_t);
    CP(G->mp, mp, nmed, int64_t); CP(G->mtc, mtc, nmed, int64_t); CP(G->mstep, mstep, nmed, int64_t); CP(G->wheel, wheel, G->BW, uint64_t);
    #undef CP
    return G;
}
int gbs_block(void *g, uint64_t *host_bits) {
    gbs_t *G = (gbs_t *)g; int64_t tbase = G->cur * G->T;
    k_rows(G, tbase); k_medium(G, tbase); k_deep(G, tbase);
    memcpy(host_bits, G->bits, (size_t)G->T * G->BW * 8);
    G->cur++; return 0;
}
int64_t gbs_cur(void *g) { return ((gbs_t *)g)->cur; }
int gbs_set_step(void *g, int64_t S) { gbs_t *G = (gbs_t *)g; if (S < 2 || (S & 1)) return -1; if (G->cur) return -2; G->S = S; return 0; }
void gbs_sync(void) {}
const char *gbs_twin(void) { return "gbs_cpu v8.56 (CPU twin of gbs.cu)"; }
