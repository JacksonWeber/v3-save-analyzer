"""
HTML dashboard generator.
Takes extracted data and produces a self-contained HTML file.
"""
import json
import os
from jinja2 import Environment, FileSystemLoader


TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


def generate_dashboard(data: dict, output_path: str):
    """Generate an HTML dashboard from extracted save data."""
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)
    template = env.get_template("dashboard.html")

    cards = _build_cards(data)
    charts = _build_charts(data.get("timeseries", {}))

    comparison = data.get("comparison", [])
    comparison_charts = []
    if comparison:
        comparison_charts = _build_comparison_charts(comparison)

    charts_json = json.dumps(charts)
    comparison_charts_json = json.dumps(comparison_charts)

    states = _format_states(data.get("states", []))
    technology = data.get("technology", {"acquired": [], "researching": ""})
    goods = data.get("goods", [])

    html = template.render(
        meta=data.get("meta", {}),
        cards=cards,
        charts=charts,
        charts_json=charts_json,
        comparison_charts=comparison_charts,
        comparison_charts_json=comparison_charts_json,
        states=states,
        technology=technology,
        goods=goods,
    )

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path


def _build_cards(data: dict) -> list:
    """Build summary card data."""
    cards = []
    meta = data.get("meta", {})
    snapshot = data.get("snapshot", {})
    timeseries = data.get("timeseries", {})

    # Country tag
    if meta.get("player_tag"):
        cards.append({"label": "Country Tag", "value": meta["player_tag"]})

    # Current GDP (last value in timeseries)
    if "gdp" in timeseries and timeseries["gdp"]:
        gdp = timeseries["gdp"][-1]
        cards.append({"label": "GDP", "value": _fmt_number(gdp)})

    # GDP per capita
    if "gdp_per_capita" in timeseries and timeseries["gdp_per_capita"]:
        gdppc = timeseries["gdp_per_capita"][-1]
        cards.append({"label": "GDP/Capita", "value": _fmt_number(gdppc)})

    # Population
    if "population" in timeseries and timeseries["population"]:
        pop = timeseries["population"][-1]
        cards.append({"label": "Population", "value": _fmt_number(pop)})
    elif "population" in snapshot:
        cards.append({"label": "Population", "value": _fmt_number(snapshot["population"])})

    # Standard of Living
    if "standard_of_living" in timeseries and timeseries["standard_of_living"]:
        sol = timeseries["standard_of_living"][-1]
        cards.append({"label": "Std. of Living", "value": f"{sol:.1f}"})

    # Literacy
    if "literacy" in timeseries and timeseries["literacy"]:
        lit = timeseries["literacy"][-1]
        if lit <= 1:
            cards.append({"label": "Literacy", "value": f"{lit*100:.1f}%"})
        else:
            cards.append({"label": "Literacy", "value": f"{lit:.1f}%"})

    # Prestige
    if "prestige" in timeseries and timeseries["prestige"]:
        cards.append({"label": "Prestige", "value": _fmt_number(timeseries["prestige"][-1])})
    elif "prestige" in snapshot:
        cards.append({"label": "Prestige", "value": _fmt_number(snapshot["prestige"])})

    # Treasury
    if "treasury" in timeseries and timeseries["treasury"]:
        cards.append({"label": "Treasury", "value": _fmt_number(timeseries["treasury"][-1])})
    elif "money" in snapshot:
        cards.append({"label": "Treasury", "value": _fmt_number(snapshot["money"])})

    # Tech count
    tech = data.get("technology", {})
    if tech.get("acquired"):
        cards.append({"label": "Technologies", "value": str(len(tech["acquired"]))})
    elif "tech_count" in snapshot:
        cards.append({"label": "Technologies", "value": str(snapshot["tech_count"])})

    # Revenue / Expenditure from snapshot
    if "revenue" in snapshot:
        cards.append({"label": "Revenue", "value": _fmt_number(snapshot["revenue"])})
    if "expenditure" in snapshot:
        cards.append({"label": "Expenditure", "value": _fmt_number(snapshot["expenditure"])})

    # If no timeseries data, use snapshot values to populate cards
    if not cards:
        for k, v in snapshot.items():
            cards.append({"label": k.replace("_", " ").title(), "value": _fmt_number(v) if isinstance(v, (int, float)) else str(v)})

    return cards


