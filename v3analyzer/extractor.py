"""
Data extractor for Victoria 3 save game data.

Extracts structured metrics from parsed PDX data:
- GDP time series
- Population
- Budget (revenue/expenditure)
- Standard of living
- Military
- Technology
- Trade
- Top goods production
"""
from typing import Any


def extract_all(gamestate: dict, meta: dict, compare_countries: bool = False) -> dict:
    """Extract all available metrics from a parsed save."""
    player_tag = _get_player_tag(meta, gamestate)
    player_id = _find_country_id(gamestate, player_tag)
    game_date = _get_game_date(meta, gamestate)

    country_data = _get_country(gamestate, player_id)
    history = _get_country_history(gamestate, player_id)

    result = {
        "meta": {
            "player_tag": player_tag,
            "player_id": player_id,
            "game_date": game_date,
            "country_name": _get_country_name(country_data, player_tag),
        },
        "timeseries": _extract_timeseries(history),
        "snapshot": _extract_snapshot(gamestate, country_data, player_id),
        "states": _extract_states(gamestate, player_id),
        "technology": _extract_technology(country_data),
        "goods": _extract_goods_production(gamestate, player_id),
        "territory_map": _extract_territory_map(gamestate, player_tag),
    }

    if compare_countries:
        result["comparison"] = _extract_all_countries(
            gamestate, player_id, selected_tags=compare_countries
        )

    return result


def list_countries(gamestate: dict, meta: dict) -> list:
    """Return a list of all countries with history data (tag, name, is_player, final GDP)."""
    player_tag = _get_player_tag(meta, gamestate)
    player_id = _find_country_id(gamestate, player_tag)
    countries_db = _get_countries_db(gamestate)

    country_history = gamestate.get("country_history", {})
    if isinstance(country_history, dict) and "database" in country_history:
        country_history = country_history["database"]

    results = []

    # Strategy 1: dedicated country_history section (sample/text saves)
    if isinstance(country_history, dict) and country_history:
        for cid_key, history in country_history.items():
            if not isinstance(history, dict):
                continue
            gdp_data = history.get("weekly_gdp", history.get("gdp", []))
            if not isinstance(gdp_data, list) or len(gdp_data) < 2:
                continue

            country_data = countries_db.get(cid_key, {})
            tag = str(country_data.get("definition", cid_key))
            name = _get_country_name(country_data, tag)
            is_player = (cid_key == player_id or str(cid_key) == str(player_id))
            final_gdp = gdp_data[-1] if gdp_data else 0

            results.append({
                "tag": tag,
                "name": name,
                "is_player": is_player,
                "final_gdp": float(final_gdp) if isinstance(final_gdp, (int, float)) else 0,
            })

    # Strategy 2: history embedded in country entries (melted binary saves)
    if not results:
        for cid_key, country_data in countries_db.items():
            if not isinstance(country_data, dict):
                continue
            gdp_block = country_data.get("gdp", {})
            if not isinstance(gdp_block, dict) or "channels" not in gdp_block:
                continue
            gdp_vals = _extract_channel_values(gdp_block)
            if len(gdp_vals) < 2:
                continue

            tag = str(country_data.get("definition", cid_key))
            name = _get_country_name(country_data, tag)
            is_player = (cid_key == player_id or str(cid_key) == str(player_id))
            final_gdp = gdp_vals[-1] if gdp_vals else 0

            results.append({
                "tag": tag,
                "name": name,
                "is_player": is_player,
                "final_gdp": float(final_gdp) if isinstance(final_gdp, (int, float)) else 0,
            })

    results.sort(key=lambda c: (not c["is_player"], -c["final_gdp"]))
    return results


