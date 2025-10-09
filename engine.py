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

    def action_type(self, action_id):
        a = self.action_map.get(action_id)
        return a.get("type") if a else None

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

    def simulate_step(self, pos_id, edge_id, opp: Opponent, success_prob=None):
        # Find chosen edge in current position
        edges = self.edges_for(pos_id)
        edge = next((e for e in edges if e["id"] == edge_id), None)
        if not edge:
            return {"outcome": "stalled", "to": pos_id, "notes": "No valid option."}

        atype = self.action_type(edge_id) or "transition"

        # Decide success
        if success_prob is not None:
            succeeded = (random.random() < float(success_prob))
        else:
            # original heuristic
            base = 0.65
            risk = 0.15 + 0.5 * opp.counter
            succeeded = (base - risk * random.random()) > 0.5

        # Submissions are terminal if successful
        if atype == "submission":
            if succeeded:
                return {
                    "outcome": "submitted",
                    "to": pos_id,  # terminal; we don't advance
                    "notes": f"You finish {edge.get('label','the submission')}."
                }
            counters = edge.get("counters", [])
            if counters:
                c = random.choice(counters)
                return {
                    "outcome": "countered",
                    "to": c["result_position"],
                    "notes": c.get("trigger", "They counter your attempt.")
                }
            return {"outcome": "stalled", "to": pos_id, "notes": "Attack defended; reset and keep control."}

        # Transitions
        if succeeded:
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

    # Legacy simple flow (unused by UI now)
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

    def actionable_position_ids(self):
        return [pid for pid in self.position_ids() if self.edges_for(pid)]

    # ---------- Submission-ending flow generation ----------
    def flow_to_submission(self, start_pos_id, min_items=12, max_items=60, tries=300):
        """
        Build a sequence (type/label/id) that:
        - starts at start_pos_id,
        - alternates Position -> Action -> ...,
        - ends on a submission ACTION,
        - has at least min_items items, <= max_items.
        """
        if start_pos_id not in self.pos_map:
            return None

        for _ in range(tries):
            seq = [{"type": "position", "label": self.position_label(start_pos_id), "id": start_pos_id}]
            pos = start_pos_id

            for _step in range(max_items):
                edges = self.edges_for(pos)
                if not edges:
                    break

                trans, subs = [], []
                for e in edges:
                    (subs if (self.action_type(e["id"]) == "submission") else trans).append(e)

                need_more = len(seq) < (min_items - 1)
                if need_more and not trans:
                    # can't grow further without ending too early → dead end
                    seq = None
                    break

                pool = trans if (need_more and trans) else (subs if subs else trans)
                if not pool:
                    seq = None
                    break

                e = random.choice(pool)
                etype = self.action_type(e["id"]) or "transition"
                seq.append({"type": "action", "label": e["label"], "id": e["id"]})

                if etype == "submission":
                    if len(seq) >= min_items:
                        return seq  # terminal on submission
                    # too early to end
                    seq = None
                    break

                # continue to next position
                nxt = e.get("success_to", pos)
                seq.append({"type": "position", "label": self.position_label(nxt), "id": nxt})
                pos = nxt

        return None

    def positions_with_submission_paths(self, min_items=12, tries=120):
        good = []
        for pid in self.position_ids():
            seq = self.flow_to_submission(pid, min_items=min_items, tries=tries)
            if seq and seq[-1]["type"] == "action" and self.action_type(seq[-1]["id"]) == "submission":
                good.append(pid)
        return good
    
    def flow_to_submission_best(self, start_pos_id, max_items=20, min_items=4, tries=400):
        """
        Longest sequence (<= max_items) that ends on a submission ACTION.
        Sequence alternates Position -> Action -> ... and submissions are terminal.
        min_items is a soft minimum; we abort if the only option is to end too early.
        """
        if start_pos_id not in self.pos_map:
            return None

        best, best_len = None, 0

        for _ in range(tries):
            seq = [{"type": "position", "label": self.position_label(start_pos_id), "id": start_pos_id}]
            pos = start_pos_id
            valid = True

            while len(seq) < max_items:
                edges = self.edges_for(pos)
                if not edges:
                    valid = False
                    break

                trans, subs = [], []
                for e in edges:
                    (subs if (self.action_type(e["id"]) == "submission") else trans).append(e)

                need_min = len(seq) < (min_items - 1)
                must_finish = len(seq) >= (max_items - 1)

                # If we still need to grow but there are no transitions, this branch can't reach min_items
                if need_min and not trans:
                    valid = False
                    break

                # Choose action: prefer transitions while we have room; finish with a submission when near cap
                if must_finish and subs:
                    e = random.choice(subs)
                else:
                    if trans and (need_min or (len(seq) < max_items - 2 and random.random() < 0.75)):
                        e = random.choice(trans)
                    elif subs:
                        e = random.choice(subs)
                    elif trans:
                        e = random.choice(trans)
                    else:
                        valid = False
                        break

                seq.append({"type": "action", "label": e["label"], "id": e["id"]})
                if self.action_type(e["id"]) == "submission":
                    if len(seq) >= min_items:
                        if len(seq) > best_len:
                            best, best_len = list(seq), len(seq)
                    break  # terminal

                nxt = e.get("success_to", pos)
                seq.append({"type": "position", "label": self.position_label(nxt), "id": nxt})
                pos = nxt

            # try next attempt

        return best

    def positions_with_submission_paths_max(self, max_items=20, min_items=4, tries=120):
        good = []
        for pid in self.position_ids():
            seq = self.flow_to_submission_best(pid, max_items=max_items, min_items=min_items, tries=tries)
            if seq and seq[-1]["type"] == "action" and self.action_type(seq[-1]["id"]) == "submission":
                good.append(pid)
        return good

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



