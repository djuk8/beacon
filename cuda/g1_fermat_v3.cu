/* BEACON G1 -- batched base-2 Fermat screen with Gerbicz-Li in-ladder checks.
   Handoff-v2 P3: CGBN-based batched-Fermat driver for grinder (GTX 1070,
   sm_61) and the 5090 fleet. GPU verdicts are SCREENING ONLY (doctrine:
   every find is CPU-notarized); the in-ladder check guards the dangerous
   direction -- a transient fault reporting a true PRP as composite would
   silently discard a find, so faults must be DETECTED, not assumed away.

   DUAL BACKEND (one source, same arithmetic API):
     nvcc  -> cgbn_cuda.h device kernel (production screen)
     g++   -DCPU_TEST -> cgbn_mpz.h GMP-backed CPU path (logic gate: the
           same templated routine, bit-compared against gmpy2 by g2_harness)

   LADDER: fixed-window (w=5) left-to-right Montgomery exponentiation of
   base 2 to exponent E = n-1, exactly the CGBN sample_04 powm structure.

   GERBICZ-LI CHECK (derivation):
     Group the w-bit chunks into blocks of J chunks. Let y_m be the ladder
     state at block boundary m. One block does
         y_{m+1} = y_m^(2^(wJ)) * 2^(V_m)   (mod n),
     V_m = the wJ-bit integer formed by the block's chunks. Over any span of
     C consecutive blocks define A = prod_{t=m}^{m+C-1} y_t and
     B = prod_{t=m+1}^{m+C} y_t. Multiplying the block relations:
         B = A^(2^(wJ)) * 2^(sum V_t)       (mod n).
     A and B cost one mont_mul each per block; the verification costs wJ
     squarings + one ~50-bit powm of 2 per span. With w=5, J=8, C=64 the
     overhead is ~6-8%. A corrupted state anywhere inside a span breaks the
     identity => verdict GEC_ALARM (host rescreens / routes to CPU). The
     <=J-1 tail chunks after the last full block are unprotected (few dozen
     mont ops; documented, negligible).

   FILE CONTRACT (g2_harness.py is the other party):
     candidates: u32 magic 'G2C1' | u32 bits | u64 count | count * (bits/32)
                 u32 limbs, little-endian limb order (CGBN cgbn_mem_t layout)
     verdicts:   u32 magic 'G2V1' | u32 bits | u64 count | count bytes
                 0=composite  1=Fermat-2 PRP  2=GEC alarm
   Size classes (TPI/BITS): 8/2048, 16/4096, 32/8192, 32/16384, 32/32768.
   All candidates must be odd (anchored candidates always are).

   usage: g1_fermat cand.bin verdict.bin [--repeat N] [--inject IDX BDRY]
                                         [--device D]
   v3.4 (2026-08-24, C): base-2 bitwise ladder -- window multiplies replaced by
        AMM-safe modular doublings (Rn carry fold; verdicts byte-identical: every
        equality already canonicalizes via cgbn_rem). Window table removed.
        O4' defaults: --chunk 6 --growth 1.15 (10-wave DP optimum, O4_SCHEDULE_NOTE).
   v3.3 (2026-08-22, C): one allocation, bins read straight into instances; --lock PATH = flock held only around the GPU phase.
   v3.2: --bins list.txt (several bins, same bits, list order) for --ee; EARLY-EXIT MODE, legacy path untouched. (v3.0 schedule rounding bug fixed: rint)
     g1_fermat cand.bin verdict.bin --ee sizes.bin [--chunk 6] [--growth 1.15] [--marker 3]
     g1_fermat list.txt verdict.bin --bins --ee sizes.bin [--lock /tmp/raidgpuN.lock]   (list.txt: one bin path per line)
     sizes.bin: u32 magic 'G2S1' | u32 nk | nk * u32 sizes (per-k candidate counts,
     contiguous in cand.bin in the order to test = center-out).  Candidates go to the
     device once; waves of per-k chunks (chunk, chunk*growth, ...) are launched from
     device memory by index; a k stops at its first PRP/alarm; untested positions get
     the marker.  Verdict file byte-identical to ee_serve.py's (same schedule, same stop
     rule).  GEC in-ladder check unchanged.
*/
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <math.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/file.h>

#ifdef CPU_TEST
  /* CGBN's mpz backend is written for nvcc's HOST pass (__CUDACC__ defined,
     __CUDA_ARCH__ not). Emulate that under plain g++: pull the runtime types
     first, then raise __CUDACC__ so cgbn_mpz.h suppresses its conflicting
     dim3 typedef and cgbn.h dispatches to the mpz backend via __GMP_H__. */
  #include <cuda_runtime.h>
  #ifndef __CUDACC__
    #define __CUDACC__ 1
  #endif
  #ifndef __host__
    #define __host__
  #endif
  #ifndef __device__
    #define __device__
  #endif
  #ifndef __forceinline__
    #define __forceinline__ inline
  #endif
