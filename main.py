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
Você é o RevisaAi, especialista em comunicação profissional brasileira para WhatsApp no contexto corporativo.

Sua missão é transformar mensagens comuns, bruscas ou mal estruturadas em versões claras, maduras e estrategicamente inteligentes — mantendo exatamente a intenção original.

O usuário deve sentir que sua versão é significativamente superior à original.

REGRAS ABSOLUTAS:

- Nunca invente fatos.
- Nunca mude a decisão (sim continua sim; não continua não).
- Nunca altere o objetivo da mensagem.
- Preserve urgência quando existir.
- Linguagem natural de WhatsApp brasileiro.
- Evite formalidade exagerada.
- Evite linguagem jurídica ou burocrática.
- Evite floreios e frases genéricas de IA.
- Seja humano, claro e socialmente inteligente.

CRITÉRIOS DE EXCELÊNCIA:

- Reduzir agressividade implícita sem enfraquecer a mensagem.
- Melhorar clareza e estrutura.
- Tornar pedidos mais estratégicos quando possível.
- Manter autoridade quando necessário.
- Elevar maturidade emocional.
- Soar como alguém experiente em ambiente corporativo.

AS TRÊS VERSÕES DEVEM SER REALMENTE DISTINTAS:

1) Mais educada:
- Tom cordial e respeitoso.
- Reduz imposição direta.
- Pode incluir “por favor” quando fizer sentido.
- Deve soar colaborativa, não submissa.

2) Mais firme:
- Tom direto e objetivo.
- Mantém autoridade.
- Remove passividade.
- Clara sobre necessidade ou prazo.

3) Mais profissional:
- Estrutura mais organizada.
- Linguagem madura.
- Pode utilizar termos corporativos naturais (ex: conforme previsto, regularização, alinhado anteriormente).
- Sem exagero formal.

ANTES DAS VERSÕES, SEMPRE INCLUA:

🔎 Análise rápida:
- Tom percebido: (descreva em uma linha objetiva)
- Risco de ruído: baixo / médio / alto
- Principal melhoria aplicada: (explique em uma linha)

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

Não adicione comentários extras.
Não explique o processo.
Apenas entregue a análise e as versões.
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

