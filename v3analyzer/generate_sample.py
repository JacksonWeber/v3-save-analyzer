"""Generate a realistic synthetic Victoria 3 save file for testing."""
import zipfile
import math
import os
import random

random.seed(42)


def _gdp_series(base, growth_rate, weeks, noise=0.02):
    """Generate GDP-like exponential growth with noise."""
    values = []
    val = base
    for i in range(weeks):
        val *= (1 + growth_rate + random.uniform(-noise, noise))
        values.append(round(val, 1))
    return values


def _pop_series(base, growth_rate, weeks):
    values = []
    val = base
    for i in range(weeks):
        val *= (1 + growth_rate + random.uniform(-0.0005, 0.0005))
        values.append(int(val))
    return values


def _sol_series(base, improvement, weeks):
    values = []
    val = base
    for i in range(weeks):
        val += improvement + random.uniform(-0.02, 0.02)
        values.append(round(val, 2))
    return values


def _literacy_series(base, improvement, weeks):
    values = []
    val = base
    for i in range(weeks):
        val = min(1.0, val + improvement + random.uniform(-0.001, 0.001))
        values.append(round(val, 4))
    return values


def _budget_series(base, growth, weeks, noise=0.03):
    values = []
    val = base
    for i in range(weeks):
        val *= (1 + growth + random.uniform(-noise, noise))
        values.append(round(val, 1))
    return values


def _prestige_series(base, weeks):
    values = []
    val = base
    for i in range(weeks):
        val += random.uniform(0.5, 3.0)
        values.append(round(val, 1))
    return values


def _fmt_array(values):
    """Format a list of values as PDX array string."""
    lines = []
    for i in range(0, len(values), 8):
        chunk = values[i:i+8]
        lines.append("                " + " ".join(str(v) for v in chunk))
    return "\n".join(lines)


WEEKS = 260  # ~5 years of weekly data (1836-1841)

COUNTRIES = {
    "GBR": {
        "name": "Great Britain", "type": "recognized", "id": 0,
        "gdp_base": 120000, "gdp_growth": 0.008, "pop_base": 16000000, "pop_growth": 0.001,
        "sol_base": 11.5, "sol_improve": 0.008, "lit_base": 0.45, "lit_improve": 0.0008,
        "rev_base": 45000, "rev_growth": 0.007, "exp_base": 40000, "exp_growth": 0.006,
        "prestige_base": 200, "money": 850000,
        "techs": ["enclosure", "manufacturies", "railways", "steel_working", "nationalism",
                   "empiricism", "centralization", "democracy", "urbanization",
                   "international_trade", "stock_exchange", "central_banking",
                   "mutual_funds", "electrical_generation", "telephone",
                   "bessemer_process", "rotary_valve_engine", "cotton_gin",
                   "mechanical_tools", "atmospheric_engine"],
        "researching": "radio",
        "army": 180, "navy": 120,
        "states": [
            ("state_home_counties", 4200000, 280000, 55),
            ("state_midlands", 3100000, 195000, 42),
            ("state_lancashire", 2900000, 185000, 40),
            ("state_yorkshire", 2400000, 160000, 35),
            ("state_wales", 1300000, 72000, 22),
            ("state_lowlands", 1800000, 110000, 30),
            ("state_highlands", 600000, 25000, 10),
            ("state_east_anglia", 900000, 55000, 18),
            ("state_west_country", 800000, 48000, 16),
            ("state_ulster", 700000, 32000, 12),
        ],
    },
    "FRA": {
        "name": "France", "type": "recognized", "id": 1,
        "gdp_base": 100000, "gdp_growth": 0.006, "pop_base": 28000000, "pop_growth": 0.0005,
        "sol_base": 10.8, "sol_improve": 0.006, "lit_base": 0.38, "lit_improve": 0.0007,
        "rev_base": 38000, "rev_growth": 0.006, "exp_base": 36000, "exp_growth": 0.005,
        "prestige_base": 180, "money": 620000,
        "techs": ["enclosure", "manufacturies", "railways", "nationalism", "centralization",
                   "urbanization", "international_trade", "stock_exchange",
                   "atmospheric_engine", "cotton_gin"],
        "researching": "steel_working",
        "army": 250, "navy": 80,
        "states": [
            ("state_ile_de_france", 3800000, 240000, 48),
            ("state_provence", 2200000, 120000, 28),
            ("state_burgundy", 1900000, 100000, 25),
            ("state_normandy", 1600000, 85000, 22),
        ],
    },
    "PRU": {
        "name": "Prussia", "type": "recognized", "id": 2,
        "gdp_base": 75000, "gdp_growth": 0.009, "pop_base": 14000000, "pop_growth": 0.0012,
        "sol_base": 10.0, "sol_improve": 0.007, "lit_base": 0.55, "lit_improve": 0.0009,
        "rev_base": 30000, "rev_growth": 0.008, "exp_base": 28000, "exp_growth": 0.007,
        "prestige_base": 150, "money": 420000,
        "techs": ["enclosure", "manufacturies", "nationalism", "centralization",
                   "empiricism", "urbanization", "atmospheric_engine"],
        "researching": "railways",
        "army": 200, "navy": 40,
        "states": [
            ("state_brandenburg", 2800000, 150000, 35),
            ("state_silesia", 2200000, 110000, 28),
            ("state_rhineland", 2000000, 105000, 26),
        ],
    },
}


