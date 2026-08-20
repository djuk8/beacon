# 6. Hygiene: a decade of measurable design loss

## 6.1 The census
Parsing the full public list (121,457 rows; 118,718 primorial
expressions, 100.0% of non-literal non-power rows; 2,702 literals;
37 power forms) and evaluating the structural-k inflation of 2.6
on each artifact yields 3,263 records with inflation >= 1.15:

    A.Renyer  1,998   all with 715 = 5*11*13 | k   x1.32-1.42
    Jacobsen    876   15 = 3*5 | k (2015-16)       x2.2-2.42
    M.Jansen    232                                 mixed
    RobSmith    112;  Rosnthal 42;  PierCami 3.

The Renyer signature covers roughly a fifth of his 10,119 rows
landed in 2026 alone. Cost translation: survivor inflation r
multiplies the luck exponent, so the window bill multiplies by
e^((r-1)E) -- typically x2-5 at the affected configurations.

## 6.2 Folklore, lost and found
The 107,102-row historical first-occurrence family (M.Jansen-era,
small divisors like d = 30) is almost entirely CLEAN: with random
k nearly half would be flagged, so the classical community
evidently enforced gcd(k, d) = 1 as folklore. The modern big-d
campaigns dropped the habit and paid for a decade. The fix is one
line in any k generator: reject k unless gcd(k, d) = 1.

## 6.3 Framing and conduct
The factorizations above are public data; the interpretation is
new. We report the phenomenon in aggregate, treat every named
row as historical record rather than critique, and are sending
private notes to the affected active discoverers at publication
(drafts filed; see repository policy). We also suggest, with
respect, that the list-project tooling could adopt the one-line
lint -- it would have saved the field several GPU-years.
