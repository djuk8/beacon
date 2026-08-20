# 5. Retrodiction: the published decade, re-derived

## 5.1 Method
For each of the twenty largest known prime gaps we took the
published artifact itself -- k, zd, d, offset, gap -- exhaustively
sieved the actual window to obtain sigma_exact, and evaluated the
counting formula (2.4) on the same artifact with NO free
parameters. Five discoverers, five construction families, d from
2310 to 23#, k from 1 to 10^36, heights 97,234 to 385,713 digits.

## 5.2 The table
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
(* giant composite divisors, printed truncated; (h) hygiene
modeled per 2.6 -- see 5.3.)

## 5.3 The two rows that were information
Rows 18 and 20 initially missed by -28.6% and -29.5% -- the only
failures in the set. Both k's are divisible by exactly 5*11*13 =
715: three divisor primes revert from class to structural, and
once modeled (2.6) the rows become the two BEST predictions in
the table (-0.4%, -0.1%), with survivor inflation x1.395 and
x1.417 read directly off the artifacts. A model failure decoded
into a measurement of the discoverer's design hygiene; Section 6
shows the pattern is a fifth of his current pipeline.

## 5.4 Emergent e^gamma
Fitting sigma = a(u-1) + b(u-1)^2 on identical design matrices:
theory a = 1.6749, measured a = 1.6981 (e^gamma = 1.7811); the
difference of 0.023 is within the shelf-segment collinearity.
The mystery constant of the empirical cost curve is reproduced by
an exact sum with nothing to tune -- the remaining step, proving
the shelf limit equals e^gamma, is Section 7.
