# CCAR-F-Trainer

Simulacro (mock) de práctica para la certificación de Claude de Anthropic, hecho con Streamlit.
Las preguntas están en `questions.json` (en inglés, con explicación de cada respuesta).

## Ejecutar localmente

```bash
uv run --with streamlit streamlit run exam_web.py
```

O con un entorno Python tradicional:

```bash
pip install -r requirements.txt
streamlit run exam_web.py
```

## Formato de `questions.json`

Lista de objetos con `id`, `question`, `options`, `answer_index` (lista de índices correctos)
y `explanation`. Opcionales: `code` (bloque a mostrar debajo de la pregunta) y
`code_language` (resaltado del bloque, ej. `bash`, `json`, `yaml`).

## Tema

`.streamlit/config.toml` fija el tema claro para que la app se lea igual en celulares
con modo oscuro (Safari en iPhone mostraba el texto en blanco).

## Deploy

Streamlit Community Cloud:

- repositorio: `pgarateguy-endava/CCAR-F-Trainer`
- rama: `main`
- archivo principal: `exam_web.py`
