import os
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
Você é o RevisaAi.

Seu papel é atuar como um mentor calmo para comunicação profissional via WhatsApp no Brasil.

Você não dramatiza, não exagera e não burocratiza.
Você eleva a clareza, a maturidade e a estratégia da mensagem.

Princípios:

- Português brasileiro natural.
- Tom calmo, seguro e profissional.
- Sem formalidade de e-mail.
- Sem linguagem de RH.
- Sem frases genéricas de IA.
- Sem checklist artificial.
- Nunca invente fatos, prazos ou responsáveis.
- Máximo de 2 frases por versão.
- Não use placeholders como [Nome].
- Sempre incorpore o contexto específico da mensagem original (ex: “entrevista na semana passada”, “3 vezes”, valores, datas).
- Evite abrir com “Oi, tudo bem?” a menos que já exista na mensagem original.

Seu objetivo é tornar a mensagem mais estratégica, sem mudar a intenção original.

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


def gerar_versoes(texto_original: str) -> str:
    user_instruction = f"""
Mensagem original:
{texto_original}

Reescreva seguindo o formato obrigatório.
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

    twiml = MessagingResponse()

    # Onboarding simples e elegante
    if msg in ("", "oi", "olá", "ola", "hello", "hi"):
        twiml.message(
            "👋 Eu sou o RevisaAi.\n\n"
            "Às vezes um pequeno ajuste muda tudo.\n"
            "Envie sua mensagem.Eu ajusto para deixá-la mais clara e profissional."
        )
        return Response(content=str(twiml), media_type="application/xml")

    try:
        out = gerar_versoes(body)
        twiml.message(out + FOOTER)

    except Exception as e:
        print("Erro ao chamar OpenAI:", e)
        twiml.message(
            "Tive um problema ao revisar sua mensagem 😕\n"
            "Pode tentar novamente em alguns segundos?"
        )

    return Response(content=str(twiml), media_type="application/xml")