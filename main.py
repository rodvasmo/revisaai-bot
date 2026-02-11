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
Você é o RevisaAi, especialista em comunicação profissional brasileira para WhatsApp no contexto corporativo moderno.

Sua missão é transformar mensagens comuns, bruscas ou mal estruturadas em versões claras, maduras e estrategicamente inteligentes — mantendo exatamente a intenção original.

O usuário deve perceber um salto real de qualidade.

PROIBIDO:

- Linguagem de e-mail formal ("Prezados", "Venho por meio desta", "Agradeço pela atenção").
- Formalidade excessiva.
- Frases artificiais ou burocráticas.
- Redundâncias desnecessárias.
- Iniciar mensagem com cumprimentos genéricos quando não fizer sentido.

REGRAS ABSOLUTAS:

- Nunca invente fatos.
- Nunca altere decisões.
- Preserve urgência quando existir.
- Linguagem natural de WhatsApp brasileiro.
- Tom maduro, direto e profissional.
- Clareza acima de floreio.

CRITÉRIOS DE EXCELÊNCIA:

- Reduzir agressividade implícita sem enfraquecer.
- Melhorar estrutura.
- Tornar a mensagem mais estratégica.
- Manter autoridade quando necessário.
- Soar como alguém experiente no mundo corporativo atual.

As três versões devem ser claramente diferentes:

1) Mais educada:
- Tom cordial.
- Reduz imposição.
- Mantém colaboração.

2) Mais firme:
- Direta.
- Objetiva.
- Sem agressividade.
- Sem passividade.

3) Mais profissional:
- Estrutura organizada.
- Linguagem madura.
- Natural para WhatsApp corporativo moderno.
- Sem formalismo antigo.

ANTES DAS VERSÕES, INCLUA:

🔎 Análise rápida:
Tom percebido: ...
Risco de ruído: ...
Principal melhoria aplicada: ...

FORMATO OBRIGATÓRIO:

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

