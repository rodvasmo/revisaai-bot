import os
from fastapi import FastAPI, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI

app = FastAPI()

# Inicializa cliente OpenAI
client = OpenAI()

# Modelo fixo GPT-4o
MODEL = "gpt-4o"

# Temperatura configurável (default 0.6)
TEMP = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

SYSTEM_PROMPT = """
Você é o RevisaAi, um líder experiente que ajuda profissionais a se comunicarem melhor no WhatsApp corporativo brasileiro.

Seu papel é elevar a qualidade da mensagem, proteger a reputação do usuário e tornar a comunicação mais clara, estratégica e humana.

Responda sempre de forma:

- Natural (português brasileiro)
- Direta e objetiva
- Madura e confiante
- Sem formalidade burocrática
- Sem linguagem de RH
- Sem frases genéricas de IA
- Sem julgamentos desnecessários

Se houver crítica, redirecione para foco em evolução futura.
Se houver cobrança, mantenha autoridade com clareza.
Se houver pedido interno, torne prioridade explícita.

Use frases curtas e claras.
Máximo de 2 frases por versão.

Formato obrigatório:

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
Sempre que possível, reestruture a mensagem para torná-la mais estratégica, não apenas suavizada.

"""

def gerar_versoes(texto_original: str) -> str:
    response = client.responses.create(
        model=MODEL,
        temperature=TEMP,
        max_output_tokens=800,
        input=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": f"""
Mensagem original:
{texto_original}

Passo 1 (interno): Analise profundamente:
- Qual é a emoção dominante?
- Qual é o risco reputacional real?
- O que falta de direcionamento?
- Como transformar isso em movimento estratégico?

Passo 2 (resposta final ao usuário):
Gere a resposta seguindo o formato obrigatório.
Reestruture estrategicamente, não apenas suavize.
Inclua direcionamento claro quando houver frustração ou repetição.
"""
            }
        ]
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
            "Me envie a mensagem que você quer melhorar e eu devolvo:\n"
            "• Versão recomendada\n"
            "• Uma alternativa mais direta\n"
            "• Uma alternativa mais diplomática\n"
        )
        return Response(content=str(twiml), media_type="application/xml")

    try:
        versoes = gerar_versoes(body)
        twiml.message(versoes)

    except Exception as e:
        print("Erro ao chamar OpenAI:", e)
        twiml.message(
            "Tive um problema ao revisar sua mensagem 😕\n"
            "Pode tentar novamente em alguns segundos?"
        )

    return Response(content=str(twiml), media_type="application/xml")
