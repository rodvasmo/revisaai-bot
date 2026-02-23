import os
import json
from fastapi import FastAPI, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI

app = FastAPI()
client = OpenAI()

MODEL = "gpt-4o"
TEMP = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

FOOTER = "\n\nSe quiser, revise a próxima comigo também."

SYSTEM_PROMPT = """
Você é o RevisaAi, um líder experiente que ajuda profissionais a se comunicarem melhor no WhatsApp corporativo brasileiro.

Seu papel é elevar a qualidade da mensagem, proteger a reputação do usuário e tornar a comunicação mais clara, estratégica e humana.

Regras:
- Nunca invente fatos.
- Nunca invente prazos, valores, nomes ou decisões.
- Linguagem natural de WhatsApp, tom maduro, direto e humano.
- Sem formalidade de e-mail, sem RH, sem burocracia, sem frases genéricas.

VOZ (MUITO IMPORTANTE):
- Tom: executivo moderno, calmo e objetivo.
- Não use saudações coletivas ou informais: "oi, pessoal", "galera", "equipe".
- Não use justificativas ou apaziguamento: "entendo que todos estão ocupados".
- Não use agradecimentos automáticos: "obrigado", "agradeço".
- Evite exclamações.
- Não seja longo: no máximo 2 frases por versão (recomendado: 1–2 linhas).

PADRÃO PARA "PEDIR STATUS + PRÓXIMO PASSO":
- Sempre peça: status + responsável + próximo passo + prazo (sem inventar).
- Prefira uma pergunta única bem estruturada, ou 2 frases curtas.

REGRA DE OURO (NÃO IGNORAR O CONTEXTO):
- Se a mensagem original trouxer fatos concretos (ex: "3 vezes", "ainda não foi resolvido", "NF", valores, datas),
  a Versão recomendada DEVE incluir esse fato de forma neutra em 1 frase curta.
- A Versão recomendada deve seguir este padrão:
  (1) Contexto neutro com o fato + (2) Pedido de encaminhamento (status + responsável + próximo passo + prazo).

Quando houver frustração/cobrança repetida, transforme em direcionamento claro.
Se faltar contexto (prazo, pedido, próximo passo), peça UMA informação objetiva antes de gerar as versões.

Formato final obrigatório:

🧠 Diagnóstico:
Tom percebido: ...
Risco de impacto negativo: baixo / médio / alto

⚠️ Ponto de atenção (se houver risco relevante):
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

ROUTER_PROMPT = """
Você é um classificador. Retorne APENAS JSON válido, sem texto extra.

Escolha mode em:
- "default"
- "ask_context"
- "status_proximo_passo"
- "prazo_hoje"
- "prazo_especifico"

Regras:
- Use "status_proximo_passo" para cobranças/follow-ups com repetição/frustração onde o usuário pede update/status/retorno.
- Use "ask_context" quando for cobrança/repetição e estiver ambíguo se a pessoa quer (A) resolver hoje, (B) prazo específico, (C) pedir status + próximo passo.
- Use "prazo_hoje" quando a mensagem explicitamente pedir resolver hoje/final do dia.
- Use "prazo_especifico" quando a mensagem tiver um prazo explícito (data/horário/até X).
- Caso contrário, "default".

