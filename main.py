import os
from fastapi import FastAPI, Request
from fastapi.responses import Response
from twilio.twiml.messaging_response import MessagingResponse
from openai import OpenAI

app = FastAPI()
client = OpenAI()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
TEMP = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
MAX_TOKENS = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "650"))

FOOTER = "\n\nSe quiser, revise a próxima comigo também."

SYSTEM_PROMPT = """
Você é o RevisaAi.

Atue como um mentor sofisticado de comunicação profissional no WhatsApp brasileiro.

Seu papel é refinar a mensagem: elevar clareza, maturidade e estratégia, mantendo integralmente a intenção e os fatos do usuário.

Postura:

- Português brasileiro natural.
- Tom calmo, articulado e seguro.
- Sofisticado, sem formalidade institucional.
- Profissional, sem frieza.
- Evite frases genéricas de IA.
- Evite linguagem de RH ou corporativa padrão.
- Evite checklist artificial.
- Evite abertura automática como “Oi, tudo bem?” (a menos que já exista na mensagem original).
- Não use placeholders como [Nome].
- Nunca invente fatos, prazos, responsáveis ou decisões.
- Nunca substituir afirmações factuais por formulações genéricas.

Preservação de contexto:

- Preserve explicitamente elementos como:
  “ainda não tive retorno”
  “já foi pedido 3 vezes”
  datas, valores e repetições.
- Não enfraqueça a força original da mensagem.
- Refine sem neutralizar.

Qualidade editorial:

- Máximo de 2 frases por versão.
- Prefira formulações naturais a construções institucionais.
- Evite termos como:
  “inadequado”
  “alinhado com o esperado”
  “não atendeu às expectativas”
  “adequado”
  “desconforto”
- Evite finalizar com “por favor” se a frase já for naturalmente respeitosa.
- No diagnóstico, evite conselhos genéricos como “adicionar cordialidade”.
  Seja específico sobre como a mensagem pode ser interpretada.

Tratamento por intenção:

1) Crítica comportamental:
- Contextualize o evento objetivamente.
- Transforme julgamento em dimensão estratégica.
- Direcione para evolução futura.
- Nunca manter a formulação emocional original.

2) Cobrança com repetição:
- Frase 1: Contexto neutro com o fato preservado.
- Frase 2: Pedido de encaminhamento claro (status, responsável, próximo passo e prazo) em formulação natural, sem checklist mecânico.

3) Follow-up externo (entrevista, contrato, proposta etc.):
- Preserve fatos e tempo.
- Peça atualização e próximos passos sem inventar prazo.
- Prefira “atualização” em vez de “update” na versão recomendada.
- Evite institucionalizar (“há alguma atualização disponível”).

4) Pedido interno:
- Deixe claro o objetivo e prioridade.
- Preserve prazos existentes.
- Não invente prazo.

Objetivo final:

A Versão recomendada deve ser a mais estratégica e equilibrada das três.
Ela não deve ser a mais neutra nem a mais conservadora.
Ela deve soar como a melhor escolha executiva.
Nunca seca.
Nunca burocrática.
Nunca excessivamente cordial.
Nunca institucional.

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

# Micro-frameworks (invisíveis) para consistência
MODE_GUIDES = {
    "critica_comportamental": """
A mensagem é uma crítica sobre postura/comportamento.

Obrigatório na Versão recomendada:
- Reestruture em 2 frases:
  1) Contexto objetivo do evento (ex: “Na reunião de hoje…”).
  2) Transforme julgamento em dimensão estratégica + evolução futura (ex: “poderia ter sido mais estratégica… vale refletirmos…”).
- Evite linguagem emocional (“me causou desconforto”) e termos acusatórios (“inadequado”, “errado”).
- Foque em comportamento e melhora futura; tom calmo e firme.
""",
    "cobranca_repetida": """
A mensagem é uma cobrança com repetição/frustração (ex: “já foi pedido 3 vezes”, “ainda não avançou”).

Obrigatório na Versão recomendada:
- 2 frases:
  1) Contexto neutro com o fato (repetição/atraso) preservando os termos do original.
  2) Pedido de ENCAMINHAMENTO CLARO em uma frase natural (sem checklist seco):
     peça status + responsável + próximo passo + prazo, sem inventar.
- Não use “quem pode me informar” se o destinatário já é o interlocutor.
""",
    "followup_externo": """
A mensagem é um follow-up externo (entrevista, contrato, e-mail, proposta, etc.).

Obrigatório na Versão recomendada:
- Preserve fatos (“na semana passada”, “ainda não tive retorno”).
- Peça atualização/andamento e próximos passos, sem inventar prazo.
- Evite institucionalizar (“há alguma atualização disponível”); prefira naturalidade (“você consegue me atualizar…”).
""",
    "pedido_interno": """
