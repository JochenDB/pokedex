#!/usr/bin/env python3
"""
Build sets-data.json from local JSON files (no API calls needed).

Expected folder structure:
  data/
    pokemon-tcg-data/     # Cloned from https://github.com/PokemonTCG/pokemon-tcg-data
      sets/
        en.json           # All sets metadata
      cards/
        en/
          {set_id}.json   # Cards per set (e.g., sv1.json, me2pt5.json)

Run with: python3 build-sets-data.py

To update data: cd data/pokemon-tcg-data && git pull
"""

import json
import os
from collections import defaultdict

# Directory paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'data', 'pokemon-tcg-data')
SETS_FILE = os.path.join(DATA_DIR, 'sets', 'en.json')
CARDS_DIR = os.path.join(DATA_DIR, 'cards', 'en')
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'sets-data.json')


def load_sets(series_filter=None):
    """Load sets from local JSON file"""
    print(f"Loading sets from {SETS_FILE}...")
    
    if not os.path.exists(SETS_FILE):
        raise FileNotFoundError(
            f"Sets file not found: {SETS_FILE}\n"
            f"Please clone the repo: git clone https://github.com/PokemonTCG/pokemon-tcg-data.git data/pokemon-tcg-data"
        )
    
    with open(SETS_FILE, 'r', encoding='utf-8') as f:
        sets = json.load(f)
    
    # Filter by series if specified
    if series_filter:
        original_count = len(sets)
        if isinstance(series_filter, list):
            sets = [s for s in sets if s.get('series', '') in series_filter]
        else:
            sets = [s for s in sets if s.get('series', '').lower() == series_filter.lower()]
        print(f"Found {len(sets)} sets in '{series_filter}' series (filtered from {original_count} total)")
    else:
        print(f"Found {len(sets)} sets")
    
    return sets