Responda somente com JSON no formato:
{"mode":"default"}
"""


# Memória simples por remetente (MVP) — some se o serviço reiniciar
PENDING = {}  # {from_number: {"original": "..."}}


def _is_context_choice(text: str) -> bool:
    t = text.strip().lower()
    return t in {"a", "b", "c"}


def route_message(texto: str) -> str:
    """
    Roteador conservador: escolhe um modo SEM alterar o writer.
    Se falhar, cai em default.
    """
    try:
        r = client.responses.create(
            model=MODEL,
            temperature=0.0,
            max_output_tokens=80,
            input=[
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user", "content": texto},
            ],
        )
        raw = (r.output_text or "").strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end == -1:
            return "default"
        obj = json.loads(raw[start : end + 1])
        mode = obj.get("mode", "default")
        allowed = {"default", "ask_context", "status_proximo_passo", "prazo_hoje", "prazo_especifico"}
        return mode if mode in allowed else "default"
    except Exception:
        return "default"


def gerar_versoes(texto_original: str, modo: str | None = None) -> str:
    extra = ""

    if modo == "prazo_hoje":
        extra = (
            "O usuário quer cobrar com prioridade para resolver hoje (sem inventar horário). "
            "Tom executivo moderno, calmo e objetivo. Máximo 2 frases por versão."
        )

    elif modo == "prazo_especifico":
        extra = (
            "O usuário quer cobrar com prazo específico (já presente na mensagem). "
            "Use exatamente o prazo informado pelo usuário, sem inventar. "
            "Tom executivo moderno, calmo e objetivo. Máximo 2 frases por versão."
        )

    elif modo == "status_proximo_passo":
        extra = (
            "Objetivo: cobrança executiva pedindo status + responsável + próximo passo + prazo, sem inventar fatos. "
            "A Versão recomendada DEVE ter exatamente 2 frases curtas e soar natural (sem checklist). "
            "Estrutura obrigatória da Versão recomendada:\n"
            "Frase 1: Contexto neutro com o fato (ex: 'Esse ponto já foi solicitado 3 vezes e ainda não avançou.').\n"
            "Frase 2: Pedido em formato de ENCAMINHAMENTO CLARO (uma única frase), evitando checklist.\n\n"
            "Use uma destas frases como base (adapte minimamente):\n"
            "A) 'Você consegue me passar um encaminhamento claro — status, responsável, próximo passo e prazo?'\n"
            "B) 'Podemos fechar um encaminhamento claro com status, responsável, próximo passo e prazo?'\n"
        )

    user_instruction = f"""
Mensagem original:
{texto_original}

Contexto adicional (se houver):
{extra}

Gere a resposta final no formato obrigatório.
Reestruture estrategicamente e proponha encaminhamento claro quando aplicável, sem inventar fatos.
"""

    response = client.responses.create(
        model=MODEL,
        temperature=TEMP,
        max_output_tokens=700,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_instruction},
        ],
    )

    return response.output_text


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    body = (form.get("Body") or "").strip()
    msg = body.lower()
    from_number = (form.get("From") or "").strip()

    twiml = MessagingResponse()

    # Mensagem inicial
    if msg in ("", "oi", "olá", "ola", "hello", "hi"):
        twiml.message(
            "👋 Oi! Eu sou o RevisaAi.\n\n"
            "Às vezes um pequeno ajuste muda tudo.\n"
            "Envie sua mensagem. Eu ajusto para deixá-la mais clara e profissional."
        )
        return Response(content=str(twiml), media_type="application/xml")

    try:
        # Se estamos esperando escolha A/B/C (fluxo existente)
        if from_number in PENDING and _is_context_choice(body):
            original = PENDING[from_number]["original"]
            choice = body.strip().lower()

            modo = None
            if choice == "a":
                modo = "prazo_hoje"
            elif choice == "b":
                modo = "prazo_especifico"
            elif choice == "c":
                modo = "status_proximo_passo"

            PENDING.pop(from_number, None)

            out = gerar_versoes(original, modo=modo)
            twiml.message(out + FOOTER)
            return Response(content=str(twiml), media_type="application/xml")

        # Router conservador (não altera writer)
        mode = route_message(body)

        if mode == "ask_context":
            PENDING[from_number] = {"original": body}
            twiml.message(
                "Rápido: você quer cobrar como?\n"
                "A) Resolver hoje\n"
                "B) Com prazo específico\n"
                "C) Pedir status + próximo passo\n\n"
                "Responda só com A, B ou C."
            )
            return Response(content=str(twiml), media_type="application/xml")

        if mode in {"status_proximo_passo", "prazo_hoje", "prazo_especifico"}:
            out = gerar_versoes(body, modo=mode)
        else:
            out = gerar_versoes(body)

        twiml.message(out + FOOTER)

    except Exception as e:
        print("Erro ao chamar OpenAI:", e)
        twiml.message("Tive um problema ao revisar sua mensagem 😕 Pode tentar novamente em alguns segundos?")

    return Response(content=str(twiml), media_type="application/xml")