#endif
#include <gmp.h>              /* host/CPU: selects the cgbn mpz backend */
#include "cgbn/cgbn.h"

#define MAGIC_C 0x31433247u   /* 'G2C1' LE */
#define MAGIC_V 0x31563247u   /* 'G2V1' LE */
enum { V_COMPOSITE=0, V_PRP=1, V_GEC_ALARM=2 };

template<uint32_t tpi, uint32_t bits>
struct f2_params_t {
  static const uint32_t TPB=0;
  static const uint32_t MAX_ROTATION=4;
  static const uint32_t SHM_LIMIT=0;
  static const bool     CONSTANT_TIME=false;
  static const uint32_t TPI=tpi;
  static const uint32_t BITS=bits;
  /* the 32K class is the per-thread resource monster (32-limb bignums,
     multi-KB window in local mem); shrink its launch + window */
  static const uint32_t LTPB=(bits>=24576) ? 32u : 128u;
  static const uint32_t WINDOW_BITS=(bits>=24576) ? 4u : 5u;
  static const uint32_t GEC_J=8;     /* chunks per block: block exp 2^(w*J) */
  static const uint32_t GEC_C=64;    /* blocks per verification span        */
};

// 1024-bit class (measured 2026-09-25 on an idle RTX 5090: 1.90M tests/s vs 486k at 2048 bits; TPI 4 does not build with CGBN, LTPB 256 / window 5 was the best of the swept variants)
template<> struct f2_params_t<8u,1024u> {
  static const uint32_t TPB=0; static const uint32_t MAX_ROTATION=4; static const uint32_t SHM_LIMIT=0; static const bool CONSTANT_TIME=false;
  static const uint32_t TPI=8; static const uint32_t BITS=1024; static const uint32_t LTPB=256u; static const uint32_t WINDOW_BITS=5u;
  static const uint32_t GEC_J=8; static const uint32_t GEC_C=64; };

template<class params>
class fermat2_t {
  public:
  static const uint32_t w=params::WINDOW_BITS;
  static const uint32_t J=params::GEC_J;
  static const uint32_t C=params::GEC_C;

  typedef struct {
    cgbn_mem_t<params::BITS> n;
    uint32_t                 verdict;
  } instance_t;

  typedef cgbn_context_t<params::TPI, params>   context_t;
  typedef cgbn_env_t<context_t, params::BITS>   env_t;
  typedef typename env_t::cgbn_t                bn_t;
  typedef typename env_t::cgbn_local_t          bn_local_t;

  context_t _context;
  env_t     _env;
  int32_t   _instance;

  __device__ __forceinline__ fermat2_t(cgbn_monitor_t monitor,
      cgbn_error_report_t *report, int32_t instance)
    : _context(monitor, report, (uint32_t)instance), _env(_context),
      _instance(instance) {}

  /* (2^e)~ for small e (<=64 bits), via square-and-multiply on 2~ */
  __device__ __forceinline__ void mont_pow2(bn_t &r, uint64_t e,
      const bn_t &two_m, const bn_t &one_m, const bn_t &n, uint32_t np0) {
    cgbn_set(_env, r, one_m);
    if(e==0) return;
    int32_t top=63;
    while(!((e>>top)&1)) top--;
    for(int32_t b=top;b>=0;b--) {
      cgbn_mont_sqr(_env, r, r, n, np0);
      if((e>>b)&1)
        cgbn_mont_mul(_env, r, r, two_m, n, np0);
    }
  }

  /* v3.4: multiply the AMM representative by 2. cgbn mont ops keep reps in
     [0,2^BITS) (subtract-n on container carry only -- read core_mont_imad.cu
     + impl_mpz.cc, both backends identical). add's container carry is folded
     via 2^BITS === Rn (mod n); terminates in <=2 folds since Rn < n << 2^BITS. */
  __device__ __forceinline__ void mont_dbl(bn_t &x, const bn_t &Rn) {
    int32_t c=cgbn_add(_env, x, x, x);
    while(c) c=cgbn_add(_env, x, x, Rn);
  }