def load_cards_for_set(set_id):
    """Load cards from local JSON file for a specific set"""
    cards_file = os.path.join(CARDS_DIR, f'{set_id}.json')
    
    if not os.path.exists(cards_file):
        return None
    
    with open(cards_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_pokemon_name(name):
    """Normalize Pokémon name for grouping cards (fallback when no dex number)"""
    if not name:
        return None
    
    name = name.lower().strip()
    
    # Remove common TCG suffixes/prefixes
    suffixes = ['ex', 'gx', 'v', 'vmax', 'vstar', 'vunion']
    prefixes = ['team', 'rockets', 'rocket', 'dark', 'light', 'shining', 'radiant']
    
    parts = name.split()
    filtered = [p for p in parts if p not in suffixes and p not in prefixes]
    
    return ' '.join(filtered) if filtered else None


def build_sets_data(series_filter=None):
    """Build comprehensive sets data with Pokémon mappings from local files"""
    sets = load_sets(series_filter=series_filter)
    
    sets_data = []
    skipped_sets = []
    
    for idx, set_info in enumerate(sets, 1):
        set_id = set_info['id']
        print(f"\n[{idx}/{len(sets)}] Processing: {set_info['name']} ({set_id})")
        
        # Load cards for this set
        cards = load_cards_for_set(set_id)
        
        if cards is None:
            print(f"  ⚠ No card file found, skipping...")
            skipped_sets.append({'id': set_id, 'name': set_info['name']})
            continue
        
        print(f"  Found {len(cards)} cards")
        
        set_data = {
            'id': set_id,
            'name': set_info['name'],
            'series': set_info.get('series', ''),
            'release_date': set_info.get('releaseDate', ''),
            'total_cards': set_info.get('total', 0),
            'logo': set_info.get('images', {}).get('logo', ''),
            'symbol': set_info.get('images', {}).get('symbol', ''),
            'pokemon': []
        }
        
        # Group Pokémon cards by dex number (or normalized name as fallback)
        pokemon_cards = defaultdict(list)
        
        for card in cards:
            # Only include Pokémon cards
            if card.get('supertype') != 'Pokémon':
                continue
            
            # Use nationalPokedexNumbers if available (preferred - no fuzzy matching!)
            dex_numbers = card.get('nationalPokedexNumbers', [])
            
            # Use first dex number as the key, or fall back to normalized name
            if dex_numbers:
                key = f"dex_{dex_numbers[0]}"
            else:
                key = normalize_pokemon_name(card.get('name', ''))
                if not key:
                    continue
            
            card_info = {
                'card_name': card.get('name', ''),
                'number': card.get('number', ''),
                'rarity': card.get('rarity', 'Common'),
                'types': card.get('types', []),
                'image_small': card.get('images', {}).get('small', ''),
                'subtypes': card.get('subtypes', []),
                'dex_numbers': dex_numbers  # Store for direct lookup
            }
            
            pokemon_cards[key].append(card_info)
        
        # Add unique Pokémon to set data
        for key, cards_list in pokemon_cards.items():
            # Get the most common rarity for this Pokémon in this set
            rarities = [c['rarity'] for c in cards_list if c['rarity']]
            most_common_rarity = max(set(rarities), key=rarities.count) if rarities else 'Common'
            
            # Extract dex number from key or from cards
            if key.startswith('dex_'):
                dex_num = int(key.split('_')[1])
                pokemon_name = cards_list[0]['card_name']  # Use original card name
            else:
                dex_num = None
                pokemon_name = key
            
            # Get all dex numbers from cards (for cards with multiple)
            all_dex = set()
            for c in cards_list:
                all_dex.update(c.get('dex_numbers', []))
            
            set_data['pokemon'].append({
                'name': normalize_pokemon_name(cards_list[0]['card_name']) or pokemon_name,
                'dex_number': dex_num,
                'dex_numbers': sorted(all_dex) if all_dex else [],
                'rarity': most_common_rarity,
                'card_count': len(cards_list),
                'cards': cards_list
            })
        
        print(f"  ✓ Extracted {len(set_data['pokemon'])} unique Pokémon")
        sets_data.append(set_data)
    
    return sets_data, skipped_sets


def main():
    print("=" * 60)
    print("Pokémon TCG Set Data Builder (Local Files)")
    print("=" * 60)
    
    # Check data directory exists
    if not os.path.exists(DATA_DIR):
        print(f"\n⚠ Data directory not found: {DATA_DIR}")
        print(f"\nPlease clone the repo:")
        print(f"  git clone https://github.com/PokemonTCG/pokemon-tcg-data.git data/pokemon-tcg-data")
        return
    
    # Filter to specific series (set to None for all sets)
    # Examples: "Scarlet & Violet", "Sword & Shield", ["Scarlet & Violet", "Sword & Shield"]
    SERIES_FILTER = ["Scarlet & Violet", "Mega Evolution"]
    
    if SERIES_FILTER:
        print(f"\nFiltering to series: {SERIES_FILTER}")
    else:
        print("\nProcessing ALL series")
    
    try:
        sets_data, skipped_sets = build_sets_data(series_filter=SERIES_FILTER)
        
        # Save output
        print(f"\n\nSaving to {OUTPUT_FILE}...")
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(sets_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Successfully saved data for {len(sets_data)} sets")
        
        # Print summary
        total_pokemon = sum(len(s['pokemon']) for s in sets_data)
        print(f"\nSummary:")
        print(f"  Total sets processed: {len(sets_data)}")
        print(f"  Total Pokémon entries: {total_pokemon}")
        if sets_data:
            print(f"  Average Pokémon per set: {total_pokemon / len(sets_data):.1f}")
        
        # Report skipped sets
        if skipped_sets:
            print(f"\n⚠ Skipped {len(skipped_sets)} set(s) (no card files):")
            for s in skipped_sets[:10]:  # Show first 10
                print(f"  - {s['name']} ({s['id']})")
            if len(skipped_sets) > 10:
                print(f"  ... and {len(skipped_sets) - 10} more")
            print(f"\nUpdate the repo to get missing card files:")
            print(f"  cd data/pokemon-tcg-data && git pull")
        
    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == '__main__':
    main()