def _extract_all_countries(gamestate: dict, player_id: int, selected_tags=None) -> list:
    """Extract timeseries for all countries that have history data.
    If selected_tags is a list of tag strings, only include those countries."""
    countries_db = _get_countries_db(gamestate)
    country_history = gamestate.get("country_history", {})
    if isinstance(country_history, dict) and "database" in country_history:
        country_history = country_history["database"]

    # Build tag filter set
    tag_filter = None
    if isinstance(selected_tags, (list, set)) and selected_tags:
        tag_filter = set(str(t) for t in selected_tags)

    countries = []

    # Strategy 1: dedicated country_history section
    if isinstance(country_history, dict) and country_history:
        for cid_key, history in country_history.items():
            if not isinstance(history, dict):
                continue

            country_data = countries_db.get(cid_key, {})
            tag = str(country_data.get("definition", cid_key))

            if tag_filter and tag not in tag_filter:
                continue

            ts = _extract_timeseries(history)
            if not ts or "gdp" not in ts:
                continue

            name = _get_country_name(country_data, tag)
            is_player = (cid_key == player_id or str(cid_key) == str(player_id))

            countries.append({
                "tag": tag,
                "name": name,
                "is_player": is_player,
                "timeseries": ts,
            })

    # Strategy 2: history embedded in country entries (melted binary saves)
    if not countries:
        for cid_key, country_data in countries_db.items():
            if not isinstance(country_data, dict):
                continue
            tag = str(country_data.get("definition", cid_key))
            if tag_filter and tag not in tag_filter:
                continue

            history = _extract_embedded_history(country_data)
            if not history:
                continue

            ts = _extract_timeseries(history)
            if not ts or "gdp" not in ts:
                continue

            name = _get_country_name(country_data, tag)
            is_player = (cid_key == player_id or str(cid_key) == str(player_id))

            countries.append({
                "tag": tag,
                "name": name,
                "is_player": is_player,
                "timeseries": ts,
            })

    # Sort: player first, then by final GDP descending
    countries.sort(
        key=lambda c: (not c["is_player"], -(c["timeseries"].get("gdp", [0])[-1])),
    )
    return countries


def _get_player_tag(meta: dict, gamestate: dict) -> str:
    """Get the player's country tag."""
    # Check meta first
    if isinstance(meta, dict):
        if "player" in meta:
            return meta["player"]
        if "player_tag" in meta:
            return meta["player_tag"]
    # Check gamestate
    if "player_manager" in gamestate:
        pm = gamestate["player_manager"]
        if isinstance(pm, dict):
            if "database" in pm:
                db = pm["database"]
                if isinstance(db, dict):
                    for k, v in db.items():
                        if isinstance(v, dict) and "country" in v:
                            return _resolve_country_tag(gamestate, v["country"])
            # Try player_country_id
            if "player_country" in pm:
                return str(pm["player_country"])
    # Fallback
    if "played_country" in gamestate:
        pc = gamestate["played_country"]
        if isinstance(pc, dict) and "country" in pc:
            return str(pc["country"])
    return "UNKNOWN"


def _resolve_country_tag(gamestate: dict, country_ref: Any) -> str:
    """Resolve a country reference to its tag."""
    countries = _get_countries_db(gamestate)
    if isinstance(country_ref, int) and country_ref in countries:
        c = countries[country_ref]
        if isinstance(c, dict) and "definition" in c:
            return str(c["definition"])
    return str(country_ref)


def _find_country_id(gamestate: dict, player_tag: str) -> int:
    """Find the numeric country ID for a given tag."""
    countries = _get_countries_db(gamestate)
    for cid, cdata in countries.items():
        if isinstance(cdata, dict):
            definition = cdata.get("definition", "")
            if str(definition) == player_tag:
                return cid
            # Sometimes tag is stored directly
            tag = cdata.get("tag", "")
            if str(tag) == player_tag:
                return cid
    # If player_tag is numeric, use directly
    try:
        return int(player_tag)
    except (ValueError, TypeError):
        return None


def _get_countries_db(gamestate: dict) -> dict:
    """Get the countries database."""
    cm = gamestate.get("country_manager", {})
    if isinstance(cm, dict):
        db = cm.get("database", {})
        if isinstance(db, dict):
            return db
    return {}


def _get_country(gamestate: dict, country_id: int) -> dict:
    """Get country data by ID."""
    if country_id is None:
        return {}
    countries = _get_countries_db(gamestate)
    return countries.get(country_id, {})


def _get_country_name(country_data: dict, fallback_tag: str) -> str:
    """Get a human-readable country name."""
    if isinstance(country_data, dict):
        for key in ("definition", "tag", "country_type"):
            if key in country_data:
                val = country_data[key]
                if isinstance(val, str) and len(val) > 0:
                    return val
    return fallback_tag


