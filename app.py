import json
import time
import random
import streamlit as st
from engine import Engine, Opponent, srs_grade, srs_due
import streamlit.components.v1 as components
from pyvis.network import Network

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

/* History box */
.history-box {
border: 1px solid #e6e6e6;
border-radius: 12px;
padding: 12px 14px;
margin: 0.5rem 0 0.75rem;
background: #fafafa;
}
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
    if "modal" not in st.session_state:
        st.session_state.modal = {"open": False}
    if "flowchart_context" not in st.session_state:
        st.session_state.flowchart_context = None
    if "flowchart_edge_highlight" not in st.session_state:
        st.session_state.flowchart_edge_highlight = None


def handle_flowchart_click_param():
    # New API (dict-like proxy)
    qp = getattr(st, "query_params", None)

    # Read params
    if qp is not None:
        fc_id = qp.get("fc_click")
        fc_type = qp.get("fc_type")
    else:
        # Fallback for older Streamlit
        params = st.experimental_get_query_params()
        fc_id = (params.get("fc_click") or [None])[0]
        fc_type = (params.get("fc_type") or [None])[0]

    if not fc_id or not fc_type:
        return

    # Clear the params so we don't loop
    if qp is not None:
        for k in ("fc_click", "fc_type", "page"):
            if k in st.query_params:
                del st.query_params[k]
    else:
        st.experimental_set_query_params()  # clear

    # Open the quick menu centered on the clicked node
    st.session_state.page = "flowchart"
    st.session_state.flowchart_context = {"type": fc_type, "id": fc_id}
    eng = st.session_state.engine
    if fc_type == "position":
        label = eng.position_label(fc_id)
    else:
        a = eng.action(fc_id)
        label = a["label"] if a else fc_id
    open_quick_menu(fc_type, fc_id, label)


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


def nav_to_flowchart(entity_type: str, entity_id: str):
    st.session_state.flowchart_context = {"type": entity_type, "id": entity_id}
    st.session_state.page = "flowchart"
    st.rerun()


def open_quick_menu(entity_type: str, entity_id: str, label: str):
    st.session_state.modal = {"open": True, "type": entity_type, "id": entity_id, "label": label}


def quick_menu_overlay():
    modal = st.session_state.get("modal") or {}
    if not modal.get("open"):
        return

    title_text = f'Open "{modal.get("label","")}"'

    def body():
        col1, col2, col3 = st.columns(3)
        if col1.button("See details", key="vbjj_modal_details"):
            et, eid = modal["type"], modal["id"]
            st.session_state.modal["open"] = False
            nav_to_detail("position" if et == "position" else "action", eid)
            st.stop()
        if col2.button("See flowchart", key="vbjj_modal_flow"):
            et, eid = modal["type"], modal["id"]
            st.session_state.modal["open"] = False
            a = st.session_state.engine.action(eid) if et != "position" else None
            st.session_state.flowchart_edge_highlight = a["id"] if a and a.get("type") == "transition" else None
            nav_to_flowchart(et, eid)
            st.stop()
        if col3.button("Back", key="vbjj_modal_back"):
            st.session_state.modal["open"] = False
            st.rerun()

    if hasattr(st, "dialog"):
        @st.dialog(title_text, width="small")
        def _dlg():
            body()
        _dlg()  # open the dialog
    elif hasattr(st, "experimental_dialog"):
        with st.experimental_dialog(title_text):
            body()
    else:
        # Very old Streamlit fallback: inline block (not a true overlay)
        with st.container(border=True):
            st.write(title_text)
            body()

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


