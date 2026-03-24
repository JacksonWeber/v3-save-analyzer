"""Generate a realistic synthetic Victoria 3 save file for testing."""
import zipfile
import math
import os
import random

random.seed(42)


def _gdp_series(base, growth_rate, weeks, noise=0.001):
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
        val *= (1 + growth_rate + random.uniform(-0.000025, 0.000025))
        values.append(int(val))
    return values


def _sol_series(base, improvement, weeks):
    values = []
    val = base
    for i in range(weeks):
        val += improvement + random.uniform(-0.001, 0.001)
        values.append(round(val, 2))
    return values


def _literacy_series(base, improvement, weeks):
    values = []
    val = base
    for i in range(weeks):
        val = min(1.0, val + improvement + random.uniform(-0.00005, 0.00005))
        values.append(round(val, 4))
    return values


def _budget_series(base, growth, weeks, noise=0.0015):
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
        val += random.uniform(0.025, 0.15)
        values.append(round(val, 1))
    return values


def _fmt_array(values):
    """Format a list of values as PDX array string."""
    lines = []
    for i in range(0, len(values), 8):
        chunk = values[i:i+8]
        lines.append("                " + " ".join(str(v) for v in chunk))
    return "\n".join(lines)


WEEKS = 5200  # ~100 years of weekly data (1836-1936)

