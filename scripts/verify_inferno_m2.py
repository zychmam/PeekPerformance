"""Run the M2 Inferno demo through the shared pipeline in an isolated database."""

import argparse
import json
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import zstandard
from demoparser2 import DemoParser

from src.demos.demo_analyzer import DemoAnalyzer
from src.demos.demo_manager import DemoManager
from src.demos.spatial_service import get_spatial_context
from src.demos.tactical_rounds import load_tactical_match
from src.gui.radar_player import playback_data, playback_html
from src.maps.registry import get_profile, profile_compatibility
from src.storage.database import Database


def verify(demo: Path) -> dict:
    started = time.perf_counter()
    analysis = DemoAnalyzer(demo).get_full_analysis()
    analysis.content_hash = DemoManager.content_hash(demo)
    analysis.stored_file_name = demo.name
    profile = get_profile(analysis.map_name)
    assert profile is not None
    assert profile_compatibility(profile, analysis.header.get('patch_version')) == 'verified'
    assert len(analysis.rounds_df) == 20
    assert len(analysis.player_info) == 10
    plants = DemoParser(str(demo)).parse_event(
        'bomb_planted', player=['X', 'Y', 'last_place_name']
    )
    independent_plants = {
        (int(row.tick), int(row.site), row.user_last_place_name)
        for row in plants.itertuples()
    }
    assert {
        (24989, 296, 'BombsiteA'),
        (51159, 1023, 'BombsiteB'),
        (68896, 1023, 'BombsiteB'),
    }.issubset(independent_plants)
    workspace = Path(__file__).resolve().parents[1]
    temporary = tempfile.TemporaryDirectory(dir=workspace)
    if not Path(temporary.name).resolve().is_relative_to(workspace.resolve()):
        raise ValueError('Temporary database escaped the workspace')
    with temporary as temp:
        db = Database(str(Path(temp) / 'm2.db'))
        manager = DemoManager(str(demo.parent))
        db.upsert_demo_analysis(analysis)
        context = get_spatial_context(db, manager, analysis, 1)
        result = load_tactical_match(db, analysis.content_hash, 1)
        assert result is not None and result.rounds
        initial_calls = time.perf_counter() - started
        with (
            patch(
                'src.demos.observations.DemoAnalyzer',
                side_effect=AssertionError('parser opened'),
            ),
            patch.object(manager, 'analysis_path', side_effect=AssertionError('demo reopened')),
        ):
            warm = get_spatial_context(db, manager, analysis, 2)
            alternate = get_spatial_context(db, manager, analysis, 1)
            assert len(warm.states) > 0 and len(alternate.states) > 0
            assert context.observations.states.event_id.tolist() == (
                alternate.observations.states.event_id.tolist()
            )
        labels = dict(zip(
            analysis.player_info.steamid.astype(str),
            analysis.player_info.name.astype(str),
            strict=True,
        ))
        radar = playback_data(context, analysis, 1, labels, next(iter(labels)))
        assert radar['radar_image'] and len(radar['players']) >= 2
        assert sum(p['selected'] for p in radar['players']) == 1
        assert 'data:image/png;base64' in playback_html(radar)
        locations = Counter(context.states.location_status)
        sites = Counter(context.states.region_id.dropna())
        entries = [
            {'round': e['round'], 'site': e['site'], 'tick': e['tick'],
             'routes': e['routes'], 'participants': len(e['participants'])}
            for e in context.entries
        ]
        all_entries = []
        location_counts = Counter()
        for round_number in range(1, len(analysis.rounds_df) + 1):
            round_context = get_spatial_context(db, manager, analysis, round_number)
            location_counts.update(round_context.states.location_status)
            all_entries.extend(
                {'round': e['round'], 'site': e['site'], 'tick': e['tick'],
                 'routes': e['routes'], 'participants': len(e['participants'])}
                for e in round_context.entries
            )
        assert {
            (3, 'A', 24551),
            (7, 'B', 47766),
            (10, 'B', 67298),
            (13, 'A', 86410),
        }.issubset({(e['round'], e['site'], e['tick']) for e in all_entries})
        return {
            'demo': demo.name, 'map': analysis.map_name,
            'patch': analysis.header.get('patch_version'),
            'rounds': len(analysis.rounds_df), 'players': len(analysis.player_info),
            'kills': len(analysis.kills_df), 'bomb_events': len(analysis.bomb_events_df),
            'states_round_1': len(context.states), 'locations_round_1': dict(locations),
            'regions_round_1': dict(sites), 'entries_round_1': entries,
            'locations_all_rounds': dict(location_counts), 'entries_all_rounds': all_entries,
            'independent_plants': sorted(independent_plants),
            'tactical_rounds_loaded': len(result.rounds),
            'radar_players': len(radar['players']),
            'radar_samples': sum(len(p['samples']) for p in radar['players']),
            'cold_seconds': round(initial_calls, 2),
        }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('demo', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.demo.name.endswith('.dem.zst'):
        workspace = Path(__file__).resolve().parents[1]
        temporary = tempfile.TemporaryDirectory(dir=workspace)
        if not Path(temporary.name).resolve().is_relative_to(workspace.resolve()):
            raise ValueError('Temporary demo escaped the workspace')
        with temporary as temp:
            extracted = Path(temp) / args.demo.name.removesuffix('.zst')
            with args.demo.open('rb') as source, extracted.open('wb') as target:
                zstandard.ZstdDecompressor().copy_stream(source, target)
            result = verify(extracted)
        result['demo'] = args.demo.name
    else:
        result = verify(args.demo)
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
