# Gera enunciados.json com o enunciado de cada exercício e o segundo em que começa a resolução.
#
# Preparação (uma vez):
#   python -m pip install yt-dlp
#   Chave gratuita em aistudio.google.com, e no Prompt de Comando:
#     set GEMINI_KEY=SUA_CHAVE
#     set GEMINI_MODEL=gemini-flash-latest
#
# Uso (na pasta Trilha, onde está o index.html):
#   python gerar_enunciados.py index.html
#
# Pode rodar quantas vezes quiser: os exercícios já prontos são pulados.
# Se o YouTube bloquear temporariamente, o script para sozinho e salva o progresso.
import json, os, random, re, sys, time, urllib.request, urllib.error
import yt_dlp

KEY = os.environ.get("GEMINI_KEY", "").strip()
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
HTML = sys.argv[1] if len(sys.argv) > 1 else "index.html"
SAIDA = "enunciados.json"
MAX_FALHAS_SEGUIDAS = 6

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

PROMPT = """Você recebe a transcrição, com tempos em segundos, de um vídeo de exercício de Python do Curso em Vídeo.

Tarefas:
1. Escreva o enunciado do exercício em português, do jeito que o professor explica o problema. Não inclua a solução nem dicas de código.
2. Informe em que segundo começa a resolução, ou seja, quando o professor começa a programar a solução. Se não ficar claro, use null.

Responda somente com JSON neste formato: {"enunciado": "...", "resolucao_segundo": 123}

Título do vídeo: __TITULO__

Transcrição:
__TRECHO__"""


def legenda(vid):
    """Baixa a legenda com o próprio yt-dlp (com tempo limite), preferindo português."""
    pasta = "legendas_tmp"
    os.makedirs(pasta, exist_ok=True)
    url = "https://www.youtube.com/watch?v=" + vid
    opcoes = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["pt", "pt-BR", "en"],
        "subtitlesformat": "json3",
        "outtmpl": os.path.join(pasta, "%(id)s.%(ext)s"),
        "socket_timeout": 30,
        "retries": 3,
    }
    with yt_dlp.YoutubeDL(opcoes) as ydl:
        ydl.download([url])
    arquivos = sorted(
        f for f in os.listdir(pasta)
        if f.startswith(vid + ".") and f.endswith(".json3")
    )
    if not arquivos:
        raise RuntimeError("sem legenda")
    with open(os.path.join(pasta, arquivos[0]), encoding="utf-8") as f:
        dados = json.load(f)
    segs = []
    for e in dados.get("events", []):
        txt = "".join(x.get("utf8", "") for x in (e.get("segs") or [])).strip()
        if txt:
            segs.append({"start": (e.get("tStartMs") or 0) / 1000, "text": txt})
    if not segs:
        raise RuntimeError("sem legenda")
    return segs


def gemini(texto):
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent?key=%s" % (MODEL, KEY)
    body = json.dumps({
        "contents": [{"parts": [{"text": texto}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }).encode("utf-8")
    for tentativa in range(3):
        req = urllib.request.Request(url, data=body, headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.load(r)
            return j["candidates"][0]["content"]["parts"][0]["text"]
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 503) and tentativa < 2:
                time.sleep(30 * (tentativa + 1))
                continue
            raise


falhas_seguidas = 0
pendentes = [v for v in videos if v not in out]
print(len(pendentes), "faltam")

for i, vid in enumerate(pendentes, 1):
    titulo = videos[vid]
    try:
        segs = legenda(vid)
    except Exception as e:
        falhas_seguidas += 1
        print("  sem legenda:", vid, "|", titulo[:45])
        if falhas_seguidas >= MAX_FALHAS_SEGUIDAS:
            print("\nO YouTube bloqueou as legendas por enquanto. Espere 1 hora e rode de novo;")
            print("o progresso já salvo fica guardado.")
            break
        time.sleep(random.uniform(15, 25))
        continue

    falhas_seguidas = 0
    linhas = ["[%ds] %s" % (int(s["start"]), s["text"].replace("\n", " ")) for s in segs if s["start"] <= 900]
    prompt = PROMPT.replace("__TITULO__", titulo).replace("__TRECHO__", "\n".join(linhas))
    try:
        r = json.loads(gemini(prompt))
    except Exception as e:
        print("  falhou na IA:", vid, str(e)[:80])
        time.sleep(15)
        continue

    res = r.get("resolucao_segundo")
    out[vid] = {
        "enunciado": str(r.get("enunciado", "")).strip(),
        "resolucao": int(res) if isinstance(res, (int, float)) else None,
    }
    print(i, titulo[:55], "ok")
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    time.sleep(random.uniform(6, 10))

print("salvo em", SAIDA, "| total pronto:", len(out), "de", len(videos))
