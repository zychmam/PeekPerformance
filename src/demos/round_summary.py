"""Short, source-backed round summaries for the team and selected player."""

from dataclasses import dataclass

from src.maps.resolver import region_label, resolve_region
from src.demos.round_index import round_state_index
from src.models.tactical import Status


@dataclass(frozen=True)
class SummaryItem:
    title: str
    text: str
    tick: int | None = None
    evidence_ids: tuple[str, ...] = ()
    brief: str | None = None


def _time(tick, record, tick_rate):
    return f"{max(0, (tick - record.freeze_end_tick) / tick_rate):.1f} s" if tick is not None and record.freeze_end_tick is not None else "czas nieustalony"


def _name(player_id, labels):
    return labels.get(str(player_id), "Nieustalony gracz")


def _area(region_id, profile):
    return region_label(region_id, profile) if region_id else "miejsce nieustalone"


def _position_text(position, profile, record, tick_rate):
    if position.status != Status.OBSERVED or position.sample_tick is None:
        return "brak świeżej próbki pozycji"
    return f"{_area(position.area, profile)} (próbka {_time(position.sample_tick, record, tick_rate)})"


def _source_status(record, name):
    source = record.availability.get(name)
    return source.status if source else Status.UNKNOWN


def _alive_at(record, tick):
    """Counts remain valid between death ticks only when the kill source is known."""
    if _source_status(record, "kills") not in {Status.OBSERVED, Status.ABSENT}:
        return None
    state = next((state for state in reversed(record.alive_states) if state.tick <= tick), None)
    return state if state and state.t_alive is not None and state.ct_alive is not None else None


def _player_evidence(snapshot, evidence, player_id):
    return tuple(eid for eid in snapshot.evidence_ids if eid in evidence
                 and str(evidence[eid].data.get("steamid")) == str(player_id))


def _count(value, one, few, many):
    if value == 1:
        return f"1 {one}"
    if value % 10 in {2, 3, 4} and value % 100 not in {12, 13, 14}:
        return f"{value} {few}"
    return f"{value} {many}"


def _start_snapshot(preparation, record, tick_rate):
    contact_tick = min((c.tick for c in record.contacts), default=None)
    if contact_tick is not None:
        snap = preparation.setup_before_contact
        if snap is None or not contact_tick - tick_rate <= snap.tick < contact_tick:
            return None
        return snap
    return min(preparation.snapshots, key=lambda s: s.tick, default=None)


def _prep(side, preparation, record, evidence, profile, tick_rate):
    details = []
    snap = _start_snapshot(preparation, record, tick_rate)
    if snap and snap.counts:
        counts = ", ".join(f"{_area(area, profile)}: {count}" for area, count in snap.counts.items())
        before = " przed pierwszym zarejestrowanym kontaktem" if record.contacts else ""
        quality = "; niepełne pokrycie" if snap.status != Status.OBSERVED else ""
        details.append(f"{_time(snap.tick, record, tick_rate)}{before}: obecność graczy — {counts}{quality}.")
    else:
        details.append("Brak świeżego ustawienia sprzed pierwszego zarejestrowanego kontaktu."
                       if record.contacts else "Brak ustawienia we wczesnej fazie rundy.")
    throws = [evidence[eid] for eid in preparation.thrown_utility_ids if eid in evidence]
    if throws:
        kinds = {}
        for event in throws:
            kind = str(event.data.get("kind") or "granat")
            kinds[kind] = kinds.get(kind, 0) + 1
        details.append("Rzucone utility w pierwszych 15 s: " + ", ".join(f"{n} × {kind}" for kind, n in kinds.items()) + ".")
    elif _source_status(record, "throws") in {Status.OBSERVED, Status.ABSENT}:
        details.append("Nie zarejestrowano rzutu utility w pierwszych 15 s.")
    if not details:
        details.append("Za mało danych o przygotowaniu.")
    refs = tuple(dict.fromkeys(
        (list(snap.evidence_ids) if snap else [])
        + [event.id for event in throws]
    ))
    brief = f"{side}: {details[0].rstrip('.')}"
    if throws:
        brief += f"; {len(throws)} rzutów utility w 0–15 s"
    elif _source_status(record, "throws") in {Status.OBSERVED, Status.ABSENT}:
        brief += "; bez zarejestrowanego rzutu utility w 0–15 s"
    else:
        brief += "; rzuty utility — niepełne dane"
    return SummaryItem(f"Początek · {side}", " ".join(details), snap.tick if snap else None, refs, brief)


