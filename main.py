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
Você é o RevisaAi, especialista em comunicação profissional em português do Brasil.

Sua função é reescrever mensagens curtas de WhatsApp no contexto corporativo.

Regras importantes:
- Não invente fatos.
- Não adicione informações que não estavam na mensagem original.
- Preserve a intenção.
- Não altere um "sim" para "não" ou vice-versa.
- Linguagem natural de WhatsApp, mas profissional.
- Máximo ~250 caracteres por versão.

Sempre responda neste formato:

1) Mais educada: ...
2) Mais firme: ...
3) Mais profissional: ...
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

