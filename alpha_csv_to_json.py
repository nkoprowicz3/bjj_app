import csv
import json
from pathlib import Path
from collections import defaultdict
import re

DATA_DIR = "data"
TECH_CANDIDATES = ["techniques_alpha.csv", "techniques_alpha.tsv"]
POS_CANDIDATES = ["positions_alpha.csv", "positions_alpha.tsv"]
OUT_FILE = "content.json"

def find_first(path_candidates):
    base = Path(DATA_DIR)
    for name in path_candidates:
        p = base / name
        if p.exists():
            return p
    raise FileNotFoundError(f"Missing files. Looked for: {', '.join(str(base / n) for n in path_candidates)}")

def read_table(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
            delim = dialect.delimiter
        except Exception:
            # fallback: tab for .tsv, comma otherwise
            delim = "\t" if path.suffix.lower() == ".tsv" else ","
        return list(csv.DictReader(f, delimiter=delim))

def slugify(s):
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "untitled"

def split_multi(val):
    if not val:
        return []
    # split on actual newlines or pipes " | "
    parts = []
    for piece in re.split(r"\n|\|", val):
        p = piece.strip()
        if p:
            parts.append(p)
    return parts

def build_graph():
    tech_path = find_first(TECH_CANDIDATES)
    pos_path = None
    try:
        pos_path = find_first(POS_CANDIDATES)
    except FileNotFoundError:
        pass

    tech_rows = read_table(tech_path)
    pos_rows = read_table(pos_path) if pos_path else []

    positions = {}
    # From positions_alpha
    for r in pos_rows:
        name = (r.get("Position") or "").strip()
        if not name:
            continue
        pid = slugify(name)
        positions[pid] = {
            "id": pid,
            "label": name,
        }
        kp = split_multi(r.get("Key points", ""))
        hz = split_multi(r.get("Hazards", ""))
        obj = split_multi(r.get("Objectives", ""))
        if kp: positions[pid]["key_points"] = kp
        if hz: positions[pid]["hazards"] = hz
        if obj: positions[pid]["objectives"] = obj
        vids = split_multi(r.get("Links", ""))
        if vids:
            positions[pid]["videos"] = [{"url": u} for u in vids]

    by_origin = defaultdict(list)
    used_action_ids = set()

    for r in tech_rows:
        start = (r.get("Starting position") or "").strip()
        typ = (r.get("Type") or "").strip().lower()
        tech = (r.get("Technique") or "").strip()
        end = (r.get("End position") or "").strip() or start
        links = split_multi(r.get("Links", ""))
        steps = split_multi(r.get("Steps", ""))
        keys = split_multi(r.get("Keys", ""))

        if not start or not tech:
            continue
        if typ not in ("submission", "transition"):
            typ = "transition"

        start_id = slugify(start)
        end_id = slugify(end)
        tech_id_base = slugify(tech)
        tech_id = tech_id_base
        if tech_id in used_action_ids:
            tech_id = f"{tech_id_base}_from_{start_id}"
        while tech_id in used_action_ids:
            tech_id += "_x"
        used_action_ids.add(tech_id)

        if start_id not in positions:
            positions[start_id] = {"id": start_id, "label": start}
        if end_id not in positions:
            positions[end_id] = {"id": end_id, "label": end}

        action_obj = {
            "id": tech_id,
            "label": tech,
            "steps": steps,
            "success_to": end_id,
        }
        if keys:
            action_obj["keys"] = keys
        if links:
            action_obj["videos"] = [{"url": u} for u in links]

        by_origin[start_id].append((typ, action_obj))

    out_positions = []
    for pid, pobj in positions.items():
        actions = by_origin.get(pid, [])
        if actions:
            subs = [a for t, a in actions if t == "submission"]
            trans = [a for t, a in actions if t == "transition"]
            if subs:
                pobj["submissions"] = subs
            if trans:
                pobj["transitions"] = trans
        out_positions.append(pobj)

    graph = {
        "positions": sorted(out_positions, key=lambda x: x["label"].lower()),
        "opponent_profiles": [
            {"id": "pressure_passer", "label": "Pressure passer", "posture": 0.8, "counter": 0.6},
            {"id": "balanced", "label": "Balanced", "posture": 0.6, "counter": 0.5},
        ],
    }
    return graph

if __name__ == "__main__":
    out = build_graph()
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"Wrote {OUT_FILE} with {len(out['positions'])} positions")