/* gbs.cu -- GPU-resident bucket sieve for the swap construction (CUDA, 2026-09-10 night).
 * All per-prime arithmetic (first landing, FK basis, small-prime residues) is computed ONCE on the CPU by the certified
 * code (bsieve.c v2 records; js2 constants; mask constants) and uploaded. Per block the GPU does only 64-bit stepping:
 *   K_A: per window row: init (coprime windows alive, j=0 dead), small-prime masks (p <= PMASK), wheel primes.
 *   K_B: per (prime, i) for medium primes (PMASK < p <= Q1=1e6): walk t = t_i, t_i+p, ... < T.
 *   K_C: per prime for deep primes (Q1 < p <= Qd): FK record stepping; landings applied by atomicAnd; record updated.
 * Layout: T rows x BW words (1 = alive). Exact same kill set as the CPU pipeline (gate: byte-identical rings). */
#include <cuda_runtime.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct { uint64_t w0, w1, w2; } rec_t;                    /* bsieve.c v2 packed record */
#define R_P(r)  ((r).w0 & ((1ULL << 36) - 1))
#define R_I(r)  ((int32_t)(((r).w0 >> 36) & 2047))
#define R_A0(r) ((int32_t)(((r).w0 >> 47) & 4095) - 2048)
#define R_T(r)  ((int64_t)((r).w1 & ((1ULL << 44) - 1)))
#define R_B0(r) ((int32_t)(((r).w1 >> 44) & 4095))
#define R_A1(r) ((int64_t)(r).w2)

typedef struct {
    int64_t T, I, Sh, BW, k0; int64_t nrec; rec_t *d_rec; uint64_t *d_bits; int64_t cur;
    /* small-prime masks */ int nsm; int64_t *d_sp, *d_spe, *d_spc; uint64_t *d_mask; int64_t *d_moff; /* mask offset per prime (words) */
    /* medium primes */ int64_t nmed; int64_t *d_mp, *d_mtc, *d_mstep; /* tc, step per prime (js2 constants) */
    uint64_t *d_wheel;                                              /* wheel template for wheel primes in the medium table */
} gbs_t;

#define CK(x) do { cudaError_t e = (x); if (e != cudaSuccess) { fprintf(stderr, "CUDA %s @%d: %s\n", #x, __LINE__, cudaGetErrorString(e)); return -1; } } while (0)

__device__ __forceinline__ int coprime2310(int64_t k) { return (k % 3) && (k % 5) && (k % 7) && (k % 11); }   /* k odd always */

/* K_A: row init + wheel + small-prime masks */
__global__ void k_rows(int64_t T, int64_t I, int64_t Sh, int64_t BW, int64_t k0, int64_t tbase, uint64_t *bits,
                       int nsm, const int64_t *sp, const int64_t *spe, const int64_t *spc, const uint64_t *mask, const int64_t *moff, const uint64_t *wheel) {
    int64_t row = blockIdx.x * (int64_t)blockDim.x + threadIdx.x; if (row >= T) return;
    uint64_t *w = bits + row * BW; int64_t t = tbase + row; int64_t k = k0 + 2 * t;
    if (!coprime2310(k)) { for (int64_t x = 0; x < BW; x++) w[x] = 0; return; }
    for (int64_t x = 0; x < BW; x++) w[x] = wheel[x];                                     /* alive except j=0 and wheel primes' j==0 mod p */
    for (int q = 0; q < nsm; q++) {
        int64_t p = sp[q], e = spe[q]; if (p == 2) continue; int64_t r;
        if ((2 * e) % p == 0) r = Sh % p; else { r = (spc[q] - (t % p) * e) % p; if (r < 0) r += p; }
        const uint64_t *mk = mask + moff[q] + r * BW;
        for (int64_t x = 0; x < BW; x++) w[x] &= ~mk[x];
    }
}
/* K_B: medium primes, one thread per (prime, i) */
__global__ void k_medium(int64_t T, int64_t I, int64_t BW, int64_t k0, int64_t tbase, uint64_t *bits, int64_t nmed, const int64_t *mp, const int64_t *mtc, const int64_t *mstep) {
    int64_t id = blockIdx.x * (int64_t)blockDim.x + threadIdx.x; if (id >= nmed * I) return;
    int64_t q = id / I, i = id % I; int64_t p = mp[q];
    int64_t x = (mtc[q] + (i * (mstep[q] % p)) % p + p - (tbase % p)) % p;                /* absolute t_i = tc + i*step (mod p); block row = t - tbase */
    for (int64_t tt = x; tt < T; tt += p) { atomicAnd((unsigned long long *)(bits + tt * BW + (i >> 6)), ~(1ULL << (i & 63))); }
}
/* K_C: deep primes, one thread per record */
__global__ void k_deep(int64_t T, int64_t I, int64_t BW, int64_t tbase, uint64_t *bits, int64_t nrec, rec_t *rec) {
    int64_t q = blockIdx.x * (int64_t)blockDim.x + threadIdx.x; if (q >= nrec) return;
    rec_t r = rec[q]; int64_t lim = tbase + T; int64_t t = R_T(r); if (t >= lim) return;
    int64_t x = R_I(r); int32_t a0 = R_A0(r), b0 = R_B0(r); int64_t a1 = R_A1(r); int64_t p = (int64_t)R_P(r);
    int64_t b1 = (a1 * (int64_t)b0 - p) / a0;                                              /* exact: a0*b1 - a1*b0 = -p */
    while (t < lim) {
        atomicAnd((unsigned long long *)(bits + (t - tbase) * BW + (x >> 6)), ~(1ULL << (x & 63)));
        if (x >= -(int64_t)a0)   { x += a0;      t += a1; }
        else if (x < I - b0)     { x += b0;      t += b1; }
        else                     { x += a0 + b0; t += a1 + b1; }
    }
    r.w0 = (r.w0 & ~(2047ULL << 36)) | ((uint64_t)(uint32_t)x << 36);
    r.w1 = (r.w1 & ~((1ULL << 44) - 1)) | (uint64_t)t;
    rec[q] = r;
}