def generate_save(path):
    """Generate a synthetic V3 save file."""
    meta = f'''date = "1841.3.15"
player = "GBR"
save_game_version = 3
playthrough_id = "synthetic_test_001"
'''

    # Build country_manager
    cm_entries = []
    for tag, c in COUNTRIES.items():
        techs_str = "\n".join(f'                    "{t}"' for t in c["techs"])
        cm_entries.append(f'''        {c["id"]} = {{
            definition = "{tag}"
            country_type = "{c["type"]}"
            money = {c["money"]}
            prestige = {c["prestige_base"]}
            technology = {{
                acquired_technologies = {{
{techs_str}
                }}
                researching = "{c["researching"]}"
            }}
            budget = {{
                revenue = {c["rev_base"]}
                expense = {c["exp_base"]}
            }}
            military = {{
                army_size = {c["army"]}
                navy_size = {c["navy"]}
            }}
        }}''')

    # Build country_history
    ch_entries = []
    for tag, c in COUNTRIES.items():
        gdp = _gdp_series(c["gdp_base"], c["gdp_growth"], WEEKS)
        pop = _pop_series(c["pop_base"], c["pop_growth"], WEEKS)
        sol = _sol_series(c["sol_base"], c["sol_improve"], WEEKS)
        lit = _literacy_series(c["lit_base"], c["lit_improve"], WEEKS)
        rev = _budget_series(c["rev_base"], c["rev_growth"], WEEKS)
        exp = _budget_series(c["exp_base"], c["exp_growth"], WEEKS)
        pres = _prestige_series(c["prestige_base"], WEEKS)

        ch_entries.append(f'''        {c["id"]} = {{
            weekly_gdp = {{
{_fmt_array(gdp)}
            }}
            weekly_population = {{
{_fmt_array(pop)}
            }}
            weekly_sol = {{
{_fmt_array(sol)}
            }}
            weekly_literacy = {{
{_fmt_array(lit)}
            }}
            weekly_revenue = {{
{_fmt_array(rev)}
            }}
            weekly_expense = {{
{_fmt_array(exp)}
            }}
            weekly_prestige = {{
{_fmt_array(pres)}
            }}
        }}''')

    # Build state_manager
    state_entries = []
    state_id = 0
    for tag, c in COUNTRIES.items():
        for sname, spop, sgdp, sinfra in c["states"]:
            state_entries.append(f'''        {state_id} = {{
            definition = "{sname}"
            country = {c["id"]}
            population = {spop}
            gdp = {sgdp}
            infrastructure = {sinfra}
        }}''')
            state_id += 1

    # Build market_manager with goods
    goods_data = {
        "grain": (85000, 78000, 20),
        "iron": (52000, 55000, 40),
        "coal": (95000, 88000, 30),
        "fabric": (48000, 45000, 25),
        "tools": (35000, 38000, 45),
        "steel": (28000, 30000, 50),
        "arms": (22000, 20000, 55),
        "tea": (15000, 18000, 35),
        "opium": (8000, 12000, 60),
        "wine": (12000, 11000, 28),
        "wood": (65000, 60000, 15),
        "rubber": (5000, 7000, 48),
        "oil": (3000, 4000, 42),
        "sugar": (18000, 17000, 22),
        "tobacco": (10000, 9500, 30),
    }
    goods_entries = []
    for gname, (prod, cons, price) in goods_data.items():
        goods_entries.append(f'''                {gname} = {{
                    produced = {prod}
                    consumed = {cons}
                    price = {price}
                }}''')

    gamestate = f'''date = "1841.3.15"
player_manager = {{
    database = {{
        0 = {{
            country = 0
            is_player = yes
        }}
    }}
}}
country_manager = {{
    database = {{
{chr(10).join(cm_entries)}
    }}
}}
country_history = {{
    database = {{
{chr(10).join(ch_entries)}
    }}
}}
state_manager = {{
    database = {{
{chr(10).join(state_entries)}
    }}
}}
market_manager = {{
    database = {{
        0 = {{
            goods = {{
{chr(10).join(goods_entries)}
            }}
        }}
    }}
}}
'''

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("meta", meta)
        zf.writestr("gamestate", gamestate)

    return path


if __name__ == "__main__":
    import sys
    dest = sys.argv[1] if len(sys.argv) > 1 else "sample_save.v3"
    generate_save(dest)
    size_kb = os.path.getsize(dest) / 1024
    print(f"Generated: {dest} ({size_kb:.1f} KB)")
