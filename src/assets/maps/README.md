# Mirage radar

`de_mirage.png` and the overview transform in `de_mirage.json` were retrieved
from the pinned [Awpy data release 2000927](https://github.com/pnxenopoulos/awpy-data/releases/tag/2000927).
Radar imagery originates from Counter-Strike 2 / Valve; no ownership or new license
over game assets is claimed. Awpy extraction project: https://github.com/pnxenopoulos/awpy-data.

The PNG is 1024 × 1024. World-to-pixel transform:
`px=(X-pos_x)/scale`, `py=(pos_y-Y)/scale`. Rotation is zero for this asset.
The plot instead anchors the image in world coordinates with extent 1024*scale.
The radar is a presentation aid, not collision geometry or a visibility model.
The supplied demo reports patch 14189; exact geometric equivalence to this asset
release is not asserted. Zone labels currently come from the demo itself.

`de_inferno.png` and `de_inferno.json` come from the same pinned Awpy release.
Its transform is `pos_x=-2087`, `pos_y=3870`, `scale=4.9`. The Inferno demo
reports patch 14186; its nav labels are the source of the region profile.