def _later_balance(record, evidence, tick_rate):
    """Expose later lead changes and clutch situations, without claiming cause."""
    if _source_status(record, "kills") not in {Status.OBSERVED, Status.ABSENT}:
        return []
    states = sorted(record.alive_states, key=lambda s: s.tick)
    boundary = record.opening_window_end_tick
    if boundary is None:
        return []
    previous = _alive_at(record, boundary)
    result = []
    for state in states:
        if state.tick <= boundary:
            continue
        if state.t_alive is None or state.ct_alive is None:
            previous = None
            continue
        if previous is not None:
            old = previous.t_alive - previous.ct_alive
            new = state.t_alive - state.ct_alive
            changed = (old > 0 and new <= 0) or (old < 0 and new >= 0) or (old == 0 and new != 0)
            clutch = (state.t_alive == 1 and previous.t_alive > 1 and state.ct_alive > 0
                      or state.ct_alive == 1 and previous.ct_alive > 1 and state.t_alive > 0)
            if (changed or clutch) and state.t_alive > 0 and state.ct_alive > 0:
                refs = tuple(dict.fromkeys(previous.evidence_ids + state.evidence_ids + [
                    eid for eid in record.event_ids if eid in evidence
                    and evidence[eid].source == "kills" and evidence[eid].tick == state.tick]))
                result.append(SummaryItem("Późniejsza zmiana liczebności",
                    f"{_time(state.tick, record, tick_rate)} · {previous.t_alive} T : {previous.ct_alive} CT → "
                    f"{state.t_alive} T : {state.ct_alive} CT.", state.tick, refs))
        previous = state
    return result


def _equipment(record, labels, player_id=None):
    foundation = record.foundation
    if not foundation:
        return []
    observations = [o for o in foundation.equipment_start
                    if player_id is None or o.player_id == player_id]
    parts, refs = [], []
    for side, team in (("T", 2), ("CT", 3)):
        players = [p for p in record.players if p.side == side
                   and (player_id is None or p.player_id == player_id)]
        if not players:
            continue
        samples = {o.player_id: o for o in observations if o.team_num == team
                   and o.tick == record.freeze_end_tick and o.player_id in {p.player_id for p in players}}
        known = [o for o in samples.values() if o.inventory is not None]
        inventories = {}
        for obs in known:
            for name, count in obs.inventory.items():
                inventories[name] = inventories.get(name, 0) + count
        gear = ", ".join(f"{name} ×{count}" for name, count in sorted(inventories.items())) or "brak odczytu ekwipunku"
        prefix = _name(player_id, labels) if player_id else side
        parts.append(f"{prefix}: ekwipunek odczytany dla {len(known)}/{len(players)} graczy — {gear}.")
        armor = [o.armor for o in samples.values() if o.armor is not None]
        kits = [o.defuse_kit for o in samples.values() if o.defuse_kit is not None]
        if armor:
            parts.append(f"Pancerz > 0: {sum(a > 0 for a in armor)}/{len(armor)} odczytanych.")
        if side == "CT" and kits:
            parts.append(f"Kity: {sum(bool(k) for k in kits)}/{len(kits)} odczytanych.")
        refs.extend(eid for o in samples.values() for eid in o.evidence_ids)
    return [SummaryItem("Wyposażenie na starcie", " ".join(parts), record.freeze_end_tick,
                        tuple(dict.fromkeys(refs)))] if parts else []


