import json
import time
import random
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from streamlit_js_eval import streamlit_js_eval

# Configuración de página
st.set_page_config(page_title="Claude Certification Mock", page_icon="🧠", layout="centered")

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        /* El color de fondo y de texto lo define el tema (.streamlit/config.toml).
           No forzar background acá: en iOS con modo oscuro dejaba texto blanco sobre fondo claro. */
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
        .stCheckbox {
            padding: 0.15rem 0;
        }
        /* Ajustes para celular */
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

# --- 1. Carga de Datos con Caché ---
@st.cache_data
def load_questions(path_str: str):
    path = Path(path_str)
    if not path.exists():
        return None  # Manejo suave del error

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if not isinstance(data, list):
        raise ValueError("El JSON debe contener una lista de preguntas.")
        
    # Validación y Normalización
    for q in data:
        if not all(k in q for k in ("question", "options", "answer_index")):
            continue # O lanzar error, aquí saltamos preguntas rotas
            
        # Normalizar answer_index a lista siempre
        if isinstance(q["answer_index"], int):
            q["answer_index"] = [q["answer_index"]]
            
    return data

# --- 2. Gestión del Estado ---
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


st.sidebar.header("⚙️ Configuración")
json_path = st.sidebar.text_input("Ruta del JSON", DEFAULT_JSON_FILE)
limit = st.sidebar.number_input("Límite de preguntas (0 = todas)", min_value=0, value=0, step=1)
shuffle_qs = st.sidebar.checkbox("🔀 Orden Aleatorio", value=False)
immediate_feedback = st.sidebar.checkbox("👀 Feedback Inmediato", value=True, help="Muestra la respuesta correcta justo después de contestar.")

if st.sidebar.button("🔄 Reiniciar Quiz", type="primary"):
    for k in defaults.keys():
        del ss[k]
    ss["_clear_ls"] = ss["_resume_dismissed"] = True
    st.rerun()

# --- 4. Funciones Lógicas ---
def start_quiz():
    resolved_path = resolve_json_path(json_path)
    qs = load_questions(resolved_path)
    if qs is None:
        st.error(f"No se encontró el archivo: {resolved_path}")
        return

    # Copia para no mutar el caché
    qs = [dict(q, _src=i) for i, q in enumerate(qs)]  # _src: posición original, para guardar el progreso en la URL 
    
    if shuffle_qs:
        random.shuffle(qs)
        
    if limit and limit > 0:
        qs = qs[:limit]

    if not qs:
        st.warning("No hay preguntas válidas cargadas.")
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
    # Escapa '_' fuera de `código` para que no se interprete como cursiva
    parts = text.split("`")
    return "`".join(p if i % 2 else p.replace("_", r"\_") for i, p in enumerate(parts))

def submit_answer(q, choices):
    # Calcular corrección
    correct_indices = set(q["answer_index"])
    user_indices = set(choices) if choices is not None else set()
    is_correct = (correct_indices == user_indices) and (choices is not None)
    
    if ss.index < len(ss.answers):
        prev = ss.answers[ss.index]
        if prev["correct"]:
            ss.score -= 1  # quitamos el punto anterior

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
    ss.user_selection = choices  # Guardar para mostrar en UI

def next_question():
    ss.index += 1
    ss.current_q_answered = False
    ss.user_selection = None
    st.rerun()

def prev_question():
    if ss.index > 0:
        ss.index -= 1
        ss.current_q_answered = False  # volvemos a modo edición
        # recuperar selección previa si existe
        if ss.index < len(ss.answers):
            ss.user_selection = ss.answers[ss.index]["chosen"]
        else:
            ss.user_selection = None
        st.rerun()

# --- 5. Renderizado de Resultados ---
def render_results():
    elapsed = time.time() - ss.t0 if ss.t0 else 0.0
    total = len(ss.order)
    pct = (ss.score/total)*100 if total else 0

    st.balloons()
    st.title("📊 Resultados Finales")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Puntuación", f"{ss.score}/{total}")
    c2.metric("Porcentaje", f"{pct:.1f}%")
    c3.metric("Tiempo", f"{elapsed:.1f} s")

    with st.expander("🔍 Revisión Detallada", expanded=True):
        for i, ans in enumerate(ss.answers):
            color = "green" if ans["correct"] else "red"
            icon = "✅" if ans["correct"] else "❌"
            if ans["chosen"] is None:
                icon = "⏭️ (Saltada)"
                color = "gray"
                
            st.markdown(f":{color}[**{i+1}. {ans['question']}**]")
            st.write(f"Estado: {icon}")
            
            correct_txt = [ans['options'][idx] for idx in ans['correct_index']]
            st.caption(f"Respuesta correcta: **{', '.join(correct_txt)}**")
            
            if ans["explanation"]:
                with st.expander("Explicación", expanded=True):
                    st.write(ans["explanation"])
            st.divider()

    if st.button("Volver al Inicio"):
        for k in defaults.keys():
            del ss[k]
        ss["_clear_ls"] = ss["_resume_dismissed"] = True
        st.rerun()

# --- 5b. Progreso guardado en la URL ---
# st.session_state vive en el servidor y se pierde si Safari suspende la pestaña,
# si se recarga la página o si la app se reinicia. Por eso guardamos el progreso
# en la URL (?o=orden&i=índice&a=respuestas&t=inicio) y lo restauramos al volver.
def encode_answers() -> str:
    return ".".join(
        "s" if ans["chosen"] is None else "+".join(map(str, ans["chosen"]))
        for ans in ss.answers
    )


def restore_from_url(qp=None):
    """Restaura el progreso desde la URL o desde un dict (el avance guardado en el navegador)."""
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
                raise ValueError("opción fuera de rango")
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
            raise ValueError("progreso inválido")
    except (ValueError, IndexError, KeyError, TypeError):
        st.query_params.clear()  # URL vieja o incompatible: empezamos de cero
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


