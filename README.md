# Victoria 3 Save Game Analyzer

Parses Victoria 3 save files and generates an interactive HTML dashboard with charts showing GDP growth, population trends, budget, and other key metrics over time.

## Features

- **GDP Over Time** — line chart of weekly GDP values
- **GDP Growth Rate** — derived percentage growth chart
- **GDP Per Capita** — GDP divided by population
- **Population Trends** — population growth over time
- **Standard of Living** — SoL trajectory
- **Literacy Rate** — education progress
- **Budget** — revenue vs expenditure comparison
- **Prestige** — prestige accumulation
- **Country Summary Cards** — current GDP, population, treasury, tech count, etc.
- **States Table** — population and GDP by state
- **Technology List** — all researched technologies
- **Goods Production** — top goods by production volume

## Requirements

- Python 3.9+
- `jinja2` (`pip3 install jinja2`)

## Quick Start

```bash
# Install dependency
pip3 install jinja2

# Analyze a save file
python3 -m v3analyzer your_save.v3

# Open result in browser automatically
python3 -m v3analyzer your_save.v3 --open

# Specify output directory
python3 -m v3analyzer your_save.v3 -o my_output/

# Override player country
python3 -m v3analyzer your_save.v3 --country FRA
```

## Save File Format

The tool supports **text-format** Victoria 3 saves (.v3 ZIP files). To save in text format:

1. Edit `~/Documents/Paradox Interactive/Victoria 3/pdx_settings.json`
2. Set `"save_file_format": "zip_text_all"` under the `game` section
3. Re-save your game

Binary saves are not supported (the tool will tell you how to convert).

## Output

A single self-contained `index.html` file with:
- Dark theme matching the Victoria 3 aesthetic
- Interactive Chart.js charts with hover tooltips
- Responsive layout (works on mobile)
- No server required — just open the HTML file

## Project Structure

```
v3-save-analyzer/
├── v3analyzer/
│   ├── cli.py           # CLI entrypoint
│   ├── loader.py        # ZIP extraction, format detection
│   ├── parser.py        # PDXScript recursive descent parser
│   ├── extractor.py     # Data extraction from parsed tree
│   ├── generator.py     # HTML dashboard generation
│   └── templates/
│       └── dashboard.html
├── tests/
│   ├── test_parser.py   # 18 parser unit tests
│   └── test_e2e.py      # End-to-end pipeline tests
├── requirements.txt
└── README.md
```