COUNTRIES = {
    "GBR": {
        "name": "Great Britain", "type": "recognized", "id": 0,
        "gdp_base": 120000, "gdp_growth": 0.0004, "pop_base": 16000000, "pop_growth": 0.00005,
        "sol_base": 11.5, "sol_improve": 0.0004, "lit_base": 0.45, "lit_improve": 0.00004,
        "rev_base": 45000, "rev_growth": 0.00035, "exp_base": 40000, "exp_growth": 0.0003,
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
        "gdp_base": 100000, "gdp_growth": 0.0003, "pop_base": 28000000, "pop_growth": 0.000025,
        "sol_base": 10.8, "sol_improve": 0.0003, "lit_base": 0.38, "lit_improve": 0.000035,
        "rev_base": 38000, "rev_growth": 0.0003, "exp_base": 36000, "exp_growth": 0.00025,
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
        "gdp_base": 75000, "gdp_growth": 0.00045, "pop_base": 14000000, "pop_growth": 0.00006,
        "sol_base": 10.0, "sol_improve": 0.00035, "lit_base": 0.55, "lit_improve": 0.000045,
        "rev_base": 30000, "rev_growth": 0.0004, "exp_base": 28000, "exp_growth": 0.00035,
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
    "AUS": {
        "name": "Austria", "type": "recognized", "id": 3,
        "gdp_base": 65000, "gdp_growth": 0.00025, "pop_base": 30000000, "pop_growth": 0.00004,
        "sol_base": 9.5, "sol_improve": 0.0002, "lit_base": 0.25, "lit_improve": 0.000025,
        "rev_base": 28000, "rev_growth": 0.00025, "exp_base": 27000, "exp_growth": 0.00025,
        "prestige_base": 160, "money": 380000,
        "techs": ["enclosure", "manufacturies", "nationalism", "centralization",
                   "atmospheric_engine"],
        "researching": "railways",
        "army": 280, "navy": 30,
        "states": [
            ("state_austria", 2400000, 130000, 30),
            ("state_bohemia", 3200000, 140000, 32),
            ("state_hungary", 4500000, 100000, 20),
            ("state_galicia", 2800000, 50000, 12),
        ],
    },
    "RUS": {
        "name": "Russia", "type": "recognized", "id": 4,
        "gdp_base": 90000, "gdp_growth": 0.0002, "pop_base": 60000000, "pop_growth": 0.000075,
        "sol_base": 7.5, "sol_improve": 0.00015, "lit_base": 0.12, "lit_improve": 0.000015,
        "rev_base": 35000, "rev_growth": 0.0002, "exp_base": 34000, "exp_growth": 0.0002,
        "prestige_base": 170, "money": 500000,
        "techs": ["enclosure", "manufacturies", "centralization"],
        "researching": "nationalism",
        "army": 450, "navy": 50,
        "states": [
            ("state_moscow", 2500000, 110000, 25),
            ("state_saint_petersburg", 1800000, 95000, 28),
            ("state_ukraine", 5500000, 80000, 15),
            ("state_siberia", 3000000, 30000, 5),
        ],
    },
    "USA": {
        "name": "United States", "type": "recognized", "id": 5,
        "gdp_base": 55000, "gdp_growth": 0.0006, "pop_base": 13000000, "pop_growth": 0.0001,
        "sol_base": 12.0, "sol_improve": 0.00045, "lit_base": 0.60, "lit_improve": 0.00005,
        "rev_base": 20000, "rev_growth": 0.0005, "exp_base": 18000, "exp_growth": 0.00045,
        "prestige_base": 80, "money": 250000,
        "techs": ["enclosure", "manufacturies", "democracy", "centralization",
                   "cotton_gin", "atmospheric_engine", "empiricism"],
        "researching": "railways",
        "army": 40, "navy": 25,
        "states": [
            ("state_new_york", 2200000, 100000, 30),
            ("state_pennsylvania", 1800000, 85000, 25),
            ("state_virginia", 1500000, 60000, 18),
            ("state_massachusetts", 900000, 55000, 22),
        ],
    },
    "TUR": {
        "name": "Ottoman Empire", "type": "recognized", "id": 6,
        "gdp_base": 45000, "gdp_growth": 0.00015, "pop_base": 25000000, "pop_growth": 0.00005,
        "sol_base": 8.0, "sol_improve": 0.0001, "lit_base": 0.08, "lit_improve": 0.000015,
        "rev_base": 18000, "rev_growth": 0.00015, "exp_base": 19000, "exp_growth": 0.0002,
        "prestige_base": 100, "money": 180000,
        "techs": ["centralization"],
        "researching": "enclosure",
        "army": 200, "navy": 35,
        "states": [
            ("state_constantinople", 1200000, 65000, 18),
            ("state_anatolia", 4500000, 55000, 10),
            ("state_mesopotamia", 2000000, 25000, 6),
        ],
    },
    "SPA": {
        "name": "Spain", "type": "recognized", "id": 7,
        "gdp_base": 40000, "gdp_growth": 0.0002, "pop_base": 12000000, "pop_growth": 0.00003,
        "sol_base": 9.0, "sol_improve": 0.0002, "lit_base": 0.20, "lit_improve": 0.000025,
        "rev_base": 15000, "rev_growth": 0.0002, "exp_base": 16000, "exp_growth": 0.00025,
        "prestige_base": 90, "money": 140000,
        "techs": ["enclosure", "manufacturies", "centralization"],
        "researching": "nationalism",
        "army": 120, "navy": 45,
        "states": [
            ("state_castile", 3000000, 60000, 15),
            ("state_catalonia", 1800000, 55000, 18),
            ("state_andalusia", 2500000, 40000, 12),
        ],
    },
    "NET": {
        "name": "Netherlands", "type": "recognized", "id": 8,
        "gdp_base": 35000, "gdp_growth": 0.00035, "pop_base": 3000000, "pop_growth": 0.00005,
        "sol_base": 11.0, "sol_improve": 0.00035, "lit_base": 0.55, "lit_improve": 0.00004,
        "rev_base": 14000, "rev_growth": 0.0003, "exp_base": 12000, "exp_growth": 0.00025,
        "prestige_base": 70, "money": 200000,
        "techs": ["enclosure", "manufacturies", "international_trade", "stock_exchange",
                   "centralization", "urbanization"],
        "researching": "railways",
        "army": 40, "navy": 50,
        "states": [
            ("state_holland", 1800000, 80000, 25),
            ("state_flanders", 1200000, 45000, 18),
        ],
    },
    "BEL": {
        "name": "Belgium", "type": "recognized", "id": 9,
        "gdp_base": 28000, "gdp_growth": 0.00045, "pop_base": 4000000, "pop_growth": 0.00004,
        "sol_base": 10.5, "sol_improve": 0.0003, "lit_base": 0.48, "lit_improve": 0.000035,
        "rev_base": 11000, "rev_growth": 0.00035, "exp_base": 10000, "exp_growth": 0.0003,
        "prestige_base": 40, "money": 120000,
        "techs": ["enclosure", "manufacturies", "railways", "centralization",
                   "urbanization", "atmospheric_engine"],
        "researching": "steel_working",
        "army": 50, "navy": 10,
        "states": [
            ("state_wallonia", 2000000, 65000, 22),
            ("state_brabant", 1500000, 55000, 20),
        ],
    },
    "SAR": {
        "name": "Sardinia-Piedmont", "type": "recognized", "id": 10,
        "gdp_base": 22000, "gdp_growth": 0.00035, "pop_base": 5000000, "pop_growth": 0.000035,
        "sol_base": 9.2, "sol_improve": 0.00025, "lit_base": 0.28, "lit_improve": 0.00003,
        "rev_base": 9000, "rev_growth": 0.0003, "exp_base": 8500, "exp_growth": 0.0003,
        "prestige_base": 50, "money": 95000,
        "techs": ["enclosure", "manufacturies", "centralization", "nationalism"],
        "researching": "railways",
        "army": 60, "navy": 20,
        "states": [
            ("state_piedmont", 2500000, 48000, 16),
            ("state_sardinia", 500000, 12000, 6),
        ],
    },
    "SWE": {
        "name": "Sweden", "type": "recognized", "id": 11,
        "gdp_base": 20000, "gdp_growth": 0.0003, "pop_base": 3500000, "pop_growth": 0.00004,
        "sol_base": 10.0, "sol_improve": 0.00025, "lit_base": 0.65, "lit_improve": 0.00003,
        "rev_base": 8000, "rev_growth": 0.00025, "exp_base": 7500, "exp_growth": 0.00025,
        "prestige_base": 45, "money": 110000,
        "techs": ["enclosure", "manufacturies", "centralization", "empiricism"],
        "researching": "nationalism",
        "army": 45, "navy": 25,
        "states": [
            ("state_svealand", 1800000, 40000, 14),
            ("state_gotaland", 1200000, 30000, 12),
        ],
    },
    "JAP": {
        "name": "Japan", "type": "unrecognized", "id": 12,
        "gdp_base": 30000, "gdp_growth": 0.00025, "pop_base": 30000000, "pop_growth": 0.00004,
        "sol_base": 8.5, "sol_improve": 0.00015, "lit_base": 0.35, "lit_improve": 0.000025,
        "rev_base": 12000, "rev_growth": 0.0002, "exp_base": 11000, "exp_growth": 0.0002,
        "prestige_base": 30, "money": 160000,
        "techs": ["centralization"],
        "researching": "enclosure",
        "army": 100, "navy": 15,
        "states": [
            ("state_kanto", 4000000, 50000, 12),
            ("state_kansai", 3500000, 45000, 11),
            ("state_kyushu", 2500000, 25000, 8),
        ],
    },
    "QNG": {
        "name": "Qing China", "type": "unrecognized", "id": 13,
        "gdp_base": 110000, "gdp_growth": 0.0001, "pop_base": 350000000, "pop_growth": 0.000025,
        "sol_base": 7.0, "sol_improve": 0.00005, "lit_base": 0.08, "lit_improve": 0.00001,
        "rev_base": 40000, "rev_growth": 0.0001, "exp_base": 42000, "exp_growth": 0.00015,
        "prestige_base": 120, "money": 300000,
        "techs": [],
        "researching": "centralization",
        "army": 350, "navy": 20,
        "states": [
            ("state_zhili", 25000000, 60000, 10),
            ("state_jiangsu", 30000000, 55000, 9),
            ("state_guangdong", 20000000, 45000, 8),
            ("state_sichuan", 35000000, 35000, 6),
        ],
    },
    "BRZ": {
        "name": "Brazil", "type": "recognized", "id": 14,
        "gdp_base": 18000, "gdp_growth": 0.0003, "pop_base": 5000000, "pop_growth": 0.000075,
        "sol_base": 8.5, "sol_improve": 0.00015, "lit_base": 0.12, "lit_improve": 0.00002,
        "rev_base": 7000, "rev_growth": 0.00025, "exp_base": 6500, "exp_growth": 0.00025,
        "prestige_base": 25, "money": 75000,
        "techs": ["enclosure", "centralization"],
        "researching": "manufacturies",
        "army": 30, "navy": 15,
        "states": [
            ("state_rio_de_janeiro", 800000, 25000, 10),
            ("state_bahia", 1200000, 18000, 7),
            ("state_minas_gerais", 1500000, 15000, 6),
        ],
    },
    "MEX": {
        "name": "Mexico", "type": "recognized", "id": 15,
        "gdp_base": 15000, "gdp_growth": 0.0002, "pop_base": 7000000, "pop_growth": 0.00006,
        "sol_base": 8.0, "sol_improve": 0.0001, "lit_base": 0.10, "lit_improve": 0.000015,
        "rev_base": 6000, "rev_growth": 0.00015, "exp_base": 6500, "exp_growth": 0.0002,
        "prestige_base": 20, "money": 55000,
        "techs": ["centralization"],
        "researching": "enclosure",
        "army": 35, "navy": 8,
        "states": [
            ("state_mexico_valley", 1500000, 22000, 8),
            ("state_jalisco", 800000, 10000, 5),
        ],
    },
    "EGY": {
        "name": "Egypt", "type": "unrecognized", "id": 16,
        "gdp_base": 12000, "gdp_growth": 0.00025, "pop_base": 5500000, "pop_growth": 0.00005,
        "sol_base": 7.5, "sol_improve": 0.00015, "lit_base": 0.06, "lit_improve": 0.000015,
        "rev_base": 5000, "rev_growth": 0.0002, "exp_base": 4800, "exp_growth": 0.0002,
        "prestige_base": 15, "money": 40000,
        "techs": [],
        "researching": "centralization",
        "army": 60, "navy": 10,
        "states": [
            ("state_lower_egypt", 3000000, 20000, 8),
            ("state_upper_egypt", 2500000, 12000, 5),
        ],
    },
    "PER": {
        "name": "Persia", "type": "unrecognized", "id": 17,
        "gdp_base": 10000, "gdp_growth": 0.00015, "pop_base": 6000000, "pop_growth": 0.00004,
        "sol_base": 7.0, "sol_improve": 0.0001, "lit_base": 0.05, "lit_improve": 0.00001,
        "rev_base": 4000, "rev_growth": 0.00015, "exp_base": 3800, "exp_growth": 0.00015,
        "prestige_base": 10, "money": 30000,
        "techs": [],
        "researching": "centralization",
        "army": 50, "navy": 5,
        "states": [
            ("state_tehran", 1500000, 15000, 6),
            ("state_isfahan", 1200000, 10000, 5),
        ],
    },
}


def generate_save(path):
    """Generate a synthetic V3 save file."""
    meta = f'''date = "1936.1.1"
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

    gamestate = f'''date = "1936.1.1"
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
