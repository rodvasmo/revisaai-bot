import os
import re
from fastapi import FastAPI, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI

app = FastAPI()
client = OpenAI()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
TEMP = float(os.getenv("OPENAI_TEMPERATURE", "0.6"))
MAX_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "650"))

FOOTER = "\n\nSe quiser, revise a próxima comigo também."

# =========================
# 1) BASE STYLE (GLOBAL)
# =========================
SYSTEM_BASE = """
Você é o RevisaAi.

Atue como um profissional maduro ajustando frases de comunicação no WhatsApp brasileiro.

Objetivo:
Refinar a mensagem para ficar mais clara, madura e bem colocada — sem alterar intenção, fatos ou responsabilidades explícitas.

Estilo:
- Português brasileiro natural.
- Tom calmo, articulado e seguro.
- Sofisticado, mas não formal.
- Profissional, mas não frio.
- Sem linguagem de RH, sem consultoria, sem burocracia.
- Sem frases genéricas de IA.
- Sem checklist artificial.
- Máximo de 2 frases por versão.
- Não use placeholders como [Nome].
- Evite “Oi, tudo bem?” a menos que exista no original.

Regras críticas:
- Nunca invente fatos, prazos, responsáveis ou decisões.
- Preserve responsabilidade explícita quando existir (ex: “você ficou de…”).
- Não transforme em construção impessoal/passiva:
  proibido: “Fico no aguardo…”, “Aguardo retorno…”, “Permaneço no aguardo…”
- Evite iniciar a Versão recomendada com “Você poderia…”.
  Prefira “Você consegue…”, “Você pode…”, ou formulações naturais equivalentes.
- Não use termos acusatórios/infantilizantes: “prometeu”, “cobrador”.

Hierarquia:
- A Versão recomendada deve ser a mais equilibrada e madura (puxada para o lado diplomático), sem soar passiva.

Formato obrigatório:

🧠 Diagnóstico:
Tom percebido: ...
Risco de impacto negativo: baixo / médio / alto

⚠️ Ponto de atenção (somente se houver risco relevante):
...

🎯 Versão recomendada:
...

---

Outras opções:

1️⃣ Mais direta:
...

2️⃣ Mais diplomática:
...

Não explique o processo.
"""

# =========================
# 2) MINI-PROMPTS POR TIPO
# =========================
TYPE_GUIDES = {
    "critica": """
Intenção detectada: CRÍTICA / FEEDBACK sobre postura/atitude/abordagem.

Diretrizes:
- Eleve para uma formulação construtiva e orientada ao futuro (sem “RH speak”).
- Mantenha firmeza calma; evite acusação pessoal crua.
- Preserve o fato (ex: “na reunião de hoje”) se existir no original.
- Evite palavras como “inadequado”, “não atendeu”, “expectativas”, “desconforto”.
""",
    "cobranca_repetida": """
Intenção detectada: COBRANÇA COM REPETIÇÃO / SEM AVANÇO.

Diretrizes:
- Preserve explicitamente o fato da repetição/ausência de avanço (“já falamos”, “3 vezes”, “continua igual”).
- Evite permissividade na Versão recomendada (não use “poderíamos”, “você acha que podemos”, “seria possível”).
- A Versão recomendada deve ser firme e madura, orientada a avanço, sem checklist e sem “framework executivo”.
- Evite perguntas genéricas (“como podemos resolver essa questão?”). Prefira pedido natural de atualização/avanço.
""",
    "followup_externo": """
Intenção detectada: FOLLOW-UP EXTERNO (entrevista, proposta, contrato, retorno).

Diretrizes:
- Preserve o tempo/fato (“semana passada”, “ainda não tive retorno”) se existir.
- Peça atualização de forma natural, sem institucionalizar.
- Evite “há alguma atualização disponível”.
""",
    "pedido_interno": """
Intenção detectada: PEDIDO INTERNO (ajuda, entrega, material, prioridade).

Diretrizes:
- Deixe claro o que você precisa e a prioridade.
- Se houver prazo no original, preserve; se não houver, não invente.
- Evite soar seco; mas não seja prolixo.
""",
    "neutro": """
Intenção detectada: NEUTRO / GERAL.

Diretrizes:
- Apenas refine para clareza e maturidade, preservando intenção e fatos.
""",
}

