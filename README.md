# Warhammer40k_AI

Warhammer40k_AI is a Python library for processing and managing Wahapedia data. It provides an easy-to-use interface for loading, sanitizing, and retrieving information from various Wahapedia JSON files.

Ultimate goal is to create a Warhammer 40k AI that can be used to play Warhammer 40k with AI opponents.

## Installation

You can install Warhammer40k_AI using pip:

```bash
pip install warhammer40k_ai
```

## Usage

The first time you use this program you need to pull down the Warhammer 40k Datasheets from Wahapedia by typing:

```
cd .\scripts\
python -m get_datasheets -f -c -o ../wahapedia_data -s ../wahapedia_data
cd ..
```

Here's a basic example of how to use Warhammer40k_AI:

```
python -m warhammer40k_ai.UI.ModelUI
```

## License

This project is licensed under the MIT License.