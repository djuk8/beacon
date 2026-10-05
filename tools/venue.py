"""venue.py -- the one place a venue is defined. Reads ~/beacon/raid610/VENUE.json; absent = the crown (1439#/2310, 611 digits, 2048-bit class).
A venue is: zd (wheel bound), d (the swap primes' product), swap, kdig (digits of k), bits (driver class), merit (window edge), rings (ladder edges), ladder (design file)."""
import json, os
DEFAULT = dict(name="crown", zd=1439, d=2310, swap=[2, 3, 5, 7, 11], kdig=13, bits=2048, merit=45.0,
               rings="1568,4374,7244,10198,13500,17734,22818,31576", ladder="ladder_crown.json")
def load(theater=os.path.expanduser("~/beacon/raid610")):
    v = dict(DEFAULT); p = os.path.join(theater, "VENUE.json")
    if os.path.exists(p): v.update(json.load(open(p)))
    lp = os.path.join(theater, v["ladder"])
    if os.path.exists(lp):
        try: v["rings"] = ",".join(str(int(e)) for e in json.load(open(lp))["edges"])
        except Exception: pass
    return v
if __name__ == "__main__":
    import sys; v = load(); print(" ".join(str(v[k]) for k in sys.argv[1:]) if len(sys.argv) > 1 else json.dumps(v))
