import random
import time

class Opponent:
    def __init__(self, id, posture=0.7, counter=0.5, label=None):
        self.id = id
        self.posture = posture
        self.counter = counter
        self.label = label or id

class Engine:
    def __init__(self, graph):
        self.graph = graph
        self.pos_map = {p["id"]: p for p in graph.get("positions", [])}
        # Build a global action map for transitions and submissions
        self.action_map = {}
        for p in graph.get("positions", []):
            for e in (p.get("transitions", []) or []):
                ed = e.copy()
                ed["type"] = "transition"
                ed["from"] = p["id"]
                self.action_map[ed["id"]] = ed
            for e in (p.get("submissions", []) or []):
                ed = e.copy()
                ed["type"] = "submission"
                ed["from"] = p["id"]
                self.action_map[ed["id"]] = ed

    def position_ids(self):
        return [p["id"] for p in self.graph.get("positions", [])]

    def position_label(self, pos_id):
        p = self.pos_map.get(pos_id)
        return p["label"] if p else pos_id

    def position(self, pos_id):
        return self.pos_map[pos_id]

    def action(self, action_id):
        return self.action_map.get(action_id)

    def edges_for(self, pos_id):
        p = self.position(pos_id)
        return (p.get("transitions", []) or []) + (p.get("submissions", []) or [])

    def study_prompt(self, pos_id):
        p = self.position(pos_id)
        return {
            "position": p["label"],
            "answer_key": {
                "key_points": p.get("key_points", []),
                "hazards": p.get("hazards", []),
                "transitions": [e["label"] for e in self.edges_for(pos_id)]
            }
        }

    def simulate_step(self, pos_id, edge_id, opp: Opponent):
        p = self.position(pos_id)
        edges = self.edges_for(pos_id)
        edge = next((e for e in edges if e["id"] == edge_id), None)
        if not edge:
            return {"outcome": "stalled", "to": pos_id, "notes": "No valid option."}

        # Basic success model
        base = 0.65
        risk = 0.15 + 0.5 * opp.counter
        success = base - risk * random.random()

        if success > 0.5:
            return {"outcome": "success", "to": edge.get("success_to", pos_id), "notes": "Clean execution."}

        counters = edge.get("counters", [])
        if counters:
            c = random.choice(counters)
            return {
                "outcome": "countered",
                "to": c["result_position"],
                "notes": c.get("trigger", "They counter your attempt.")
            }

        return {"outcome": "stalled", "to": pos_id, "notes": "Stalemate; reset grips."}

    def maybe_opponent_attack(self, pos_id, opp: Opponent):
        p = self.position(pos_id)
        atks = p.get("opponent_attacks", [])
        if not atks:
            return None
        if random.random() < 0.25 * opp.counter:
            return random.choice(atks)
        return None

    def flow_sequence(self, start_pos_id, length=20):
        seq = []
        pos = start_pos_id
        for _ in range(length):
            if pos not in self.pos_map:
                break
            p = self.position(pos)
            seq.append({"type": "position", "label": p["label"], "id": pos})
            edges = self.edges_for(pos)
            if not edges:
                break
            e = random.choice(edges)
            seq.append({"type": "action", "label": e["label"], "id": e["id"]})
            pos = e.get("success_to", pos)
        return seq

# Simple spaced repetition (Leitner-like)
def srs_grade(store, card_id, grade):
    now = time.time()
    card = store.get(card_id, {"box": 1, "due": now})
    if grade <= 2:
        card["box"] = 1
        delay = 24 * 3600
    elif grade == 3:
        delay = 2 * 24 * 3600
    elif grade == 4:
        card["box"] = min(card["box"] + 1, 5)
        delay = 5 * 24 * 3600
    else:
        card["box"] = min(card["box"] + 1, 5)
        delay = 10 * 24 * 3600
    card["due"] = now + delay
    store[card_id] = card

def srs_due(store, prefix=None):
    now = time.time()
    due = []
    for cid, meta in store.items():
        if prefix and not cid.startswith(prefix):
            continue
        if meta.get("due", 0) <= now:
            due.append(cid)
    return due
