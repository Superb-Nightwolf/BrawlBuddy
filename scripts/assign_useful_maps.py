import json

with open('data/maps_catalog.json', 'r', encoding='utf-8') as f:
    maps_catalog = json.load(f)

with open('data/brawler_guides.json', 'r', encoding='utf-8') as f:
    brawler_guides = json.load(f)

# Quick lookup by map name
map_by_name = {m['name'].lower(): m for m in maps_catalog.values()}
map_by_id = {int(k): v for k, v in maps_catalog.items()}

# Curated specific maps for certain standout brawlers / archetypes
EXACT_PICKS = {
    "buster": [15001311, 15001320, 15000132, 15001319], # Sneaky Fields, Double Swoosh, Center Stage, Hard Rock Mine
    "bibi": [15001311, 15000132, 15000293, 15001320],   # Sneaky Fields, Center Stage, Parallel Plays, Double Swoosh
    "rosa": [15001320, 15001311, 15001319, 15000306],   # Double Swoosh, Sneaky Fields, Hard Rock Mine, Dueling Beetles
    "frank": [15001311, 15000132, 15001320, 15000306],
    "piper": [15000005, 15001318, 15001316, 15000440],  # Shooting Star, Out In The Open, Goldarm Gulch, Flaring Phoenix
    "mandy": [15000005, 15001318, 15000703, 15001316],
    "nani": [15000005, 15001316, 15001318, 15000440],
    "brock": [15000005, 15000019, 15001316, 15000018],
    "colt": [15000019, 15000018, 15000118, 15000132],
    "rico": [15000118, 15000053, 15000306, 15001319],
    "chuck": [15000053, 15000019, 15000137, 15000293],  # Safe Zone, Hot Potato, Pit Stop, Parallel Plays
    "colette": [15000019, 15000018, 15000132, 15001316],
    "jessie": [15000306, 15000010, 15000018, 15000132],
    "penny": [15000010, 15000306, 15001319, 15000300],
    "gene": [15001319, 15001320, 15001316, 15000082],
    "tara": [15001320, 15001319, 15001311, 15000132],
    "amber": [15000300, 15000306, 15000053, 15001320],
    "shelly": [15000132, 15001311, 15001239, 15000950],
    "bull": [15000053, 15000137, 15001311, 15001239],
    "darryl": [15000053, 15000137, 15001311, 15000018],
    "edgar": [15000053, 15001239, 15000293, 15001311],
    "fang": [15000118, 15001311, 15001316, 15000132],
    "mortis": [15000082, 15000005, 15001311, 15000118],
    "dynamike": [15000292, 15000053, 15000137, 15000306],
    "barley": [15000292, 15000053, 15000306, 15000053],
    "tick": [15000005, 15000082, 15000292, 15000306],
    "sprout": [15000082, 15000292, 15001317, 15000306],
    "grom": [15000292, 15000306, 15001316, 15001317],
    "larry & lawrie": [15000292, 15000306, 15000132, 15001319],
    "cordelius": [15001311, 15001320, 15001239, 15000950],
    "buzz": [15001311, 15001320, 15001239, 15000950],
    "angelo": [15000005, 15001318, 15000440, 15001316],
    "belle": [15001316, 15001317, 15000440, 15001318],
}

