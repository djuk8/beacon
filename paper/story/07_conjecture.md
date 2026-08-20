# 7. The e^gamma conjecture (Theorem 1, stated)

## 7.1 The object
For lam -> infinity take zd = lam, d fixed even squarefree, Q with
ln Q / ln zd fixed, and the certified sum of 2.4. Define

  sigma_d(m, lam) = (e^gamma ln Q / (m lam)) * Theta(zd, Q) *
      2 * SUM_{s even d-smooth} c_d(s) [ (pi(J/s) - pi(zd))_+ + 1_{s<=J} ],
  J = (m/2) lam,   u = 1 + ln(m/2)/ln lam.

SHELF LIMIT: lam -> infinity with sigma held on the record locus
(m and u locked through L = ln lam as in 3.4).

CONJECTURE T1. On the shelf, d sigma / du -> e^gamma at u -> 1+,
uniformly in the admissible d; equivalently the empirical shelf
coefficient a equals e^gamma exactly, with corrections O(1/L).

## 7.2 What is already exact
(i) Q-invariance: the ln Q cancellation of 2.5(i).
(ii) Channel-mass identity: SUM_s c_d(s)/s = 1 (3.2) -- the
d-neutrality of the untruncated limit.
(iii) Fixed-u limit: with all channels open the marginal rate is
e^gamma * omega(u), omega the Buchstab function -- the measured
fence law, including its cusp at u = 2.
(iv) The one-line lip cancellation: beta * rho * lam with
rho(zd+) = 1/ln Q gives e^gamma with every Q and height
cancelling. It is NOT a proof of T1: parity and q > zd forbid
prime survivors at the lip, the true lip is the channel staircase
of 3.2 (first jump w_d(2), e.g. 0.1289 at d = 30030), and the
constant is EMERGENT along the shelf rather than local. The
preregistered naive version of this argument was refuted
(Appendix A, H6); its corpse marks where the theorem lives.

## 7.3 Invitation
The sum interpolates Buchstab (prime side) and Dickman (smooth
side) with elementary weights; no unproved hypothesis appears
anywhere in its definition, and machine certification pins its
value across 87 <= D <= 385,713 to 1-4%. We believe the shelf
asymptotics are within reach of classical methods (Mertens, PNT,
smooth-number counts), and we would regard a proof by others as
the best possible outcome of publishing this paper. All
certified numerics, gates, and the exact evaluator ship in the
repository.
