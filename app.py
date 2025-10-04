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

/* Buttons */
.stButton > button {
  width: 100% !important;
  padding: 18px 20px;
  border-radius: 14px;
  font-size: 1.18rem;
  font-weight: 800;
  border: 1px solid #e6e6e6;
  background: white;
  color: #111;
  box-shadow: 0 1px 2px rgba(0,0,0,0.06);
}
.stButton > button:hover { border-color: #cfcfcf; }

/* Landing layout */
.menu-center { text-align: center; }
.menu-card { margin: 0.75rem 0 0.25rem; text-align: center; }
.menu-desc { margin-top: 0.35rem; color: #5a5a5a; font-size: 0.96rem; text-align: center; }

/* Back button */
.back-wrap .stButton > button {
  width: auto !important; padding: 8px 12px; font-size: 0.95rem; font-weight: 600;
  border-radius: 10px; white-space: nowrap;
}

/* Flow and simulate headings */
.flow-text h1 { font-size: 2rem; text-align: center; }
.current-pos { text-align: center; margin: 0.6rem 0 1rem; }
.current-pos .prefix { display: block; font-size: 0.95rem; font-weight: 700; color: #666; margin-bottom: 0.2rem; }
.current-pos .name { font-size: 1.5rem; font-weight: 800; }
.section-title { font-weight: 800; font-size: 1.1rem; margin: 0.8rem 0 0.25rem; }

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
        ids = st.session_state.engine.position_ids()
        st.session_state.sim_pos = ids[0] if ids else None
    if "sim_log" not in st.session_state:
        st.session_state.sim_log = []
    if "flow_running" not in st.session_state:
        st.session_state.flow_running = False
    if "flow_seq" not in st.session_state:
        st.session_state.flow_seq = []
    if "flow_index" not in st.session_state:
        st.session_state.flow_index = 0
    if "flow_speed" not in st.session_state:
        st.session_state.flow_speed = 10
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

def grade_scaled_and_store(card_prefix: str, pos_id: str, recalled_count: int, total_count: int, slider_key: str):
    if total_count <= 0:
        return
    default_val = min(max(total_count // 2, 0), total_count)
    val = st.slider(f"Grade your recall (0–{total_count})", 0, total_count, default_val, key=slider_key)
    grade_0_5 = int(round((val / total_count) * 5))
    srs_grade(st.session_state.srs, f"{card_prefix}:{pos_id}", grade_0_5)

def study_screen():
    back_button()
    st.subheader("Study")

    eng = st.session_state.engine
    pos_id = st.session_state.study_pos
    if not pos_id:
        st.error("No positions available.")
        return

    p = eng.position(pos_id)
    st.header(p["label"])
    if st.button(f"Details: {p['label']}", key=f"pos_detail_{pos_id}"):
        nav_to_detail("position", pos_id)

    # Key points
    if st.button("Show key points", key=f"btn_keys_{pos_id}"):
        st.session_state[f"reveal_keys_{pos_id}"] = True
    if st.session_state.get(f"reveal_keys_{pos_id}"):
        keys = p.get("key_points", [])
        if keys:
            st.write("Key points:")
            for k in keys:
                st.write(f"  • {k}")
            grade_scaled_and_store("P", pos_id, 0, len(keys), f"grade_keys_{pos_id}")
        else:
            st.info("No key points listed.")
    st.divider()

    # Submissions
    if st.button("Show submissions", key=f"btn_subs_{pos_id}"):
        st.session_state[f"reveal_subs_{pos_id}"] = True
    if st.session_state.get(f"reveal_subs_{pos_id}"):
        subs = p.get("submissions", []) or []
        if subs:
            st.write("Submissions:")
            for e in subs:
                if st.button(e["label"], key=f"sub_{e['id']}"):
                    nav_to_detail("action", e["id"])
            grade_scaled_and_store("SU", pos_id, 0, len(subs), f"grade_subs_{pos_id}")
        else:
            st.info("No submissions listed.")
    st.divider()

    # Transitions
    if st.button("Show transitions", key=f"btn_trans_{pos_id}"):
        st.session_state[f"reveal_trans_{pos_id}"] = True
    if st.session_state.get(f"reveal_trans_{pos_id}"):
        trans = p.get("transitions", []) or []
        if trans:
            st.write("Transitions:")
            for e in trans:
                if st.button(e["label"], key=f"trans_{e['id']}"):
                    nav_to_detail("action", e["id"])
            grade_scaled_and_store("TR", pos_id, 0, len(trans), f"grade_trans_{pos_id}")
        else:
            st.info("No transitions listed.")
    st.divider()

    if st.button("Next position", key="study_next"):
        ids = eng.position_ids()
        if len(ids) > 1:
            choices = [i for i in ids if i != pos_id]
            st.session_state.study_pos = random.choice(choices)
        else:
            st.session_state.study_pos = pos_id
        st.rerun()

    due_positions = len(srs_due(st.session_state.srs, "P:"))
    due_subs = len(srs_due(st.session_state.srs, "SU:"))
    due_transitions = len(srs_due(st.session_state.srs, "TR:"))
    st.caption(f"Due reviews — Key points: {due_positions} • Submissions: {due_subs} • Transitions: {due_transitions}")

def simulate_screen():
    back_button()
    st.subheader("Simulate")
    st.write("Make a choice. See the consequence. Occasionally defend an opponent attack.")

    eng = st.session_state.engine
    opp = st.session_state.opp

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
        if st.button("Details about current position", key=f"sim_pos_detail_{pos_id}"):
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
                result = eng.simulate_step(pos_id, choice_labels[pick], opp)
                st.session_state.sim_log.append({
                    "from": pos_id,
                    "action": pick,
                    "outcome": result["outcome"],
                    "notes": result["notes"],
                    "to": result["to"]
                })
                st.session_state.sim_pos = result["to"]
                st.success(f"{result['outcome'].capitalize()}: {result['notes']}")
                st.rerun()
            if cols[1].button(f"Details: {pick}", key=f"detail_choice_{pos_id}"):
                nav_to_detail("action", choice_labels[pick])

    # Reset controls
    ids = eng.position_ids()
    if ids:
        pick_reset = st.selectbox("Reset to position", ids, format_func=eng.position_label, key="reset_pick")
        if st.button("Reset", key="reset_btn"):
            st.session_state.sim_pos = pick_reset
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
    st.write("Position → Action → Position every N seconds. Imagine you’re doing each step first-person.")

    eng = st.session_state.engine
    ids = eng.position_ids()
    if not ids:
        st.warning("No positions available.")
        return

    start = st.selectbox("Start position", ids, format_func=eng.position_label, index=0, key="flow_start")
    length = st.slider("Number of items", 10, 60, 20, key="flow_len")
    speed = st.slider("Seconds per item", 4, 15, st.session_state.flow_speed, key="flow_speed")

    cols = st.columns(2)
    if cols[0].button("Start flow", key="start_flow"):
        st.session_state.flow_running = True
        st.session_state.flow_seq = eng.flow_sequence(start, length)
        st.session_state.flow_index = 0
        st.rerun()
    if cols[1].button("Stop", key="stop_flow"):
        st.session_state.flow_running = False
        st.rerun()

    placeholder = st.empty()
    if st.session_state.flow_running and st.session_state.flow_seq:
        i = st.session_state.flow_index % len(st.session_state.flow_seq)
        item = st.session_state.flow_seq[i]
        with placeholder.container():
            st.markdown('<div class="flow-text">', unsafe_allow_html=True)
            st.header(f"{item['type'].capitalize()}: {item['label']}")
            st.markdown('</div>', unsafe_allow_html=True)
            if st.button("Details for current item", key=f"flow_detail_{i}"):
                if item["type"] == "position":
                    nav_to_detail("position", item["id"])
                else:
                    nav_to_detail("action", item["id"])
        time.sleep(st.session_state.flow_speed)
        st.session_state.flow_index += 1
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
                if st.button(e["label"], key=f"detail_sub_{e['id']}"):
                    nav_to_detail("action", e["id"])
        if p.get("transitions"):
            st.subheader("Transitions from here")
            for e in p["transitions"]:
                if st.button(e["label"], key=f"detail_trans_{e['id']}"):
                    nav_to_detail("action", e["id"])

    else:  # action
        a = eng.action(eid)
        if not a:
            st.error("Technique not found.")
            return
        st.header(f"{a['label']} ({a['type']})")
        cols = st.columns(2)
        with cols[0]:
            if st.button(f"From: {eng.position_label(a['from'])}", key=f"from_pos_{a['from']}"):
                nav_to_detail("position", a["from"])
        dest = a.get("success_to")
        if dest and dest in eng.pos_map:
            with cols[1]:
                if st.button(f"To: {eng.position_label(dest)}", key=f"to_pos_{dest}"):
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
    st.sidebar.write("Opponent profile:")
    label = st.sidebar.selectbox("Style", ["Pressure passer", "Balanced"], index=0)
    if label == "Pressure passer":
        st.session_state.opp = Opponent(id="pressure_passer", posture=0.8, counter=0.6, label=label)
    else:
        st.session_state.opp = Opponent(id="balanced", posture=0.6, counter=0.5, label=label)
    st.sidebar.divider()
    st.sidebar.markdown("Tips: Tap items to open details. Videos embed from your CSV links.")

def main():
    init_state()
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