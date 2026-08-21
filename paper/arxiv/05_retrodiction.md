# 5. Retrodiction of the published record set

## 5.1 Protocol
For each of the twenty largest known prime gaps we took the
published artifact -- $k, z, d$, offset, gap -- exhaustively
sieved the actual window to obtain $\sigma_{\mathrm{ex}}$, and
evaluated $T_d$ on the same artifact with no adjustable
quantity. The set spans five discoverers, five construction
families, $d$ from $2310$ to $23\#$, $k$ from $1$ to $10^{36}$,
and heights $97{,}234$ to $385{,}713$ digits.

## 5.2 Results
    rk   digits        d        u   sig_ex  sig_th   dev%
     1  385,713      23#    1.161   0.274   0.270   -1.5
     2  289,083      17#    1.136   0.255   0.252   -1.1
     3  289,082      23#    1.132   0.230   0.225   -2.1
     4  208,095  9699690    1.154   0.251   0.247   -1.6
     5  208,096    30030    1.152   0.254   0.251   -1.0
     6  337,314      23#    1.107   0.168   0.163   -3.1
     7  216,841    30030    1.144   0.254   0.251   -1.0
     8  208,093  9699690    1.146   0.240   0.235   -2.0
     9  208,094   510510    1.143   0.232   0.228   -1.7
    10  173,457    46410    1.148   0.246   0.243   -1.2
    11  157,490   510510    1.154   0.251   0.246   -1.8
    12  216,849    46410    1.124   0.188   0.186   -1.3
    13  208,102     2310    1.124   0.189   0.186   -1.3
    14   99,750  2.2e12*    1.188   0.338   0.332   -1.7
    15  303,518      23#    1.089   0.139   0.134   -4.0
    16   97,234  1.1e11*    1.185   0.323   0.318   -1.5
    17  151,940     2310    1.143   0.251   0.249   -0.9
    18  179,864    30030    1.120   0.239   0.238   -0.4 (h)
    19  135,376    46410    1.144   0.259   0.257   -0.8
    20  151,952    30030    1.125   0.286   0.286   -0.1 (h)
(*) giant composite divisors, truncated in print. (h) hygiene
correction of 5.3 applied.

Sample mean deviation $-1.5\%$; every deviation is negative,
consistent with the $O(1/\ln z)$ corrections omitted from $T_d$
and with evaluation at a single class realization rather than
the class-torus average of Theorem 3.2.

## 5.3 The two informative failures
Rows 18 and 20 initially deviated by $-28.6\%$ and $-29.5\%$ --
the only failures. Both cofactors are divisible by exactly
$5\cdot 11\cdot 13 = 715$; Corollary 3.7(b) applies, the
inflation factors $1.395$ and $1.417$ are read off the
artifacts, and the corrected rows become the two most accurate
in the table ($-0.4\%$, $-0.1\%$). A model failure decoded into
a measurement of the discoverer's design hygiene; Section 6.4
shows the pattern extends across a fifth of that discoverer's
current output.

## 5.4 Emergent shelf slope
Fitting $\sigma = a(u-1) + b(u-1)^2$ on identical design
matrices over the record set yields $a = 1.6749$ (theory)
against $a = 1.6981$ (measured), with $e^{\gamma} = 1.7811$; the
gap of $0.023$ is within the collinearity of the narrow shelf
segment. The constant of the practitioners' curve is reproduced
by an exact sum with nothing to tune; the identity itself is
Conjecture 3.9.

## 5.5 Independent confirmation of the deep limit
The fence-rate law of Corollary 3.4 was measured in an earlier
phase of this program, independently of the counting expression
and before it existed: a preregistered forward prediction of the
rate confirmed at $6$--$7\sigma$ in both directions; the
Buchstab cusp at $u = 2$ detected at $8.45\sigma$; a
$94{,}885$-fence out-of-sample test with zero fitted parameters
($\chi^2$ $p = 0.19$); and the constant Mertens-style rate
rejected at more than $8\sigma$. Within the present framework
these measurements are confirmations of the deep limit of
Theorem 3.3, and the cusp is the opening of the two-prime
channels at the boundary of Proposition 3.1.