def _get_game_date(meta: dict, gamestate: dict) -> str:
    """Get the current game date."""
    if isinstance(meta, dict) and "date" in meta:
        return str(meta["date"])
    if "date" in gamestate:
        return str(gamestate["date"])
    return "Unknown"


def _get_country_history(gamestate: dict, country_id: int) -> dict:
    """Get the country_history entry for the player.

    Supports two formats:
    1. Separate country_history section (sample/text saves)
    2. History embedded in country_manager entries (melted binary saves)
    """
    # Try dedicated country_history section first
    ch = gamestate.get("country_history", {})
    if isinstance(ch, dict) and "database" in ch:
        ch = ch["database"]
    if isinstance(ch, dict) and country_id is not None:
        result = ch.get(country_id, ch.get(str(country_id), {}))
        if result:
            return result

    # Fallback: history embedded in country_manager entry
    country_data = _get_country(gamestate, country_id)
    if isinstance(country_data, dict):
        return _extract_embedded_history(country_data)
    return {}


def _extract_channel_values(channel_data: dict) -> list:
    """Extract values from a channel-based history block.

    Melted format: {sample_rate: 28, count: N, channels: {0: {date, index, values: [...]}}}
    """
    if not isinstance(channel_data, dict):
        return []
    channels = channel_data.get("channels", {})
    if isinstance(channels, dict):
        ch0 = channels.get("0", channels.get(0, {}))
        if isinstance(ch0, dict):
            vals = ch0.get("values", [])
            if isinstance(vals, list):
                return vals
    return []


def _extract_embedded_history(country_data: dict) -> dict:
    """Convert embedded channel-based history to the flat format expected by _extract_timeseries.

    Maps: country.gdp.channels.0.values → weekly_gdp, etc.
    """
    history = {}

    # Channel-based history fields in melted saves
    channel_map = {
        "gdp": "weekly_gdp",
        "prestige": "weekly_prestige",
        "literacy": "weekly_literacy",
        "avgsoltrend": "weekly_sol",
    }

    for field, history_key in channel_map.items():
        data = country_data.get(field, {})
        if isinstance(data, dict) and "channels" in data:
            vals = _extract_channel_values(data)
            if vals:
                history[history_key] = vals

    # Population from pop_statistics (current value, not timeseries)
    ps = country_data.get("pop_statistics", {})
    if isinstance(ps, dict):
        total_pop = 0
        for k in ("population_lower_strata", "population_middle_strata",
                   "population_upper_strata"):
            v = ps.get(k, 0)
            if isinstance(v, (int, float)):
                total_pop += v
        if total_pop > 0:
            # Create a single-value population series
            history["weekly_population"] = [total_pop]

    return history


def _extract_timeseries(history: dict) -> dict:
    """Extract time-series data from country history."""
    timeseries = {}

    # Map of save-file keys to our output keys
    key_map = {
        "weekly_gdp": "gdp",
        "weekly_money": "treasury",
        "weekly_population": "population",
        "weekly_sol": "standard_of_living",
        "weekly_revenue": "revenue",
        "weekly_expense": "expenditure",
        "weekly_literacy": "literacy",
        "weekly_prestige": "prestige",
        "weekly_clout": "clout",
        "weekly_innovations": "innovations",
        "weekly_military_strength": "military_strength",
        "weekly_gdp_per_capita": "gdp_per_capita",
        "gdp": "gdp",
        "money": "treasury",
        "population": "population",
        "sol": "standard_of_living",
        "revenue": "revenue",
        "expense": "expenditure",
        "literacy": "literacy",
        "prestige": "prestige",
    }

    if not isinstance(history, dict):
        return timeseries

    for save_key, output_key in key_map.items():
        if save_key in history:
            val = history[save_key]
            if isinstance(val, list):
                timeseries[output_key] = [
                    float(v) if isinstance(v, (int, float)) else 0.0
                    for v in val
                ]
            elif isinstance(val, (int, float)):
                timeseries[output_key] = [float(val)]

    # Derive GDP growth rate if we have GDP
    if "gdp" in timeseries and len(timeseries["gdp"]) > 1:
        gdp = timeseries["gdp"]
        growth = []
        for i in range(1, len(gdp)):
            if gdp[i - 1] != 0:
                growth.append(((gdp[i] - gdp[i - 1]) / gdp[i - 1]) * 100)
            else:
                growth.append(0.0)
        timeseries["gdp_growth_rate"] = growth

    # Derive GDP per capita if not present
    if (
        "gdp_per_capita" not in timeseries
        and "gdp" in timeseries
        and "population" in timeseries
    ):
        gdp = timeseries["gdp"]
        pop = timeseries["population"]
        min_len = min(len(gdp), len(pop))
        timeseries["gdp_per_capita"] = [
            gdp[i] / pop[i] if pop[i] != 0 else 0 for i in range(min_len)
        ]

    return timeseries


