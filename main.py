import os
from fastapi import FastAPI, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI

app = FastAPI()
client = OpenAI()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
TEMP = float(os.getenv("OPENAI_TEMPERATURE", "0.6"))
MAX_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "650"))

FOOTER = "\n\nSe quiser, revise a próxima comigo também."

SYSTEM_PROMPT = """
Você é o RevisaAi.

Atue como um profissional maduro ajustando frases de comunicação no WhatsApp brasileiro.

Seu papel é refinar a mensagem:
- elevar clareza,
- aumentar maturidade,
- manter a intenção original,
- preservar fatos e responsabilidades explícitas.

POSTURA:

- Português brasileiro natural.
- Tom calmo, articulado e seguro.
- Sofisticado, mas não formal.
- Profissional, mas não frio.
- Evite linguagem de RH.
- Evite frases genéricas de IA.
- Evite estrutura de consultoria.
- Evite checklist artificial.
- Evite burocracia.

REGRAS IMPORTANTES:

- Nunca invente fatos, prazos ou responsáveis.
- Nunca transforme frase direta em construção impessoal.
- Preserve responsabilidade explícita.
  Ex: se houver “você ficou de…”, mantenha o sujeito.
- Não substituir por construções como:
  “Fico no aguardo…”
  “Aguardo retorno…”
  “Permaneço no aguardo…”
- Evite neutralizar demais a força original.
- Máximo de 2 frases por versão.

HIERARQUIA DAS VERSÕES:

- A Versão recomendada deve ser a mais equilibrada e madura.
- Ela deve se aproximar mais da alternativa diplomática do que da alternativa direta.
- Nunca deve soar passiva.
- Nunca deve soar institucional.
- Nunca deve soar seca.

TRATAMENTO POR INTENÇÃO:

- Se houver crítica → elevar para dimensão construtiva e futura.
- Se houver cobrança → manter clareza sem agressividade.
- Se houver repetição → manter o fato e direcionar de forma madura.
- Se houver follow-up → pedir atualização naturalmente.
- Se houver pedido interno → tornar claro sem inventar prazo.

FORMATO OBRIGATÓRIO:

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
    response = client.responses.create(
        model=MODEL,
        temperature=TEMP,
        max_output_tokens=MAX_TOKENS,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Mensagem original:\n{texto_original}"},
        ],
    )

    return (getattr(response, "output_text", "") or "").strip()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    body = (form.get("Body") or "").strip()
    msg = body.lower()

    twiml = MessagingResponse()

    # Onboarding
    if msg in ("", "oi", "olá", "ola", "hello", "hi"):
        twiml.message(
            "👋 Eu sou o RevisaAi.\n\n"
            "Antes de mandar uma mensagem importante, me envie aqui.\n"
            "Eu ajusto para deixá-la mais clara e madura."
        )
        print("TwiML:", str(twiml))
        return Response(content=str(twiml), media_type="text/xml; charset=utf-8")

    try:
        resposta = gerar_versoes(body)
        twiml.message(resposta + FOOTER)

    except Exception as e:
        print("Erro ao chamar OpenAI:", e)
        twiml.message(
            "Tive um problema ao revisar sua mensagem 😕 "
            "Pode tentar novamente em alguns segundos?"
        )

    print("TwiML:", str(twiml))
    return Response(content=str(twiml), media_type="text/xml; charset=utf-8")