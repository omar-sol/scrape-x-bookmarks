# scrape-x-bookmarks

This project scrapes your x.com bookmarks and saves them in a .json file

## Installation

Create a new Python environment
```bash
python -m venv env
```

Activate the environment
```bash
source env/bin/activate
```

Install the dependencies

```bash
pip install -r requirements.txt
playwright install
```

## Usage
Create an .env file with you auth cookie inside
```bash
COOKIE_STRING="...
```

```bash
python scraper.py
```