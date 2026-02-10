from fastapi import FastAPI, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    body = (form.get("Body") or "").strip()
    msg = body.lower()

    twiml = MessagingResponse()

    if msg in ("", "oi", "olá", "ola", "hello", "hi"):
        twiml.message(
            "👋 Oi! Eu sou o RevisaAi.\n\n"
            "Me mande a mensagem que você quer melhorar e eu te devolvo 3 versões:\n"
            "1) Mais educada\n2) Mais firme\n3) Mais profissional"
        )
    else:
        twiml.message(
            f"Recebi:\n“{body}”\n\n"
            "✅ Se o fluxo estiver ok, no próximo passo eu já devolvo as versões melhoradas."
        )

    return Response(content=str(twiml), media_type="application/xml")
