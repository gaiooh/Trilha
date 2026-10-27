# Gera transcricoes.json com as legendas de todas as aulas do site.
# Instalação (uma vez):  pip install youtube-transcript-api
# Uso (na pasta do site, onde está o index.html):  python baixar_transcricoes.py index.html
# Depois envie o transcricoes.json para a raiz do repositório.
import json, re, sys, time
from youtube_transcript_api import YouTubeTranscriptApi

HTML = sys.argv[1] if len(sys.argv) > 1 else "index.html"
SAIDA = "transcricoes.json"
IDIOMAS = ["pt", "pt-BR", "en"]

html = open(HTML, encoding="utf-8").read()
# Pega ID e título de cada vídeo dos arrays das aulas: ["ID","Título",segundos]
videos = {}
for vid, titulo in re.findall(r'\["([A-Za-z0-9_-]{11})","([^"]+)",\d+\]', html):
    videos.setdefault(vid, titulo)
print(len(videos), "videos encontrados")

api = YouTubeTranscriptApi()
out = {}
falhas = []
for i, (vid, titulo) in enumerate(videos.items(), 1):
    try:
        t = api.fetch(vid, languages=IDIOMAS)
        segs = t.to_raw_data() if hasattr(t, "to_raw_data") else [{"text": s.text, "start": s.start} for s in t]
    except Exception as e:
        falhas.append((vid, str(e)[:80]))
        continue

    # agrupa as falas em trechos de cerca de 60 segundos
    janelas, atual, inicio = [], [], None
    for s in segs:
        if inicio is None:
            inicio = s["start"]
        atual.append(s["text"].replace("\n", " "))
        if s["start"] - inicio >= 60:
            janelas.append([round(inicio), " ".join(atual)])
            atual, inicio = [], None
    if atual:
        janelas.append([round(inicio), " ".join(atual)])

    out[vid] = {"t": titulo, "c": janelas}
    print(i, vid, len(janelas), "trechos")
    time.sleep(0.5)

with open(SAIDA, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False)
print("salvo em", SAIDA, "| sem legenda:", len(falhas))
for vid, err in falhas:
    print("  falhou:", vid, err)
