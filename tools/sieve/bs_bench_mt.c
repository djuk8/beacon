#include "bs_api.c"
#include <time.h>
static double now(void) { struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + ts.tv_nsec * 1e-9; }
static int64_t *load_npy(const char *path, int64_t *n) { FILE *f = fopen(path, "rb"); if (!f) { perror(path); exit(1); } unsigned char hdr[12]; if (fread(hdr,1,10,f)!=10) exit(2); int hl = hdr[8] | (hdr[9] << 8); fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 10 + hl, SEEK_SET); *n = (sz - 10 - hl) / 8; int64_t *a = malloc((size_t)*n * 8); if (fread(a, 8, (size_t)*n, f) != (size_t)*n) exit(3); fclose(f); return a; }
int main(int argc, char **argv) {
    int P = atoi(argv[2]); int64_t T = 240000, hi = 1568, nq, npe; char p1[512], p2[512];
    snprintf(p1, 512, "%s/qd_1000000_100000000.npy", argv[1]); snprintf(p2, 512, "%s/pemd64_1439_2310_100000000.npy", argv[1]);
    int64_t *qd = load_npy(p1, &nq), *pe = load_npy(p2, &npe);
    double t0 = now(); void *M = bs_create_mt(qd, pe, nq, 1000000000001LL, T, hi, P); double t1 = now();
    int64_t BW = ((bsmt_t *)M)->BW; uint64_t *bits = malloc((size_t)T * BW * 8), *ref = NULL;
    printf("P=%d init %.1f s\n", P, t1 - t0);
    for (int b = 0; b < 3; b++) { memset(bits, 0xFF, (size_t)T * BW * 8); double s = now(); bs_block_mt(M, bits); double e = now();
        long alive = 0; for (size_t w = 0; w < (size_t)T * BW; w++) alive += __builtin_popcountll(bits[w]);
        printf("P=%d block %d: %.2f s  alive %ld\n", P, b, e - s, alive); }
    return 0;
}
