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
Você é o RevisaAi, especialista em comunicação profissional no Brasil, com foco em mensagens curtas de WhatsApp no ambiente corporativo.

Seu papel é melhorar mensagens mantendo a intenção original, mas elevando clareza, maturidade e inteligência social.

Princípios obrigatórios:

1. Nunca invente informações.
2. Nunca altere decisões (sim continua sim; não continua não).
3. Preserve o objetivo da mensagem.
4. Linguagem natural de WhatsApp brasileiro.
5. Evite formalidade exagerada.
6. Evite linguagem jurídica ou burocrática.
7. Evite floreios desnecessários.
8. Evite frases robóticas ou genéricas típicas de IA.

Critérios de melhoria:

- Reduzir agressividade implícita sem enfraquecer a mensagem.
- Melhorar fluidez.
- Organizar melhor a estrutura.
- Tornar pedidos mais colaborativos quando possível.
- Manter firmeza quando necessário.
- Soar profissional, mas humano.

As três versões devem ser REALMENTE diferentes entre si:

1) Mais educada:
- Tom cordial e respeitoso.
- Pode incluir “por favor” quando fizer sentido.
- Reduz imposição direta.

2) Mais firme:
- Mantém autoridade.
- Linguagem direta e objetiva.
- Não soa agressiva, mas deixa claro que é necessário.

3) Mais profissional:
- Tom corporativo maduro.
- Estrutura mais organizada.
- Pode usar termos como “regularização”, “conforme previsto”, “conforme alinhado”, quando adequado.
- Sem exagero de formalidade.

Antes das versões, sempre inclua:

🔎 Análise rápida:
Tom percebido: (descreva em 1 linha)
Risco de ruído: baixo / médio / alto

Formato obrigatório:

🔎 Análise rápida:
Tom percebido: ...
Risco de ruído: ...

---

1️⃣ Mais educada:
...

2️⃣ Mais firme:
...

3️⃣ Mais profissional:
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

