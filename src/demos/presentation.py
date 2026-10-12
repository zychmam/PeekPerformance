"""Player-facing names for demo tables; SteamIDs stay internal."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable

import pandas as pd

_ROLE_NAMES = {
    "attacker": "Atakujący",
    "user": "Trafiony gracz",
    "victim": "Ofiara",
    "assister": "Asystujący",
    "thrower": "Rzucający",
    "player": "Gracz",
    "owner": "Właściciel",
}


def is_steam_id_column(column: object) -> bool:
    return str(column).lower().replace("_", "").endswith("steamid")


def _steamid(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    result = str(value)
    return "" if result in {"", "0", "nan", "None", "<NA>"} else result


def disambiguate_names(players: Iterable[tuple[str, str]]) -> dict[str, str]:
    """Use stable ordinal suffixes when nicknames collide, never visible IDs."""
    normalized = {
        str(steamid): str(name).strip() if name is not None and not pd.isna(name) else ""
        for steamid, name in players
        if _steamid(steamid)
    }
    bases = {steamid: name or "Nieznany gracz" for steamid, name in normalized.items()}
    counts = Counter(name.casefold() for name in bases.values())
    seen: defaultdict[str, int] = defaultdict(int)
    labels: dict[str, str] = {}
    used: set[str] = set()
    for steamid in sorted(bases):
        base = bases[steamid]
        key = base.casefold()
        seen[key] += 1
        label = f"{base} ({seen[key]})" if counts[key] > 1 else base
        while label in used:
            seen[key] += 1
            label = f"{base} ({seen[key]})"
        labels[steamid] = label
        used.add(label)
    return labels


def player_labels(player_info: pd.DataFrame) -> dict[str, str]:
    if player_info.empty or "steamid" not in player_info:
        return {}
    pairs = (
        (_steamid(row.get("steamid")), row.get("name"))
        for row in player_info.to_dict("records")
    )
    return disambiguate_names(pairs)


def _column_role(column: str) -> tuple[str, str]:
    normalized = column.lower()
    if normalized in {"steamid", "steam_id"}:
        return "name", "Gracz"
    stem = normalized.removesuffix("steamid").removesuffix("steam_id").rstrip("_")
    return f"{stem}_name", _ROLE_NAMES.get(stem, f"{stem.title()} — gracz")


def presentation_frame(frame: pd.DataFrame, player_info: pd.DataFrame) -> pd.DataFrame:
    """Replace every SteamID column with a nickname column in a display copy."""
    result = frame.copy(deep=False)
    labels = player_labels(player_info)
    id_columns = [column for column in frame.columns if is_steam_id_column(column)]
    if not id_columns:
        return result
    unknown = sorted({
        _steamid(value)
        for column in id_columns
        for value in frame[column].dropna().unique()
        if _steamid(value) and _steamid(value) not in labels
    })
    if unknown:
        labels = disambiguate_names([
            *labels.items(),
            *((steamid, "Nieznany gracz") for steamid in unknown),
        ])
    name_columns: list[str] = []
    for column in id_columns:
        paired, display_name = _column_role(str(column))
        if display_name == "Gracz" and paired not in result and "Gracz" in result:
            paired = "Gracz"
        values = frame[column].astype("string").map(labels).fillna("—")
        if paired in result.columns:
            values = values.where(values.ne("—"), result[paired])
            result[paired] = values
            if display_name not in result.columns or paired == display_name:
                result = result.rename(columns={paired: display_name})
                name_columns.append(display_name)
            else:
                name_columns.append(paired)
        else:
            column_name = display_name
            if column_name in result.columns:
                column_name = f"{display_name} — nick"
            result[column_name] = values
            name_columns.append(column_name)
    result = result.drop(columns=id_columns)
    priority = list(dict.fromkeys(column for column in name_columns if column in result.columns))
    return result[priority + [column for column in result.columns if column not in priority]]
