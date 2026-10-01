import html
import json
import time
import random
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from streamlit_js_eval import streamlit_js_eval

# Page config
st.set_page_config(page_title="Claude Certification Mock", page_icon="🧠", layout="centered")

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        /* Background and text colors come from the theme (.streamlit/config.toml).
           Don't force a background here: on iOS dark mode it left white text on a light background. */
        html, body, [class*="stApp"] {
            font-family: 'Inter', sans-serif;
        }
        .stApp {
            max-width: 1200px;
            margin: 0 auto;
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        h1 {
            font-size: 3rem !important;
            line-height: 1.15 !important;
            letter-spacing: -0.04em;
            margin-bottom: 0.5rem !important;
        }
        h3 {
            font-size: 1.5rem !important;
            line-height: 1.4 !important;
        }
        .stButton > button {
            border-radius: 12px;
            border: 1px solid rgba(49, 51, 63, 0.15);
            font-weight: 600;
            transition: 0.2s ease;
        }
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        }
        .stSuccess, .stError, .stWarning, .stInfo {
            border-radius: 12px;
        }
        .stProgress > div > div {
            background: linear-gradient(90deg, #6b8cff, #7d5cf4);
        }
        .stRadio > div {
            gap: 0.5rem;
        }
        .q-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
            margin: 0.25rem 0 0.5rem;
        }
        .q-tag {
            font-size: 0.78rem;
            font-weight: 600;
            padding: 0.15rem 0.6rem;
            border-radius: 999px;
            line-height: 1.5;
        }
        .q-tag.scenario { background: #e6ecff; color: #2b3f99; }
        .q-tag.domain { background: #efe6ff; color: #5a2d9c; }
        .q-tag.topic { background: #e9f5ee; color: #1f6b3d; }
        .stCheckbox {
            padding: 0.15rem 0;
        }
        /* Mobile tweaks */
        @media (max-width: 640px) {
            .block-container {
                padding-top: 1rem;
                padding-left: 1rem;
                padding-right: 1rem;
            }
            h1 {
                font-size: 1.9rem !important;
            }
            h3 {
                font-size: 1.15rem !important;
            }
            .stButton > button {
                width: 100%;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- 1. Cached data loading ---
@st.cache_data
def load_questions(path_str: str):
    path = Path(path_str)
    if not path.exists():
        return None  # Fail soft

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if not isinstance(data, list):
        raise ValueError("The JSON file must contain a list of questions.")
        
    # Validation and normalization
    for q in data:
        if not all(k in q for k in ("question", "options", "answer_index")):
            continue  # Skip malformed questions
            
        # Always normalize answer_index to a list
        if isinstance(q["answer_index"], int):
            q["answer_index"] = [q["answer_index"]]
            
    return data

# --- 2. State management ---
ss = st.session_state
defaults = {
    "started": False, "index": 0, "score": 0, 
    "answers": [], "order": [], "t0": None, 
    "current_q_answered": False,
    "user_selection": None
}
for k, v in defaults.items():
    ss.setdefault(k, v)

# --- 3. Sidebar ---
DEFAULT_JSON_FILE = "questions.json"


def resolve_json_path(candidate: str) -> str:
    if candidate and Path(candidate).exists():
        return candidate
    if Path(DEFAULT_JSON_FILE).exists():
        return DEFAULT_JSON_FILE
    return candidate or DEFAULT_JSON_FILE


st.sidebar.header("⚙️ Settings")
json_path = st.sidebar.text_input("JSON path", DEFAULT_JSON_FILE)
limit = st.sidebar.number_input("Question limit (0 = all)", min_value=0, value=0, step=1)
shuffle_qs = st.sidebar.checkbox("🔀 Shuffle questions", value=False)
immediate_feedback = st.sidebar.checkbox("👀 Instant feedback", value=True, help="Show the correct answer right after you answer.")

# Syllabus filters (exam scenario and domain)
_all_qs = load_questions(resolve_json_path(json_path)) or []
SCENARIOS = list(dict.fromkeys(q["scenario"] for q in _all_qs if q.get("scenario")))
DOMAINS = sorted({q["domain"] for q in _all_qs if q.get("domain")})
st.sidebar.subheader("📚 Syllabus")
sel_scenarios = st.sidebar.multiselect("Scenarios", SCENARIOS, placeholder="All")
sel_domains = st.sidebar.multiselect("Domains", DOMAINS, placeholder="All")

if st.sidebar.button("🔄 Restart quiz", type="primary"):
    for k in defaults.keys():
        del ss[k]
    ss["_clear_ls"] = ss["_resume_dismissed"] = True
    st.rerun()

# --- 4. Quiz logic ---
def start_quiz():
    resolved_path = resolve_json_path(json_path)
    qs = load_questions(resolved_path)
    if qs is None:
        st.error(f"File not found: {resolved_path}")
        return

    # Copy so the cached data isn't mutated
    qs = [dict(q, _src=i) for i, q in enumerate(qs)]  # _src: original position, used to save progress

    # Syllabus filters (empty = all)
    if sel_scenarios:
        qs = [q for q in qs if q.get("scenario") in sel_scenarios]
    if sel_domains:
        qs = [q for q in qs if q.get("domain") in sel_domains]
    
    if shuffle_qs:
        random.shuffle(qs)
        
    if limit and limit > 0:
        qs = qs[:limit]

    if not qs:
        st.warning("No questions match the current settings.")
        return

    ss.order = qs
    ss.started = True
    ss.index = 0
    ss.score = 0
    ss.answers = []
    ss.t0 = time.time()
    ss.current_q_answered = False
    ss.user_selection = None
    st.rerun()

def escape_markdown(text: str) -> str:
    # Escape '_' outside `code` so it isn't rendered as italics
    parts = text.split("`")
    return "`".join(p if i % 2 else p.replace("_", r"\_") for i, p in enumerate(parts))

def submit_answer(q, choices):
    # Grade the answer
    correct_indices = set(q["answer_index"])
    user_indices = set(choices) if choices is not None else set()
    is_correct = (correct_indices == user_indices) and (choices is not None)
    
    if ss.index < len(ss.answers):
        prev = ss.answers[ss.index]
        if prev["correct"]:
            ss.score -= 1  # remove the previous point

    answer_record = {
        "question": q["question"],
        "chosen": choices,
        "correct": is_correct,
        "correct_index": q["answer_index"],
        "options": q["options"],
        "explanation": q.get("explanation", "")
    }

    if ss.index < len(ss.answers):
        ss.answers[ss.index] = answer_record
    else:
        ss.answers.append(answer_record)

    if is_correct:
        ss.score += 1
        
    ss.current_q_answered = True
    ss.user_selection = choices  # Keep it to show in the UI

def next_question():
    ss.index += 1
    ss.current_q_answered = False
    ss.user_selection = None
    st.rerun()

def prev_question():
    if ss.index > 0:
        ss.index -= 1
        ss.current_q_answered = False  # back to edit mode
        # restore the previous selection, if any
        if ss.index < len(ss.answers):
            ss.user_selection = ss.answers[ss.index]["chosen"]
        else:
            ss.user_selection = None
        st.rerun()

# --- 5. Results ---
def render_results():
    elapsed = time.time() - ss.t0 if ss.t0 else 0.0
    total = len(ss.order)
    pct = (ss.score/total)*100 if total else 0

    st.balloons()
    st.title("📊 Final results")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Score", f"{ss.score}/{total}")
    c2.metric("Percentage", f"{pct:.1f}%")
    c3.metric("Time", f"{elapsed:.1f} s")

    # Score by syllabus domain, to see what to review
    by_domain = {}
    for i, ans in enumerate(ss.answers):
        dom = ss.order[i].get("domain", "No domain")
        ok, n = by_domain.get(dom, (0, 0))
        by_domain[dom] = (ok + ans["correct"], n + 1)
    if by_domain:
        st.subheader("📚 By domain")
        for dom, (ok, n) in sorted(by_domain.items(), key=lambda kv: kv[1][0] / kv[1][1]):
            st.markdown(f"**{dom}** · {ok}/{n} ({ok / n:.0%})")
            st.progress(ok / n)

    with st.expander("🔍 Detailed review", expanded=True):
        for i, ans in enumerate(ss.answers):
            color = "green" if ans["correct"] else "red"
            icon = "✅" if ans["correct"] else "❌"
            if ans["chosen"] is None:
                icon = "⏭️ (Skipped)"
                color = "gray"
                
            st.markdown(f":{color}[**{i+1}. {ans['question']}**]")
            src = ss.order[i]
            if src.get("topic"):
                st.caption(f"📚 {src.get('domain', '')} · {src['topic']}")
            st.write(f"Status: {icon}")
            
            correct_txt = [ans['options'][idx] for idx in ans['correct_index']]
            st.caption(f"Correct answer: **{', '.join(correct_txt)}**")
            
            if ans["explanation"]:
                with st.expander("Explanation", expanded=True):
                    st.write(ans["explanation"])
            st.divider()

    if st.button("Back to start"):
        for k in defaults.keys():
            del ss[k]
        ss["_clear_ls"] = ss["_resume_dismissed"] = True
        st.rerun()

# --- 5b. Saved progress (URL + browser storage) ---
# st.session_state lives on the server and is lost if Safari suspends the tab,
# the page reloads or the app restarts. So progress is also saved in the URL
# (?o=order&i=index&a=answers&t=start) and in localStorage, and restored on return.
def encode_answers() -> str:
    return ".".join(
        "s" if ans["chosen"] is None else "+".join(map(str, ans["chosen"]))
        for ans in ss.answers
    )


def restore_from_url(qp=None):
    """Restore progress from the URL, or from a dict (the progress saved in the browser)."""
    qp = st.query_params if qp is None else qp
    if ss.started or "o" not in qp:
        return False
    try:
        data = load_questions(resolve_json_path(json_path))
        order = [dict(data[int(x)], _src=int(x)) for x in qp["o"].split(".")]
        index = int(qp.get("i", 0))
        answers, score = [], 0
        for pos, raw in enumerate(filter(None, qp.get("a", "").split("."))):
            q = order[pos]
            chosen = None if raw == "s" else [int(c) for c in raw.split("+")]
            if chosen is not None and any(c >= len(q["options"]) for c in chosen):
                raise ValueError("option out of range")
            correct = chosen is not None and set(chosen) == set(q["answer_index"])
            score += correct
            answers.append({
                "question": q["question"],
                "chosen": chosen,
                "correct": correct,
                "correct_index": q["answer_index"],
                "options": q["options"],
                "explanation": q.get("explanation", ""),
            })
        if not order or not 0 <= index <= len(order) or len(answers) > len(order):
            raise ValueError("invalid progress")
    except (ValueError, IndexError, KeyError, TypeError):
        st.query_params.clear()  # old or incompatible URL: start over
        return False

    ss.order = order
    ss.started = True
    ss.index = index
    ss.answers = answers
    ss.score = score
    ss.t0 = float(qp.get("t", time.time()))
    ss.current_q_answered = index < len(answers)
    ss.user_selection = answers[index]["chosen"] if index < len(answers) else None
    return True


LS_KEY = "ccarf_progress"  # localStorage key for saved progress


def ls_write(js: str):
    """Run JS in the browser without triggering a rerun (write-only)."""
    snippet = f"<script>try {{ {js} }} catch (e) {{}}</script>"
    if hasattr(st, "iframe"):  # newer Streamlit: components.html is deprecated
        st.iframe(snippet, height=1)
    else:
        components.html(snippet, height=0)


def sync_url():
    if ss.started:
        params = {
            "o": ".".join(str(q["_src"]) for q in ss.order),
            "i": str(ss.index),
            "a": encode_answers(),
            "t": str(int(ss.t0 or time.time())),
        }
        if st.query_params.to_dict() != params:
            st.query_params.from_dict(params)
        # Copy to browser storage, so progress can be resumed even without the URL
        ls_write(f"localStorage.setItem({json.dumps(LS_KEY)}, {json.dumps(json.dumps(params))});")
    else:
        if st.query_params:
            st.query_params.clear()
        if ss.pop("_clear_ls", False):
            ls_write(f"localStorage.removeItem({json.dumps(LS_KEY)});")


def render_resume_prompt():
    """If this browser has saved progress, offer to resume it."""
    if ss.get("_resume_dismissed"):
        return
    # Returns None until the browser responds, "" if nothing is saved
    raw = streamlit_js_eval(
        js_expressions=f"localStorage.getItem({json.dumps(LS_KEY)}) || ''",
        key="ls_read",
    )
    if not raw:
        return
    try:
        saved = json.loads(raw)
        total = len(saved["o"].split("."))
        answered = len([a for a in saved.get("a", "").split(".") if a])
        current = min(int(saved.get("i", 0)) + 1, total)
    except (ValueError, KeyError, TypeError, AttributeError):
        ls_write(f"localStorage.removeItem({json.dumps(LS_KEY)});")
        return

    with st.container(border=True):
        st.markdown(f"**💾 You have saved progress**  \nQuestion {current} of {total} · {answered} answered")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("▶️ Resume", type="primary", use_container_width=True):
                if restore_from_url(saved):
                    st.rerun()
                st.warning("Couldn't restore the saved progress.")
        with c2:
            if st.button("🗑️ Start over", use_container_width=True):
                ss["_clear_ls"] = ss["_resume_dismissed"] = True
                st.rerun()


restore_from_url()

# --- 6. Main UI ---
st.title("Claude Certification Mock Exam 🧠")
st.caption("Practice mock exam for the Anthropic Claude certification. One question at a time.")

if not ss.started:
    render_resume_prompt()
    st.info(f"Load your question file and press Start. Current file: `{resolve_json_path(json_path)}`")
    if st.button("▶️ START", type="primary"):
        start_quiz()

else:
    # Quiz in progress
    total = len(ss.order)
    
    if ss.index >= total:
        render_results()
    else:
        q = ss.order[ss.index]
        
        # Progress bar
        st.progress((ss.index) / total)
        st.caption(f"Question {ss.index + 1} of {total}")
        
        # Question syllabus tags
        tags = [(cls, q.get(cls)) for cls in ("scenario", "domain", "topic") if q.get(cls)]
        if tags:
            st.markdown(
                '<div class="q-tags">'
                + "".join(f'<span class="q-tag {cls}">{html.escape(v)}</span>' for cls, v in tags)
                + "</div>",
                unsafe_allow_html=True,
            )

        # Show the question
        st.markdown(f"### {q['question']}")
        if "code" in q:  # Optional code block
            st.code(q["code"], language=q.get("code_language", "text"))

        # An option is shown as a code block only if it spans several lines
        # (e.g. a command or a config snippet).
        def is_code_option(opt):
            return "\n" in opt.strip()

        # Answer selection
        is_multi = len(q["answer_index"]) > 1
        user_choices = []
        
        # Disable inputs once answered (feedback mode)
        disabled = ss.current_q_answered 

        if is_multi:
            st.write(f"📝 *Select {len(q['answer_index'])} options:*")
            for idx, opt in enumerate(q["options"]):
                checked = False
                if ss.user_selection and idx in ss.user_selection:
                    checked = True

                if is_code_option(opt):
                    col1, col2 = st.columns([0.05, 0.95])
                    with col1:
                        if st.checkbox(
                            "",
                            key=f"q{ss.index}_o{idx}",
                            value=checked,
                            disabled=disabled,
                            label_visibility="collapsed"
                        ):
                            user_choices.append(idx)
                    with col2:
                        st.code(opt, language="text")
                else:
                    label = escape_markdown(opt)
                    if st.checkbox(
                        label,
                        key=f"q{ss.index}_o{idx}",
                        value=checked,
                        disabled=disabled
                    ):
                        user_choices.append(idx)
        else:
            prev_idx = ss.user_selection[0] if ss.user_selection else None
            
            has_code_options = any(is_code_option(opt) for opt in q["options"])
            
            if has_code_options:
                st.write("Choose an option:")
                
                selected_option = st.radio(
                    "Select the code snippet:",
                    range(len(q["options"])),
                    index=prev_idx,
                    format_func=lambda x: f"Option {x+1}",
                    disabled=disabled,
                    key=f"radio_{ss.index}",
                    label_visibility="collapsed"
                )
                
                for idx, opt in enumerate(q["options"]):
                    is_selected = (selected_option == idx)
                    if is_selected:
                        st.markdown(f"**🔘 Option {idx + 1}** ✓")
                    else:
                        st.markdown(f"**⚪ Option {idx + 1}**")
                    
                    st.code(opt, language="text")
                    st.markdown("---")
                
                if selected_option is not None:
                    user_choices = [selected_option]
            else:
                idx_selected = st.radio(
                    "Choose an option:", 
                    range(len(q["options"])), 
                    format_func=lambda x: escape_markdown(q["options"][x]),
                    key=f"radio_{ss.index}",
                    index=prev_idx,
                    disabled=disabled
                )
                if idx_selected is not None:
                    user_choices = [idx_selected]

        st.divider()

        # --- Action buttons ---
        cols = st.columns([1, 1, 2])
        
        if not ss.current_q_answered:
            with cols[0]:
                if st.button("⬅️ Previous", disabled=ss.index == 0):
                    prev_question()

            with cols[1]:
                if st.button("Skip ⏭️"):
                    submit_answer(q, None)
                    if not immediate_feedback:
                        next_question()
                    else:
                        st.rerun()

            with cols[2]:
                can_submit = len(user_choices) > 0
                if st.button("Submit ✅", type="primary", disabled=not can_submit):
                    submit_answer(q, user_choices)
                    if not immediate_feedback:
                        next_question()
                    else:
                        st.rerun()
        
        else:
            # Show feedback inline
            last_ans = ss.answers[ss.index]  # current index
            if last_ans["correct"]:
                st.success("Correct! 🎉")
            else:
                st.error("Incorrect ❌")
                correct_txt = [q['options'][i] for i in q['answer_index']]
                st.markdown(f"**Correct answer:** {', '.join(correct_txt)}")
            
            if q.get("explanation"):
                with st.expander("Explanation", expanded=True):
                    st.write(q["explanation"])

            cols2 = st.columns([1, 1])
            with cols2[0]:
                if st.button("⬅️ Previous", disabled=ss.index == 0):
                    prev_question()
            with cols2[1]:
                if st.button("Next question ➡️", type="primary"):
                    next_question()

# Save progress at the end of every run
sync_url()