extern "C" {
/* records: nrec packed records from bsieve.c v2 init (flat). small primes: sp/spe/spc (residue constants) + mask table (concatenated per prime, p*BW words each).
   medium primes: mp/mtc/mstep (js2 constants). wheel: BW words. */
void *gbs_create(int dev, int64_t T, int64_t hi, int64_t k0, const rec_t *records, int64_t nrec,
                 int nsm, const int64_t *sp, const int64_t *spe, const int64_t *spc, const uint64_t *mask, const int64_t *moff, int64_t mask_words,
                 int64_t nmed, const int64_t *mp, const int64_t *mtc, const int64_t *mstep, const uint64_t *wheel) {
    if (cudaSetDevice(dev) != cudaSuccess) return NULL;
    gbs_t *G = (gbs_t *)calloc(1, sizeof *G); G->T = T; G->Sh = hi / 2; G->I = 2 * G->Sh + 1; G->BW = (G->I + 63) / 64; G->k0 = k0; G->nrec = nrec; G->nsm = nsm; G->nmed = nmed;
    #define UP(dst, src, n, ty) do { if (cudaMalloc((void **)&(dst), (size_t)(n) * sizeof(ty)) != cudaSuccess) return NULL; if (cudaMemcpy((dst), (src), (size_t)(n) * sizeof(ty), cudaMemcpyHostToDevice) != cudaSuccess) return NULL; } while (0)
    UP(G->d_rec, records, nrec, rec_t);
    if (cudaMalloc((void **)&G->d_bits, (size_t)T * G->BW * 8) != cudaSuccess) return NULL;
    UP(G->d_sp, sp, nsm, int64_t); UP(G->d_spe, spe, nsm, int64_t); UP(G->d_spc, spc, nsm, int64_t); UP(G->d_mask, mask, mask_words, uint64_t); UP(G->d_moff, moff, nsm, int64_t);
    UP(G->d_mp, mp, nmed, int64_t); UP(G->d_mtc, mtc, nmed, int64_t); UP(G->d_mstep, mstep, nmed, int64_t); UP(G->d_wheel, wheel, G->BW, uint64_t);
    #undef UP
    return G;
}
/* process the current block (advance cur), download the bitmap (T*BW words) into host_bits */
int gbs_block(void *g, uint64_t *host_bits) {
    gbs_t *G = (gbs_t *)g; int64_t tbase = G->cur * G->T;
    k_rows<<<(unsigned)((G->T + 255) / 256), 256>>>(G->T, G->I, G->Sh, G->BW, G->k0, tbase, G->d_bits, G->nsm, G->d_sp, G->d_spe, G->d_spc, G->d_mask, G->d_moff, G->d_wheel);
    CK(cudaGetLastError());
    int64_t nb = G->nmed * G->I; k_medium<<<(unsigned)((nb + 255) / 256), 256>>>(G->T, G->I, G->BW, G->k0, tbase, G->d_bits, G->nmed, G->d_mp, G->d_mtc, G->d_mstep);
    CK(cudaGetLastError());
    k_deep<<<(unsigned)((G->nrec + 255) / 256), 256>>>(G->T, G->I, G->BW, tbase, G->d_bits, G->nrec, G->d_rec);
    CK(cudaGetLastError());
    CK(cudaMemcpy(host_bits, G->d_bits, (size_t)G->T * G->BW * 8, cudaMemcpyDeviceToHost));
    G->cur++; return 0;
}
int64_t gbs_cur(void *g) { return ((gbs_t *)g)->cur; }
void gbs_sync(void) { cudaDeviceSynchronize(); }
}