def build_flowchart_html(eng, focus_type, focus_id, highlight_transition_id=None):
    # Nodes:
    # - Positions as boxes
    # - Submissions as diamonds
    # Edges:
    # - Transition: pos -> pos (labeled)
    # - Submission: pos -> submission (labeled, red)
    # - Submission success_to (if any): submission -> pos (unlabeled, dashed)
    net = Network(height="650px", width="100%", bgcolor="#ffffff", font_color="#111")
    net.barnes_hut()

    # Interaction and controls (adds +/- in the corner)
    opts = {
            "interaction": {
                "navigationButtons": True,
                "keyboard": {"enabled": True, "bindToWindow": True},
                "zoomView": True,
                "dragView": True,
            },
            "physics": {
                "solver": "forceAtlas2Based",
                "stabilization": {"enabled": True, "iterations": 600},
            },
            "nodes": {"font": {"size": 16}},
            "edges": {
                "arrows": {"to": {"enabled": True, "scaleFactor": 0.6}},
                "smooth": {"type": "dynamic"},
                "font": {"size": 12, "align": "horizontal"},
            },
        }
    net.set_options(json.dumps(opts))
    
    # Build nodes
    pos_ids = set(eng.pos_map.keys())
    for pid, pdata in eng.pos_map.items():
        nid = f"pos:{pid}"
        is_focus = (focus_type == "position" and focus_id == pid)
        net.add_node(
            nid,
            label=pdata.get("label", pid),
            title=pdata.get("label", pid),
            color="#eaf4ff",
            borderWidth=3 if is_focus else 1,
            shape="box",
            size=28 if is_focus else 20
        )

    # Only submissions are nodes; transitions are edges
    for aid, adata in eng.action_map.items():
        if adata.get("type") == "submission":
            nid = f"act:{aid}"
            is_focus = (focus_type != "position" and focus_id == aid)
            net.add_node(
                nid,
                label=adata.get("label", aid),
                title=f"Submission: {adata.get('label', aid)}",
                color="#ffeaea",
                shape="diamond",
                size=26 if is_focus else 18,
                borderWidth=3 if is_focus else 1
            )

    # Build edges
    # Transitions: pos -> pos (greenish)
    for aid, adata in eng.action_map.items():
        if adata.get("type") == "transition":
            src = adata.get("from")
            dst = adata.get("success_to")
            if not src or not dst or (src not in pos_ids) or (dst not in pos_ids):
                continue
            eid = f"tr:{aid}"
            is_high = (highlight_transition_id == aid)
            net.add_edge(
                f"pos:{src}",
                f"pos:{dst}",
                label=adata.get("label", aid),
                color="#2a7de1",
                width=4 if is_high else 1.5,
                dashes=False
            )

    # Submissions: pos -> submission (red)
    for aid, adata in eng.action_map.items():
        if adata.get("type") == "submission":
            src = adata.get("from")
            if src not in pos_ids:
                continue
            net.add_edge(
                f"pos:{src}",
                f"act:{aid}",
                label=adata.get("label", aid),
                color="#c92a2a",
                width=2
            )
            # If success_to exists, link submission -> pos (dashed, grey)
            dst = adata.get("success_to")
            if dst and dst in pos_ids:
                net.add_edge(
                    f"act:{aid}",
                    f"pos:{dst}",
                    color="#888888",
                    width=1,
                    dashes=True
                )

    # Generate HTML and inject "focus" behavior
    html = net.generate_html(notebook=False)

    # Choose a node to focus
    if focus_type == "position":
        focus_node = f"pos:{focus_id}"
    elif focus_type == "action":
        # Center on submission nodes if submission, otherwise center on the 'from' position if it was a transition
        a = eng.action(focus_id)
        if a and a.get("type") == "submission":
            focus_node = f"act:{focus_id}"
        elif a and a.get("type") == "transition":
            focus_node = f"pos:{a.get('from')}"
        else:
            # fallback
            focus_node = f"pos:{eng.position_ids()[0]}" if eng.position_ids() else None
    else:
        focus_node = f"pos:{eng.position_ids()[0]}" if eng.position_ids() else None

    if focus_node:
        script = f"""
        <script type="text/javascript">
        window.addEventListener('load', function() {{
          if (typeof network !== 'undefined') {{
            network.once('stabilizationIterationsDone', function () {{
              try {{
                network.fit({{ nodes: ['{focus_node}'], animation: true }});
                network.selectNodes(['{focus_node}']);
              }} catch(e) {{}}
            }});
          }}
        }});
        </script>
        """
        html = html.replace("</body>", script + "</body>")

    click_js = """
    <script type="text/javascript">
    window.addEventListener('load', function() {
    if (typeof network !== 'undefined') {
        network.on("click", function(params) {
        if (params.nodes && params.nodes.length > 0) {
            const nid = String(params.nodes[0]); // "pos:..." or "act:..."
            const parts = nid.split(":");
            const kind = (parts[0] === "act") ? "action" : "position";
            const id = parts.slice(1).join(":");
            try {
            // Notify parent page (Streamlit) to update query params
            window.parent.postMessage({ __vbjj_click: true, id: id, kind: kind }, "*");
            } catch (e) {
            console.warn("postMessage failed:", e);
            }
        }
        });
    }
    });
    </script>
    """
    html = html.replace("</body>", click_js + "</body>")
    return html
    

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

        # Search
        st.markdown('<div class="menu-card">', unsafe_allow_html=True)
        if st.button("Search techniques", key="go_search"):
            st.session_state.page = "search"
            st.rerun()
        st.markdown('<div class="menu-desc">Find any transition or submission and jump to details or flowchart</div>', unsafe_allow_html=True)
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
                    open_quick_menu("action", e["id"], e["label"])
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
                    open_quick_menu("action", e["id"], e["label"])
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
            open_quick_menu("position", pos_id, p['label'])

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
            open_quick_menu("position", pos_id, p["label"])

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
                    open_quick_menu("action", choice_labels[pick], pick)

    # History (max 3, newest first), boxed
    st.markdown('<div class="history-box">', unsafe_allow_html=True)
    st.markdown('<div class="section-title" style="margin-top:0;">History</div>', unsafe_allow_html=True)
    if st.session_state.sim_log:
        for item in reversed(st.session_state.sim_log[-3:]):
            st.write(f"- {eng.position_label(item['from'])} → {item['action']} → {item['outcome']} → {eng.position_label(item['to'])} ({item['notes']})")
    else:
        st.caption("No history yet")
    st.markdown('</div>', unsafe_allow_html=True)

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