def _build_charts(timeseries: dict) -> list:
    """Build chart configurations for the frontend."""
    charts = []

    chart_defs = [
        {
            "key": "gdp",
            "title": "GDP Over Time",
            "label": "GDP",
            "fill": True,
        },
        {
            "key": "gdp_growth_rate",
            "title": "GDP Growth Rate (%)",
            "label": "Growth %",
            "fill": False,
        },
        {
            "key": "gdp_per_capita",
            "title": "GDP Per Capita",
            "label": "GDP/Cap",
            "fill": True,
        },
        {
            "key": "population",
            "title": "Population Over Time",
            "label": "Population",
            "fill": True,
        },
        {
            "key": "standard_of_living",
            "title": "Standard of Living",
            "label": "SoL",
            "fill": False,
        },
        {
            "key": "literacy",
            "title": "Literacy Rate",
            "label": "Literacy",
            "fill": False,
        },
        {
            "key": "prestige",
            "title": "Prestige Over Time",
            "label": "Prestige",
            "fill": True,
        },
    ]

    # Budget chart (revenue + expenditure on same chart)
    if "revenue" in timeseries and "expenditure" in timeseries:
        rev = timeseries["revenue"]
        exp = timeseries["expenditure"]
        max_len = max(len(rev), len(exp))
        labels = [f"W{i+1}" for i in range(max_len)]
        charts.append({
            "title": "Budget: Revenue vs Expenditure",
            "labels": labels,
            "datasets": [
                {"label": "Revenue", "data": rev, "fill": False},
                {"label": "Expenditure", "data": exp, "fill": False},
            ],
        })

    for cdef in chart_defs:
        if cdef["key"] in timeseries and len(timeseries[cdef["key"]]) > 1:
            data = timeseries[cdef["key"]]
            labels = [f"W{i+1}" for i in range(len(data))]
            charts.append({
                "title": cdef["title"],
                "labels": labels,
                "datasets": [
                    {"label": cdef["label"], "data": data, "fill": cdef["fill"]}
                ],
            })

    return charts


def _build_comparison_charts(countries: list) -> list:
    """Build multi-country comparison charts."""
    metrics = [
        ("gdp", "GDP Comparison"),
        ("gdp_growth_rate", "GDP Growth Rate (%) Comparison"),
        ("gdp_per_capita", "GDP Per Capita Comparison"),
        ("population", "Population Comparison"),
        ("standard_of_living", "Standard of Living Comparison"),
        ("literacy", "Literacy Rate Comparison"),
        ("prestige", "Prestige Comparison"),
        ("revenue", "Revenue Comparison"),
        ("expenditure", "Expenditure Comparison"),
    ]

    charts = []
    for metric_key, title in metrics:
        datasets = []
        max_len = 0

        for country in countries:
            ts = country.get("timeseries", {})
            if metric_key not in ts or len(ts[metric_key]) < 2:
                continue

            data = ts[metric_key]
            tag = country.get("tag", "?")
            label = tag
            if country.get("is_player"):
                label += " ★"

            datasets.append({
                "label": label,
                "data": data,
                "fill": False,
                "is_player": country.get("is_player", False),
            })
            max_len = max(max_len, len(data))

        if datasets:
            labels = [f"W{i+1}" for i in range(max_len)]
            charts.append({
                "title": title,
                "labels": labels,
                "datasets": datasets,
            })

    return charts


def _format_states(states: list) -> list:
    """Format state data for display."""
    for s in states:
        s["population_fmt"] = _fmt_number(s.get("population", 0))
        s["gdp_fmt"] = _fmt_number(s.get("gdp", 0))
    # Sort by population descending
    states.sort(key=lambda s: s.get("population", 0), reverse=True)
    return states


def _fmt_number(n) -> str:
    """Format a number for display."""
    if not isinstance(n, (int, float)):
        return str(n)
    if abs(n) >= 1_000_000_000:
        return f"{n/1_000_000_000:.2f}B"
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if abs(n) >= 1_000:
        return f"{n/1_000:.1f}K"
    if isinstance(n, float):
        return f"{n:.1f}"
    return str(n)
