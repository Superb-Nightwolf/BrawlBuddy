"""
Generate benchmark matchup and teammate data for Brawl Stars brawlers.
Outputs: data/brawler_matchups.json
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "data" / "brawler_catalog.json"
OUTPUT_PATH = ROOT / "data" / "brawler_matchups.json"

# Exact POC data for Rosa (16000024)
ROSA_EXACT = {
    "brawler_id": 16000024,
    "brawler_name": "Rosa",
    "strong_against": [
        {"id": 16000043, "name": "Edgar", "win_rate": 80.4, "total_battles": 4022},
        {"id": 16000011, "name": "Mortis", "win_rate": 78.0, "total_battles": 3461},
        {"id": 16000081, "name": "Lily", "win_rate": 75.5, "total_battles": 619},
        {"id": 16000022, "name": "Tick", "win_rate": 75.1, "total_battles": 2651},
        {"id": 16000015, "name": "Piper", "win_rate": 74.3, "total_battles": 1588},
        {"id": 16000000, "name": "Shelly", "win_rate": 72.5, "total_battles": 1339},
        {"id": 16000009, "name": "Dynamike", "win_rate": 71.8, "total_battles": 2104},
        {"id": 16000034, "name": "Bea", "win_rate": 70.9, "total_battles": 1450},
        {"id": 16000016, "name": "Crow", "win_rate": 69.8, "total_battles": 1890},
        {"id": 16000001, "name": "Colt", "win_rate": 69.2, "total_battles": 2310},
    ],
    "struggles_against": [
        {"id": 16000094, "name": "Kaze", "win_rate": 49.9, "total_battles": 445},
        {"id": 16000064, "name": "Gray", "win_rate": 50.1, "total_battles": 2523},
        {"id": 16000021, "name": "Gene", "win_rate": 50.1, "total_battles": 297},
        {"id": 16000014, "name": "Bo", "win_rate": 50.2, "total_battles": 1569},
        {"id": 16000006, "name": "Barley", "win_rate": 50.9, "total_battles": 488},
        {"id": 16000052, "name": "Meg", "win_rate": 51.1, "total_battles": 1024},
        {"id": 16000039, "name": "Colette", "win_rate": 51.4, "total_battles": 1820},
        {"id": 16000059, "name": "Otis", "win_rate": 51.8, "total_battles": 890},
        {"id": 16000036, "name": "Gale", "win_rate": 52.1, "total_battles": 1420},
        {"id": 16000067, "name": "Maisie", "win_rate": 52.4, "total_battles": 780},
    ],
    "best_alongside": [
        {"id": 16000046, "name": "Belle", "win_rate": 78.4, "total_battles": 1590},
        {"id": 16000064, "name": "Gray", "win_rate": 77.2, "total_battles": 6722},
        {"id": 16000099, "name": "Pierce", "win_rate": 76.8, "total_battles": 1478},
        {"id": 16000032, "name": "Max", "win_rate": 75.4, "total_battles": 1692},
        {"id": 16000091, "name": "Lumi", "win_rate": 74.3, "total_battles": 1557},
        {"id": 16000059, "name": "Otis", "win_rate": 73.9, "total_battles": 1396},
        {"id": 16000044, "name": "Byron", "win_rate": 73.2, "total_battles": 2110},
        {"id": 16000007, "name": "Poco", "win_rate": 72.8, "total_battles": 3450},
        {"id": 16000021, "name": "Gene", "win_rate": 72.4, "total_battles": 1870},
        {"id": 16000030, "name": "Sandy", "win_rate": 71.9, "total_battles": 2240},
    ]
}

CLASS_FAVORABLE = {
    "Tank": ["Assassin", "Artillery", "Marksman"],
    "Assassin": ["Artillery", "Marksman"],
    "Artillery": ["Tank", "Damage Dealer"],
    "Marksman": ["Damage Dealer", "Tank"],
    "Controller": ["Tank", "Assassin"],
    "Support": ["Tank", "Damage Dealer"],
    "Damage Dealer": ["Tank", "Controller"],
}

CLASS_COUNTERS = {
    "Tank": ["Controller", "Damage Dealer"],
    "Assassin": ["Tank", "Controller"],
    "Artillery": ["Assassin", "Marksman"],
    "Marksman": ["Assassin", "Artillery"],
    "Controller": ["Marksman", "Artillery"],
    "Support": ["Assassin", "Marksman"],
    "Damage Dealer": ["Marksman", "Artillery"],
}

CLASS_SYNERGY = {
    "Tank": ["Support", "Marksman", "Controller"],
    "Assassin": ["Tank", "Controller", "Support"],
    "Artillery": ["Tank", "Controller", "Support"],
    "Marksman": ["Tank", "Controller", "Support"],
    "Controller": ["Damage Dealer", "Tank", "Support"],
    "Support": ["Tank", "Damage Dealer", "Assassin"],
    "Damage Dealer": ["Tank", "Support", "Controller"],
}


def build_all_matchups():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    brawlers_by_id = {b["id"]: b for b in catalog}
    brawlers_by_class = {}
    for b in catalog:
        c = b.get("class", "Damage Dealer")
        brawlers_by_class.setdefault(c, []).append(b)

    matchups_db = {}

    for brawler in catalog:
        b_id = brawler["id"]
        b_name = brawler["name"]
        b_class = brawler.get("class", "Damage Dealer")

        if b_id == 16000024:
            matchups_db[str(b_id)] = ROSA_EXACT
            continue

        rng = random.Random(b_id * 31 + 17)

        # Favorable picks
        fav_classes = CLASS_FAVORABLE.get(b_class, ["Assassin", "Marksman"])
        pool_fav = [
            b for c in fav_classes for b in brawlers_by_class.get(c, [])
            if b["id"] != b_id
        ]
        if len(pool_fav) < 10:
            pool_fav.extend([b for b in catalog if b["id"] != b_id and b not in pool_fav])
        selected_fav = rng.sample(pool_fav, min(10, len(pool_fav)))
        
        # Sort descending win rate between 68.0% and 82.0%
        base_rates_fav = sorted([round(rng.uniform(67.5, 81.5), 1) for _ in selected_fav], reverse=True)
        fav_list = []
        for i, target in enumerate(selected_fav):
            battles = rng.randint(500, 4800)
            fav_list.append({
                "id": target["id"],
                "name": target["name"],
                "win_rate": base_rates_fav[i],
                "total_battles": battles,
            })

        # Counters picks
        cnt_classes = CLASS_COUNTERS.get(b_class, ["Controller", "Damage Dealer"])
        pool_cnt = [
            b for c in cnt_classes for b in brawlers_by_class.get(c, [])
            if b["id"] != b_id and b["id"] not in [x["id"] for x in fav_list]
        ]
        if len(pool_cnt) < 10:
            pool_cnt.extend([
                b for b in catalog
                if b["id"] != b_id and b not in pool_cnt and b["id"] not in [x["id"] for x in fav_list]
            ])
        selected_cnt = rng.sample(pool_cnt, min(10, len(pool_cnt)))

        # Sort ascending win rate between 47.0% and 53.5%
        base_rates_cnt = sorted([round(rng.uniform(47.5, 53.5), 1) for _ in selected_cnt])
        cnt_list = []
        for i, target in enumerate(selected_cnt):
            battles = rng.randint(350, 4200)
            cnt_list.append({
                "id": target["id"],
                "name": target["name"],
                "win_rate": base_rates_cnt[i],
                "total_battles": battles,
            })

        # Synergy picks
        syn_classes = CLASS_SYNERGY.get(b_class, ["Support", "Tank", "Marksman"])
        pool_syn = [
            b for c in syn_classes for b in brawlers_by_class.get(c, [])
            if b["id"] != b_id
        ]
        if len(pool_syn) < 10:
            pool_syn.extend([b for b in catalog if b["id"] != b_id and b not in pool_syn])
        selected_syn = rng.sample(pool_syn, min(10, len(pool_syn)))

        # Sort descending win rate between 70.0% and 79.5%
        base_rates_syn = sorted([round(rng.uniform(70.5, 79.8), 1) for _ in selected_syn], reverse=True)
        syn_list = []
        for i, target in enumerate(selected_syn):
            battles = rng.randint(800, 6500)
            syn_list.append({
                "id": target["id"],
                "name": target["name"],
                "win_rate": base_rates_syn[i],
                "total_battles": battles,
            })

        matchups_db[str(b_id)] = {
            "brawler_id": b_id,
            "brawler_name": b_name,
            "strong_against": fav_list,
            "struggles_against": cnt_list,
            "best_alongside": syn_list,
        }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(matchups_db, f, indent=2, ensure_ascii=False)

    print(f"Successfully wrote {len(matchups_db)} brawler matchup profiles to {OUTPUT_PATH}")


if __name__ == "__main__":
    build_all_matchups()
