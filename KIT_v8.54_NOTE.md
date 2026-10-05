# Kit v8.54 - any number of cards (2026-10-05)

onstart: NCARDS (default: the GPU count), ALLCARDS, SIEVECARD (3 on boxes with more than 4 cards, the last card otherwise), SIEVECARD2 (7 on 8-card boxes)
with its own seed SIEVESEED2.txt (default SIEVESEED+250, i.e. a k-range 2e12 away - about 3 months of walking apart); the first sieve card serves cards 0-3,
the second cards 4-7; ready queues, feeders and ladder managers for every card; ladder seeds unique for any card count; GPUCORES/HERDCORES default to
8 threads per card for the feeders and the rest for the herd (set them per NUMA node on two-socket boxes: `nvidia-smi topo -m`). go_crown loops over
the GPU count; daily.sh lists the queue dirs it finds. Four-card boxes behave exactly as before.

8x RTX 5090 box, new range:   git clone <repo> ~/lab/beacon && cd ~/lab/beacon && bash deploy/fresh_box.sh --seed 3500
(seed2 defaults to 3750; both ranges are new ground: box1 walked seed 2004 to ~2079-equivalent, the rental box seed 3000 to ~3020-equivalent)
Pre-flight first: nvidia-smi --query-gpu=power.limit,clocks.max.sm,pcie.link.gen.current --format=csv ; nvidia-smi topo -m
Expected read after an hour: ~85-90k windows/s for 8 cards at 575 W (two box1s), two "SIEVE CARD" lines in onstart's output, 48 feeders, 8 ladder managers.
Untested until the first 8-card box: the second daemon's tmpfs share (two 1e10 states; BSD auto-size allows it on 483 GB), load on 128 threads (expect ~90).