A mensagem é um pedido interno (ajuda/material/entrega).

Obrigatório na Versão recomendada:
- Deixe claro o pedido e prioridade.
- Se houver prazo no original, preserve; se não houver, não invente prazo.
- Tom calmo, objetivo e direto.
""",
    "neutro": """
A mensagem é neutra/geral.

Objetivo:
- Tornar mais claro e profissional sem mudar intenção.
- Manter concisão (1–2 frases).
""",
}


def classify_mode(texto: str) -> str:
    """Classificador leve (heurística). Mantém consistência sem virar um monstro de ifs."""
    t = (texto or "").strip().lower()

    # Crítica comportamental (postura, atitude, comportamento em reunião, etc.)
    critica_markers = [
        "não gostei",
        "nao gostei",
        "sua postura",
        "sua atitude",
        "sua forma",
        "seu comportamento",
        "na reunião",
        "na reuniao",
        "foi inadequad",
        "não foi adequado",
        "nao foi adequado",
        "deixou a desejar",
    ]
    if any(m in t for m in critica_markers):
        return "critica_comportamental"

    # Cobrança repetida
    repeticao_markers = [
        "3 vezes",
        "três vezes",
        "tres vezes",
        "já foi pedido",
        "ja foi pedido",
        "já pedi",
        "ja pedi",
        "de novo",
        "novamente",
        "ainda não",
        "ainda nao",
        "não avançou",
        "nao avançou",
        "não foi resolvido",
        "nao foi resolvido",
    ]
    cobranca_verbs = [
        "resolver",
        "corrigir",
        "retornar",
        "responder",
        "atualizar",
        "status",
        "andamento",
        "encaminhamento",
        "pagamento",
        "pagar",
        "nf",
        "nota fiscal",
        "fatura",
        "invoice",
    ]
    if any(m in t for m in repeticao_markers) and any(v in t for v in cobranca_verbs):
        return "cobranca_repetida"

    # Follow-up externo (entrevista, contrato, proposta, e-mail)
    followup_markers = [
        "entrevista",
        "processo seletivo",
        "vaga",
        "recrut",
        "contrato",
        "proposta",
        "enviei",
        "encaminhei",
        "sem retorno",
        "ainda não tive retorno",
        "ainda nao tive retorno",
        "update",
        "novidades",
        "alguma atualização",
        "alguma atualizacao",
    ]
    temporal_markers = ["semana passada", "ontem", "segunda", "terça", "terca", "quarta", "quinta", "sexta", "hoje"]
    if any(m in t for m in followup_markers) and (any(x in t for x in temporal_markers) or "retorno" in t):
        return "followup_externo"

    # Pedido interno
    pedido_markers = [
        "poderia me ajudar",
        "consegue me ajudar",
        "preciso",
        "por favor",
        "me ajuda",
        "montar o material",
        "preparar o material",
        "me manda",
        "me enviar",
        "me envia",
        "até hoje",
        "ate hoje",
        "hoje",
        "até o fim do dia",
        "ate o fim do dia",
        "fim do dia",
    ]
    if any(m in t for m in pedido_markers):
        return "pedido_interno"

    return "neutro"


def gerar_versoes(texto_original: str, mode: str) -> str:
    guide = MODE_GUIDES.get(mode, MODE_GUIDES["neutro"]).strip()

    user_instruction = f"""
Mensagem original:
{texto_original}

Playbook (siga com rigor, mas sem parecer mecânico):
{guide}

Gere a resposta final no formato obrigatório.
"""

    resp = client.responses.create(
        model=MODEL,
        temperature=TEMP,
        max_output_tokens=MAX_TOKENS,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_instruction},
        ],
    )

    # Normalmente output_text funciona bem
    return (getattr(resp, "output_text", "") or "").strip() or "Não consegui gerar a resposta agora. Pode tentar novamente?"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/whatsapp")
async def whatsapp_webhook(request: Request):
    form = await request.form()
    body = (form.get("Body") or "").strip()
    msg = body.lower()

    twiml = MessagingResponse()

    # Onboarding simples
    if msg in ("", "oi", "olá", "ola", "hello", "hi"):
        twiml.message(
            "👋 Eu sou o RevisaAi.\n\n"
            "As vezes um pequeno ajuste muda tudo.\n"
            "Envie sua mensagem e eu devolvo uma versão mais clara e profissional."
        )
        return Response(content=str(twiml), media_type="application/xml")

    try:
        mode = classify_mode(body)
        out = gerar_versoes(body, mode=mode)
        twiml.message(out + FOOTER)

    except Exception as e:
        print("Erro ao chamar OpenAI:", e)
        twiml.message("Tive um problema ao revisar sua mensagem 😕 Pode tentar novamente em alguns segundos?")

    return Response(content=str(twiml), media_type="application/xml")