def flowchart_screen():
    back_button()
    st.subheader("Flowchart")
    st.caption("Pan/zoom with touch or mouse. Use the + / − buttons in the corner to zoom.")

    eng = st.session_state.engine
    if not eng.position_ids():
        st.info("No positions available.")
        return

    ctx = st.session_state.get("flowchart_context") or {}
    ftype = ctx.get("type") or "position"
    fid = ctx.get("id")
    if not fid:
        # default to any position if nothing selected
        fid = eng.position_ids()[0]
        ftype = "position"

    html = build_flowchart_html(eng, ftype, fid, st.session_state.get("flowchart_edge_highlight"))
    components.html(html, height=650, scrolling=True)
    components.html("""
        <script>
        (function () {
        // Only add once (on the PARENT window)
        try {
            if (window.parent && !window.parent.__vbjj_listener_added) {
            window.parent.__vbjj_listener_added = true;
            window.parent.addEventListener('message', function (event) {
                var data = event.data || {};
                if (data && data.__vbjj_click) {
                try {
                    var url = new URL(window.parent.location.href);
                    url.searchParams.set('fc_click', data.id);
                    url.searchParams.set('fc_type', data.kind);
                    url.searchParams.set('page', 'flowchart');
                    // Navigate parent (triggers Streamlit rerun and your handler)
                    window.parent.location.replace(url.toString());
                } catch (e) { console.warn('URL update failed', e); }
                }
            });
            }
        } catch (e) {
            console.warn('Listener install failed', e);
        }
        })();
        </script>
        """, height=0)


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
                open_quick_menu("position", item["id"], item['label'])
            else:
                open_quick_menu("action", item["id"], item['label'])

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


def search_screen():
    back_button()
    st.subheader("Search techniques")

    eng = st.session_state.engine

    # Controls
    q = st.text_input("Search", placeholder="Type a technique name…", key="tech_search").strip().lower()
    type_opt = st.selectbox("Type", ["All", "Transitions", "Submissions"], index=0, key="tech_type")

    # Build and sort full list of actions
    acts = list(eng.action_map.values())

    # Filter by type
    if type_opt != "All":
        acts = [a for a in acts if a.get("type") == type_opt[:-1].lower()]  # "Transitions" -> "transition", "Submissions" -> "submission"

    # Filter by query (match technique label or source position label)
    if q:
        def match(a):
            return (q in a.get("label","").lower()) or (q in eng.position_label(a.get("from","")).lower())
        acts = [a for a in acts if match(a)]

    # Sort: by source position, then type (transitions first), then label
    def sort_key(a):
        return (
            eng.position_label(a.get("from","")).lower(),
            0 if a.get("type") == "transition" else 1,
            a.get("label","").lower()
        )
    acts.sort(key=sort_key)

    # Render grouped by source position
    if not acts:
        st.info("No techniques match your search.")
        return

    grp = None
    for a in acts:
        src = eng.position_label(a["from"])
        if grp != src:
            grp = src
            st.markdown(f"From {src}:")
        if st.button(f"{a['label']} ({a['type']}) →", key=f"search_{a['id']}"):
            open_quick_menu("action", a["id"], a["label"])


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
                    open_quick_menu("action", e["id"], e["label"])
        if p.get("transitions"):
            st.subheader("Transitions from here")
            for e in p["transitions"]:
                if details_button(e["label"], key=f"detail_trans_{e['id']}"):
                    open_quick_menu("action", e["id"], e["label"])

    else:  # action
        a = eng.action(eid)
        if not a:
            st.error("Technique not found.")
            return
        st.header(f"{a['label']} ({a['type']})")
        cols = st.columns(2)
        with cols[0]:
            if details_button(f"From: {eng.position_label(a['from'])}", key=f"from_pos_{a['from']}"):
                open_quick_menu("position", a["from"], eng.position_label(a["from"]))
        dest = a.get("success_to")
        if dest and dest in eng.pos_map:
            with cols[1]:
                if details_button(f"To: {eng.position_label(dest)}", key=f"to_pos_{dest}"):
                    open_quick_menu("position", dest, eng.position_label(dest))
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
    handle_flowchart_click_param()
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
    elif st.session_state.page == "flowchart":
        flowchart_screen()
    elif st.session_state.page == "search":
        search_screen()
    else:
        st.session_state.page = "menu"
        st.rerun()
    quick_menu_overlay()

if __name__ == "__main__":
    main()