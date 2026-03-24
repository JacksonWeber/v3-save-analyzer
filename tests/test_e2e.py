"""End-to-end test: generate a synthetic save, parse it, produce HTML."""
import os
import sys
import tempfile
import zipfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from v3analyzer.loader import load_save
from v3analyzer.parser import parse_pdx
from v3analyzer.extractor import extract_all
from v3analyzer.generator import generate_dashboard

SYNTHETIC_META = """
date = "1870.6.15"
player = "GBR"
save_game_version = 3
"""

SYNTHETIC_GAMESTATE = """
date = "1870.6.15"
player_manager = {
    database = {
        0 = {
            country = 0
            is_player = yes
        }
    }
}
country_manager = {
    database = {
        0 = {
            definition = "GBR"
            country_type = "recognized"
            money = 523456.78
            prestige = 340
            technology = {
                acquired_technologies = {
                    "enclosure"
                    "railways"
                    "steel_working"
                    "nationalism"
                    "empiricism"
                    "centralization"
                    "democracy"
                    "urbanization"
                    "international_trade"
                    "stock_exchange"
                    "central_banking"
                    "mutual_funds"
                    "electrical_generation"
                }
                researching = "telephone"
            }
            budget = {
                revenue = 85000
                expense = 72000
            }
            military = {
                army_size = 150
                navy_size = 85
            }
        }
        1 = {
            definition = "FRA"
            country_type = "recognized"
            money = 412000.00
            prestige = 290
        }
        2 = {
            definition = "PRU"
            country_type = "recognized"
            money = 380000.00
            prestige = 310
        }
    }
}
country_history = {
    database = {
        0 = {
            weekly_gdp = {
                50000 52000 54500 57200 60000 63000 66150 69457
                72930 76576 80405 84425 88646 93078 97732 102618
                107749 113136 118793 124732 130969 137517 144393 151612
                159193 167152 175510 184285 193499 203174 213333 224000
                235200 247000 259350 272317 285933 300229 315241 331003
                347553 364931 383177 402336 422453 443576 465755 489042
                513494 539169 566127 594434 624155 655363 688131 722537
            }
            weekly_population = {
                15000000 15050000 15100000 15150000 15200000 15260000 15320000 15380000
                15450000 15520000 15590000 15670000 15750000 15830000 15920000 16010000
                16100000 16200000 16300000 16400000 16510000 16620000 16730000 16850000
                16970000 17090000 17220000 17350000 17480000 17620000 17760000 17900000
                18050000 18200000 18360000 18520000 18680000 18850000 19020000 19200000
                19380000 19560000 19750000 19940000 20140000 20340000 20550000 20760000
                20970000 21190000 21410000 21640000 21870000 22100000 22340000 22580000
            }
            weekly_sol = {
                10.2 10.3 10.3 10.4 10.5 10.5 10.6 10.7
                10.8 10.9 11.0 11.1 11.2 11.3 11.4 11.5
                11.6 11.7 11.8 11.9 12.0 12.1 12.2 12.3
                12.4 12.5 12.6 12.7 12.8 12.9 13.0 13.1
                13.2 13.3 13.4 13.5 13.6 13.7 13.8 13.9
                14.0 14.1 14.2 14.3 14.4 14.5 14.6 14.7
                14.8 14.9 15.0 15.1 15.2 15.3 15.4 15.5
            }
            weekly_literacy = {
                0.42 0.43 0.43 0.44 0.44 0.45 0.45 0.46
                0.46 0.47 0.47 0.48 0.49 0.49 0.50 0.50
                0.51 0.52 0.52 0.53 0.54 0.54 0.55 0.56
                0.56 0.57 0.58 0.58 0.59 0.60 0.61 0.61
                0.62 0.63 0.64 0.64 0.65 0.66 0.67 0.68
                0.69 0.70 0.71 0.72 0.73 0.74 0.75 0.76
                0.77 0.78 0.79 0.80 0.81 0.82 0.83 0.84
            }
            weekly_prestige = {
                100 105 110 115 120 126 132 139
                146 153 161 169 177 186 195 205
                215 226 237 249 261 274 288 302
                317 333 340 340 340 340 340 340
                340 340 340 340 340 340 340 340
                340 340 340 340 340 340 340 340
                340 340 340 340 340 340 340 340
            }
            weekly_revenue = {
                30000 31000 32000 33500 35000 36500 38000 40000
                42000 44000 46000 48000 50000 52500 55000 57500
                60000 62500 65000 67500 70000 72500 75000 77500
                80000 82000 83000 84000 85000 85000 85000 85000
                85000 85000 85000 85000 85000 85000 85000 85000
                85000 85000 85000 85000 85000 85000 85000 85000
                85000 85000 85000 85000 85000 85000 85000 85000
            }
            weekly_expense = {
                28000 29000 30000 31000 32500 34000 35500 37000
                39000 41000 43000 45000 47000 49000 51000 53000
                55000 57000 59000 61000 63000 65000 67000 69000
                71000 72000 72000 72000 72000 72000 72000 72000
                72000 72000 72000 72000 72000 72000 72000 72000
                72000 72000 72000 72000 72000 72000 72000 72000
                72000 72000 72000 72000 72000 72000 72000 72000
            }
        }
    }
}
state_manager = {
    database = {
        0 = {
            definition = "state_home_counties"
            country = 0
            population = 3200000
            gdp = 180000
            infrastructure = 45
        }
        1 = {
            definition = "state_midlands"
            country = 0
            population = 2800000
            gdp = 150000
            infrastructure = 38
        }
        2 = {
            definition = "state_lancashire"
            country = 0
            population = 2500000
            gdp = 140000
            infrastructure = 35
        }
        3 = {
            definition = "state_yorkshire"
            country = 0
            population = 2100000
            gdp = 120000
            infrastructure = 30
        }
        4 = {
            definition = "state_wales"
            country = 0
            population = 1200000
            gdp = 60000
            infrastructure = 18
        }
        5 = {
            definition = "state_ile_de_france"
            country = 1
            population = 3500000
            gdp = 200000
            infrastructure = 42
        }
    }
}
market_manager = {
    database = {
        0 = {
            goods = {
                grain = {
                    produced = 45000
                    consumed = 42000
                    price = 20
                }
                iron = {
                    produced = 32000
                    consumed = 35000
                    price = 40
                }
                coal = {
                    produced = 55000
                    consumed = 50000
                    price = 30
                }
                fabric = {
                    produced = 28000
                    consumed = 26000
                    price = 25
                }
                tools = {
                    produced = 18000
                    consumed = 20000
                    price = 45
                }
                steel = {
                    produced = 15000
                    consumed = 16000
                    price = 50
                }
                arms = {
                    produced = 12000
                    consumed = 11000
                    price = 55
                }
                tea = {
                    produced = 8000
                    consumed = 9000
                    price = 35
                }
            }
        }
    }
}
"""


