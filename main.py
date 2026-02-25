import os
import re
import time
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client as TwilioClient
from openai import OpenAI

app = FastAPI()
client = OpenAI()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
TEMP = float(os.getenv("OPENAI_TEMPERATURE", "0.6"))

MAX_TOKENS_DEFAULT = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "650"))
MAX_TOKENS_MEMO = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS_MEMO", "1100"))

FOOTER = "\n\nSe quiser, revise a próxima comigo também."

# ========= Twilio Outbound (para enviar depois) =========
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")  # ex: "whatsapp:+14155238886" (sandbox)

twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# ========= Dedupe básico (evita duplicar envios) =========
SEEN = {}  # {MessageSid: timestamp}
SEEN_TTL_SECONDS = 60 * 60  # [PROD] 60 min (antes: 10 min)

def _seen_recently(message_sid: str) -> bool:
    """Idempotência simples em memória.
    Importante: some se o serviço reiniciar, mas reduz MUITO duplicação por retry."""
    if not message_sid:
        return False

    now = time.time()

    # [PROD] limpeza por TTL
    # evita crescer infinito e cobre retries mais tardios
    expired = [sid for sid, ts in SEEN.items() if (now - ts) > SEEN_TTL_SECONDS]
    for sid in expired:
        SEEN.pop(sid, None)

    if message_sid in SEEN:
        return True

    SEEN[message_sid] = now
    return False


# =========================
# 1) BASE STYLE (GLOBAL)
# =========================
SYSTEM_BASE = """
Você é o RevisaAi.

Atue como um profissional maduro ajustando frases de comunicação no WhatsApp brasileiro.

Objetivo:
Refinar a mensagem para ficar mais clara, madura e bem colocada — sem alterar intenção, fatos ou responsabilidades explícitas.

Estilo:
- Português brasileiro natural.
- Tom calmo, articulado e seguro.
- Sofisticado, mas não formal.
- Profissional, mas não frio.
- Sem linguagem de RH, sem consultoria, sem burocracia.
- Sem frases genéricas de IA.
- Sem checklist artificial.
- Máximo de 2 frases por versão (EXCETO em memorando_estrategico).
- Não use placeholders como [Nome].
- Evite “Oi, tudo bem?” a menos que exista no original.

Regras críticas:
- Nunca invente fatos, prazos, responsáveis ou decisões.
- Preserve responsabilidade explícita quando existir (ex: “você ficou de…”).
- Não transforme em construção impessoal/passiva:
  proibido: “Fico no aguardo…”, “Aguardo retorno…”, “Permaneço no aguardo…”
- Evite iniciar a Versão recomendada com “Você poderia…”.
  Prefira “Você consegue…”, “Você pode…”, ou formulações naturais equivalentes.
- Não use termos acusatórios/infantilizantes: “prometeu”, “cobrador”.

REGRA (FIRMEZA COM CONSEQUÊNCIA):
- Se a mensagem original tiver condição + consequência (ex: “Se isso continuar…, vamos ter que…”),
  preserve a estrutura condicional e a consequência.
- Reduza apenas o tom ameaçador; NÃO dilua para linguagem genérica.

Hierarquia:
- A Versão recomendada deve ser a mais equilibrada e madura (puxada para o lado diplomático), sem soar passiva.
- Em mensagens com pressão, a Versão recomendada deve manter direção e consequência (sem ameaça).

EXEMPLOS DE REFERÊNCIA (PADRÃO DE TOM EXECUTIVO):

Exemplo 1
Mensagem original:
"Se isso continuar desse jeito, vamos ter que rever responsabilidades."

Versão recomendada:
"Se esse padrão persistir, precisaremos rever responsabilidades para assegurar execução consistente."

Exemplo 2
Mensagem original:
"Está demorando mais do que o esperado."

Versão recomendada:
"O ritmo está abaixo do esperado. Precisamos ajustar para evitar impacto nas entregas."

Exemplo 3
Mensagem original:
"Já falamos disso 3 vezes e continua igual."

Versão recomendada:
"Já discutimos esse ponto algumas vezes e ainda não houve avanço. Precisamos definir como isso evolui daqui para frente."

Exemplo 4
Mensagem original:
"Não gostei da sua postura na reunião de hoje."

Versão recomendada:
"Na reunião de hoje, sua abordagem poderia ter sido mais estratégica. Vale refletirmos sobre como conduzir situações assim de forma mais construtiva."

Exemplo 5
Mensagem original:
"Você ficou de me dar um retorno e não recebi."

Versão recomendada:
"Você ficou de me dar um retorno e ainda não recebi. Consegue me atualizar sobre isso?"

Exemplo 6
Mensagem original:
"Isso é irresponsabilidade."

Versão recomendada:
"Essa decisão trouxe um risco que já havia sido sinalizado. Precisamos ajustar a forma de condução para evitar recorrência."

Exemplo 7
Mensagem original:
"Estamos ficando para trás."

Versão recomendada:
"Estamos perdendo ritmo frente ao que precisamos entregar. Precisamos retomar foco e prioridade."

Formato obrigatório:

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

# =========================
# 2) MINI-PROMPTS POR TIPO
# =========================
TYPE_GUIDES = {
    "memorando_estrategico": """
