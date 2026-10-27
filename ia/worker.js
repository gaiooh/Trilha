// Assistente das aulas (Cloudflare Worker).
// Variável secreta obrigatória: ANTHROPIC_API_KEY
// Variável opcional: MODEL (padrão claude-haiku-5-5)

const DATA_URL = "https://raw.githubusercontent.com/gaiooh/Trilha/main/transcricoes.json";
const ORIGEM = "https://gaiooh.github.io";

const SYSTEM = `Você é o assistente das aulas do site Trilha, de programação, em português do Brasil.
Responda SOMENTE com base nos trechos de transcrição fornecidos. Se a resposta não estiver nos trechos, diga isso com clareza e sugira em qual aula procurar.
Ao citar algo, indique a aula e o minuto, por exemplo: (Curso Python 03, 12:40).
Para resumos, use tópicos curtos. Para dúvidas, responda direto e inclua exemplos de código quando ajudarem.`;

const cors = {
  "Access-Control-Allow-Origin": ORIGEM,
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "content-type",
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...cors, "content-type": "application/json; charset=utf-8" },
  });
}

function semAcento(s) {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

function mmss(s) {
  s = Math.floor(s);
  return Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0");
}

let cache = null;
async function carregar() {
  if (!cache) {
    const r = await fetch(DATA_URL, { cf: { cacheTtl: 3600, cacheEverything: true } });
    if (!r.ok) throw new Error("transcricoes indisponiveis");
    cache = await r.json();
  }
  return cache;
}

// Com uma aula aberta: usa a aula inteira. Sem aula: busca por palavras da pergunta.
function escolher(data, videos, pergunta) {
  const itens = [];
  const ids = videos && videos.length ? videos : Object.keys(data);
  for (const id of ids) {
    const v = data[id];
    if (!v) continue;
    for (const [s, txt] of v.c) itens.push({ titulo: v.t, s, txt });
  }
  if (videos && videos.length) return itens.slice(0, 600);

  const palavras = semAcento(pergunta).split(/\W+/).filter((w) => w.length > 3);
  for (const it of itens) {
    const low = semAcento(it.txt);
    it.pontos = palavras.reduce((a, w) => a + (low.includes(w) ? 1 : 0), 0);
  }
  return itens
    .filter((i) => i.pontos > 0)
    .sort((a, b) => b.pontos - a.pontos)
    .slice(0, 80);
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    if (request.method !== "POST") return json({ erro: "use POST" }, 405);

    let corpo;
    try {
      corpo = await request.json();
    } catch {
      return json({ erro: "pedido inválido" }, 400);
    }

    const pergunta = String(corpo.pergunta || "").slice(0, 500).trim();
    if (!pergunta) return json({ erro: "pergunta vazia" }, 400);
    const videos = Array.isArray(corpo.videos)
      ? corpo.videos.filter((v) => typeof v === "string").slice(0, 20)
      : null;

    try {
      const data = await carregar();
      const itens = escolher(data, videos, pergunta);
      let ctx = itens.map((i) => `[${i.titulo} · ${mmss(i.s)}] ${i.txt}`).join("\n");
      if (ctx.length > 120000) ctx = ctx.slice(0, 120000);
      if (!ctx) ctx = "(nenhum trecho encontrado)";

      const r = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-api-key": env.ANTHROPIC_API_KEY,
          "anthropic-version": "2023-06-01",
        },
        body: JSON.stringify({
          model: env.MODEL || "claude-haiku-5-5",
          max_tokens: 1200,
          system: SYSTEM,
          messages: [{ role: "user", content: `Trechos das aulas:\n${ctx}\n\nPergunta: ${pergunta}` }],
        }),
      });
      if (!r.ok) return json({ erro: "a IA não respondeu agora" }, 502);

      const j = await r.json();
      const texto = (j.content || []).filter((c) => c.type === "text").map((c) => c.text).join("\n");
      return json({ resposta: texto });
    } catch (e) {
      return json({ erro: "falha ao buscar as aulas" }, 500);
    }
  },
};