LS_KEY = "ccarf_progress"  # clave del avance en localStorage


def ls_write(js: str):
    """Ejecuta JS en el navegador sin provocar un rerun (solo escritura)."""
    components.html(f"<script>try {{ {js} }} catch (e) {{}}</script>", height=0)


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
        # Copia en la memoria del navegador, para reanudar aunque se pierda la URL
        ls_write(f"localStorage.setItem({json.dumps(LS_KEY)}, {json.dumps(json.dumps(params))});")
    else:
        if st.query_params:
            st.query_params.clear()
        if ss.pop("_clear_ls", False):
            ls_write(f"localStorage.removeItem({json.dumps(LS_KEY)});")


def render_resume_prompt():
    """Si hay un avance guardado en este navegador, ofrece reanudarlo."""
    if ss.get("_resume_dismissed"):
        return
    # Devuelve None mientras el navegador todavía no respondió, "" si no hay nada guardado
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
        st.markdown(f"**💾 Tenés un avance guardado**  \nPregunta {current} de {total} · {answered} respondidas")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("▶️ Reanudar", type="primary", use_container_width=True):
                if restore_from_url(saved):
                    st.rerun()
                st.warning("No se pudo recuperar el avance guardado.")
        with c2:
            if st.button("🗑️ Empezar de nuevo", use_container_width=True):
                ss["_clear_ls"] = ss["_resume_dismissed"] = True
                st.rerun()


restore_from_url()

# --- 6. Interfaz Principal ---
st.title("Simulacro Certificación Claude 🧠")
st.caption("Mock de práctica para la certificación de Anthropic. Avanzá una pregunta a la vez.")

if not ss.started:
    render_resume_prompt()
    st.info(f"Carga tu archivo de preguntas y presiona comenzar. Ruta actual sugerida: `{resolve_json_path(json_path)}`")
    if st.button("▶️ COMENZAR", type="primary"):
        start_quiz()

else:
    # Quiz en curso
    total = len(ss.order)
    
    if ss.index >= total:
        render_results()
    else:
        q = ss.order[ss.index]
        
        # Barra de progreso
        st.progress((ss.index) / total)
        st.caption(f"Pregunta {ss.index + 1} de {total}")
        
        # Mostrar pregunta
        st.markdown(f"### {q['question']}")
        if "code" in q:  # Soporte opcional para bloques de código
            st.code(q["code"], language=q.get("code_language", "text"))

        # Una opción se muestra como bloque de código solo si tiene varias líneas
        # (ej. un comando o un fragmento de configuración).
        def is_code_option(opt):
            return "\n" in opt.strip()

        # Lógica de Selección
        is_multi = len(q["answer_index"]) > 1
        user_choices = []
        
        # Si ya se respondió (Feedback Mode), deshabilitar inputs
        disabled = ss.current_q_answered 

        if is_multi:
            st.write(f"📝 *Selecciona {len(q['answer_index'])} opciones:*")
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
                st.write("Elige una opción:")
                
                selected_option = st.radio(
                    "Selecciona el fragmento de código:",
                    range(len(q["options"])),
                    index=prev_idx,
                    format_func=lambda x: f"Opción {x+1}",
                    disabled=disabled,
                    key=f"radio_{ss.index}",
                    label_visibility="collapsed"
                )
                
                for idx, opt in enumerate(q["options"]):
                    is_selected = (selected_option == idx)
                    if is_selected:
                        st.markdown(f"**🔘 Opción {idx + 1}** ✓")
                    else:
                        st.markdown(f"**⚪ Opción {idx + 1}**")
                    
                    st.code(opt, language="text")
                    st.markdown("---")
                
                if selected_option is not None:
                    user_choices = [selected_option]
            else:
                idx_selected = st.radio(
                    "Elige una opción:", 
                    range(len(q["options"])), 
                    format_func=lambda x: escape_markdown(q["options"][x]),
                    key=f"radio_{ss.index}",
                    index=prev_idx,
                    disabled=disabled
                )
                if idx_selected is not None:
                    user_choices = [idx_selected]

        st.divider()

        # --- Botonera de Acción ---
        cols = st.columns([1, 1, 2])
        
        if not ss.current_q_answered:
            with cols[0]:
                if st.button("⬅️ Anterior", disabled=ss.index == 0):
                    prev_question()

            with cols[1]:
                if st.button("Saltar ⏭️"):
                    submit_answer(q, None)
                    if not immediate_feedback:
                        next_question()
                    else:
                        st.rerun()

            with cols[2]:
                can_submit = len(user_choices) > 0
                if st.button("Confirmar ✅", type="primary", disabled=not can_submit):
                    submit_answer(q, user_choices)
                    if not immediate_feedback:
                        next_question()
                    else:
                        st.rerun()
        
        else:
            # Mostrar Feedback Aquí Mismo
            last_ans = ss.answers[ss.index]  # usamos el índice actual
            if last_ans["correct"]:
                st.success("¡Correcto! 🎉")
            else:
                st.error("Incorrecto ❌")
                correct_txt = [q['options'][i] for i in q['answer_index']]
                st.markdown(f"**La respuesta era:** {', '.join(correct_txt)}")
            
            if q.get("explanation"):
                with st.expander("Explicación", expanded=True):
                    st.write(q["explanation"])

            cols2 = st.columns([1, 1])
            with cols2[0]:
                if st.button("⬅️ Anterior", disabled=ss.index == 0):
                    prev_question()
            with cols2[1]:
                if st.button("Siguiente Pregunta ➡️", type="primary"):
                    next_question()

# Guardar el progreso en la URL al final de cada ejecución
sync_url()
