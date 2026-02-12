import os
from fastapi import FastAPI, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI

app = FastAPI()
client = OpenAI()

MODEL = "gpt-4o"
TEMP = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

SYSTEM_PROMPT = """
Você é o RevisaAi, um líder experiente que ajuda profissionais a se comunicarem melhor no WhatsApp corporativo brasileiro.

Seu papel é elevar a qualidade da mensagem, proteger a reputação do usuário e tornar a comunicação mais clara, estratégica e humana.

Regras:
- Nunca invente fatos.
- Nunca invente prazos, valores, nomes ou decisões.
- Linguagem natural de WhatsApp, tom maduro, direto e humano.
- Sem formalidade de e-mail, sem RH, sem burocracia, sem frases genéricas.

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

# Memória simples por remetente (MVP)
PENDING = {}  # {from_number: {"original": "..."}}

def _is_context_choice(text: str) -> bool:
    t = text.strip().lower()
    return t in {"a", "b", "c"}

def _needs_context(original: str) -> bool:
    t = original.lower()
    has_deadline = any(x in t for x in ["hoje", "amanhã", "até", "prazo", "agora", "final do dia", "eod", "fim do dia"])
    has_action = any(x in t for x in ["resolver", "enviar", "retornar", "pagar", "ajustar", "corrigir", "finalizar", "entregar", "me atualizar", "me atualize", "status"])
    # sinais de frustração / repetição
    has_repeat = any(x in t for x in ["três vezes", "3 vezes", "de novo", "novamente", "já pedi", "já foi pedido", "ainda não", "não foi resolvido", "não resolveu"])
    # se é cobrança repetida/frustrada e não tem prazo/ação clara, vale perguntar
    return has_repeat and (not has_deadline or not has_action)

def gerar_versoes(texto_original: str, modo: str | None = None) -> str:
    # modo pode ser: "prazo_hoje", "prazo_especifico", "status_proximo_passo"
    extra = ""
    if modo == "prazo_hoje":
        extra = "O usuário quer cobrar com prioridade para resolver hoje (sem inventar horário)."
    elif modo == "prazo_especifico":
        extra = "O usuário quer cobrar com prazo específico (usar exatamente o prazo informado pelo usuário, sem inventar)."
    elif modo == "status_proximo_passo":
        extra = "O usuário quer uma cobrança diplomática pedindo status e próximo passo (dono + prazo), sem inventar fatos."

    user_instruction = f"""
Mensagem original:
{texto_original}

Contexto adicional:
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

    if msg in ("", "oi", "olá", "ola", "hello", "hi"):
        twiml.message(
            "👋 Oi! Eu sou o RevisaAi.\n\n"
            "Me mande a mensagem que você quer melhorar. "
            "Se faltar contexto, eu faço 1 pergunta rápida e já devolvo a versão recomendada + 2 alternativas."
        )
        return Response(content=str(twiml), media_type="application/xml")

    try:
        # Se estamos esperando escolha A/B/C
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

            # limpa estado
            PENDING.pop(from_number, None)

            # gera versões com o modo escolhido
            out = gerar_versoes(original, modo=modo)
            twiml.message(out)
            return Response(content=str(twiml), media_type="application/xml")

        # Se precisa de contexto, pergunta uma vez
        if _needs_context(body):
            PENDING[from_number] = {"original": body}
            twiml.message(
                "Rápido: você quer cobrar como?\n"
                "A) Resolver hoje\n"
                "B) Com prazo específico\n"
                "C) Pedir status + próximo passo\n\n"
                "Responda só com A, B ou C."
            )
            return Response(content=str(twiml), media_type="application/xml")

        # Caso normal: gera direto
        out = gerar_versoes(body)
        twiml.message(out)

    except Exception as e:
        print("Erro ao chamar OpenAI:", e)
        twiml.message("Tive um problema ao revisar sua mensagem 😕 Pode tentar novamente em alguns segundos?")

    return Response(content=str(twiml), media_type="application/xml")