  /* base-2 Fermat with Gerbicz-Li spans; inject_boundary>=0 flips one bit
     of the ladder state mid-block at that boundary count (fault drill). */
  __device__ __forceinline__ uint32_t fermat_gec(const bn_t &n,
      int32_t inject_boundary) {
    bn_t       x, t, E, A, B, y_prev, chk, pw, one_m, two_m, Rn;
    int32_t    position, offset, injected=0;
    uint32_t   index, np0, chunk_in_blk=0, blk_in_span=0, boundary=0;
    uint64_t   Vblk=0, sumV=0;

    cgbn_sub_ui32(_env, E, n, 1);

    /* v3.4 base-2 bitwise ladder: no window table (frees (1<<w) bn_local_t
       of local memory). one_m = R - n == 1~ (AMM rep); two_m = 2~ kept for
       the mont_pow2 span verification. Rn = R mod n REDUCED -- the carry-fold
       constant for mont_dbl. One cgbn_rem per candidate, amortized over
       ~BITS squarings. */
    cgbn_negate(_env, t, n);
    cgbn_set(_env, one_m, t);
    cgbn_rem(_env, Rn, t, n);
    cgbn_set_ui32(_env, x, 2);
    np0=cgbn_bn2mont(_env, x, x, n);
    cgbn_set(_env, two_m, x);

    /* leading (possibly partial) chunk, exactly as sample_04 */
    position=params::BITS - cgbn_clz(_env, E);
    offset=position % w;
    position -= (offset==0) ? (int32_t)w : offset;
    index=cgbn_extract_bits_ui32(_env, E, position, w);
    /* x = 2^index~ by square-and-conditional-double from 1~ (value-identical
       to the old window load; leading zeros of a partial chunk are no-ops) */
    cgbn_set(_env, x, one_m);
    for(uint32_t s=0;s<w;s++) {
      cgbn_mont_sqr(_env, x, x, n, np0);
      if((index>>(w-1u-s))&1u) mont_dbl(x, Rn);
    }

    /* GEC state: span products start at 1~, first block parent is y_0 = x */
    cgbn_set(_env, y_prev, x);
    cgbn_set(_env, A, one_m);
    cgbn_set(_env, B, one_m);

    while(position>0) {
      position -= w;
      index=cgbn_extract_bits_ui32(_env, E, position, w);
      #pragma nounroll
      for(uint32_t s=0;s<w;s++) {
        cgbn_mont_sqr(_env, x, x, n, np0);
        if((index>>(w-1u-s))&1u) mont_dbl(x, Rn);   /* == mul by 2^index after w sqrs */
      }
      Vblk=(Vblk<<w)|index;
      chunk_in_blk++;

      /* fault drill: corrupt the ladder mid-block at a chosen boundary */
      if(inject_boundary>=0 && !injected && boundary==(uint32_t)inject_boundary
          && chunk_in_blk==J/2) {
        uint32_t bit=cgbn_extract_bits_ui32(_env, x, 17, 1);
        cgbn_insert_bits_ui32(_env, x, x, 17, 1, bit^1u);
        injected=1;
      }

      if(chunk_in_blk==J) {                    /* block boundary */
        cgbn_mont_mul(_env, A, A, y_prev, n, np0);
        cgbn_mont_mul(_env, B, B, x, n, np0);
        cgbn_set(_env, y_prev, x);
        sumV+=Vblk; Vblk=0; chunk_in_blk=0;
        boundary++; blk_in_span++;

        if(blk_in_span==C) {                   /* span verification */
          cgbn_set(_env, chk, A);
          #pragma nounroll
          for(uint32_t s=0;s<w*J;s++)
            cgbn_mont_sqr(_env, chk, chk, n, np0);
          mont_pow2(pw, sumV, two_m, one_m, n, np0);
          cgbn_mont_mul(_env, chk, chk, pw, n, np0);
          /* CGBN mont ops return reps in [0,2^BITS) congruent mod n (AMM);
             canonicalize before any equality test */
          cgbn_rem(_env, chk, chk, n);
          cgbn_rem(_env, B, B, n);
          if(!cgbn_equals(_env, chk, B))
            return V_GEC_ALARM;
          cgbn_set(_env, A, one_m);
          cgbn_set(_env, B, one_m);
          sumV=0; blk_in_span=0;
        }
      }
    }

    if(blk_in_span>0) {                        /* final partial span */
      cgbn_set(_env, chk, A);
      #pragma nounroll
      for(uint32_t s=0;s<w*J;s++)
        cgbn_mont_sqr(_env, chk, chk, n, np0);
      mont_pow2(pw, sumV, two_m, one_m, n, np0);
      cgbn_mont_mul(_env, chk, chk, pw, n, np0);
      cgbn_rem(_env, chk, chk, n);
      cgbn_rem(_env, B, B, n);
      if(!cgbn_equals(_env, chk, B))
        return V_GEC_ALARM;
    }
    /* <=J-1 tail chunks above ran unprotected (documented, negligible) */

    cgbn_mont2bn(_env, x, x, n, np0);
    cgbn_rem(_env, x, x, n);           /* canonicalize AMM representative */
    return cgbn_equals_ui32(_env, x, 1) ? V_PRP : V_COMPOSITE;
  }
};