INTENT_LABELS = {"critica", "cobranca_repetida", "followup_externo", "pedido_interno", "neutro"}


# =========================
# 3) CLASSIFICAÇÃO SEMÂNTICA (LLM)
# =========================
def classificar_intencao(texto: str) -> str:
    """
    Chamada 1 (barata/rápida): classifica intenção semanticamente.
    Retorna 1 label dentre: critica, cobranca_repetida, followup_externo, pedido_interno, neutro
    """
    prompt = f"""
Classifique a intenção principal da mensagem abaixo em APENAS UMA destas opções:
- critica
- cobranca_repetida
- followup_externo
- pedido_interno
- neutro

Regras:
- Responda com apenas a palavra da opção (sem pontuação, sem explicação).
- Se houver repetição/“continua igual”/“já foi pedido”/“3 vezes”, prefira cobranca_repetida.
- Se for pedir retorno de entrevista/proposta/contrato, prefira followup_externo.
- Se for pedido de ajuda/entrega, prefira pedido_interno.
- Se for feedback sobre postura/atitude, prefira critica.

Mensagem:
{texto}
"""
    try:
        r = client.responses.create(
            model=MODEL,
            temperature=0.0,
            max_output_tokens=20,
            input=[
                {"role": "system", "content": "Você é um classificador. Siga as instruções e responda apenas o rótulo."},
                {"role": "user", "content": prompt},
            ],
        )
        label = (getattr(r, "output_text", "") or "").strip().lower()
        # limpa casos tipo "critica\n" ou "critica."
        label = re.sub(r"[^a-z_]+", "", label)
        return label if label in INTENT_LABELS else "neutro"
    except Exception as e:
        print("Erro ao classificar intenção:", e)
        return "neutro"


# =========================
# 4) GERAÇÃO (LLM)
# =========================
def gerar_versoes(texto_original: str, intent: str) -> str:
    guide = TYPE_GUIDES.get(intent, TYPE_GUIDES["neutro"]).strip()

    user_instruction = f"""
Mensagem original:
{texto_original}

{guide}

Agora gere a resposta final no FORMATO OBRIGATÓRIO.
"""
    r = client.responses.create(
        model=MODEL,
        temperature=TEMP,
        max_output_tokens=MAX_TOKENS,
        input=[
            {"role": "system", "content": SYSTEM_BASE},
            {"role": "user", "content": user_instruction},
        ],
    )
    out = (getattr(r, "output_text", "") or "").strip()
    return out or "Não consegui gerar a resposta agora. Pode tentar novamente?"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    body = (form.get("Body") or "").strip()
    msg = body.lower()

    twiml = MessagingResponse()

    # Onboarding
    if msg in ("", "oi", "olá", "ola", "hello", "hi"):
        twiml.message(
            "👋 Eu sou o RevisaAi.\n\n"
            "Me envie uma mensagem antes de mandar no trabalho.\n"
            "Eu devolvo uma versão mais clara e madura."
        )
        print("TwiML:", str(twiml))
        return Response(content=str(twiml), media_type="text/xml; charset=utf-8")

    try:
        intent = classificar_intencao(body)
        out = gerar_versoes(body, intent=intent)
        twiml.message(out + FOOTER)

    except Exception as e:
        print("Erro ao processar:", e)
        twiml.message("Tive um problema ao revisar sua mensagem 😕 Pode tentar novamente em alguns segundos?")

    print("TwiML:", str(twiml))
    return Response(content=str(twiml), media_type="text/xml; charset=utf-8")