def _player_positions(record, evidence, player_id, profile, tick_rate, state_index=None):
    """One indexed round lookup, shared by all selected player's milestones."""
    index = state_index if state_index is not None else round_state_index(record, evidence)
    milestones = [(entry.start_tick, f"wejście T na site {entry.area or '?'}", entry.evidence_ids)
                  for entry in record.observed_entries]
    milestones += [(evidence[eid].tick, "plant", [eid]) for eid in record.bomb_event_ids
                   if eid in evidence and evidence[eid].data.get("event") == "bomb_planted"]
    milestones.append((record.end_tick, "koniec rundy", []))
    result = []
    for tick, label, event_ids in sorted(milestones):
        sample = index.before(tick, player_id=player_id,
                              max_age_ticks=max(0, round(tick_rate) - 1),
                              max_gap_ticks=round(2 * tick_rate))
        row = sample.row
        if row is not None and row.get("is_alive") is True:
            area = resolve_region(row, profile) if profile else None
            text = f"{_area(area, profile)} (próbka {_time(sample.sample_tick, record, tick_rate)})"
        elif row is not None and row.get("is_alive") is False:
            text = f"próbka {_time(sample.sample_tick, record, tick_rate)} wskazuje, że gracz nie żył"
        else:
            text = "brak świeżej próbki pozycji i stanu gracza"
        refs = tuple(dict.fromkeys([*event_ids, *([row['event_id']] if row else [])]))
        result.append(SummaryItem("Pozycja przy zdarzeniu",
                                 f"{_time(tick, record, tick_rate)} · {label}: {text}.", tick, refs))
    return result


def summary_preview(items, player=False):
    """Four short lines; full statements and evidence stay in the detail panel."""
    def first(title):
        return next((i for i in items if i.title == title), None)

    if player:
        groups = [("Początek", [first("Początek")]),
                  ("Kontakt", [first("Pierwszy kontakt gracza")]),
                  ("Udział", [first("Udział w rundzie"), first("Wymiany")]),
                  ("Wynik", [first("Zgon"), first("Wynik")])]
    else:
        changes = [i for i in items if i.title == "Późniejsza zmiana liczebności"]
        groups = [("Przygotowanie", [first("Początek · T"), first("Początek · CT")]),
                  ("Pierwsza walka", [first("Opening i stan graczy") or first("Pierwszy kontakt"),
                                     first("Odpowiedź po openingu")]),
                  ("Dalszy przebieg", [changes[-1] if changes else None,
                                      first("Próby ataku T") or first("Wejście na site"),
                                      first("Reakcje CT") or first("Bomba")]),
                  ("Wynik", [first("Koniec")])]
    return [(heading, "; ".join((i.brief or i.text).rstrip(".") for i in group if i) + ".")
            for heading, group in groups if any(group)]


