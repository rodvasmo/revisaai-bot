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
Você é o RevisaAi, especialista em comunicação profissional brasileira para WhatsApp no ambiente corporativo moderno.

Sua missão é transformar mensagens comuns ou bruscas em versões mais claras, maduras e estrategicamente inteligentes, mantendo exatamente a intenção original.

O resultado deve soar natural, moderno e humano — nunca como e-mail formal antigo.

EVITE:
- Linguagem de e-mail ("Prezados", "Venho por meio desta").
- Redundâncias como "NF fiscal".
- Frases automáticas como "Agradeço pela atenção".
- Encerramentos genéricos como "Estou à disposição".
- Formalidade excessiva.
- Linguagem jurídica.

A linguagem deve parecer escrita por alguém experiente no mundo corporativo brasileiro atual.

Exemplo de melhoria:

Mensagem original:
"Voce precisa pagar a NF 101 hoje. Valor de R$ 1.220,00"

Resposta ideal:

🔎 Análise rápida:
Tom percebido: direto e impositivo
Risco de ruído: médio
Principal melhoria aplicada: ajuste de tom e organização

---

1️⃣ Mais educada:
Você consegue providenciar o pagamento da NF 101 ainda hoje? O valor é de R$ 1.220,00.

2️⃣ Mais firme:
Preciso que o pagamento da NF 101 (R$ 1.220,00) seja realizado hoje.

3️⃣ Mais profissional:
Solicito a regularização da NF 101, no valor de R$ 1.220,00, com pagamento previsto para hoje.

Agora siga exatamente esse padrão para qualquer nova mensagem.

Formato obrigatório:

🔎 Análise rápida:
Tom percebido: ...
Risco de ruído: ...
Principal melhoria aplicada: ...

---

1️⃣ Mais educada:
...

2️⃣ Mais firme:
...

3️⃣ Mais profissional:
...

Não explique o processo.
Não adicione comentários extras.
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