def _extract_snapshot(
    gamestate: dict, country_data: dict, country_id: int
) -> dict:
    """Extract current-state snapshot metrics."""
    snapshot = {}

    if isinstance(country_data, dict):
        # Direct values
        for key in (
            "gdp",
            "population",
            "prestige",
            "money",
            "literacy",
            "country_type",
            "government",
            "ruling_interest_groups",
            "tax_level",
        ):
            if key in country_data:
                snapshot[key] = country_data[key]

        # Budget
        if "budget" in country_data:
            budget = country_data["budget"]
            if isinstance(budget, dict):
                snapshot["revenue"] = budget.get("revenue", 0)
                snapshot["expenditure"] = budget.get("expense", budget.get("expenditure", 0))

        # Military
        if "military" in country_data:
            mil = country_data["military"]
            if isinstance(mil, dict):
                snapshot["army_size"] = mil.get("army_size", 0)
                snapshot["navy_size"] = mil.get("navy_size", 0)

        # Technology count
        if "technology" in country_data:
            tech = country_data["technology"]
            if isinstance(tech, dict):
                acquired = tech.get("acquired_technologies", [])
                if isinstance(acquired, list):
                    snapshot["tech_count"] = len(acquired)

    return snapshot


def _extract_states(gamestate: dict, country_id: int) -> list:
    """Extract state-level data for the player's country."""
    states_list = []
    sm = gamestate.get("state_manager", gamestate.get("states", {}))
    if isinstance(sm, dict):
        db = sm.get("database", sm)
        if isinstance(db, dict):
            for sid, sdata in db.items():
                if not isinstance(sdata, dict):
                    continue
                owner = sdata.get("country", sdata.get("owner"))
                if owner == country_id or str(owner) == str(country_id):
                    states_list.append(
                        {
                            "id": sid,
                            "name": sdata.get("definition", sdata.get("name", str(sid))),
                            "population": sdata.get("population", 0),
                            "gdp": sdata.get("gdp", 0),
                            "infrastructure": sdata.get("infrastructure", 0),
                        }
                    )
    return states_list


def _extract_technology(country_data: dict) -> dict:
    """Extract technology info."""
    if not isinstance(country_data, dict):
        return {"acquired": [], "researching": ""}
    tech = country_data.get("technology", {})
    if not isinstance(tech, dict):
        return {"acquired": [], "researching": ""}
    acquired = tech.get("acquired_technologies", [])
    if not isinstance(acquired, list):
        acquired = []
    researching = tech.get("researching", "")
    return {
        "acquired": acquired,
        "researching": str(researching),
    }


def _extract_goods_production(gamestate: dict, country_id: int) -> list:
    """Extract top goods production data. This is best-effort since
    the save format varies between patches."""
    goods = []
    # Look in market_manager or buildings for production info
    mm = gamestate.get("market_manager", {})
    if isinstance(mm, dict):
        db = mm.get("database", {})
        if isinstance(db, dict):
            for mid, mdata in db.items():
                if not isinstance(mdata, dict):
                    continue
                goods_data = mdata.get("goods", {})
                if isinstance(goods_data, dict):
                    for gname, ginfo in goods_data.items():
                        if isinstance(ginfo, dict):
                            goods.append(
                                {
                                    "name": str(gname),
                                    "production": ginfo.get("produced", ginfo.get("supply", 0)),
                                    "consumption": ginfo.get("consumed", ginfo.get("demand", 0)),
                                    "price": ginfo.get("price", 0),
                                }
                            )

    # Sort by production value descending
    goods.sort(key=lambda g: float(g.get("production", 0)) if isinstance(g.get("production"), (int, float)) else 0, reverse=True)
    return goods[:20]


