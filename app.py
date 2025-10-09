import json
import time
import random
import streamlit as st
from engine import Engine, Opponent, srs_grade, srs_due

# --- App setup ---
st.set_page_config(
    page_title="Visualize BJJ",
    page_icon="🥋",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- Mobile-like CSS ---
MOBILE_CSS = """
<style>
#MainMenu, header, footer {visibility: hidden;}
.block-container { max-width: 520px; padding-top: 0.5rem; padding-bottom: 3rem; }

/* Buttons — base sizing/shape only (no colors here) */
.stButton > button {
  width: 100% !important;
  padding: 18px 20px;
  border-radius: 14px;
  font-size: 1.18rem;
  font-weight: 800;
  box-shadow: 0 1px 2px rgba(0,0,0,0.06);
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  border-width: 1px;
  border-style: solid;
}

/* Secondary (inactive) buttons — white */
.stButton > button[data-testid="baseButton-secondary"],
.stButton > button[kind="secondary"] {
  background: #ffffff !important;
  border-color: #e6e6e6 !important;
  color: #111111 !important;
}
.stButton > button[data-testid="baseButton-secondary"]:hover,
.stButton > button[kind="secondary"]:hover {
  border-color: #cfcfcf !important;
}

/* Primary (active) buttons — light blue */
.stButton > button[data-testid="baseButton-primary"],
.stButton > button[kind="primary"] {
  background: #eaf4ff !important;
  border-color: #b6dcff !important;
  color: #0b3d91 !important;
}
.stButton > button[data-testid="baseButton-primary"]:hover,
.stButton > button[kind="primary"]:hover {
  background: #d8ecff !important;
  border-color: #9ccfff !important;
}

/* Landing layout */
.menu-center { text-align: center; }
.menu-card { margin: 0.75rem 0 0.25rem; text-align: center; }
.menu-desc { margin-top: 0.35rem; color: #5a5a5a; font-size: 0.96rem; text-align: center; }

/* Back button */
.back-wrap .stButton > button {
  width: auto !important;
  padding: 8px 12px;
  font-size: 0.95rem;
  font-weight: 600;
  border-radius: 10px;
  white-space: nowrap;
}

/* Flow and simulate headings */
.flow-text h1 { font-size: 2rem; text-align: center; }
.current-pos { text-align: center; margin: 0.6rem 0 1rem; }
.current-pos .prefix { display: block; font-size: 0.95rem; font-weight: 700; color: #666; margin-bottom: 0.2rem; }
.current-pos .name { font-size: 1.5rem; font-weight: 800; }
.section-title { font-weight: 800; font-size: 1.1rem; margin: 0.8rem 0 0.25rem; }

/* Previous-positions trail shown under current item */
.flow-trail { margin-top: 0.25rem; color: #7a7a7a; font-size: 0.95rem; }
.flow-trail .item { margin-top: 0.15rem; }

/* Tagline */
.tagline { text-align: center; color: #666; margin-top: 0.25rem; margin-bottom: 1.0rem; }
</style>
"""

st.markdown(MOBILE_CSS, unsafe_allow_html=True)

@st.cache_data
def load_content():
    with open("content.json", encoding="utf-8") as f:
        return json.load(f)

def init_state():
    if "engine" not in st.session_state:
        data = load_content()
        st.session_state.engine = Engine(data)
        st.session_state.opp = Opponent(id="pressure_passer", posture=0.8, counter=0.6, label="Pressure passer")
    if "page" not in st.session_state:
        st.session_state.page = "menu"
    if "srs" not in st.session_state:
        st.session_state.srs = {}
    if "sim_pos" not in st.session_state:
        eng = st.session_state.engine
        good = eng.positions_with_submission_paths_max(max_items=20) or eng.actionable_position_ids()
        st.session_state.sim_pos = random.choice(good) if good else None
    if "sim_log" not in st.session_state:
        st.session_state.sim_log = []
    if "flow_running" not in st.session_state:
        st.session_state.flow_running = False
    if "flow_seq" not in st.session_state:
        st.session_state.flow_seq = []
    if "flow_index" not in st.session_state:
        st.session_state.flow_index = 0
    if "flow_speed" not in st.session_state: 
        st.session_state.flow_speed = 4 
    if "flow_prev_positions" not in st.session_state: 
        st.session_state.flow_prev_positions = []
    # Study: pick an initial random position
    if "study_pos" not in st.session_state:
        ids = st.session_state.engine.position_ids()
        st.session_state.study_pos = random.choice(ids) if ids else None
    # Detail routing state
    if "detail_type" not in st.session_state:
        st.session_state.detail_type = None  # "position" | "action"
    if "detail_id" not in st.session_state:
        st.session_state.detail_id = None
    if "return_page" not in st.session_state:
        st.session_state.return_page = None
    if "flow_prev_positions" not in st.session_state:
        st.session_state.flow_prev_positions = []
    if "flow_cache" not in st.session_state:
        st.session_state.flow_cache = {}  # {min_items: {start_pos_id: seq}}
    if "sim_finished" not in st.session_state:
        st.session_state.sim_finished = False
    if "sim_last_result" not in st.session_state:
        st.session_state.sim_last_result = None
    if "flow_finished" not in st.session_state:
        st.session_state.flow_finished = False
    if "sim_success_prob" not in st.session_state:
        st.session_state.sim_success_prob = 0.75  # default 75%


def go_back():
    target = st.session_state.return_page or "menu"
    st.session_state.page = target
    st.session_state.return_page = None
    st.rerun()

def back_button():
    st.markdown('<div class="back-wrap">', unsafe_allow_html=True)
    if st.button("← Back"):
        go_back()
    st.markdown('</div>', unsafe_allow_html=True)

def nav_to_detail(entity_type: str, entity_id: str):
    st.session_state.return_page = st.session_state.page
    st.session_state.detail_type = entity_type  # "position" | "action"
    st.session_state.detail_id = entity_id
    st.session_state.page = "detail"
    st.rerun()

def render_videos(videos):
    if not videos:
        return
    for v in videos:
        url = v.get("url") if isinstance(v, dict) else v
        if not url:
            continue
        st.video(url)

# Helper to render a button that clearly indicates it opens a details page
def details_button(label: str, key: str, use_container_width: bool = False):
    # Use a simple, consistent marker; emoji can shift baselines on some devices
    return st.button(f"{label} →", key=key, use_container_width=use_container_width)


def get_precomputed_flows(max_items: int):
    cache = st.session_state.flow_cache.get(max_items)
    if cache is not None:
        return cache
    eng = st.session_state.engine
    starts = eng.positions_with_submission_paths_max(max_items=max_items)
    seq_map = {}
    for pid in starts:
        seq = eng.flow_to_submission_best(pid, max_items=max_items)
        if seq:
            seq_map[pid] = seq
    st.session_state.flow_cache[max_items] = seq_map
    return seq_map
    

def menu_screen():
    # Center column layout: 1–4–1 so buttons span ~2/3 width
    cols = st.columns([1, 4, 1])
    with cols[1]:
        st.markdown('<div class="menu-center">', unsafe_allow_html=True)
        st.markdown('<h1 style="margin-bottom: 0.25rem;">Visualize BJJ</h1>', unsafe_allow_html=True)
        st.markdown('<div class="tagline">Use visualization to study what you&apos;ve learned</div>', unsafe_allow_html=True)

        # Study
        st.markdown('<div class="menu-card">', unsafe_allow_html=True)
        if st.button("Study", key="go_study"):
            st.session_state.page = "study"
            st.rerun()
        st.markdown('<div class="menu-desc">Cycle through positions while testing your knowledge of key points, transitions, and submissions</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Simulate
        st.markdown('<div class="menu-card">', unsafe_allow_html=True)
        if st.button("Simulate", key="go_sim"):
            eng = st.session_state.engine
            cands = eng.actionable_position_ids()
            st.session_state.sim_pos = random.choice(cands) if cands else None
            st.session_state.sim_finished = False
            st.session_state.sim_last_result = None
            st.session_state.page = "simulate"
            st.rerun()
        st.markdown('<div class="menu-desc">Fight in a mental match by choosing transitions and submissions (and watch out for counters and defenses!)</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Flow
        st.markdown('<div class="menu-card">', unsafe_allow_html=True)
        if st.button("Flow", key="go_flow"):
            st.session_state.page = "flow"
            st.rerun()
        st.markdown('<div class="menu-desc">Visualize yourself in an AI-generated match</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

def study_screen():
    back_button()
    st.subheader("Study")

    eng = st.session_state.engine
    pos_id = st.session_state.study_pos
    if not pos_id:
        st.error("No positions available.")
        return

    p = eng.position(pos_id)

    # Centered header like Simulate
    st.markdown(
        f'''
        <div class="current-pos">
        <span class="prefix">Current position:</span>
        <div class="name">{p["label"]}</div>
        </div>
        ''',
        unsafe_allow_html=True
    )

    # — Reveal controls (stacked). No dividers between them —
    
    # Key points toggle
    keys_key = f"reveal_keys_{pos_id}"
    keys_shown = st.session_state.get(keys_key, False)
    keys_btn_label = "Hide key points" if keys_shown else "Show key points"
    if st.button(keys_btn_label, key=f"btn_keys_{pos_id}", type=("primary" if keys_shown else "secondary")):
        st.session_state[keys_key] = not keys_shown
        st.rerun()

    if st.session_state.get(keys_key):
        keys = p.get("key_points", []) or []
        if keys:
            st.write("Key points:")
            for k in keys:
                st.write(f"  • {k}")
        else:
            st.info("No key points listed.")

    # Submissions toggle
    subs_key = f"reveal_subs_{pos_id}"
    subs_shown = st.session_state.get(subs_key, False)
    subs_btn_label = "Hide submissions" if subs_shown else "Show submissions"
    if st.button(subs_btn_label, key=f"btn_subs_{pos_id}", type=("primary" if subs_shown else "secondary")):
        st.session_state[subs_key] = not subs_shown
        st.rerun()

    if st.session_state.get(subs_key):
        subs = p.get("submissions", []) or []
        if subs:
            st.write("Submissions:")
            for e in subs:
                if details_button(e["label"], key=f"sub_{e['id']}"):
                    nav_to_detail("action", e["id"])
        else:
            st.info("No submissions listed.")

    # Transitions toggle
    trans_key = f"reveal_trans_{pos_id}"
    trans_shown = st.session_state.get(trans_key, False)
    trans_btn_label = "Hide transitions" if trans_shown else "Show transitions"
    if st.button(trans_btn_label, key=f"btn_trans_{pos_id}", type=("primary" if trans_shown else "secondary")):
        st.session_state[trans_key] = not trans_shown
        st.rerun()

    if st.session_state.get(trans_key):
        trans = p.get("transitions", []) or []
        if trans:
            st.write("Transitions:")
            for e in trans:
                if details_button(e["label"], key=f"trans_{e['id']}"):
                    nav_to_detail("action", e["id"])
        else:
            st.info("No transitions listed.")

    # Single separator before bottom controls
    st.divider()

    # Bottom-right controls: spacer + two wide columns so labels don't wrap
    spacer, col_next, col_details = st.columns([4, 120, 120])
    with col_next:
        if st.button("Next position", key="study_next", use_container_width=True):
            ids = eng.position_ids()
            if len(ids) > 1:
                choices = [i for i in ids if i != pos_id]
                st.session_state.study_pos = random.choice(choices)
            else:
                st.session_state.study_pos = pos_id
            st.rerun()
    with col_details:
        if details_button(f"Details: {p['label']}", key=f"pos_detail_{pos_id}", use_container_width=True):
            nav_to_detail("position", pos_id)

    # Due reviews summary (kept; grading sliders removed)
    due_positions = len(srs_due(st.session_state.srs, "P:"))
    due_subs = len(srs_due(st.session_state.srs, "SU:"))
    due_transitions = len(srs_due(st.session_state.srs, "TR:"))
    st.caption(f"Due reviews — Key points: {due_positions} • Submissions: {due_subs} • Transitions: {due_transitions}")

def simulate_screen():
    back_button()
    st.subheader("Simulate")
    if st.session_state.get("sim_finished"):
        st.success("You won! Let's go again.")
    st.write("Make a choice. See the consequence. Occasionally defend an opponent attack.")

    eng = st.session_state.engine
    opp = st.session_state.opp

    # Ensure we start from a position that has actions
    pos_id = st.session_state.sim_pos
    if (not pos_id) or (not eng.edges_for(pos_id)):
        cands = eng.actionable_position_ids()
        st.session_state.sim_pos = random.choice(cands) if cands else None
        st.session_state.sim_finished = False
        st.session_state.sim_last_result = None
        pos_id = st.session_state.sim_pos

    if not pos_id or pos_id not in eng.pos_map:
        st.warning("Select a start position below to begin.")
    else:
        p = eng.position(pos_id)
        st.markdown(
            f'''
            <div class="current-pos">
            <span class="prefix">Current position:</span>
            <div class="name">{p["label"]}</div>
            </div>
            ''',
            unsafe_allow_html=True
        )
        if details_button(f"Details about {eng.position_label(pos_id)}", key=f"sim_pos_detail_{pos_id}"):
            nav_to_detail("position", pos_id)

        # Opponent attack chance (before your action)
        atk = eng.maybe_opponent_attack(pos_id, opp)
        if atk:
            st.write(f"Opponent threatens: {atk.get('label') or atk['id']}")
            if st.button("Reveal defense", key=f"reveal_def_{atk['id']}"):
                for step in atk.get("defense", []):
                    st.write(f"  • {step}")

        # Choices
        edges = eng.edges_for(pos_id)
        if not edges:
            st.info("No actions available here.")
        else:
            choice_labels = {e["label"]: e["id"] for e in edges}
            pick = st.radio("Choose your action", list(choice_labels.keys()), key=f"choice_{pos_id}")
            cols = st.columns(2)
            if cols[0].button("Go", key=f"go_{pos_id}"):
                result = eng.simulate_step(
                            pos_id,
                            choice_labels[pick],
                            opp,
                            success_prob=st.session_state.sim_success_prob,
                        )
                st.session_state.sim_log.append({
                "from": pos_id,
                "action": pick,
                "outcome": result["outcome"],
                "notes": result["notes"],
                "to": result["to"]
            })
                if result["outcome"] == "submitted":
                    st.session_state.sim_finished = True
                    # keep current position; do not clear sim_pos
                    st.rerun()
                else:
                    st.session_state.sim_pos = result["to"]
                    st.success(f"{result['outcome'].capitalize()}: {result['notes']}")
                    st.rerun()
            with cols[1]:
                if details_button(f"Details: {pick}", key=f"detail_choice_{pos_id}"):
                    nav_to_detail("action", choice_labels[pick])

    # Reset controls
    ids = eng.positions_with_submission_paths_max(max_items=20) or eng.actionable_position_ids()
    if ids:
        pick_reset = st.selectbox("Reset to position", ids, format_func=eng.position_label, key="reset_pick")
        if st.button("Reset", key="reset_btn"):
            st.session_state.sim_pos = pick_reset
            st.session_state.sim_finished = False
            st.session_state.sim_last_result = None
            st.session_state.sim_log = []
            st.rerun()

    if st.button("Clear history", key="clear_log"):
        st.session_state.sim_log = []
        st.rerun()

    # History (newest first)
    if st.session_state.sim_log:
        st.markdown('<div class="section-title">History</div>', unsafe_allow_html=True)
        for item in reversed(st.session_state.sim_log[-10:]):
            st.write(f"- {eng.position_label(item['from'])} → {item['action']} → {item['outcome']} → {eng.position_label(item['to'])} ({item['notes']})")


def flow_screen():
    back_button()
    st.subheader("Flow")
    st.write("Position → Action → Position. Imagine you’re doing each step first-person.")
    if st.session_state.get("flow_finished"):
        st.success("You won! Let's go again.")

    eng = st.session_state.engine
    all_ids = eng.position_ids()
    if not all_ids:
        st.warning("No positions available.")
        return

    # Controls
    len_options = [10, 12, 15, 18, 20, 25, 30, 40, 50, 60]
    length = st.selectbox("Number of items", len_options, index=len_options.index(20), key="flow_len")
    speed_options = [4, 5, 6, 7, 8, 9, 10, 12, 15]
    speed = st.selectbox("Seconds per item", speed_options, index=0, key="flow_speed")

    # Precompute valid starts and sequences for selected length
    seq_map = get_precomputed_flows(length)
    good_starts = list(seq_map.keys())
    if not good_starts:
        st.info("No submission-ending flows under this maximum length. Try increasing 'Number of items'.")
        return

    start = st.selectbox("Start position", good_starts, format_func=eng.position_label, key="flow_start")

    cols = st.columns(2)
    if cols[0].button("Start flow", key="start_flow"):
        st.session_state.flow_running = True
        st.session_state.flow_finished = False
        st.session_state.flow_seq = seq_map[start]
        st.session_state.flow_index = 0
        st.session_state.flow_prev_positions = []
        st.rerun()
    if cols[1].button("Stop", key="stop_flow"):
        st.session_state.flow_running = False
        st.rerun()

    # Always render the current item if a sequence exists
    seq = st.session_state.flow_seq
    if seq:
        i = min(st.session_state.flow_index, len(seq) - 1)
        item = seq[i]

        st.markdown('<div class="flow-text">', unsafe_allow_html=True)
        st.header(f"{item['type'].capitalize()}: {item['label']}")
        st.markdown('</div>', unsafe_allow_html=True)

        # Trail under the current item (previous positions)
        trail = st.session_state.get("flow_prev_positions", [])
        if trail:
            html = '<div class="flow-trail">' + ''.join(f'<div class="item">{t}</div>' for t in trail[:2]) + '</div>'
            st.markdown(html, unsafe_allow_html=True)

        # Details for whatever is currently shown
        label = f"Details for {item['label']}"
        btn_key = f"flow_detail_{i}_{item['type']}_{item['id']}"
        if details_button(label, key=btn_key, use_container_width=True):
            if item["type"] == "position":
                nav_to_detail("position", item["id"])
            else:
                nav_to_detail("action", item["id"])

        # Auto-advance only while running
        if st.session_state.flow_running:
            time.sleep(st.session_state.flow_speed)
            if i < len(seq) - 1:
                # Update trail when leaving a position frame
                if item["type"] == "position":
                    prev = st.session_state.get("flow_prev_positions", [])
                    st.session_state.flow_prev_positions = ([item["label"]] + prev)[:2]
                st.session_state.flow_index += 1
                st.rerun()
            else:
                # Finished: freeze on last frame and show banner
                st.session_state.flow_running = False
                st.session_state.flow_finished = True
                st.session_state.flow_index = len(seq) - 1
                st.rerun()


def detail_screen():
    back_button()
    eng = st.session_state.engine
    etype = st.session_state.detail_type
    eid = st.session_state.detail_id
    if not etype or not eid:
        st.error("Nothing selected.")
        return

    if etype == "position":
        p = eng.position(eid)
        st.header(p["label"])
        render_videos(p.get("videos"))
        if p.get("key_points"):
            st.subheader("Key points")
            for k in p["key_points"]:
                st.write(f"• {k}")
        if p.get("hazards"):
            st.subheader("Hazards")
            for h in p["hazards"]:
                st.write(f"• {h}")
        if p.get("objectives"):
            st.subheader("Objectives")
            for o in p["objectives"]:
                st.write(f"• {o}")
        if p.get("submissions"):
            st.subheader("Submissions from here")
            for e in p["submissions"]:
                if details_button(e["label"], key=f"detail_sub_{e['id']}"):
                    nav_to_detail("action", e["id"])
        if p.get("transitions"):
            st.subheader("Transitions from here")
            for e in p["transitions"]:
                if details_button(e["label"], key=f"detail_trans_{e['id']}"):
                    nav_to_detail("action", e["id"])

    else:  # action
        a = eng.action(eid)
        if not a:
            st.error("Technique not found.")
            return
        st.header(f"{a['label']} ({a['type']})")
        cols = st.columns(2)
        with cols[0]:
            if details_button(f"From: {eng.position_label(a['from'])}", key=f"from_pos_{a['from']}"):
                nav_to_detail("position", a["from"])
        dest = a.get("success_to")
        if dest and dest in eng.pos_map:
            with cols[1]:
                if details_button(f"To: {eng.position_label(dest)}", key=f"to_pos_{dest}"):
                    nav_to_detail("position", dest)
        render_videos(a.get("videos"))
        if a.get("keys"):
            st.subheader("Keys")
            for k in a["keys"]:
                st.write(f"• {k}")
        if a.get("reasons"):
            st.subheader("When to use it")
            for r in a["reasons"]:
                st.write(f"• {r}")
        if a.get("steps"):
            st.subheader("Steps")
            for s in a["steps"]:
                st.write(f"• {s}")
        if a.get("counters"):
            st.subheader("Common counters")
            for c in a["counters"]:
                txt = c.get("trigger", "")
                to = c.get("result_position")
                line = f"- {txt}" if txt else "- Counter"
                if to and to in eng.pos_map:
                    line += f" → {eng.position_label(to)}"
                st.write(line)

def sidebar():
    st.sidebar.header("Settings")

    # Simulate
    st.sidebar.subheader("Simulate")
    choice = st.sidebar.selectbox(
        "Chances of transition/submission success",
        ["50%", "75%", "100%"],
        index=1,  # default 75%
    )
    st.session_state.sim_success_prob = int(choice.strip("%")) / 100.0

    st.sidebar.divider()
    st.sidebar.markdown("Tips: Tap items to open details. Videos embed from your CSV links.")


def main():
    init_state()
    if "flow_cache_version" not in st.session_state or st.session_state.flow_cache_version != 3:
        st.session_state.flow_cache = {}
        st.session_state.flow_cache_version = 3
    sidebar()
    if st.session_state.page == "menu":
        menu_screen()
    elif st.session_state.page == "study":
        study_screen()
    elif st.session_state.page == "simulate":
        simulate_screen()
    elif st.session_state.page == "flow":
        flow_screen()
    elif st.session_state.page == "detail":
        detail_screen()
    else:
        st.session_state.page = "menu"
        st.rerun()

if __name__ == "__main__":
    main()