/* ------------------------------------------------------------------ I/O */
typedef struct { uint32_t magic, bits; uint64_t count; } file_hdr_t;

static void *read_candidates(const char *path, uint32_t *bits, uint64_t *count) {
  FILE *f=fopen(path,"rb");
  if(!f){perror(path);exit(2);}
  file_hdr_t h;
  if(fread(&h,sizeof h,1,f)!=1 || h.magic!=MAGIC_C){
    fprintf(stderr,"bad candidate file\n");exit(2);}
  *bits=h.bits; *count=h.count;
  size_t limbs=h.bits/32, bytes=(size_t)h.count*limbs*4;
  void *data=malloc(bytes);
  if(fread(data,1,bytes,f)!=bytes){fprintf(stderr,"short read\n");exit(2);}
  fclose(f);
  return data;
}

static void write_verdicts(const char *path, uint32_t bits, uint64_t count,
                           const uint8_t *v) {
  char tmp[1024];
  snprintf(tmp,sizeof tmp,"%s.tmp",path);
  FILE *f=fopen(tmp,"wb");
  if(!f){perror(tmp);exit(2);}
  file_hdr_t h; h.magic=MAGIC_V; h.bits=bits; h.count=count;
  fwrite(&h,sizeof h,1,f);
  fwrite(v,1,count,f);
  fclose(f);
  if(rename(tmp,path)){perror("rename verdicts");exit(2);}  /* atomic */
}

static double now_s(void){ struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC,&ts); return ts.tv_sec+1e-9*ts.tv_nsec; }

/* -------------------------------------------------------------- GPU path */
#ifndef CPU_TEST
#include "../CGBN/samples/utility/support.h"

template<class params>
__global__ void __launch_bounds__(params::LTPB) kernel_fermat(cgbn_error_report_t *report,
    typename fermat2_t<params>::instance_t *instances, uint32_t count,
    int32_t inject_idx, int32_t inject_boundary) {
  int32_t instance=(blockIdx.x*blockDim.x + threadIdx.x)/params::TPI;
  if(instance>=(int32_t)count) return;
  fermat2_t<params> f(cgbn_report_monitor, report, instance);
  typename fermat2_t<params>::bn_t n;
  cgbn_load(f._env, n, &(instances[instance].n));
  instances[instance].verdict =
    f.fermat_gec(n, instance==inject_idx ? inject_boundary : -1);
}

template<class params>
static void run_gpu(const char *cpath, const char *vpath, int repeat,
                    int inject_idx, int inject_boundary) {
  typedef typename fermat2_t<params>::instance_t instance_t;
  uint32_t bits; uint64_t count;
  uint32_t *limbs=(uint32_t*)read_candidates(cpath,&bits,&count);
  size_t nl=bits/32;
  instance_t *inst=(instance_t*)malloc(sizeof(instance_t)*count);
  for(uint64_t i=0;i<count;i++){
    memcpy(inst[i].n._limbs, limbs+i*nl, nl*4);
    inst[i].verdict=0xFF;
  }
  free(limbs);

  instance_t *g_inst; cgbn_error_report_t *report;
  CUDA_CHECK(cudaMalloc((void**)&g_inst, sizeof(instance_t)*count));
  CUDA_CHECK(cudaMemcpy(g_inst, inst, sizeof(instance_t)*count,
                        cudaMemcpyHostToDevice));
  CUDA_CHECK(cgbn_error_report_alloc(&report));
  int32_t TPB=params::LTPB, IPB=TPB/params::TPI;
  double t0=now_s();
  for(int r=0;r<repeat;r++) {
    kernel_fermat<params><<<(count+IPB-1)/IPB, TPB>>>(report, g_inst,
        (uint32_t)count, inject_idx, inject_boundary);
    /* launch-config errors (out-of-resources etc.) are returned HERE and
       are NOT reported by a later cudaDeviceSynchronize -- check both */
    CUDA_CHECK(cudaGetLastError());
  }
  CUDA_CHECK(cudaDeviceSynchronize());
  double dt=now_s()-t0;
  CGBN_CHECK(report);
  CUDA_CHECK(cudaMemcpy(inst, g_inst, sizeof(instance_t)*count,
                        cudaMemcpyDeviceToHost));
  uint8_t *v=(uint8_t*)malloc(count);
  uint64_t prp=0, alarm=0, untouched=0;
  for(uint64_t i=0;i<count;i++){
    v[i]=(uint8_t)inst[i].verdict;
    prp+=(v[i]==V_PRP); alarm+=(v[i]==V_GEC_ALARM);
    untouched+=(v[i]==0xFF);
  }
  if(untouched){
    fprintf(stderr,"g1_fermat[GPU]: FATAL -- %llu/%llu instances untouched "
            "(kernel did not execute)\n",(unsigned long long)untouched,
            (unsigned long long)count);
    exit(3);
  }
  write_verdicts(vpath,bits,count,v);
  fprintf(stderr,"g1_fermat[GPU]: bits=%u count=%llu repeat=%d | %.3fs | "
          "%.1f tests/s | prp=%llu gec_alarm=%llu\n", bits,
          (unsigned long long)count, repeat, dt, repeat*count/dt,
          (unsigned long long)prp,(unsigned long long)alarm);
  free(v); free(inst);
  CUDA_CHECK(cudaFree(g_inst));
  CUDA_CHECK(cgbn_error_report_free(report));
}
#define RUN run_gpu