# Mode-to-maps ranking by archetype
MODE_MAPS_BY_CLASS = {
    "Marksman": {
        "Knockout": [15001318, 15000440, 15001316, 15000703],
        "Bounty": [15000005, 15000082],
        "Heist": [15000019, 15000018],
        "Brawl Ball": [15000051, 15000118, 15000132],
        "Gem Grab": [15001319, 15000010],
        "Hot Zone": [15000300, 15000292],
        "Showdown": [15001239, 15000950]
    },
    "Tank": {
        "Brawl Ball": [15001311, 15000132, 15001312, 15000144],
        "Gem Grab": [15001320, 15001319, 15001321],
        "Hot Zone": [15000306, 15000293, 15000300],
        "Heist": [15000053, 15000137, 15000018],
        "Showdown": [15001239, 15000950],
        "Knockout": [15001316, 15001317],
        "Bounty": [15000082, 15000005]
    },
    "Assassin": {
        "Brawl Ball": [15001311, 15000132, 15000118],
        "Gem Grab": [15001320, 15001319, 15001321],
        "Knockout": [15001316, 15001317, 15000440],
        "Showdown": [15001239, 15000950],
        "Bounty": [15000082, 15000005],
        "Hot Zone": [15000293, 15000306],
        "Heist": [15000053, 15000137]
    },
    "Artillery": {
        "Hot Zone": [15000292, 15000306, 15000300],
        "Knockout": [15001317, 15001316, 15000440],
        "Bounty": [15000082, 15000005],
        "Heist": [15000053, 15000137],
        "Gem Grab": [15000010, 15001319],
        "Brawl Ball": [15000118, 15000132],
        "Showdown": [15001239, 15000950]
    },
    "Controller": {
        "Hot Zone": [15000300, 15000306, 15000292],
        "Gem Grab": [15001319, 15000010, 15001320],
        "Brawl Ball": [15000132, 15001311, 15000118],
        "Knockout": [15001316, 15001317],
        "Heist": [15000018, 15000019],
        "Bounty": [15000082, 15000005],
        "Showdown": [15001239, 15000950]
    },
    "Support": {
        "Gem Grab": [15001319, 15001320, 15000010],
        "Brawl Ball": [15000132, 15001311, 15000051],
        "Hot Zone": [15000300, 15000306],
        "Knockout": [15001316, 15000440],
        "Bounty": [15000082, 15000005],
        "Heist": [15000019, 15000053],
        "Showdown": [15001239, 15000950]
    },
    "Damage Dealer": {
        "Brawl Ball": [15000132, 15001311, 15000118],
        "Heist": [15000019, 15000053, 15000018],
        "Gem Grab": [15001319, 15001320],
        "Hot Zone": [15000306, 15000300],
        "Knockout": [15001316, 15001318],
        "Bounty": [15000005, 15000082],
        "Showdown": [15001239, 15000950]
    }
}

# Fallback default map pool across major modes
DEFAULT_MAP_IDS = [15001311, 15001320, 15000132, 15001316]

count_assigned = 0
for b_id, guide in brawler_guides.items():
    b_name = guide.get('name', '').lower()
    b_class = guide.get('class', 'Damage Dealer')
    mode_fit = guide.get('mode_fit', [])

    chosen_ids = []

    # 1. Check exact curated picks
    if b_name in EXACT_PICKS:
        chosen_ids = list(EXACT_PICKS[b_name])
    else:
        # 2. Iterate favored modes
        class_table = MODE_MAPS_BY_CLASS.get(b_class, MODE_MAPS_BY_CLASS['Damage Dealer'])
        for mode in mode_fit:
            maps_for_mode = class_table.get(mode, [])
            for mid in maps_for_mode:
                if mid not in chosen_ids:
                    chosen_ids.append(mid)
                    break # Take one top map per favored mode first

        # 3. If fewer than 4, take second best maps from favored modes
        if len(chosen_ids) < 4:
            for mode in mode_fit:
                maps_for_mode = class_table.get(mode, [])
                for mid in maps_for_mode:
                    if mid not in chosen_ids:
                        chosen_ids.append(mid)
                        if len(chosen_ids) == 4:
                            break
                if len(chosen_ids) == 4:
                    break

        # 4. If still fewer than 4, pick from general class table
        if len(chosen_ids) < 4:
            for mode, maps_for_mode in class_table.items():
                for mid in maps_for_mode:
                    if mid not in chosen_ids:
                        chosen_ids.append(mid)
                        if len(chosen_ids) == 4:
                            break
                if len(chosen_ids) == 4:
                    break

        # 5. Fallback if still needed
        for mid in DEFAULT_MAP_IDS:
            if len(chosen_ids) == 4:
                break
            if mid not in chosen_ids:
                chosen_ids.append(mid)

    # Convert chosen_ids into full map objects
    useful_maps = []
    for mid in chosen_ids[:4]:
        map_info = map_by_id.get(mid)
        if map_info:
            useful_maps.append({
                "id": map_info['id'],
                "name": map_info['name'],
                "mode": map_info['mode'],
                "image_url": map_info['image_url']
            })

    guide['useful_maps'] = useful_maps
    count_assigned += 1

print(f"Assigned useful_maps to {count_assigned} brawlers.")

# Verify Buster
buster_guide = next(v for v in brawler_guides.values() if v.get('name', '').upper() == 'BUSTER')
print("Buster useful_maps:")
for m in buster_guide['useful_maps']:
    print(f" - {m['name']} ({m['mode']}) -> {m['image_url']}")

# Save back to brawler_guides.json
with open('data/brawler_guides.json', 'w', encoding='utf-8') as f:
    json.dump(brawler_guides, f, indent=2, ensure_ascii=False)

print("Saved updated data/brawler_guides.json successfully.")
