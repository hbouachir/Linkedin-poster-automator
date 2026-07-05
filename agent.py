"""
Agent IA Telegram + Gemini
--------------------------
Tu écris à ton bot Telegram, l'agent comprend la demande et exécute
automatiquement la bonne action (génération de post LinkedIn, article
Medium, sauvegarde de brouillon, etc.) grâce au function calling de Gemini.

Lancement :
    python agent.py

Variables d'environnement nécessaires (voir .env.example) :
    GEMINI_API_KEY
    TELEGRAM_BOT_TOKEN
"""

import os
import logging
from pathlib import Path

import requests
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

LINKEDIN_ACCESS_TOKEN = os.environ.get("LINKEDIN_ACCESS_TOKEN")
LINKEDIN_PERSON_URN = os.environ.get("LINKEDIN_PERSON_URN")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY manquant. Définis-le en variable d'environnement.")
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN manquant. Définis-le en variable d'environnement.")
# LinkedIn est optionnel : l'agent fonctionne sans (génération + sauvegarde
# uniquement) si LINKEDIN_ACCESS_TOKEN n'est pas défini. Utile tant que tu
# n'as pas encore lancé linkedin_auth.py.

DRAFTS_DIR = Path("drafts")
DRAFTS_DIR.mkdir(exist_ok=True)

