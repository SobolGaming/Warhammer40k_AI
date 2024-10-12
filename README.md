# Warhammer40k_AI

Warhammer40k_AI is a Python library for processing and managing Wahapedia data. It provides an easy-to-use interface for loading, sanitizing, and retrieving information from various Wahapedia JSON files.

Ultimate goal is to create a Warhammer 40k AI that can be used to play Warhammer 40k with AI opponents.

Majority of the code has been written by CursorAI with purely prompt engineering.

## Usage

The first time you use this program you need to pull down the Warhammer 40k Datasheets from Wahapedia by typing:

```bash
mkdir wahapedia_data
cd .\scripts\
python3 -m get_datasheets -f -c -o ../wahapedia_data -s ../wahapedia_data
cd ..
```

You will also want to install dependencies and this project as a local pip package:

```bash
pip3 install -r requirements.txt
pip3 install -e .
```

Here's a basic example of how to use Warhammer40k_AI:

For the Wahapedia UI:
```
python3 -m warhammer40k_ai.UI.wahapedia_ui
```

For the Gym Environment:
```
python3 scripts/main.py
```

## License

This project is licensed under the MIT License.