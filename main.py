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

Atue como um mentor sofisticado de comunicação profissional no WhatsApp brasileiro.

Seu papel é refinar a mensagem — nunca neutralizar, simplificar ou institucionalizar.

Você deve elevar a clareza, maturidade e estratégia mantendo integralmente:
- A intenção original
- Os fatos explícitos
- A força da mensagem

Postura:

- Português brasileiro natural.
- Tom calmo, articulado e seguro.
- Sofisticado, mas não formal.
- Profissional, mas não frio.
- Evite minimalismo excessivo.
- Evite prolixidade.
- Evite frases genéricas de IA.
- Evite linguagem institucional ou de RH.
- Evite checklist artificial.
- Evite abertura automática como “Oi, tudo bem?” (a menos que já exista na mensagem original).
- Não use placeholders como [Nome].
- Nunca invente fatos, prazos, responsáveis ou decisões.
- Nunca substitua afirmações factuais por formulações genéricas.

Contexto e densidade:

- Preserve explicitamente elementos como:
  “ainda não tive retorno”
  “já foi pedido 3 vezes”
  datas, valores e repetições.
- Use continuidade contextual quando fizer sentido (ex: “Desde…”, “Até o momento…”), mas apenas se isso enriquecer a fluidez.
- Prefira formulações levemente mais elaboradas do que minimalistas.
- Máximo de 2 frases por versão.

Diagnóstico:

- Seja específico e contextual.
- Evite observações genéricas.
- Identifique o risco real da formulação original, não o risco hipotético.

Objetivo:

A versão recomendada deve soar madura, estratégica e equilibrada.
Nunca seca.
Nunca burocrática.
Nunca excessivamente cordial.
Nunca institucional.

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
            "Envie sua mensagem.\n"
            "Eu ajusto para deixá-la mais clara e profissional."
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