def team_summary(record, evidence, labels, profile, tick_rate, response_seconds=5.0):
    """Order follows observed round chronology; unknown stays unknown."""
    items = [
        _prep("T", record.t_preparation, record, evidence, profile, tick_rate),
        _prep("CT", record.ct_setup, record, evidence, profile, tick_rate),
    ]
    first_tick = min((contact.tick for contact in record.contacts), default=None)
    if first_tick is not None:
        contacts = [contact for contact in record.contacts if contact.tick == first_tick]
        contact = contacts[0]
        mode = {"firearm": "z broni", "utility": "utility", "mixed": "mieszany"}.get(
            contact.modality, "rodzaj nieustalony"
        )
        action = "eliminacja" if contact.kind == "kill_only" else "obrażenia"
        text = (f"{_time(contact.tick, record, tick_rate)} · {action} ({mode}): "
                f"{_name(contact.attacker_id, labels)} ({contact.attacker_side}) → "
                f"{_name(contact.victim_id, labels)} ({contact.victim_side}). "
                f"Pozycje przed kontaktem: {_name(contact.attacker_id, labels)} — "
                f"{_position_text(contact.attacker_position, profile, record, tick_rate)}; "
                f"{_name(contact.victim_id, labels)} — "
                f"{_position_text(contact.victim_position, profile, record, tick_rate)}.")
        if len(contacts) > 1:
            text += f" W tym samym ticku: {len(contacts)} kontakty bez ustalonej kolejności."
        brief = (f"{_time(contact.tick, record, tick_rate)} · {action} ({mode}): "
                 f"{_name(contact.attacker_id, labels)} → {_name(contact.victim_id, labels)}")
        items.append(SummaryItem("Pierwszy kontakt", text, contact.tick,
                                 tuple(dict.fromkeys(eid for c in contacts for eid in c.evidence_ids)), brief))
    else:
        message = ("Nie zarejestrowano kontaktu z przeciwnikiem." if record.contacts_status == Status.ABSENT
                   else "Nie można ustalić pierwszego kontaktu z dostępnych zdarzeń.")
        items.append(SummaryItem("Pierwszy kontakt", message))
    if record.opening_kill_ids:
        kills = [evidence[eid] for eid in record.opening_kill_ids if eid in evidence]
        if kills:
            first = kills[0]
            text = (f"{_time(first.tick, record, tick_rate)} · opening: "
                    f"{_name(first.data.get('attacker_steamid'), labels)} ({'T' if first.data.get('attacker_team_num') == 2 else 'CT'}) "
                    f"eliminuje {_name(first.data.get('user_steamid'), labels)}.")
            if len(kills) > 1:
                text += " Równoczesne fragi otwierające: " + str(len(kills)) + "."
            after = _alive_at(record, first.tick)
            if after and after.t_alive is not None and after.ct_alive is not None:
                text += f" Po tym ticku: {after.t_alive} T : {after.ct_alive} CT."
            items.append(SummaryItem("Opening i stan graczy", text, first.tick, tuple(e.id for e in kills)))
    elif record.opening_status != Status.ABSENT:
        items.append(SummaryItem("Opening i stan graczy", "Nie można wiarygodnie ustalić openingu."))
    if record.opening_window_end_tick is not None:
        followups = [evidence[eid] for eid in record.opening_window_kill_ids if eid in evidence]
        counts = {side: sum(1 for event in followups
                            if str(event.data.get("attacker_team_num")) == team)
                  for side, team in (("T", "2"), ("CT", "3"))}
        opening_refs = set(record.opening_kill_ids)
        opening_trades = [link for link in record.refrag_links if link.death_id in opening_refs]
        scope = ("do końca rundy" if record.opening_window_end_tick == record.end_tick
                 else f"w ciągu {response_seconds:g} s po openingu")
        if record.opening_response_status in {Status.OBSERVED, Status.PARTIAL}:
            prefix = "co najmniej " if record.opening_response_status == Status.PARTIAL else ""
            text = (f"{scope.capitalize()}: {prefix}{counts['T']} kolejnych fragów T, "
                    f"{prefix}{counts['CT']} CT.")
            if opening_trades:
                link = opening_trades[0]
                reply = evidence[link.response_kill_id]
                text += (f" {_name(reply.data.get('attacker_steamid'), labels)} wymienił śmierć kolegi, "
                         f"zabijając jego zabójcę po {link.delay_ticks / tick_rate:.1f} s.")
                if len(opening_trades) > 1:
                    text += f" Łącznie {len(opening_trades)} powiązań refraga z openingiem."
            else:
                text += (" Nie odnotowano refraga openingu w tym oknie."
                         if record.opening_response_status == Status.OBSERVED else
                         " Refrag openingu nie został potwierdzony w niepełnych danych.")
            state = _alive_at(record, record.opening_window_end_tick)
            if state and state.t_alive is not None and state.ct_alive is not None:
                text += f" Stan po oknie: {state.t_alive} T : {state.ct_alive} CT."
            items.append(SummaryItem("Odpowiedź po openingu", text,
                                     followups[0].tick if followups else record.opening_window_end_tick,
                                     tuple(record.opening_kill_ids + record.opening_window_kill_ids),
                                     f"{scope}: {prefix}{counts['T']} kolejnych fragów T, {prefix}{counts['CT']} CT; "
                                     f"potwierdzone powiązania refraga openingu: {len(opening_trades)}"))
        else:
            items.append(SummaryItem("Odpowiedź po openingu",
                                     f"Brak wystarczających danych, by ocenić odpowiedź w {response_seconds:g} sekundach po openingu."))
    entries = sorted(record.observed_entries, key=lambda e: e.start_tick)
    if entries:
        first = entries[0]
        text = f"{_time(first.start_tick, record, tick_rate)} · potwierdzone wejście T na site {first.area or '?'}"
        text += f"; uczestnicy: {len(first.participants)} T w zaobserwowanej grupie."
        if len(entries) > 1:
            text += f" Łącznie potwierdzono {len(entries)} wejścia."
        state = _alive_at(record, first.start_tick)
        if state:
            text += f" Przy wejściu: {state.t_alive} T : {state.ct_alive} CT."
        items.append(SummaryItem("Wejście na site", text, first.start_tick, tuple(first.evidence_ids)))
    bomb = sorted((evidence[eid] for eid in record.bomb_event_ids if eid in evidence and
                   evidence[eid].data.get("event") in {"bomb_planted", "bomb_defused", "bomb_exploded"}),
                  key=lambda event: event.tick)
    if bomb:
        names = {"bomb_planted": "plant", "bomb_defused": "rozbrojenie", "bomb_exploded": "wybuch"}
        descriptions = []
        for event in bomb:
            phrase = f"{_time(event.tick, record, tick_rate)} · {names[event.data['event']]}"
            if event.data["event"] == "bomb_planted":
                state = _alive_at(record, event.tick)
                if state:
                    phrase += f" przy {state.t_alive} T : {state.ct_alive} CT"
            descriptions.append(phrase)
        text = "; ".join(descriptions)
        items.append(SummaryItem("Bomba", text + ".", bomb[0].tick, tuple(e.id for e in bomb)))
    items.extend(_later_balance(record, evidence, tick_rate))
    items.extend(_equipment(record, labels))
    items.extend(tactical_summary(record, labels, profile, tick_rate))
    winner = record.winner_side or "nieustalona strona"
    reasons = {"bomb_defused": "rozbrojenie bomby", "bomb_exploded": "wybuch bomby",
               "t_killed": "eliminacja T", "ct_killed": "eliminacja CT",
               "target_saved": "upływ czasu", "time": "upływ czasu"}
    reason = reasons.get(record.end_reason, record.end_reason or "nieustalony")
    items.append(SummaryItem("Koniec", f"Rundę wygrała strona {winner}. Powód: {reason}.", record.end_tick))
    return items