Intenção detectada: MEMORANDO ESTRATÉGICO / COMUNICAÇÃO DE LIDERANÇA (texto longo).

Objetivo:
Reestruturar como um memo executivo: firme, claro, específico e orientado a execução.
Não apenas “limpar” frases.

Voz:
- Português brasileiro natural, tom calmo e firme.
- Evite linguagem corporativa genérica e clichês.
  Proibido: “observamos”, “precisa ser abordado com prioridade”, “superarmos desafios”, “avançarmos juntos”,
  “conto com o comprometimento”, “confio na capacidade”, “impactos negativos”.
- Evite termos emocionais/ambíguos: “constrangedor”, “desconforto”, “ninguém assume nada”.
  Reformule para: preparo, padrão, responsabilidade, decisão, execução, retrabalho.

Estrutura (Versão recomendada):
- 2–3 parágrafos curtos, com sequência lógica.
- Pode passar de 2 frases, mas mantenha concisão.

Regras:
- Preserve fatos do texto original.
- Não invente prazo, responsável, número, ou “próxima etapa” específica.
""",
    "critica": """
Intenção detectada: CRÍTICA / FEEDBACK sobre postura/atitude/abordagem.

Diretrizes:
- Eleve para formulação construtiva e orientada ao futuro (sem “RH speak”).
- Firmeza calma; evite acusação pessoal crua.
- Preserve fatos (ex: “na reunião de hoje”) se existir no original.
""",
    "cobranca_repetida": """
Intenção detectada: COBRANÇA COM REPETIÇÃO / SEM AVANÇO.

Diretrizes:
- Preserve repetição/sem avanço (“já falamos”, “3 vezes”, “continua igual”).
- Evite permissividade na Versão recomendada.
- Firme e madura, orientada a avanço, sem checklist.
""",
    "cobranca_firme": """
Intenção detectada: COBRANÇA FIRME (demora / ritmo / atraso).

Diretrizes:
- Preserve a constatação de demora.
- Adicione leve direcionamento para avanço.
- Não invente prazo. Sem checklist.
""",
    "followup_externo": """
Intenção detectada: FOLLOW-UP EXTERNO.

Diretrizes:
- Preserve tempo/fato (“semana passada”, “ainda não tive retorno”) se existir.
- Peça atualização de forma natural.
""",
    "pedido_interno": """
Intenção detectada: PEDIDO INTERNO.

Diretrizes:
- Deixe claro o que precisa e a prioridade.
- Preserve prazos existentes; se não houver, não invente.
""",
    "neutro": """
Intenção detectada: NEUTRO / GERAL.

Diretrizes:
- Apenas refine para clareza e maturidade.
""",
}

INTENT_LABELS = set(TYPE_GUIDES.keys())

# =========================
# 2.5) GATILHO PARA TEXTO LONGO
# =========================
def _is_long_text(texto: str) -> bool:
    t = (texto or "").strip()
    words = len(t.split())
    paragraphs = len([p for p in re.split(r"\n\s*\n", t) if p.strip()])
    has_multi_sentences = len(re.findall(r"[.!?]", t)) >= 3
    return (words >= 90) or (paragraphs >= 2 and words >= 60) or (has_multi_sentences and words >= 80)

# =========================
# 3) CLASSIFICAÇÃO (LLM)
# =========================
def classificar_intencao(texto: str) -> str:
    if _is_long_text(texto):
        return "memorando_estrategico"

    prompt = f"""
Classifique a intenção principal da mensagem abaixo em APENAS UMA destas opções:
- critica
- cobranca_repetida
- cobranca_firme
- followup_externo
- pedido_interno
- neutro

