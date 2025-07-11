# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CSDbSpider is a Python tool for collecting, downloading, converting, and organizing C64 (Commodore 64) releases from the CSDb (Commodore Scene Database). The project focuses on archival and preservation of C64 software including demos, games, and other releases.

## Architecture

The codebase is organized into several core modules:

- **csdb.py**: Main module handling CSDb API interaction, web scraping, and release collection. Contains data structures for Link, Compo, and Event objects.
- **tools64.py**: Core Release dataclass and C64-specific file processing utilities. Handles unpacking, conversion, and metadata extraction.
- **utils.py**: Utility functions for file operations, name sanitization, directory management, and URL handling.
- **gb64.py**: GameBase64 integration for additional metadata sources.
- **packs.py**: Pack file handling and processing.
- **tosec.py**: TOSEC (The Old School Emulation Center) naming convention support.

### Key Data Structures

- **Release**: Primary dataclass representing a C64 release with metadata (title, group, year, rating, downloads, etc.)
- **Link**: Represents a CSDb link with ID, rating, and placement information
- **Compo/Event**: Data structures for competition and event organization

## Common Development Commands

### Testing
```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest test_csdb.py
python -m pytest test_tools64.py
python -m pytest test_utils.py

# Run tests with verbose output
python -m pytest -v
```

### Building Dependencies
```bash
# Build cbmconvert (C64 conversion tool)
make all

# Install cbmconvert system-wide
sudo make install
```

### Running the Application
```bash
# Example: Download top 99 releases with custom naming template
./csdb.py -l toplist -m 99 -t "Top/{rank:02}. {group} - {title}{ ({year})}"

# Search for releases
./csdb.py -s "search term"

# Download from specific group
./csdb.py -g "group_name"
```

## External Dependencies

The project requires several external tools for full functionality:
- `cbmconvert` and `zip2disk` for C64 format conversion
- `unrar`, `lha`, `7z`, `tar`/`gz` for archive handling
- `beautifulsoup4` Python package for HTML parsing

## File Processing Pipeline

1. **Collection**: Scrape CSDb for release metadata
2. **Filtering**: Apply filters by type, year, rating
3. **Download**: Fetch release files with caching
4. **Unpacking**: Extract archives using appropriate tools
5. **Conversion**: Convert to PRG or D64 formats when possible
6. **Organization**: Apply naming templates and directory structure

## Testing Data

Test data is located in `testdata/` directory containing sample C64 files, HTML pages, and archives for testing the processing pipeline.

## Caching Strategy

The system implements comprehensive caching:
- Downloaded files are cached to avoid re-downloading
- CSDb metadata is cached and includes precached data for popular releases
- This allows for quick template changes without re-downloading