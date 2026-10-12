"""Small explicit registry. Never substitute a different map's profile."""

import json
from functools import lru_cache
from pathlib import Path

from src.models.spatial import MapProfile

PROFILE_DIR = Path(__file__).with_name("profiles")
WORKSPACE = Path(__file__).resolve().parents[2]
_REGISTERED = {
    "de_mirage": PROFILE_DIR / "de_mirage.json",
    "de_inferno": PROFILE_DIR / "de_inferno.json",
}


def validate_assets(profile: MapProfile, root: Path = WORKSPACE) -> None:
    for level in profile.radar_levels:
        path = (root / level.image).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f"Missing or invalid radar asset: {level.image}")


@lru_cache(maxsize=16)
def _load(path: str, modified_ns: int) -> MapProfile:
    profile = MapProfile.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
    validate_assets(profile)
    return profile


def get_profile(map_name: str) -> MapProfile | None:
    path = _REGISTERED.get(map_name)
    if path is None:
        return None
    return _load(str(path), path.stat().st_mtime_ns)


def profile_compatibility(profile: MapProfile, patch_version=None) -> str:
    """Availability and verified compatibility are independent properties."""
    verified = profile.compatibility.get("verified_patch_versions", [])
    return "verified" if str(patch_version) in map(str, verified) else "unverified"