def _extract_subject_map(gamestate: dict) -> dict:
    """Extract subject → overlord tag mapping from gamestate.
    In V3 saves, subjects have an 'overlord' field with the overlord's country id.
    Returns dict of subject_tag → overlord_tag.
    """
    countries_db = _get_countries_db(gamestate)

    # Build country_id → tag mapping
    id_to_tag = {}
    for cid, cdata in countries_db.items():
        if isinstance(cdata, dict):
            tag = str(cdata.get("definition", cdata.get("tag", str(cid))))
            id_to_tag[cid] = tag
            id_to_tag[str(cid)] = tag
            id_to_tag[int(cid) if str(cid).isdigit() else cid] = tag

    subject_map = {}  # subject_tag → overlord_tag
    for cid, cdata in countries_db.items():
        if not isinstance(cdata, dict):
            continue
        overlord = cdata.get("overlord")
        if overlord is None:
            continue
        # overlord can be a dict like { country = X } or just an id
        if isinstance(overlord, dict):
            overlord_id = overlord.get("country", overlord.get("id"))
        else:
            overlord_id = overlord
        if overlord_id is None:
            continue
        subject_tag = id_to_tag.get(cid, id_to_tag.get(str(cid), str(cid)))
        overlord_tag = id_to_tag.get(overlord_id, id_to_tag.get(str(overlord_id), str(overlord_id)))
        if subject_tag and overlord_tag and subject_tag != overlord_tag:
            subject_map[subject_tag] = overlord_tag

    return subject_map


def _extract_territory_map(gamestate: dict, player_tag: str) -> dict:
    """Extract territory data: all states grouped by owning country."""
    countries_db = _get_countries_db(gamestate)

    # Build country_id → tag/name mapping
    id_to_info = {}
    for cid, cdata in countries_db.items():
        if isinstance(cdata, dict):
            tag = str(cdata.get("definition", cdata.get("tag", str(cid))))
            id_to_info[cid] = tag
            id_to_info[str(cid)] = tag

    # Extract subject relationships
    subject_map = _extract_subject_map(gamestate)

    # Collect all states grouped by owner tag
    territories = {}  # tag → { states: [...], total_pop, total_gdp }
    sm = gamestate.get("state_manager", gamestate.get("states", {}))
    if isinstance(sm, dict):
        db = sm.get("database", sm)
        if isinstance(db, dict):
            for sid, sdata in db.items():
                if not isinstance(sdata, dict):
                    continue
                owner = sdata.get("country", sdata.get("owner"))
                tag = id_to_info.get(owner, id_to_info.get(str(owner), str(owner)))
                name = str(sdata.get("definition", sdata.get("name", str(sid))))
                pop = sdata.get("population", 0)
                gdp = sdata.get("gdp", 0)
                infra = sdata.get("infrastructure", 0)
                if not isinstance(pop, (int, float)):
                    pop = 0
                if not isinstance(gdp, (int, float)):
                    gdp = 0

                if tag not in territories:
                    territories[tag] = {
                        "tag": tag,
                        "is_player": (tag == player_tag),
                        "states": [],
                        "total_pop": 0,
                        "total_gdp": 0,
                    }
                territories[tag]["states"].append({
                    "name": name.replace("state_", "").replace("_", " ").title(),
                    "population": pop,
                    "gdp": gdp,
                    "infrastructure": infra,
                })
                territories[tag]["total_pop"] += pop
                territories[tag]["total_gdp"] += gdp

    # Sort countries by total GDP descending, states within each by population
    country_list = sorted(territories.values(), key=lambda c: -c["total_gdp"])
    for c in country_list:
        c["states"].sort(key=lambda s: -s["population"])

    return {
        "player_tag": player_tag,
        "countries": country_list,
        "subject_map": subject_map,
    }