/* -------------------------------------------------------------- CPU path */
#else
template<class params>
static void run_cpu(const char *cpath, const char *vpath, int repeat,
                    int inject_idx, int inject_boundary) {
  typedef typename fermat2_t<params>::instance_t instance_t;
  uint32_t bits; uint64_t count;
  uint32_t *limbs=(uint32_t*)read_candidates(cpath,&bits,&count);
  size_t nl=bits/32;
  instance_t *inst=(instance_t*)malloc(sizeof(instance_t)*count);
  for(uint64_t i=0;i<count;i++)
    memcpy(inst[i].n._limbs, limbs+i*nl, nl*4);
  free(limbs);
  uint8_t *v=(uint8_t*)malloc(count);
  uint64_t prp=0, alarm=0;
  double t0=now_s();
  for(uint64_t i=0;i<count;i++){
    fermat2_t<params> f(cgbn_no_checks, NULL, (int32_t)i);
    typename fermat2_t<params>::bn_t n;
    cgbn_load(f._env, n, &(inst[i].n));
    v[i]=(uint8_t)f.fermat_gec(n,
        (int64_t)i==(int64_t)inject_idx ? inject_boundary : -1);
    prp+=(v[i]==V_PRP); alarm+=(v[i]==V_GEC_ALARM);
  }
  double dt=now_s()-t0;
  (void)repeat;
  write_verdicts(vpath,bits,count,v);
  fprintf(stderr,"g1_fermat[CPU/mpz]: bits=%u count=%llu | %.3fs | "
          "%.1f tests/s | prp=%llu gec_alarm=%llu\n", bits,
          (unsigned long long)count, dt, count/dt,
          (unsigned long long)prp,(unsigned long long)alarm);
  free(v); free(inst);
}
#define RUN run_cpu
#endif

/* --bins list.txt: several bins (same bits) read straight into the instance array; one allocation (v3.3) */
static int list_files(const char *listpath, char ***files) {
  FILE *lf=fopen(listpath,"r"); if(!lf){perror(listpath);exit(2);}
  char line[4096]; int n=0, cap=64; char **v=(char**)malloc(sizeof(char*)*cap);
  while(fgets(line,sizeof line,lf)){ size_t L=strlen(line); while(L&&(line[L-1]=='\n'||line[L-1]=='\r'||line[L-1]==' ')) line[--L]=0; if(!L) continue;
    if(n==cap){cap*=2; v=(char**)realloc(v,sizeof(char*)*cap);} v[n++]=strdup(line); }
  fclose(lf); *files=v; return n;
}
/* ------------------------------------------------------- early-exit mode */
#define MAGIC_S 0x31533247u   /* 'G2S1' LE */
static uint32_t *read_sizes(const char *path, uint32_t *nk) {
  FILE *f=fopen(path,"rb"); if(!f){perror(path);exit(2);}
  uint32_t mg; if(fread(&mg,4,1,f)!=1||mg!=MAGIC_S||fread(nk,4,1,f)!=1){fprintf(stderr,"bad sizes file\n");exit(2);}
  uint32_t *sz=(uint32_t*)malloc(4*(size_t)*nk);
  if(fread(sz,4,*nk,f)!=*nk){fprintf(stderr,"short sizes read\n");exit(2);}
  fclose(f); return sz;
}
/* schedule boundaries: 0, chunk, chunk+round(chunk*g), ... capped at S  (== ee_serve.schedule) */
static int schedule(int chunk, double growth, int S, int *b) {
  int n=0; b[n++]=0; double c=chunk;
  while(b[n-1]<S){ int step=(int)rint(c); /* rint = round-half-even == Python round(); (int)(c+0.5) gave 106 vs 105 at wave 5 */ if(step<1) step=1; int nx=b[n-1]+step; b[n++]=nx<S?nx:S; if(growth>1.0) c*=growth; }
  return n;
}
typedef struct { uint64_t off; uint32_t size, tested; uint8_t alive; } kstate_t;

