#!/usr/bin/env python3
"""
Fetch Pokémon TCG set data from the API and cache it locally
Run with: python3 fetch-sets.py

This script fetches all sets and their cards, then creates a mapping
of which Pokémon appear in which sets with their rarities.
"""

import requests
import json
import time
import os
from collections import defaultdict

API_BASE = 'https://api.pokemontcg.io/v2'

def load_api_key():
    """Load API key from .api_key file or environment variable"""
    # Try environment variable first
    api_key = os.environ.get('POKEMON_TCG_API_KEY')
    if api_key:
        return api_key
    
    # Try loading from .api_key file
    key_file = os.path.join(os.path.dirname(__file__), '.api_key')
    if os.path.exists(key_file):
        with open(key_file, 'r') as f:
            return f.read().strip()
    
    return None

API_KEY = load_api_key()

def get_headers():
    """Get headers for API requests, including API key if available"""
    headers = {}
    if API_KEY:
        headers['X-Api-Key'] = API_KEY
    return headers

def fetch_with_retry(url, max_retries=3, timeout=120):
    """Fetch URL with retry logic and exponential backoff"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=get_headers(), timeout=timeout)
            response.raise_for_status()
            return response
        except (requests.exceptions.Timeout, requests.exceptions.HTTPError) as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                print(f"  Retry {attempt + 1}/{max_retries} after {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise

def fetch_all_sets(series_filter=None):
    """Fetch all Pokémon TCG sets, optionally filtered by series"""
    print("Fetching all sets...")
    url = f"{API_BASE}/sets"
    response = fetch_with_retry(url)
    sets = response.json()['data']
    
    # Filter by series if specified
    if series_filter:
        original_count = len(sets)
        sets = [s for s in sets if s.get('series', '').lower() == series_filter.lower()]
        print(f"Found {len(sets)} sets in '{series_filter}' series (filtered from {original_count} total)")
    else:
        print(f"Found {len(sets)} sets")
    
    return sets

def fetch_cards_for_set(set_id, page=1, page_size=50):
    """Fetch all cards for a specific set"""
    url = f"{API_BASE}/cards?q=set.id:{set_id}&page={page}&pageSize={page_size}"
    response = fetch_with_retry(url)
    return response.json()

def normalize_pokemon_name(name):
    """Normalize Pokémon name to match pokedex-map.json format"""
    if not name:
        return None
    
    # Convert to lowercase
    name = name.lower().strip()
    
    # Remove common TCG suffixes
    suffixes = ['ex', 'gx', 'v', 'vmax', 'vstar', 'vunion']
    prefixes = ['team', 'rockets', 'rocket', 'dark', 'light', 'shining', 'radiant']
    
    # Split and filter
    parts = name.split()
    filtered = [p for p in parts if p not in suffixes and p not in prefixes]
    
    return ' '.join(filtered) if filtered else None

def build_sets_data(series_filter=None, output_file='sets-data.json'):
    """Build comprehensive sets data with Pokémon mappings"""
    sets = fetch_all_sets(series_filter=series_filter)
    
    # Load existing progress if available
    sets_data = []
    processed_set_ids = set()
    failed_sets = []
    
    if os.path.exists(output_file):
        print(f"\nFound existing {output_file}, loading progress...")
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                sets_data = json.load(f)
            processed_set_ids = {s['id'] for s in sets_data}
            print(f"Resuming from {len(sets_data)} already processed sets")
        except Exception as e:
            print(f"Could not load existing file: {e}")
            sets_data = []
    
    for idx, set_info in enumerate(sets, 1):
        # Skip if already processed
        if set_info['id'] in processed_set_ids:
            print(f"\n[{idx}/{len(sets)}] Skipping {set_info['name']} ({set_info['id']}) - already processed")
            continue
        
        print(f"\n[{idx}/{len(sets)}] Processing set: {set_info['name']} ({set_info['id']})")
        
        try:
            set_data = {
                'id': set_info['id'],
                'name': set_info['name'],
                'series': set_info.get('series', ''),
                'release_date': set_info.get('releaseDate', ''),
                'total_cards': set_info.get('total', 0),
                'logo': set_info.get('images', {}).get('logo', ''),
                'symbol': set_info.get('images', {}).get('symbol', ''),
                'pokemon': []  # List of {name, number, rarity, types}
            }
            
            # Fetch all cards for this set
            page = 1
            all_cards = []
            page_size = 50
            
            while True:
                print(f"  Fetching page {page}...")
                result = fetch_cards_for_set(set_info['id'], page, page_size=page_size)
                cards = result['data']
                all_cards.extend(cards)
                
                if page >= result['totalCount'] // page_size + 1:
                    break
                page += 1
                time.sleep(0.1)  # Rate limiting
            
            print(f"  Found {len(all_cards)} cards")
            
            # Extract Pokémon cards (exclude Trainer, Energy, etc.)
            pokemon_cards = defaultdict(list)
            
            for card in all_cards:
                # Only include Pokémon cards
                if card.get('supertype') != 'Pokémon':
                    continue
                
                pokemon_name = normalize_pokemon_name(card.get('name', ''))
                if not pokemon_name:
                    continue
                
                card_info = {
                    'card_name': card.get('name', ''),
                    'number': card.get('number', ''),
                    'rarity': card.get('rarity', 'Common'),
                    'types': card.get('types', []),
                    'image_small': card.get('images', {}).get('small', ''),
                    'subtypes': card.get('subtypes', [])
                }
                
                pokemon_cards[pokemon_name].append(card_info)
            
            # Add unique Pokémon to set data
            for pokemon_name, cards in pokemon_cards.items():
                # Get the most common rarity for this Pokémon in this set
                rarities = [c['rarity'] for c in cards]
                most_common_rarity = max(set(rarities), key=rarities.count)
                
                set_data['pokemon'].append({
                    'name': pokemon_name,
                    'rarity': most_common_rarity,
                    'card_count': len(cards),
                    'cards': cards
                })
            
            print(f"  Extracted {len(set_data['pokemon'])} unique Pokémon")
            sets_data.append(set_data)
            
            # Save progress incrementally after each set
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(sets_data, f, indent=2, ensure_ascii=False)
                print(f"  ✓ Saved progress ({len(sets_data)}/{len(sets)} sets)")
            except Exception as e:
                print(f"  Warning: Could not save progress: {e}")
            
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed_sets.append({'id': set_info['id'], 'name': set_info['name'], 'error': str(e)})
            print(f"  Skipping to next set...")
        
        # Small delay between sets
        time.sleep(0.2)
    
    return sets_data, failed_sets

def main():
    print("=" * 60)
    print("Pokémon TCG Set Data Fetcher")
    print("=" * 60)
    
    # Filter to only Scarlet & Violet series (currently available for sale)
    # Change the filter to incrementally load
    SERIES_FILTER = "Mega Evolution"
    print(f"\nFiltering to series: {SERIES_FILTER}")
    
    try:
        output_file = 'sets-data.json'
        sets_data, failed_sets = build_sets_data(series_filter=SERIES_FILTER, output_file=output_file)
        
        # Final save (already saved incrementally, but doing it once more for consistency)
        print(f"\n\nFinal save to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(sets_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Successfully saved data for {len(sets_data)} sets")
        print(f"✓ Output file: {output_file}")
        
        # Print summary statistics
        total_pokemon = sum(len(s['pokemon']) for s in sets_data)
        print(f"\nSummary:")
        print(f"  Total sets: {len(sets_data)}")
        print(f"  Total Pokémon entries: {total_pokemon}")
        print(f"  Average Pokémon per set: {total_pokemon / len(sets_data):.1f}")
        
        # Report failed sets if any
        if failed_sets:
            print(f"\n⚠ Warning: {len(failed_sets)} set(s) failed to download:")
            for failed in failed_sets:
                print(f"  - {failed['name']} ({failed['id']}): {failed['error']}")
            print(f"\nTo retry failed sets, just run the script again - it will skip already processed sets.")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise

if __name__ == '__main__':
    main()
