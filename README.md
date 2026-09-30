# CCAR-F-Trainer

Quiz de certificación PCAP en Python con Streamlit.

## Ejecutar localmente

```bash
uv run --with streamlit streamlit run exam_web.py
```

O si tenés un entorno Python tradicional:

```bash
pip install -r requirements.txt
streamlit run exam_web.py
```

La app usa el archivo `questions.json` por defecto.

## Deploy

Se puede publicar en Streamlit Community Cloud apuntando a:

- repositorio: `pgarateguy-endava/CCAR-F-Trainer`
- rama: `main`
- archivo principal: `exam_web.py`