def player_summary(record, evidence, player_id, labels, profile, tick_rate, *, state_index=None):
    player = next((p for p in record.players if p.player_id == str(player_id)), None)
    if player is None:
        return [SummaryItem("Gracz", "Brak tego gracza w składzie rundy.")]
    items = []
    prep = record.t_preparation if player.side == "T" else record.ct_setup
    snap = _start_snapshot(prep, record, tick_rate)
    observed = next((p for p in snap.players if p["player_id"] == str(player_id)), None) if snap else None
    start = _area(observed.get("area"), profile) if observed and observed.get("alive") else "pozycja nieustalona"
    moment = "przed pierwszym zarejestrowanym kontaktem" if record.contacts else "we wczesnej fazie rundy"
    if snap:
        moment += f" ({_time(snap.tick, record, tick_rate)}; próbka {_time(observed.get('sample_tick', snap.tick), record, tick_rate) if observed else 'nieustalona'})"
    items.append(SummaryItem("Początek", f"{_name(player_id, labels)} gra po stronie {player.side or '?'}. Pozycja {moment}: {start}.",
                             snap.tick if snap else None,
                             _player_evidence(snap, evidence, player_id) if snap else ()))
    contacts = [c for c in record.contacts if c.id in player.contact_references.get("first_any", [])]
    if contacts:
        first = contacts[0]
        attacker = first.attacker_id == str(player_id)
        if first.kind == "kill_only":
            role = "eliminuje" if attacker else "ginie od"
        else:
            role = "zadaje obrażenia" if attacker else "otrzymuje obrażenia od"
        other = first.victim_id if first.attacker_id == str(player_id) else first.attacker_id
        own_pos = first.attacker_position if first.attacker_id == str(player_id) else first.victim_position
        other_pos = first.victim_position if attacker else first.attacker_position
        mode = {"firearm": "broń", "utility": "utility", "mixed": "broń i utility"}.get(
            first.modality, "rodzaj nieustalony"
        )
        text = (f"{_time(first.tick, record, tick_rate)} · {role} {_name(other, labels)} "
                f"({mode}). Pozycje: {_name(player_id, labels)} — {_position_text(own_pos, profile, record, tick_rate)}; "
                f"{_name(other, labels)} — {_position_text(other_pos, profile, record, tick_rate)}.")
        brief = (f"{_time(first.tick, record, tick_rate)} · {role} {_name(other, labels)} ({mode})")
        if any(evidence[eid].source == "kills" for eid in first.evidence_ids if eid in evidence) and first.kind != "kill_only":
            text += " W tym samym ticku odnotowano eliminację przeciwnika." if first.attacker_id == str(player_id) else " W tym samym ticku gracz zginął."
            brief += "; eliminacja w tym samym ticku" if attacker else "; zgon w tym samym ticku"
        if len(contacts) > 1:
            text += " Kilka kontaktów w tym samym ticku; kolejność nieustalona."
        items.append(SummaryItem("Pierwszy kontakt gracza", text, first.tick,
                                 tuple(eid for c in contacts for eid in c.evidence_ids), brief))
    else:
        items.append(SummaryItem("Pierwszy kontakt gracza", "Nie zaobserwowano własnego kontaktu z przeciwnikiem." if player.contact_status == Status.ABSENT else "Pierwszy kontakt gracza nieustalony."))
    own_trades = [link for link in record.refrag_links
                  if str(evidence[link.response_kill_id].data.get("attacker_steamid")) == str(player_id)]
    death_trades = [link for link in record.refrag_links
                    if str(evidence[link.death_id].data.get("user_steamid")) == str(player_id)]
    if own_trades or death_trades:
        parts = []
        if own_trades:
            unique_kills = len({link.response_kill_id for link in own_trades})
            parts.append(f"Refragi gracza: {_count(unique_kills, 'zabójstwo', 'zabójstwa', 'zabójstw')} "
                         f"wymieniające {_count(len(own_trades), 'śmierć', 'śmierci', 'śmierci')} kolegów.")
        if death_trades:
            link = death_trades[0]
            reply = evidence[link.response_kill_id]
            parts.append(f"Jego śmierć wymienił {_name(reply.data.get('attacker_steamid'), labels)} po {link.delay_ticks / tick_rate:.1f} s.")
        first_reply = min((evidence[link.response_kill_id].tick for link in own_trades + death_trades))
        refs = tuple(dict.fromkeys(eid for link in own_trades + death_trades for eid in link.evidence_ids))
        items.append(SummaryItem("Wymiany", " ".join(parts), first_reply, refs))
    kills = [evidence[eid] for eid in record.event_ids if eid in evidence and evidence[eid].source == "kills"]
    own_kills = [e for e in kills if str(e.data.get("attacker_steamid")) == str(player_id)
                 and e.data.get("attacker_team_num") != e.data.get("user_team_num")]
    deaths = [e for e in kills if str(e.data.get("user_steamid")) == str(player_id)]
    kills_available = _source_status(record, "kills") in {Status.OBSERVED, Status.ABSENT}
    events = ([_count(len(own_kills), "frag", "fragi", "fragów"),
               _count(len(deaths), "zgon", "zgony", "zgonów")]
              if kills_available else [f"zaobserwowane fragi: {len(own_kills)}; zgony: {len(deaths)} (niepełne dane)"])
    own_contacts = [contact for contact in record.contacts if contact.attacker_id == str(player_id)]
    if own_contacts:
        damage = sum(contact.actual_damage or 0 for contact in own_contacts)
        events.append(f"{damage:g} zaobserwowanych obrażeń HP")
    all_throw_ids = record.foundation.thrown_utility_ids if record.foundation else []
    throws = [evidence[eid] for eid in all_throw_ids if eid in evidence
              and str(evidence[eid].data.get("user_steamid")) == str(player_id)]
    early_throw_ids = set(prep.thrown_utility_ids)
    early_throws = sum(event.id in early_throw_ids for event in throws)
    throws_available = _source_status(record, "throws") in {Status.OBSERVED, Status.ABSENT}
    events.append((f"{_count(len(throws), 'rzut', 'rzuty', 'rzutów')} utility w rundzie, "
                   f"w tym {early_throws} do 15 s"
                   if throws_available else
                   f"zaobserwowane rzuty utility: {len(throws)} (niepełne dane)"))
    own_entries = [e for e in record.observed_entries if str(player_id) in e.participants]
    if own_entries:
        events.append(f"wejście na site {own_entries[0].area or '?'}")
    bomb_actions = [evidence[eid] for eid in record.bomb_event_ids if eid in evidence
                    and str(evidence[eid].data.get("user_steamid")) == str(player_id)
                    and evidence[eid].data.get("event") in {"bomb_planted", "bomb_defused"}]
    for event in bomb_actions:
        events.append("podłożył bombę" if event.data["event"] == "bomb_planted"
                      else "rozbroił bombę")
    evidence_ids = tuple(dict.fromkeys(
        [e.id for e in own_kills + deaths + throws + bomb_actions]
        + [eid for contact in own_contacts for eid in contact.evidence_ids]
        + [eid for entry in own_entries for eid in entry.evidence_ids]
    ))
    event_ticks = [e.tick for e in own_kills + deaths + throws + bomb_actions]
    event_ticks += [entry.start_tick for entry in own_entries]
    items.append(SummaryItem("Udział w rundzie", " · ".join(events) + ".",
                             min(event_ticks, default=None), evidence_ids))
    movement = next((move for move in prep.movements if move.player_id == str(player_id)), None)
    if movement:
        text = (f"W pierwszych 15 s potwierdzono przejście: "
                f"{_area(movement.from_area, profile)} → {_area(movement.to_area, profile)} "
                f"(od {_time(movement.arrival_tick, record, tick_rate)}).")
        items.append(SummaryItem("Ruch", text, movement.arrival_tick,
                                 tuple(movement.evidence_ids)))
    if deaths:
        death = min(deaths, key=lambda event: event.tick)
        attacker = _name(death.data.get("attacker_steamid"), labels)
        items.append(SummaryItem("Zgon", f"{_time(death.tick, record, tick_rate)} · zginął od {attacker}.",
                                 death.tick, (death.id,)))
    elif kills_available:
        items.append(SummaryItem("Zakończenie", "W zapisanych zdarzeniach rundy nie ma zgonu tego gracza."))
    items.extend(_equipment(record, labels, str(player_id)))
    items.extend(_player_positions(record, evidence, str(player_id), profile, tick_rate, state_index))
    items.extend(tactical_summary(record, labels, profile, tick_rate, player_id=str(player_id)))
    winner = record.winner_side
    result = "wygrana" if winner == player.side else "przegrana" if winner in {"T", "CT"} else "wynik nieustalony"
    items.append(SummaryItem("Wynik", f"Dla gracza: {result} rundy ({player.side or '?'}).", record.end_tick))
    return items