Regras:
- Responda com apenas a palavra da opção (sem pontuação, sem explicação).
- Se houver repetição explícita, prefira cobranca_repetida.
- Se houver demora/atraso sem repetição, prefira cobranca_firme.
- Se for entrevista/proposta/contrato, prefira followup_externo.
- Se for pedido interno, prefira pedido_interno.
- Se for postura/atitude, prefira critica.

Mensagem:
{texto}
"""
    try:
        r = client.responses.create(
            model=MODEL,
            temperature=0.0,
            max_output_tokens=20,
            input=[
                {"role": "system", "content": "Você é um classificador. Responda apenas o rótulo exato."},
                {"role": "user", "content": prompt},
            ],
        )
        label = (getattr(r, "output_text", "") or "").strip().lower()
        label = re.sub(r"[^a-z_]+", "", label)
        return label if label in INTENT_LABELS else "neutro"
    except Exception as e:
        print("Erro ao classificar intenção:", e)
        return "neutro"

# =========================
# 4) GERAÇÃO (LLM)
# =========================
def gerar_versoes(texto_original: str, intent: str) -> str:
    guide = TYPE_GUIDES.get(intent, TYPE_GUIDES["neutro"]).strip()

    user_instruction = f"""
Mensagem original:
{texto_original}

{guide}

Agora gere a resposta final no FORMATO OBRIGATÓRIO.
"""

    max_tokens = MAX_TOKENS_MEMO if intent == "memorando_estrategico" else MAX_TOKENS_DEFAULT

    r = client.responses.create(
        model=MODEL,
        temperature=TEMP,
        max_output_tokens=max_tokens,
        input=[
            {"role": "system", "content": SYSTEM_BASE},
            {"role": "user", "content": user_instruction},
        ],
    )
    out = (getattr(r, "output_text", "") or "").strip()
    return out or "Não consegui gerar a resposta agora. Pode tentar novamente?"

# =========================
# 5) ENVIO ASSÍNCRONO VIA TWILIO
# =========================
def send_whatsapp(to_number: str, text: str) -> None:
    if not twilio_client:
        print("Twilio não configurado (SID/TOKEN).")
        return
    if not TWILIO_WHATSAPP_FROM:
        print("TWILIO_WHATSAPP_FROM não configurado.")
        return
    try:
        twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=to_number,
            body=text,
        )
    except Exception as e:
        print("Erro ao enviar via Twilio:", e)

def process_and_send(from_number: str, original_text: str, message_sid: str = "") -> None:
    # [PROD] logs mínimos e latência
    job_start = time.time()
    words = len((original_text or "").split())

    try:
        intent = classificar_intencao(original_text)

        openai_start = time.time()
        out = gerar_versoes(original_text, intent=intent)
        openai_latency = time.time() - openai_start

        send_whatsapp(from_number, out + FOOTER)

        total = time.time() - job_start
        print(
            f"[revisaai] sid={message_sid or '-'} intent={intent} words={words} "
            f"openai_s={openai_latency:.2f} total_s={total:.2f}"
        )

    except Exception as e:
        total = time.time() - job_start
        print(
            f"[revisaai] sid={message_sid or '-'} ERROR words={words} total_s={total:.2f} err={e}"
        )
        send_whatsapp(from_number, "Tive um problema ao revisar sua mensagem 😕 Pode tentar novamente em alguns segundos?")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    form = await request.form()
    body = (form.get("Body") or "").strip()
    msg = body.lower()
    from_number = (form.get("From") or "").strip()
    message_sid = (form.get("MessageSid") or "").strip()

    # [PROD] dedupe antes de qualquer coisa (já estava certo)
    if _seen_recently(message_sid):
        twiml = MessagingResponse()
        return Response(content=str(twiml), media_type="text/xml; charset=utf-8")

    twiml = MessagingResponse()

    # Onboarding (não mexi)
    if msg in ("", "oi", "olá", "ola", "hello", "hi"):
        twiml.message(
            "👋 Eu sou o RevisaAi.\n\n"
            "Se a mensagem é importante, vale revisar antes de enviar.\n"
            "Manda aqui."
        )
        return Response(content=str(twiml), media_type="text/xml; charset=utf-8")

    # ACK imediato + background (não mexi)
    twiml.message("⏳ Revisando… já te devolvo.")

    # [PROD] passa MessageSid pro log
    background_tasks.add_task(process_and_send, from_number, body, message_sid)

    return Response(content=str(twiml), media_type="text/xml; charset=utf-8")