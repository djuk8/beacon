# PRIVATE NOTE DRAFTS -- DO NOT SEND BEFORE PARADE DAY
# NOT FOR EXPORT. Excluded from public snapshot by include-list.

## To A. Renyer (draft)
Subject: something useful we found in your 2026 entries
Hi -- before our paper goes public I wanted you to hear this from
me directly, because it is worth real compute to you. Your record
pipeline's k values are divisible by 715 = 5*11*13. Under the
k*zd#/d construction those primes then kill j = 0 mod p instead
of a movable class, which inflates the survivor count of every
window by a measurable x1.32-1.42 -- about e^((r-1)E) = 2-5x more
windows per record at your configurations. The fix is one line:
require gcd(k, d) = 1 in your k generator. For what it's worth,
our cost model rates your PLACEMENTS as close to optimal -- this
is the one leak, and it's free to close. Details and the exact
per-row numbers are in the paper (Section 6) and reproducible
from the public repo. Congratulations on an extraordinary year of
entries. -- M. Vojvoda (Djuk8)

## To D. Jacobsen (draft)
Subject: a historical pattern in 2015-16 entries + a lint idea
Hi -- with thanks for your long stewardship of the gap list.
While validating a counting law against the full list we noticed
your 2015-16 campaign rows (11-12.5k digits) carry k divisible by
15, which under k*zd#/d inflates window survivor counts x2.2-2.4
(mechanism and census in Section 6 of the attached). Entirely
historical -- but the same scan suggests a cheap community win:
a one-line gcd(k, d) = 1 lint in the list tooling would flag the
pattern at submission time. Happy to contribute the check. The
paper re-derives all twenty top records, several of them yours,
from first principles -- we hope it reads as the tribute it is.
-- M. Vojvoda (Djuk8)
