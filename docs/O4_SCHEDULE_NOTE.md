# O4' early-exit schedule fit (2026-08-24) -- from 56e9 crown tests, beta_eff = 0.01488
Sequential floor 55.6 tests/k. Current [chunk 8, growth 1.5] = 64.8. Optimal 6-wave = 63.1 (current is
within 2.6% of its wave-count optimum). Gains need MORE waves: 10-wave optimum 59.9 (-7.5%); parameter pair
chunk=6 growth=1.15 matches it to 0.2%. BUT: v3 holds the GPU lock across inter-wave host work (~0.8 s/wave),
so +4 waves ~ +3.2 s host vs -3.2 s GPU: NET ZERO as parameters alone. Realizing -7.5% requires async
index build (wave w+1 prepared during wave w) -- a small v3.4 change, gated by the existing R-ladder.
VERDICT: bundle into the O3/v4 build; do not ship as a knob. -C