genai.configure(api_key=GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# Outils (functions) que l'agent peut appeler
# ---------------------------------------------------------------------------
# Chaque fonction doit avoir une docstring claire : c'est ce que Gemini lit
# pour décider quand et comment l'appeler. Les type hints sont importants.

_last_model_used_for_content: dict = {}  # petit cache mémoire simple (facultatif)


def generate_linkedin_post(sujet: str, ton: str = "professionnel") -> str:
    """Génère un post LinkedIn court et engageant sur un sujet donné.

    Args:
        sujet: Le sujet principal du post (ex: "Terraform", "monitoring AWS").
        ton: Le ton souhaité (ex: "professionnel", "décontracté", "inspirant").
    """
    prompt = (
        f"Écris un post LinkedIn en français, ton {ton}, environ 100-150 mots, "
        f"sur le sujet suivant : {sujet}. "
        "Structure : accroche forte en premiere ligne, corps avec une idée "
        "concrete ou un retour d'experience, call-to-action a la fin. "
        "Pas de hashtags excessifs (3 maximum a la fin)."
    )
    return _call_gemini_raw(prompt)


def generate_medium_article(sujet: str, longueur: str = "moyenne") -> str:
    """Génère un brouillon d'article Medium détaillé sur un sujet donné.

    Args:
        sujet: Le sujet principal de l'article.
        longueur: "courte" (~300 mots), "moyenne" (~600 mots) ou "longue" (~1000 mots).
    """
    mots = {"courte": 300, "moyenne": 600, "longue": 1000}.get(longueur, 600)
    prompt = (
        f"Écris un article de blog en français, style Medium, sur le sujet : {sujet}. "
        f"Longueur cible : environ {mots} mots. "
        "Structure : titre accrocheur, introduction, 2-3 sections avec sous-titres, "
        "conclusion avec ouverture. Ton expert mais accessible."
    )
    return _call_gemini_raw(prompt)


def save_draft(contenu: str, plateforme: str) -> str:
    """Sauvegarde un brouillon de contenu dans un fichier local pour relecture.

    Args:
        contenu: Le texte du brouillon à sauvegarder.
        plateforme: La plateforme cible ("linkedin" ou "medium").
    """
    filename = DRAFTS_DIR / f"drafts_{plateforme.lower()}.txt"
    with open(filename, "a", encoding="utf-8") as f:
        f.write(contenu.strip() + "\n\n---\n\n")
    return f"Brouillon sauvegardé dans {filename}"


def list_recent_drafts(plateforme: str, nombre: int = 3) -> str:
    """Liste les derniers brouillons sauvegardés pour une plateforme donnée.

    Args:
        plateforme: La plateforme cible ("linkedin" ou "medium").
        nombre: Nombre de brouillons récents à retourner.
    """
    filename = DRAFTS_DIR / f"drafts_{plateforme.lower()}.txt"
    if not filename.exists():
        return "Aucun brouillon trouvé pour cette plateforme."
    content = filename.read_text(encoding="utf-8")
    entries = [e.strip() for e in content.split("---") if e.strip()]
    recent = entries[-nombre:]
    return "\n\n===\n\n".join(recent) if recent else "Aucun brouillon trouvé."


def post_to_linkedin(contenu: str) -> str:
    """Publie immédiatement un texte sur ton profil LinkedIn personnel.

    ATTENTION : cette action est irréversible et publique. Ne l'utilise
    QUE si l'utilisateur a explicitement demandé de publier maintenant
    (ex: "publie ce post sur LinkedIn"). Ne publie jamais un contenu
    généré sans confirmation explicite de l'utilisateur dans le message.

    Args:
        contenu: Le texte exact à publier sur LinkedIn.
    """
    if not LINKEDIN_ACCESS_TOKEN or not LINKEDIN_PERSON_URN:
        return (
            "Impossible de publier : LinkedIn n'est pas configuré. "
            "Lance d'abord linkedin_auth.py pour générer un token, "
            "puis ajoute LINKEDIN_ACCESS_TOKEN et LINKEDIN_PERSON_URN à ton .env."
        )

    url = "https://api.linkedin.com/rest/posts"
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "LinkedIn-Version": "202401",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    payload = {
        "author": LINKEDIN_PERSON_URN,
        "commentary": contenu,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=15)

    if resp.status_code in (200, 201):
        return "Post publié avec succès sur LinkedIn."
    if resp.status_code == 401:
        return (
            "Token LinkedIn expiré ou invalide. Relance linkedin_auth.py "
            "pour en générer un nouveau."
        )
    return f"Échec de la publication (code {resp.status_code}) : {resp.text}"


def _call_gemini_raw(prompt: str) -> str:
    """Appel Gemini simple, sans function calling, pour la génération de contenu."""
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content(prompt)
    return response.text


# ---------------------------------------------------------------------------
# Configuration de l'agent avec function calling
# ---------------------------------------------------------------------------

AGENT_TOOLS = [
    generate_linkedin_post,
    generate_medium_article,
    save_draft,
    list_recent_drafts,
    post_to_linkedin,
]

SYSTEM_INSTRUCTION = (
    "Tu es l'assistant personnel de prospection freelance d'un Senior DevOps "
    "Engineer AWS. Tu l'aides a générer et gérer du contenu LinkedIn et Medium "
    "pour développer son activité freelance. "
    "Utilise les outils disponibles pour générer du contenu, le sauvegarder, "
    "ou consulter les brouillons existants. "
    "Réponds toujours en français, de façon concise et actionnable. "
    "Si une demande est ambiguë, pose une question courte avant d'agir. "
    "IMPORTANT : n'utilise l'outil post_to_linkedin QUE si l'utilisateur "
    "a explicitement demandé de publier maintenant (mots comme 'publie', "
    "'poste-le', 'envoie-le sur LinkedIn'). Après une simple génération, "
    "propose toujours le texte et demande confirmation avant de publier."
)

agent_model = genai.GenerativeModel(
    "gemini-2.5-flash",
    tools=AGENT_TOOLS,
    system_instruction=SYSTEM_INSTRUCTION,
)

# Une session de chat par utilisateur Telegram (clé = chat_id)
_user_sessions: dict = {}


def _get_session(chat_id: int):
    if chat_id not in _user_sessions:
        _user_sessions[chat_id] = agent_model.start_chat(
            enable_automatic_function_calling=True
        )
    return _user_sessions[chat_id]


# ---------------------------------------------------------------------------
# Handlers Telegram
# ---------------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    user_text = update.message.text
    logger.info("Message reçu de %s : %s", chat_id, user_text)

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    try:
        session = _get_session(chat_id)
        response = session.send_message(user_text)
        reply = response.text or "(pas de réponse générée)"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erreur lors du traitement du message")
        reply = f"Une erreur est survenue : {exc}"

    # Telegram limite les messages à 4096 caractères
    for i in range(0, len(reply), 4000):
        await update.message.reply_text(reply[i : i + 4000])


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Salut ! Je suis ton agent de prospection freelance.\n\n"
        "Exemples de ce que tu peux me demander :\n"
        "- Génère un post LinkedIn sur Terraform\n"
        "- Écris un article Medium sur le monitoring AWS et sauvegarde-le\n"
        "- Montre-moi mes 3 derniers brouillons LinkedIn"
    )


def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex("^/start"), handle_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Agent démarré, en écoute des messages Telegram (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
