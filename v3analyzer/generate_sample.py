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
            ("state_home_counties", 3200330, 240024, 55),
            ("state_lancashire", 2112211, 150495, 52),
            ("state_midlands", 1920192, 129612, 49),
            ("state_yorkshire", 1728172, 110170, 46),
            ("state_west_country", 864086, 48604, 41),
            ("state_east_anglia", 800080, 43204, 39),
            ("state_wales", 704070, 34323, 35),
            ("state_lowlands", 1440144, 86408, 44),
            ("state_highlands", 352035, 11881, 24),
            ("state_leinster", 768076, 31683, 30),
            ("state_munster", 576057, 20738, 26),
            ("state_connaught", 384038, 11521, 22),
            ("state_ulster", 480048, 18001, 27),
            ("state_ceylon", 192019, 3600, 13),
            ("state_jamaica", 144014, 2376, 12),
            ("state_bahamas", 19201, 259, 9),
            ("state_bermuda", 12801, 172, 9),
            ("state_malta", 96009, 2520, 19),
            ("state_newfoundland", 48004, 540, 8),
            ("state_west_indies", 80008, 1200, 11),
            ("state_guayana", 28802, 259, 6),
            ("state_guatemala", 24002, 180, 5),
            ("state_upper_andalusia", 16001, 360, 16),
            ("state_indian_ocean_territory", 4800, 36, 5),
            ("state_south_atlantic_islands", 4800, 28, 5),
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
            ("state_ile_de_france", 4023966, 144862, 48),
            ("state_normandy", 2123752, 57341, 36),
            ("state_brittany", 1900199, 41044, 28),
            ("state_picardy", 1564870, 39434, 33),
            ("state_champagne", 1341317, 32835, 32),
            ("state_burgundy", 1453093, 37664, 34),
            ("state_alsace_lorraine", 1229540, 30984, 33),
            ("state_lorraine", 1005988, 23540, 31),
            ("state_franche_comte", 782435, 17463, 29),
            ("state_french_low_countries", 894211, 21890, 32),
            ("state_maine_anjou", 1117764, 23338, 27),
            ("state_orleans", 1229540, 27443, 29),
            ("state_poitou", 1005988, 19918, 26),
            ("state_aquitaine", 1229540, 25672, 27),
            ("state_guyenne", 894211, 17705, 26),
            ("state_languedoc", 1117764, 22534, 26),
            ("state_auvergne_limousin", 1005988, 18107, 24),
            ("state_rhone", 1453093, 37664, 34),
            ("state_provence", 1341317, 31386, 31),
            ("state_corsica", 178842, 2253, 16),
            ("state_algiers", 335329, 2414, 9),
            ("state_constantine", 223552, 1207, 7),
            ("state_oran", 178842, 965, 7),
            ("state_guayana", 33532, 120, 5),
            ("state_west_indies", 89421, 579, 8),
            ("state_senegal", 67065, 193, 5),
            ("state_ivory_coast", 44710, 96, 5),
            ("state_indian_ocean_territory", 22355, 64, 5),
            ("state_madras", 111776, 482, 5),
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
            ("state_brandenburg", 2282614, 123260, 42),
            ("state_lower_silesia", 1369565, 53248, 30),
            ("state_upper_silesia", 1141304, 40059, 27),
            ("state_rhineland", 1217391, 51276, 32),
            ("state_ruhr", 1065217, 46017, 33),
            ("state_westphalia", 1293478, 50290, 30),
            ("state_north_rhine", 1217391, 48646, 31),
            ("state_pomerania", 913043, 27117, 23),
            ("state_east_prussia", 1065217, 28760, 21),
            ("state_west_prussia", 760869, 19721, 20),
            ("state_posen", 836956, 18982, 17),
            ("state_anhalt", 456521, 14791, 25),
            ("state_brunswick", 380434, 11915, 24),
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
            ("state_austria", 3679253, 80943, 35),
            ("state_bohemia", 4528301, 74716, 26),
            ("state_moravia", 2264150, 32377, 22),
            ("state_west_galicia", 2830188, 21792, 12),
            ("state_east_galicia", 3113207, 20547, 10),
            ("state_bukovina", 849056, 4669, 8),
            ("state_lombardy", 3396226, 52301, 24),
            ("state_venetia", 2688679, 38448, 22),
            ("state_tyrol", 990566, 10896, 17),
            ("state_south_tyrol", 707547, 7471, 16),
            ("state_styria", 1273584, 14569, 18),
            ("state_slovenia", 990566, 10460, 16),
            ("state_istria", 566037, 5230, 14),
            ("state_dalmatia", 707547, 4981, 11),
            ("state_upper_silesia", 1132075, 11207, 15),
            ("state_montenegro", 283018, 1245, 7),
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
            ("state_moscow", 5220832, 78311, 30),
            ("state_ingria", 3480530, 44376, 25),
            ("state_kiev", 3045464, 18272, 12),
            ("state_kharkov", 2175331, 11420, 10),
            ("state_chernihiv", 1740265, 7831, 9),
            ("state_cherson", 1522732, 6395, 8),
            ("state_volhynia", 1957798, 8222, 8),
            ("state_crimea", 652599, 3132, 9),
            ("state_taurida", 870132, 3262, 7),
            ("state_bessarabia", 1087665, 4078, 7),
            ("state_kursk", 1740265, 7831, 9),
            ("state_oryol", 1522732, 6852, 9),
            ("state_ryazan", 1305199, 5481, 8),
            ("state_tambov", 1522732, 5710, 7),
            ("state_smolensk", 1305199, 5481, 8),
            ("state_tver", 1305199, 5481, 8),
            ("state_yaroslavl", 1087665, 4894, 9),
            ("state_novgorod", 1087665, 4078, 7),
            ("state_pskov", 870132, 2871, 6),
            ("state_nizhny_novgorod", 1522732, 7309, 9),
            ("state_kazan", 1522732, 6395, 8),
            ("state_samara", 1087665, 3589, 6),
            ("state_vyatka", 870132, 2349, 5),
            ("state_perm", 870132, 2349, 5),
            ("state_ufa", 783119, 1879, 5),
            ("state_ural", 652599, 1957, 6),
            ("state_chelyabinsk", 522079, 1409, 5),
            ("state_astrakhan", 652599, 1762, 5),
            ("state_rostov", 1087665, 4078, 7),
            ("state_kuban", 783119, 2349, 6),
            ("state_stavropol", 652599, 1762, 5),
            ("state_north_caucasus", 522079, 1174, 5),
            ("state_dagestan", 435066, 783, 5),
            ("state_greater_caucasus", 348053, 522, 5),
            ("state_armenia", 261039, 469, 5),
            ("state_azerbaijan", 348053, 626, 5),
            ("state_elizavetpol", 217533, 326, 5),
            ("state_kars", 174026, 208, 5),
            ("state_kalmykia", 217533, 261, 5),
            ("state_chuvashia", 522079, 1174, 5),
            ("state_tartaria", 652599, 1762, 5),
            ("state_arkhangelsk", 435066, 783, 5),
            ("state_east_karelia", 348053, 522, 5),
            ("state_kola", 130519, 117, 5),
            ("state_nenetsia", 87013, 65, 5),
            ("state_vilnius", 870132, 3262, 7),
            ("state_kaunas", 652599, 2153, 6),
            ("state_riga", 652599, 2740, 8),
            ("state_vitebsk", 652599, 1762, 5),
            ("state_minsk", 870132, 2349, 5),
            ("state_mogilev", 652599, 1566, 5),
            ("state_brest", 652599, 1566, 5),
            ("state_galich", 435066, 978, 5),
            ("state_greater_poland", 1087665, 4078, 7),
            ("state_lesser_poland", 870132, 2871, 6),
            ("state_mazovia", 1087665, 4078, 7),
            ("state_dobrudja", 348053, 783, 5),
            ("state_tobolsk", 261039, 313, 5),
            ("state_tomsk", 217533, 228, 5),
            ("state_akmolinsk", 174026, 156, 5),
            ("state_uralsk", 217533, 228, 5),
            ("state_surgut", 87013, 65, 5),
            ("state_ob", 130519, 97, 5),
            ("state_krasnoyarsk", 174026, 156, 5),
            ("state_upper_yeniseysk", 87013, 65, 5),
            ("state_irkutsk", 217533, 228, 5),
            ("state_trans_baikal", 130519, 97, 5),
            ("state_buryatia", 87013, 65, 5),
            ("state_yakutsk", 87013, 52, 5),
            ("state_okhotsk", 43506, 26, 5),
            ("state_kamchatka", 21753, 13, 5),
            ("state_chukotka", 13051, 5, 5),
            ("state_kolyma", 13051, 5, 5),
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
            ("state_new_york", 1610681, 67647, 35),
            ("state_pennsylvania", 1308657, 49467, 31),
            ("state_virginia", 1107325, 30229, 22),
            ("state_massachusetts", 654328, 25283, 32),
            ("state_ohio", 805327, 23676, 24),
            ("state_north_carolina", 704661, 16277, 19),
            ("state_south_carolina", 503329, 10992, 18),
            ("state_georgia", 503329, 10569, 17),
            ("state_kentucky", 553662, 12789, 19),
            ("state_tennessee", 553662, 12091, 18),
            ("state_maryland", 402663, 12176, 25),
            ("state_connecticut", 301997, 10781, 29),
            ("state_new_jersey", 352330, 11542, 27),
            ("state_maine", 352330, 8878, 21),
            ("state_new_hampshire", 221465, 6045, 22),
            ("state_vermont", 201331, 5073, 21),
            ("state_rhode_island", 100665, 3382, 28),
            ("state_delaware", 80532, 2367, 24),
            ("state_alabama", 402663, 7102, 14),
            ("state_mississippi", 301997, 4819, 13),
            ("state_louisiana", 352330, 7102, 16),
            ("state_indiana", 352330, 8138, 19),
            ("state_illinois", 251664, 6130, 20),
            ("state_missouri", 251664, 5284, 17),
            ("state_arkansas", 150998, 2219, 12),
            ("state_michigan", 150998, 3044, 16),
            ("state_district_of_columbia", 40266, 1606, 33),
            ("state_florida", 80532, 1285, 13),
            ("state_iowa", 50332, 887, 14),
            ("state_wisconsin", 50332, 845, 14),
            ("state_west_virginia", 201331, 3805, 15),
            ("state_minnesota", 20133, 253, 10),
            ("state_kansas", 10066, 105, 8),
            ("state_nebraska", 5033, 46, 7),
            ("state_colorado", 3019, 25, 7),
            ("state_north_dakota", 2013, 15, 6),
            ("state_south_dakota", 2013, 15, 6),
            ("state_montana", 1006, 6, 5),
            ("state_wyoming", 1006, 6, 5),
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
            ("state_eastern_thrace", 2344680, 42203, 22),
            ("state_hudavendigar", 2051582, 20310, 12),
            ("state_aydin", 1758499, 15826, 11),
            ("state_ankara", 1465416, 10550, 8),
            ("state_kastamonu", 1025791, 5908, 7),
            ("state_konya", 1318874, 8308, 7),
            ("state_adana", 879249, 5064, 7),
            ("state_trabzon", 879249, 4431, 6),
            ("state_erzurum", 732708, 2901, 5),
            ("state_diyarbakir", 732708, 2637, 5),
            ("state_kars", 293083, 791, 5),
            ("state_bulgaria", 1611957, 11025, 8),
            ("state_northern_thrace", 732708, 4616, 7),
            ("state_western_thrace", 439624, 2532, 7),
            ("state_eastern_serbia", 732708, 3956, 6),
            ("state_western_serbia", 732708, 3692, 6),
            ("state_bosnia", 879249, 3956, 5),
            ("state_macedonia", 879249, 4431, 6),
            ("state_albania", 586166, 2110, 5),
            ("state_thessalia", 732708, 3956, 6),
            ("state_kosovo", 439624, 1424, 5),
            ("state_montenegro", 234466, 633, 5),
            ("state_skopia", 439624, 1740, 5),
            ("state_dobrudja", 351699, 1392, 5),
            ("state_cyprus", 293083, 1318, 5),
            ("state_east_aegean_islands", 234466, 928, 5),
            ("state_baghdad", 879249, 2848, 5),
            ("state_mosul", 586166, 1582, 5),
            ("state_basra", 439624, 1186, 5),
            ("state_deir_ez_zor", 293083, 633, 5),
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
            ("state_new_castile", 1925142, 63529, 25),
            ("state_catalonia", 1283422, 35999, 21),
            ("state_old_castile", 1122994, 20382, 13),
            ("state_leon", 882352, 13976, 12),
            ("state_lower_andalusia", 1203208, 20647, 13),
            ("state_upper_andalusia", 1042780, 17205, 12),
            ("state_valencia", 1042780, 19958, 14),
            ("state_galicia", 882352, 12229, 10),
            ("state_aragon", 721925, 11911, 12),
            ("state_extremadura", 641711, 7411, 8),
            ("state_murcia", 481283, 7147, 11),
            ("state_asturias", 401069, 6352, 12),
            ("state_balearic_islands", 160427, 2117, 10),
            ("state_canary_islands", 128342, 1270, 7),
            ("state_al_rif", 80213, 317, 5),
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
            ("state_holland", 1636366, 191454, 30),
            ("state_gelre", 681818, 57436, 21),
            ("state_friesland", 545454, 39567, 18),
            ("state_guayana", 40909, 478, 5),
            ("state_gold_coast", 27272, 191, 5),
            ("state_west_indies", 68181, 1196, 5),
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
            ("state_flanders", 1942858, 122399, 25),
            ("state_wallonia", 1714285, 119999, 28),
            ("state_gelre", 342857, 15599, 18),
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
            ("state_piedmont", 3508774, 154385, 22),
            ("state_savoy", 701754, 18526, 13),
            ("state_sardinia", 526315, 6947, 6),
            ("state_provence", 263157, 5789, 11),
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
            ("state_svealand", 1377051, 78491, 22),
            ("state_gotaland", 1147540, 49057, 16),
            ("state_scania", 573770, 23547, 15),
            ("state_norrland", 344262, 6868, 7),
            ("state_gotland", 57377, 1308, 8),
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
            ("state_kanto", 7297301, 72972, 15),
            ("state_kansai", 6486486, 58378, 13),
            ("state_chubu", 4054054, 26351, 9),
            ("state_chugoku", 2837837, 15608, 8),
            ("state_kyushu", 3648648, 18972, 7),
            ("state_shikoku", 1824324, 8209, 6),
            ("state_tohoku", 3243243, 12324, 5),
            ("state_hokkaido", 324324, 486, 5),
            ("state_ryukyu_islands", 283783, 709, 5),
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
            ("state_zhili", 26605879, 79817, 12),
            ("state_beijing", 6651463, 17958, 10),
            ("state_shandong", 23945267, 35917, 6),
            ("state_jiangsu", 26605853, 43899, 6),
            ("state_nanjing", 10642341, 18517, 6),
            ("state_zhejiang", 18624097, 29053, 6),
            ("state_fujian", 13302926, 16761, 5),
            ("state_guangdong", 19954389, 26938, 5),
            ("state_sichuan", 29266438, 28095, 5),
            ("state_hunan", 15963511, 18198, 5),
            ("state_henan", 19954389, 20952, 5),
            ("state_shanxi", 10642341, 10216, 5),
            ("state_xian", 11972633, 12571, 5),
            ("state_jiangxi", 13302926, 13968, 5),
            ("state_guangxi", 7981755, 6704, 5),
            ("state_guizhou", 6651463, 4389, 5),
            ("state_yunnan", 6651463, 4389, 5),
            ("state_gansu", 5321170, 3192, 5),
            ("state_suzhou", 9312048, 15364, 6),
            ("state_shaozhou", 5321170, 4789, 5),
            ("state_eastern_hubei", 11972633, 13648, 5),
            ("state_western_hubei", 6651463, 5587, 5),
            ("state_chongqing", 7981755, 7183, 5),
            ("state_northern_anhui", 9312048, 8939, 5),
            ("state_southern_anhui", 7981755, 8380, 5),
            ("state_ningxia", 1995438, 1077, 5),
            ("state_qinghai", 1064234, 319, 5),
            ("state_formosa", 1995438, 1316, 5),
            ("state_shengjing", 3990877, 2993, 5),
            ("state_southern_manchuria", 2660585, 1596, 5),
            ("state_northern_manchuria", 1064234, 383, 5),
            ("state_outer_manchuria", 399087, 71, 5),
            ("state_amur", 266058, 39, 5),
            ("state_hinggan", 665146, 159, 5),
            ("state_urga", 532117, 95, 5),
            ("state_uliastai", 266058, 39, 5),
            ("state_altai", 266058, 39, 5),
            ("state_dzungaria", 399087, 71, 5),
            ("state_tianshan", 665146, 119, 5),
            ("state_jetisy", 399087, 59, 5),
            ("state_kirghizia", 399087, 59, 5),
            ("state_tuva", 133029, 15, 5),
            ("state_alxa", 266058, 39, 5),
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
            ("state_rio_de_janeiro", 809723, 29149, 14),
            ("state_bahia", 708502, 12753, 7),
            ("state_minas_gerais", 910931, 14757, 6),
            ("state_sao_paulo", 506072, 10020, 7),
            ("state_pernambuco", 607287, 10493, 6),
            ("state_maranhao", 253036, 2550, 5),
            ("state_ceara", 303643, 3279, 5),
            ("state_paraiba", 202429, 2040, 5),
            ("state_rio_grande_do_norte", 151821, 1366, 5),
            ("state_piaui", 121457, 874, 5),
            ("state_parana", 151821, 1639, 5),
            ("state_santa_catarina", 121457, 1224, 5),
            ("state_goias", 101214, 655, 5),
            ("state_mato_grosso", 50607, 218, 5),
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
            ("state_mexico", 1663378, 34930, 12),
            ("state_jalisco", 762376, 8805, 6),
            ("state_bajio", 831683, 9081, 6),
            ("state_veracruz", 693069, 6986, 5),
            ("state_oaxaca", 554455, 3493, 5),
            ("state_guerrero", 346534, 2037, 5),
            ("state_chiapas", 277227, 1280, 5),
            ("state_yucatan", 346534, 2037, 5),
            ("state_zacatecas", 346534, 2547, 5),
            ("state_durango", 207920, 1091, 5),
            ("state_sinaloa", 166336, 768, 5),
            ("state_sonora", 110891, 419, 5),
            ("state_chihuahua", 138613, 523, 5),
            ("state_new_mexico", 69306, 174, 5),
            ("state_texas", 207920, 654, 5),
            ("state_rio_grande", 110891, 279, 5),
            ("state_california", 69306, 174, 5),
            ("state_baja_california", 41584, 87, 5),
            ("state_arizona", 27722, 46, 5),
            ("state_colorado", 13861, 23, 5),
            ("state_nevada", 6930, 8, 5),
            ("state_utah", 6930, 8, 5),
        ],
    },
    "EGY": {
        "name": "Egypt", "type": "unrecognized", "id": 16,
        "overlord": 6,  # Subject of TUR (Ottoman Empire)
        "gdp_base": 12000, "gdp_growth": 0.00025, "pop_base": 5500000, "pop_growth": 0.00005,
        "sol_base": 7.5, "sol_improve": 0.00015, "lit_base": 0.06, "lit_improve": 0.000015,
        "rev_base": 5000, "rev_growth": 0.0002, "exp_base": 4800, "exp_growth": 0.0002,
        "prestige_base": 15, "money": 40000,
        "techs": [],
        "researching": "centralization",
        "army": 60, "navy": 10,
        "states": [
            ("state_lower_egypt", 1629639, 35851, 12),
            ("state_middle_egypt", 814814, 8066, 5),
            ("state_upper_egypt", 679012, 5228, 5),
            ("state_sinai", 67901, 224, 5),
            ("state_matruh", 40740, 107, 5),
            ("state_egyptian_desert", 27160, 47, 5),
            ("state_blue_nile", 339506, 1344, 5),
            ("state_dongola", 135802, 358, 5),
            ("state_kordofan", 162962, 358, 5),
            ("state_eritrea", 108641, 191, 5),
            ("state_syria", 407407, 2688, 5),
            ("state_lebanon", 203703, 1568, 5),
            ("state_palestine", 162962, 896, 5),
            ("state_transjordan", 67901, 179, 5),
            ("state_aleppo", 339506, 2091, 5),
            ("state_adana", 203703, 1120, 5),
            ("state_crete", 108641, 525, 5),
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
            ("state_isfahan", 914289, 15542, 10),
            ("state_fars", 800000, 8840, 6),
            ("state_tabriz", 742857, 8839, 7),
            ("state_irakajemi", 685714, 9325, 8),
            ("state_khorasan", 628571, 4274, 5),
            ("state_mazandaran", 457142, 3497, 5),
            ("state_kerman", 400000, 2380, 5),
            ("state_luristan", 342857, 1748, 5),
            ("state_persian_kurdistan", 285714, 1214, 5),
            ("state_urmia", 342857, 1748, 5),
            ("state_semnan", 171428, 815, 5),
            ("state_laristan", 228571, 854, 5),
        ],
    },
    "TUN": {
        "name": "Tunis", "type": "unrecognized", "id": 18,
        "overlord": 6,  # Subject of TUR (Ottoman Empire)
        "gdp_base": 3000, "gdp_growth": 0.00015, "pop_base": 1200000, "pop_growth": 0.00003,
        "sol_base": 6.5, "sol_improve": 0.0001, "lit_base": 0.04, "lit_improve": 0.00001,
        "rev_base": 1200, "rev_growth": 0.00015, "exp_base": 1100, "exp_growth": 0.00015,
        "prestige_base": 5, "money": 8000,
        "techs": [],
        "researching": "centralization",
        "army": 15, "navy": 5,
        "states": [
            ("state_tunis", 720000, 5400, 7),
            ("state_sousse", 360000, 1800, 5),
            ("state_djerba", 120000, 420, 5),
        ],
    },
    "TRI": {
        "name": "Tripolitania", "type": "unrecognized", "id": 19,
        "overlord": 6,  # Subject of TUR (Ottoman Empire)
        "gdp_base": 1500, "gdp_growth": 0.0001, "pop_base": 600000, "pop_growth": 0.00002,
        "sol_base": 5.5, "sol_improve": 0.00005, "lit_base": 0.03, "lit_improve": 0.000005,
        "rev_base": 600, "rev_growth": 0.0001, "exp_base": 580, "exp_growth": 0.0001,
        "prestige_base": 3, "money": 4000,
        "techs": [],
        "researching": "centralization",
        "army": 8, "navy": 3,
        "states": [
            ("state_tripolitania", 360000, 1800, 5),
            ("state_fezzan", 120000, 240, 5),
            ("state_cyrenaica", 120000, 360, 5),
        ],
    },
    "WAL": {
        "name": "Wallachia", "type": "recognized", "id": 20,
        "overlord": 6,  # Subject of TUR (Ottoman Empire)
        "gdp_base": 4000, "gdp_growth": 0.0002, "pop_base": 2500000, "pop_growth": 0.00004,
        "sol_base": 7.0, "sol_improve": 0.0001, "lit_base": 0.08, "lit_improve": 0.000015,
        "rev_base": 1600, "rev_growth": 0.0002, "exp_base": 1500, "exp_growth": 0.0002,
        "prestige_base": 8, "money": 12000,
        "techs": [],
        "researching": "centralization",
        "army": 20, "navy": 0,
        "states": [
            ("state_wallachia", 1750000, 14000, 8),
            ("state_oltenia", 750000, 4000, 6),
        ],
    },
    "MOL": {
        "name": "Moldavia", "type": "recognized", "id": 21,
        "overlord": 6,  # Subject of TUR (Ottoman Empire)
        "gdp_base": 2500, "gdp_growth": 0.00015, "pop_base": 1500000, "pop_growth": 0.00003,
        "sol_base": 6.5, "sol_improve": 0.0001, "lit_base": 0.06, "lit_improve": 0.00001,
        "rev_base": 1000, "rev_growth": 0.00015, "exp_base": 950, "exp_growth": 0.00015,
        "prestige_base": 5, "money": 8000,
        "techs": [],
        "researching": "centralization",
        "army": 12, "navy": 0,
        "states": [
            ("state_moldavia", 1050000, 6300, 7),
            ("state_southern_bessarabia", 450000, 1800, 5),
        ],
    },
    "HAN": {
        "name": "Hannover", "type": "recognized", "id": 22,
        "overlord": 0,  # Subject of GBR (personal union)
        "gdp_base": 8000, "gdp_growth": 0.0003, "pop_base": 1800000, "pop_growth": 0.00004,
        "sol_base": 9.5, "sol_improve": 0.00025, "lit_base": 0.50, "lit_improve": 0.000035,
        "rev_base": 3200, "rev_growth": 0.00025, "exp_base": 3000, "exp_growth": 0.00025,
        "prestige_base": 20, "money": 35000,
        "techs": ["enclosure", "manufacturies", "centralization"],
        "researching": "nationalism",
        "army": 25, "navy": 5,
        "states": [
            ("state_hannover", 1080000, 16200, 18),
            ("state_east_frisia", 360000, 3960, 12),
            ("state_brunswick", 360000, 4680, 14),
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
        overlord_str = ""
        if "overlord" in c:
            overlord_str = f'\n            overlord = {{ country = {c["overlord"]} }}'
        cm_entries.append(f'''        {c["id"]} = {{
            definition = "{tag}"
            country_type = "{c["type"]}"
            money = {c["money"]}
            prestige = {c["prestige_base"]}{overlord_str}
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