class TestEndToEnd(unittest.TestCase):
    def test_full_pipeline_from_text(self):
        """Test the full pipeline with raw text gamestate."""
        meta = parse_pdx(SYNTHETIC_META)
        gamestate = parse_pdx(SYNTHETIC_GAMESTATE)
        data = extract_all(gamestate, meta)

        self.assertEqual(data["meta"]["player_tag"], "GBR")
        self.assertEqual(data["meta"]["game_date"], "1870.6.15")
        self.assertIn("gdp", data["timeseries"])
        self.assertGreater(len(data["timeseries"]["gdp"]), 10)
        self.assertIn("gdp_growth_rate", data["timeseries"])
        self.assertIn("population", data["timeseries"])
        self.assertGreater(len(data["states"]), 0)
        self.assertGreater(len(data["technology"]["acquired"]), 0)

        # Generate HTML
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "index.html")
            generate_dashboard(data, output)
            self.assertTrue(os.path.exists(output))
            with open(output) as f:
                html = f.read()
            self.assertIn("GBR", html)
            self.assertIn("1870.6.15", html)
            self.assertIn("Chart", html)
            self.assertIn("chart-1", html)
            self.assertGreater(len(html), 5000)

    def test_full_pipeline_from_zip(self):
        """Test loading from a ZIP file like a real .v3 save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake .v3 ZIP
            v3_path = os.path.join(tmpdir, "test_save.v3")
            with zipfile.ZipFile(v3_path, "w") as zf:
                zf.writestr("meta", SYNTHETIC_META)
                zf.writestr("gamestate", SYNTHETIC_GAMESTATE)

            raw = load_save(v3_path)
            self.assertIn("gamestate", raw)
            self.assertIn("meta", raw)

            meta = parse_pdx(raw["meta"])
            gamestate = parse_pdx(raw["gamestate"])
            data = extract_all(gamestate, meta)

            self.assertEqual(data["meta"]["player_tag"], "GBR")

            output = os.path.join(tmpdir, "output", "index.html")
            generate_dashboard(data, output)
            self.assertTrue(os.path.exists(output))


if __name__ == "__main__":
    unittest.main()
