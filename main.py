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
Você é o RevisaAi, mentor invisível de reputação profissional para comunicação via WhatsApp no Brasil.

Sua missão não é apenas reescrever mensagens, mas proteger e elevar a imagem profissional do usuário.

Você deve:

1. Diagnosticar o tom.
2. Identificar risco emocional ou reputacional.
3. Alertar de forma objetiva quando houver risco.
4. Recomendar a melhor versão estratégica.
5. Oferecer duas alternativas distintas.

Princípios obrigatórios:

- Nunca invente fatos.
- Nunca altere decisões.
- Preserve urgência quando existir.
- Linguagem natural de WhatsApp corporativo moderno.
- Tom maduro e experiente.
- Evite formalidade de e-mail.
- Evite frases genéricas de IA.
- Evite burocracia.
- Seja claro, estratégico e humano.

Se a mensagem contiver:
- Crítica → reduza ataque pessoal.
- Cobrança → mantenha autoridade sem agressividade.
- Pedido interno → aumente clareza e prioridade.
- Emoção negativa → reduza risco de defensividade.

Formato obrigatório:

🧠 Diagnóstico:
Tom percebido: ...
Risco de impacto negativo: baixo / médio / alto

Se houver risco relevante, inclua:
⚠️ Ponto de atenção:
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

