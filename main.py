import os
from fastapi import FastAPI, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI

app = FastAPI()

# Inicializa cliente OpenAI
client = OpenAI()

# Modelo padrão (pode mudar via variável de ambiente)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """
Você é o RevisaAi, especialista em comunicação profissional no Brasil, com foco em mensagens curtas de WhatsApp corporativo.

Objetivo:
Transformar mensagens mal escritas, bruscas ou vagas em versões claras, estratégicas e profissionalmente inteligentes.

Regras essenciais:
- Nunca invente fatos.
- Nunca altere a intenção original.
- Preserve decisões (sim continua sim; não continua não).
- Linguagem natural de WhatsApp, mas madura.
- Evite formalidade exagerada.
- Evite floreios.
- Seja claro, objetivo e socialmente inteligente.

Critérios de melhoria:
- Reduzir agressividade implícita.
- Aumentar clareza.
- Melhorar estrutura.
- Tornar pedido mais colaborativo quando aplicável.
- Manter impacto quando necessário.

Formato obrigatório:

🔎 Análise rápida:
Tom percebido: ...
Risco de ruído: baixo / médio / alto

---

1) Mais educada:
...

2) Mais firme:
...

3) Mais profissional:
...
"""

def gerar_versoes(texto_original: str) -> str:
    response = client.responses.create(
        model=MODEL,
        instructions=SYSTEM_PROMPT,
        input=f"Mensagem original:\n{texto_original}\n\nGere as três versões agora."
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

    # Mensagem inicial
    if msg in ("", "oi", "olá", "ola", "hello", "hi"):
        twiml.message(
            "👋 Oi! Eu sou o RevisaAi.\n\n"
            "Me envie a mensagem que você quer melhorar e eu devolvo 3 versões:\n"
            "1) Mais educada\n"
            "2) Mais firme\n"
            "3) Mais profissional"
        )
        return Response(content=str(twiml), media_type="application/xml")

    try:
        versoes = gerar_versoes(body)
        twiml.message(versoes)

    except Exception as e:
        print("Erro ao chamar OpenAI:", e)
        twiml.message(
            "Tive um problema ao revisar sua mensagem agora 😕\n"
            "Pode tentar novamente em alguns segundos?"
        )

    return Response(content=str(twiml), media_type="application/xml")

