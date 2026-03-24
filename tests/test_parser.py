"""Unit tests for the PDXScript parser."""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from v3analyzer.parser import parse_pdx


class TestBasicParsing(unittest.TestCase):
    def test_simple_key_value(self):
        result = parse_pdx('name = "Test Country"')
        self.assertEqual(result["name"], "Test Country")

    def test_integer_value(self):
        result = parse_pdx("population = 12345")
        self.assertEqual(result["population"], 12345)

    def test_float_value(self):
        result = parse_pdx("gdp = 1234.56")
        self.assertAlmostEqual(result["gdp"], 1234.56)

    def test_boolean_yes(self):
        result = parse_pdx("is_player = yes")
        self.assertTrue(result["is_player"])

    def test_boolean_no(self):
        result = parse_pdx("is_ai = no")
        self.assertFalse(result["is_ai"])

    def test_date_value(self):
        result = parse_pdx("date = 1836.1.1")
        self.assertEqual(result["date"], "1836.1.1")

    def test_unquoted_string(self):
        result = parse_pdx("tag = GBR")
        self.assertEqual(result["tag"], "GBR")


class TestNestedBlocks(unittest.TestCase):
    def test_nested_block(self):
        text = """
        country = {
            name = "Britain"
            tag = GBR
        }
        """
        result = parse_pdx(text)
        self.assertEqual(result["country"]["name"], "Britain")
        self.assertEqual(result["country"]["tag"], "GBR")

    def test_deeply_nested(self):
        text = """
        a = {
            b = {
                c = 42
            }
        }
        """
        result = parse_pdx(text)
        self.assertEqual(result["a"]["b"]["c"], 42)

    def test_empty_block(self):
        text = "empty = {}"
        result = parse_pdx(text)
        self.assertEqual(result["empty"], {})


class TestArrays(unittest.TestCase):
    def test_number_array(self):
        text = "values = { 1 2 3 4 5 }"
        result = parse_pdx(text)
        self.assertEqual(result["values"], [1, 2, 3, 4, 5])

    def test_string_array(self):
        text = 'tags = { GBR FRA PRU }'
        result = parse_pdx(text)
        self.assertEqual(result["tags"], ["GBR", "FRA", "PRU"])

    def test_quoted_string_array(self):
        text = 'names = { "Alice" "Bob" "Charlie" }'
        result = parse_pdx(text)
        self.assertEqual(result["names"], ["Alice", "Bob", "Charlie"])


class TestComments(unittest.TestCase):
    def test_line_comment(self):
        text = """
        # This is a comment
        value = 42
        """
        result = parse_pdx(text)
        self.assertEqual(result["value"], 42)

    def test_inline_comment(self):
        text = "value = 42 # inline comment"
        result = parse_pdx(text)
        self.assertEqual(result["value"], 42)


class TestDuplicateKeys(unittest.TestCase):
    def test_duplicate_keys(self):
        text = """
        item = { name = "sword" }
        item = { name = "shield" }
        """
        result = parse_pdx(text)
        self.assertIsInstance(result["item"], list)
        self.assertEqual(len(result["item"]), 2)
        self.assertEqual(result["item"][0]["name"], "sword")
        self.assertEqual(result["item"][1]["name"], "shield")


class TestMultipleKeyValues(unittest.TestCase):
    def test_multiple_top_level(self):
        text = """
        a = 1
        b = 2
        c = 3
        """
        result = parse_pdx(text)
        self.assertEqual(result["a"], 1)
        self.assertEqual(result["b"], 2)
        self.assertEqual(result["c"], 3)


class TestComplexStructure(unittest.TestCase):
    def test_country_history_like(self):
        """Test a structure similar to what we'd see in a real save."""
        text = """
        country_history = {
            0 = {
                weekly_gdp = { 100.5 200.3 300.1 400.7 }
                weekly_population = { 1000 1100 1200 1300 }
            }
            1 = {
                weekly_gdp = { 500.0 600.0 }
                weekly_population = { 2000 2100 }
            }
        }
        """
        result = parse_pdx(text)
        ch = result["country_history"]
        # Numeric keys are parsed as integers by the parser
        # Check both int and string keys for robustness
        key0 = 0 if 0 in ch else "0"
        key1 = 1 if 1 in ch else "1"
        self.assertIn(key0, ch)
        self.assertEqual(len(ch[key0]["weekly_gdp"]), 4)
        self.assertAlmostEqual(ch[key0]["weekly_gdp"][0], 100.5)
        self.assertEqual(ch[key1]["weekly_population"], [2000, 2100])


if __name__ == "__main__":
    unittest.main()
