"""Day and night: a star never gets a night side, Earth keeps its night.

Frames are drawn at a fixed moment, so the check does not depend on the clock.
Run: make test
"""
import datetime
import os
import sys
import types
from argparse import Namespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ascii_earth import globe as g  # noqa: E402

when = datetime.datetime(2026, 11, 1, 16, 0, tzinfo=datetime.timezone.utc)


class Fixed(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return when


g.datetime = types.SimpleNamespace(datetime=Fixed, timezone=datetime.timezone)
os.environ["COLUMNS"], os.environ["LINES"] = "80", "30"


def frame(body, **kw):
    args = Namespace(body=body, lon=28.0, lat=10.0, follow=False, sun=False, no_rings=False,
                     top="", bottom="", no_labels=True, size=50, aspect=2.0, no_stars=True,
                     stars=0.03, glyphs="braille", color="truecolor", no_ring=False,
                     palette="natural", ramp="")
    vars(args).update(kw)
    g.set_color(2.1, 0.55)
    return g.build_frame(g.body_texture(body), args)


bad = 0
for body in ("sun", "earth"):
    same = frame(body) == frame(body, sun=True)
    want = body == "sun"
    ok = same == want
    bad += not ok
    print(f"{'ok  ' if ok else 'FAIL'} {body}: with --sun the frame is {'the same' if same else 'different'}")
# Follow: the Sun turns under the view but has no night; compare with plain view at the same point.
decl, sunlon = g.subsolar(when)
import math  # noqa: E402
lat, lon = math.degrees(decl), math.degrees(sunlon)
same = frame("sun", follow=True) == frame("sun", lat=lat, lon=lon)
bad += not same
print(f"{'ok  ' if same else 'FAIL'} sun --follow: {'no night side' if same else 'a night side'}")
sys.exit(1 if bad else 0)