#ifndef CPU_TEST
template<class params>
__global__ void __launch_bounds__(params::LTPB) kernel_fermat_idx(cgbn_error_report_t *report,
    typename fermat2_t<params>::instance_t *instances, const uint32_t *idx, uint32_t m, uint8_t *verd) {
  int32_t i=(blockIdx.x*blockDim.x + threadIdx.x)/params::TPI;
  if(i>=(int32_t)m) return;
  uint32_t inst=idx[i];
  fermat2_t<params> f(cgbn_report_monitor, report, inst);
  typename fermat2_t<params>::bn_t n;
  cgbn_load(f._env, n, &(instances[inst].n));
  uint32_t v=f.fermat_gec(n, -1);
  if(threadIdx.x % params::TPI == 0) verd[inst]=(uint8_t)v;
}
#endif

template<class params>
static void run_ee(const char *cpath, const char *vpath, const char *spath, int chunk, double growth, int marker, int islist, const char *lockpath) {
  typedef typename fermat2_t<params>::instance_t instance_t;
  uint32_t bits=0; uint64_t count=0; uint32_t nk;
  char **files; int nf;
  if(islist) nf=list_files(cpath,&files); else { files=(char**)malloc(sizeof(char*)); files[0]=strdup(cpath); nf=1; }
  /* pre-scan headers: bits + total count, then one allocation */
  for(int i=0;i<nf;i++){ FILE *f=fopen(files[i],"rb"); if(!f){perror(files[i]);exit(2);} file_hdr_t h;
    if(fread(&h,sizeof h,1,f)!=1||h.magic!=MAGIC_C){fprintf(stderr,"bad candidate file %s\n",files[i]);exit(2);}
    if(bits==0) bits=h.bits; else if(h.bits!=bits){fprintf(stderr,"mixed bits in list\n");exit(2);} count+=h.count; fclose(f); }
  if(bits!=params::BITS){fprintf(stderr,"size-class mismatch\n");exit(2);}
  uint32_t *sizes=read_sizes(spath,&nk);
  uint64_t sum=0; uint32_t S=0; for(uint32_t k=0;k<nk;k++){ sum+=sizes[k]; if(sizes[k]>S) S=sizes[k]; }
  if(sum!=count){fprintf(stderr,"sizes sum %llu != count %llu\n",(unsigned long long)sum,(unsigned long long)count);exit(2);}
  size_t nbytes=bits/8;
  instance_t *inst=(instance_t*)malloc(sizeof(instance_t)*count);
  { uint64_t i=0; uint8_t *buf=(uint8_t*)malloc(nbytes*4096);
    for(int fi=0;fi<nf;fi++){ FILE *f=fopen(files[fi],"rb"); file_hdr_t h; if(fread(&h,sizeof h,1,f)!=1){exit(2);}
      uint64_t left=h.count;
      while(left){ size_t take=left<4096?left:4096; if(fread(buf,nbytes,take,f)!=take){fprintf(stderr,"short read %s\n",files[fi]);exit(2);}
        for(size_t j=0;j<take;j++){ memcpy(inst[i].n._limbs, buf+j*nbytes, nbytes); inst[i].verdict=0xFF; i++; } left-=take; }
      fclose(f); }
    free(buf); for(int fi=0;fi<nf;fi++) free(files[fi]); free(files); }
  kstate_t *ks=(kstate_t*)malloc(sizeof(kstate_t)*nk);
  { uint64_t off=0; for(uint32_t k=0;k<nk;k++){ ks[k].off=off; ks[k].size=sizes[k]; ks[k].tested=0; ks[k].alive=1; off+=sizes[k]; } }
  uint8_t *v=(uint8_t*)malloc(count); memset(v,(uint8_t)marker,count);
  int bnd[512]; int nb=schedule(chunk,growth,(int)S,bnd);
  uint32_t *idx=(uint32_t*)malloc(4*count);
  int lockfd=-1; double tl0=now_s();
  if(lockpath){ lockfd=open(lockpath,O_RDWR|O_CREAT,0666); if(lockfd<0||flock(lockfd,LOCK_EX)){perror("lock");exit(2);} }
  double t_lockwait=now_s()-tl0;
  double t0=now_s(); uint64_t tested=0; int launches=0;
#ifndef CPU_TEST
  instance_t *g_inst; uint8_t *g_v; uint32_t *g_idx; cgbn_error_report_t *report;
  CUDA_CHECK(cudaMalloc((void**)&g_inst, sizeof(instance_t)*count));
  CUDA_CHECK(cudaMemcpy(g_inst, inst, sizeof(instance_t)*count, cudaMemcpyHostToDevice));
  CUDA_CHECK(cudaMalloc((void**)&g_v, count)); CUDA_CHECK(cudaMemset(g_v, 0xFF, count));
  CUDA_CHECK(cudaMalloc((void**)&g_idx, 4*count));
  CUDA_CHECK(cgbn_error_report_alloc(&report));
  int32_t TPB=params::LTPB, IPB=TPB/params::TPI;
  uint8_t *wv=(uint8_t*)malloc(count);
#endif
  for(int w=1; w<nb; w++){
    uint32_t m=0;
    for(uint32_t k=0;k<nk;k++){ if(!ks[k].alive) continue; uint32_t lo=ks[k].tested, hi=ks[k].size<(uint32_t)bnd[w]?ks[k].size:(uint32_t)bnd[w];
      for(uint32_t p=lo;p<hi;p++) idx[m++]=(uint32_t)(ks[k].off+p); }
    if(!m) break;
#ifndef CPU_TEST
    CUDA_CHECK(cudaMemcpy(g_idx, idx, 4*(size_t)m, cudaMemcpyHostToDevice));
    kernel_fermat_idx<params><<<(m+IPB-1)/IPB, TPB>>>(report, g_inst, g_idx, m, g_v);
    CUDA_CHECK(cudaGetLastError()); CUDA_CHECK(cudaDeviceSynchronize()); CGBN_CHECK(report);
    CUDA_CHECK(cudaMemcpy(wv, g_v, count, cudaMemcpyDeviceToHost));
    for(uint32_t i=0;i<m;i++){ if(wv[idx[i]]==0xFF){fprintf(stderr,"g1_fermat[EE]: FATAL -- untouched instance %u\n",idx[i]);exit(3);} v[idx[i]]=wv[idx[i]]; }
#else
    for(uint32_t i=0;i<m;i++){ fermat2_t<params> f(cgbn_no_checks, NULL, (int32_t)idx[i]); typename fermat2_t<params>::bn_t n;
      cgbn_load(f._env, n, &(inst[idx[i]].n)); v[idx[i]]=(uint8_t)f.fermat_gec(n,-1); }
#endif
    launches++; tested+=m;
    for(uint32_t k=0;k<nk;k++){ if(!ks[k].alive) continue; uint32_t lo=ks[k].tested, hi=ks[k].size<(uint32_t)bnd[w]?ks[k].size:(uint32_t)bnd[w];
      int hit=0; for(uint32_t p=lo;p<hi;p++){ uint8_t x=v[ks[k].off+p]; if(x==V_PRP||x==V_GEC_ALARM) hit=1; }
      ks[k].tested=hi; if(hit||hi>=ks[k].size) ks[k].alive=0; }
  }
  double dt=now_s()-t0;
#ifndef CPU_TEST
  CUDA_CHECK(cudaFree(g_inst)); CUDA_CHECK(cudaFree(g_v)); CUDA_CHECK(cudaFree(g_idx)); CUDA_CHECK(cgbn_error_report_free(report)); free(wv);
#endif
  if(lockfd>=0){ flock(lockfd,LOCK_UN); close(lockfd); }       /* GPU phase over: next process may start its waves */
  uint64_t prp=0, alarm=0; for(uint64_t i=0;i<count;i++){ prp+=(v[i]==V_PRP); alarm+=(v[i]==V_GEC_ALARM); }
  write_verdicts(vpath,bits,count,v);
  fprintf(stderr,"g1_fermat[EE]: bits=%u count=%llu ks=%u tested=%llu (%.3f) waves=%d | %.3fs gpu-phase (lock wait %.2fs) | %.1f tests/s | prp=%llu gec_alarm=%llu\n",
          bits,(unsigned long long)count,nk,(unsigned long long)tested,(double)tested/(double)count,launches,dt,t_lockwait,tested/dt,
          (unsigned long long)prp,(unsigned long long)alarm);
  free(v); free(inst); free(ks); free(idx); free(sizes);
}

