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
    }

    if compare_countries:
        result["comparison"] = _extract_all_countries(
            gamestate, player_id
        )

    return result


def _extract_all_countries(gamestate: dict, player_id: int) -> list:
    """Extract timeseries for all countries that have history data."""
    countries_db = _get_countries_db(gamestate)
    country_history = gamestate.get("country_history", {})
    if isinstance(country_history, dict) and "database" in country_history:
        country_history = country_history["database"]

    countries = []
    if not isinstance(country_history, dict):
        return countries

    for cid_key, history in country_history.items():
        if not isinstance(history, dict):
            continue
        ts = _extract_timeseries(history)
        if not ts or "gdp" not in ts:
            continue

        country_data = countries_db.get(cid_key, {})
        tag = str(country_data.get("definition", cid_key))
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
    """Get the country_history entry for the player."""
    ch = gamestate.get("country_history", {})
    if isinstance(ch, dict) and "database" in ch:
        ch = ch["database"]
    if isinstance(ch, dict) and country_id is not None:
        return ch.get(country_id, ch.get(str(country_id), {}))
    return {}


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
