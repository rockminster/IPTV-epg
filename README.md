# IPTV-epg

Builds a combined UK EPG (Electronic Program Guide) from multiple sources with intelligent channel matching.

## Features

- **Multi-tier Channel Matching**: Matches M3U playlist channels to EPG data using:
  1. **ID matching** with alias normalization (handles common UK channel ID variations)
  2. **Exact name matching** after normalization 
  3. **Fuzzy name matching** using difflib.SequenceMatcher (default threshold: 0.86)

- **Multiple EPG Sources**: Combines data from:
  - [epg.pw](https://epg.pw) UK EPG data
  - [iptv-org](https://iptv-org.github.io) UK guide data

- **Smart Deduplication**: Removes duplicate programs by (start time, stop time, title) and prefers longer descriptions

- **Automated Updates**: GitHub Actions workflow runs every 6 hours to rebuild the EPG

## Setup

1. **Configure Secret**: Set `M3U_URL` as a repository secret containing your M3U playlist URL
2. **Enable GitHub Pages**: Configure Pages to deploy from the `gh-pages` branch 
3. **Run Workflow**: The EPG will be automatically built and published

## Output

- **Gzipped XMLTV**: `docs/uk_merged.xml.gz` - The merged EPG file
- **Web Interface**: `docs/index.html` - Simple web page with download link and build timestamp

## Channel Matching Examples

The system handles common UK channel variations:
- `bbcone` → `bbc.one.uk`
- `ITV1` → `itv1.uk` 
- `Channel 4 HD` → `channel4.uk` (via fuzzy matching)

## Requirements

- Python 3.11+
- `requests` library (see requirements.txt)

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set M3U URL (optional for testing)
export M3U_URL="your_m3u_url_here"

# Run merge script
python merge.py
```

The script will create `docs/uk_merged.xml.gz` and `docs/index.html`.