int main(int argc, char **argv) {
  if(argc<3){
    fprintf(stderr,"usage: g1_fermat cand.bin verdict.bin [--repeat N] "
                   "[--inject IDX BDRY] [--device D]\n");
    return 2;
  }
  int repeat=1, inject_idx=-1, inject_boundary=-1, device=0;
  const char *spath=NULL, *lockpath=NULL; int chunk=6, marker=3, islist=0; double growth=1.15;   /* v3.4: O4-prime 10-wave DP optimum */
  for(int i=3;i<argc;i++){
    if(!strcmp(argv[i],"--repeat")&&i+1<argc)      repeat=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--ee")&&i+1<argc)     spath=argv[++i];
    else if(!strcmp(argv[i],"--bins"))             islist=1;
    else if(!strcmp(argv[i],"--lock")&&i+1<argc)   lockpath=argv[++i];
    else if(!strcmp(argv[i],"--chunk")&&i+1<argc)  chunk=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--growth")&&i+1<argc) growth=atof(argv[++i]);
    else if(!strcmp(argv[i],"--marker")&&i+1<argc) marker=atoi(argv[++i]);
    else if(!strcmp(argv[i],"--inject")&&i+2<argc){
      inject_idx=atoi(argv[++i]); inject_boundary=atoi(argv[++i]); }
    else if(!strcmp(argv[i],"--device")&&i+1<argc) device=atoi(argv[++i]);
  }
#ifndef CPU_TEST
  cudaSetDevice(device);
#else
  (void)device;
#endif
  /* peek bits to dispatch the size class */
  file_hdr_t h;
  if(!islist){
    FILE *f=fopen(argv[1],"rb");
    if(!f){perror(argv[1]);return 2;}
    if(fread(&h,sizeof h,1,f)!=1||h.magic!=MAGIC_C){
      fprintf(stderr,"bad candidate file\n");return 2;}
    fclose(f);
  }
  if(islist){ FILE *lf=fopen(argv[1],"r"); char first[4096]={0}; if(lf){ if(fgets(first,sizeof first,lf)){ size_t L=strlen(first); while(L&&(first[L-1]=='\n'||first[L-1]=='\r')) first[--L]=0; } fclose(lf);} 
    FILE *f1=fopen(first,"rb"); if(!f1||fread(&h,sizeof h,1,f1)!=1||h.magic!=MAGIC_C){fprintf(stderr,"--bins: cannot read first bin '%s'\n",first);return 2;} fclose(f1);
    if(!spath){fprintf(stderr,"--bins requires --ee sizes.bin\n");return 2;} }
  if(spath){
    if(marker==0||marker==1||marker==2||marker>255){fprintf(stderr,"marker must be 3..255\n");return 2;}
    switch(h.bits){
      case  1024: run_ee<f2_params_t< 8, 1024> >(argv[1],argv[2],spath,chunk,growth,marker,islist,lockpath); break;
      case  2048: run_ee<f2_params_t< 8, 2048> >(argv[1],argv[2],spath,chunk,growth,marker,islist,lockpath); break;
      case  4096: run_ee<f2_params_t<16, 4096> >(argv[1],argv[2],spath,chunk,growth,marker,islist,lockpath); break;
      case  8192: run_ee<f2_params_t<32, 8192> >(argv[1],argv[2],spath,chunk,growth,marker,islist,lockpath); break;
      case 16384: run_ee<f2_params_t<32,16384> >(argv[1],argv[2],spath,chunk,growth,marker,islist,lockpath); break;
      case 24576: run_ee<f2_params_t<32,24576> >(argv[1],argv[2],spath,chunk,growth,marker,islist,lockpath); break;
      case 32768: run_ee<f2_params_t<32,32768> >(argv[1],argv[2],spath,chunk,growth,marker,islist,lockpath); break;
      default: fprintf(stderr,"unsupported bits=%u\n",h.bits); return 2;
    }
    return 0;
  }
  switch(h.bits){
    case  1024: RUN<f2_params_t< 8, 1024> >(argv[1],argv[2],repeat,inject_idx,inject_boundary); break;
    case  2048: RUN<f2_params_t< 8, 2048> >(argv[1],argv[2],repeat,inject_idx,inject_boundary); break;
    case  4096: RUN<f2_params_t<16, 4096> >(argv[1],argv[2],repeat,inject_idx,inject_boundary); break;
    case  8192: RUN<f2_params_t<32, 8192> >(argv[1],argv[2],repeat,inject_idx,inject_boundary); break;
    case 16384: RUN<f2_params_t<32,16384> >(argv[1],argv[2],repeat,inject_idx,inject_boundary); break;
    case 24576: RUN<f2_params_t<32,24576> >(argv[1],argv[2],repeat,inject_idx,inject_boundary); break;
    case 32768: RUN<f2_params_t<32,32768> >(argv[1],argv[2],repeat,inject_idx,inject_boundary); break;
    default: fprintf(stderr,"unsupported bits=%u (classes: 1024,2048,4096,8192,"
                     "16384,24576,32768)\n",h.bits); return 2;
  }
  return 0;
}
