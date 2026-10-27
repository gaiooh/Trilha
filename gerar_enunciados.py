# Gera enunciados.json com o enunciado de cada exercício e o segundo em que começa a resolução.
#
# Preparação (uma vez, no Prompt de Comando):
#   pip install youtube-transcript-api
#   Pegue uma chave gratuita em aistudio.google.com e rode:  set GEMINI_KEY=SUA_CHAVE
#
# Uso (na pasta do site, onde está o index.html):
#   python gerar_enunciados.py index.html
#
# Pode rodar de novo: os exercícios já feitos são pulados.
import json, os, re, sys, time, urllib.request
from youtube_transcript_api import YouTubeTranscriptApi

KEY = os.environ.get("GEMINI_KEY", "").strip()
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
HTML = sys.argv[1] if len(sys.argv) > 1 else "index.html"
SAIDA = "enunciados.json"

if not KEY or KEY.startswith("SUA_"):
    sys.exit("Defina GEMINI_KEY com a sua chave real antes de rodar.")

html = open(HTML, encoding="utf-8").read()
videos = {}
for vid, titulo in re.findall(r'\["([A-Za-z0-9_-]{11})","([^"]+)",\d+\]', html):
    if re.search(r"Exerc[ií]cio Python #\d+", titulo):
        videos.setdefault(vid, titulo)
print(len(videos), "exercícios encontrados")

out = {}
if os.path.exists(SAIDA):
    out = json.load(open(SAIDA, encoding="utf-8"))

api = YouTubeTranscriptApi()

PROMPT = """Você recebe a transcrição, com tempos em segundos, de um vídeo de exercício de Python do Curso em Vídeo.

Tarefas:
1. Escreva o enunciado do exercício em português, do jeito que o professor explica o problema. Não inclua a solução nem dicas de código.
2. Informe em que segundo começa a resolução, ou seja, quando o professor começa a programar a solução. Se não ficar claro, use null.

Responda somente com JSON neste formato: {"enunciado": "...", "resolucao_segundo": 123}

Título do vídeo: __TITULO__

Transcrição:
__TRECHO__"""


def gemini(texto):
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (MODEL, KEY)
    body = json.dumps({
        "contents": [{"parts": [{"text": texto}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        j = json.load(r)
    return j["candidates"][0]["content"]["parts"][0]["text"]


for i, (vid, titulo) in enumerate(videos.items(), 1):
    if vid in out:
        continue
    try:
        segs = api.fetch(vid, languages=["pt", "pt-BR", "en"]).to_raw_data()
    except Exception as e:
        print("  sem legenda:", vid, str(e)[:60])
        continue
    linhas = []
    for s in segs:
        if s["start"] <= 900:
            linhas.append("[%ds] %s" % (int(s["start"]), s["text"].replace("\n", " ")))
    prompt = PROMPT.replace("__TITULO__", titulo).replace("__TRECHO__", "\n".join(linhas))
    try:
        r = json.loads(gemini(prompt))
    except Exception as e:
        print("  falhou na IA:", vid, str(e)[:80])
        time.sleep(10)
        continue
    res = r.get("resolucao_segundo")
    out[vid] = {
        "enunciado": str(r.get("enunciado", "")).strip(),
        "resolucao": int(res) if isinstance(res, (int, float)) else None,
    }
    print(i, titulo[:55], "ok")
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    time.sleep(4)

print("salvo em", SAIDA, "| total:", len(out))