def tactical_summary(record, labels, profile, tick_rate, player_id=None):
    items = []
    outcomes = {"planted": "plant", "entered": "wejście", "withdrawn": "wycofanie",
                "stopped": "zatrzymanie", "unknown": "zakończenie nieustalone"}
    attacks = [a for a in record.attacks if player_id is None
               or player_id in a.episode.participants or player_id in a.detached_players]
    if attacks:
        descriptions = [f"{_time(a.episode.start_tick, record, tick_rate)} · cel {a.target_site}, "
                        f"{len(a.episode.participants)} uczestników: {outcomes[a.outcome]}"
                        for a in attacks]
        refs = tuple(dict.fromkeys(ref for a in attacks for ref in a.episode.evidence_ids))
        items.append(SummaryItem("Próby ataku T", "; ".join(descriptions) + ".",
                                 attacks[0].episode.start_tick, refs,
                                 f"Próby T: {' → '.join(a.target_site for a in attacks)}; ostatnia: {outcomes[attacks[-1].outcome]}"))
    rotations = [r for r in record.rotations if r.outcome == "arrived"
                 and (player_id is None or r.player_id == player_id)]
    if rotations:
        descriptions = [f"{_name(r.player_id, labels)}: {_area(r.from_area, profile)} → "
                        f"sektor {r.target_site}, przybycie {_time(r.arrival_tick, record, tick_rate)}"
                        for r in rotations]
        items.append(SummaryItem("Reakcje CT", "; ".join(descriptions) + ".",
                                 rotations[0].episode.start_tick,
                                 tuple(dict.fromkeys(ref for r in rotations for ref in r.episode.evidence_ids)),
                                 f"CT: {len(rotations)} obserwowanych przybyć do sektora celu po kontakcie/plancie"))
    if record.retake.episode and (player_id is None or player_id in record.retake.episode.participants):
        retake = record.retake
        items.append(SummaryItem("Retake", f"Próba odbicia site'u od {_time(retake.episode.start_tick, record, tick_rate)}; "
                                 + {"won": "wygrana CT.", "lost": "przegrana CT."}.get(retake.outcome, "wynik nieustalony."),
                                 retake.episode.start_tick, tuple(retake.episode.evidence_ids)))
    return items
