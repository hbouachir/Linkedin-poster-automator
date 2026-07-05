# Agent Telegram + Gemini — Prospection Freelance

Agent conversationnel : tu parles à ton bot Telegram, il génère et gère
du contenu LinkedIn / Medium pour toi (function calling Gemini).

## 1. Prérequis

- Python 3.10+
- Une clé API Gemini gratuite : https://aistudio.google.com/ → "Get API key"
- Un bot Telegram : parle à **@BotFather** sur Telegram → `/newbot` → récupère le token

## 2. Installation

```bash
python -m venv venv
source venv/bin/activate        # sous Windows : venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Configuration

```bash
cp .env.example .env
```

Ouvre `.env` et colle tes deux clés :

```
GEMINI_API_KEY=AIzaSy...
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
```

Puis charge les variables avant de lancer (Linux/Mac) :

```bash
export $(cat .env | xargs)
```

Sous Windows (PowerShell) :

```powershell
Get-Content .env | ForEach-Object {
    $name, $value = $_.split('=')
    Set-Item -Path "Env:$name" -Value $value
}
```

## 4. Lancer l'agent

```bash
python agent.py
```

Tu dois voir dans le terminal :
```
Agent démarré, en écoute des messages Telegram (polling)...
```

## 5. Utilisation

Va sur Telegram, ouvre une conversation avec ton bot, envoie `/start` puis essaie par exemple :

- "Génère-moi un post LinkedIn sur Terraform"
- "Écris un article Medium sur le monitoring AWS et sauvegarde-le"
- "Montre-moi mes 3 derniers brouillons LinkedIn"

L'agent choisit lui-même quelle action exécuter (génération, sauvegarde,
consultation) grâce au function calling — tu n'as rien à coder de plus.

## 6. Activer la publication réelle sur LinkedIn (optionnel)

Par défaut, l'agent génère et sauvegarde des brouillons, mais ne publie
rien. Pour lui donner la capacité de publier directement sur ton profil
LinkedIn :

1. Crée une app sur https://www.linkedin.com/developers/apps
2. Dans l'onglet "Products", active **"Share on LinkedIn"**
3. Dans l'onglet "Auth", récupère ton **Client ID** et **Client Secret**,
   et ajoute `http://localhost:8000/callback` comme Redirect URL
4. Exporte ces deux valeurs, puis lance le script d'autorisation :

```bash
export LINKEDIN_CLIENT_ID=...
export LINKEDIN_CLIENT_SECRET=...
python linkedin_auth.py
```

5. Ton navigateur s'ouvre, tu te connectes et autorises l'app
6. Le script t'affiche `LINKEDIN_ACCESS_TOKEN` et `LINKEDIN_PERSON_URN`
   → colle ces deux valeurs dans ton `.env`
7. Relance `agent.py` — l'outil `post_to_linkedin` est maintenant actif

⚠️ Le token expire au bout d'environ 60 jours : il faudra relancer
`linkedin_auth.py` pour en générer un nouveau à ce moment-là.

⚠️ Important : l'agent ne publie que ton propre contenu, sur commande
explicite de ta part ("publie ce post"). Il ne likera, ne commentera et
n'enverra jamais de message à d'autres utilisateurs de façon automatisée —
LinkedIn interdit ce type d'automatisation dans ses conditions
d'utilisation et ça expose ton compte à un bannissement.

## 7. Où sont stockés les brouillons ?

Dans le dossier `drafts/`, un fichier texte par plateforme
(`drafts_linkedin.txt`, `drafts_medium.txt`). C'est volontairement simple
(pas de base de données) — tu peux migrer vers un fichier JSON ou une
vraie DB plus tard si besoin.

## 8. Faire tourner l'agent en continu (sans garder ton PC allumé)

Options gratuites :
- **Render.com** (plan gratuit "Background Worker")
- **Railway.app** (plan gratuit limité mais suffisant pour un usage perso)
- Une petite instance EC2 t3.micro (free tier AWS, cohérent avec ton profil)

Dans tous ces cas : définis `GEMINI_API_KEY` et `TELEGRAM_BOT_TOKEN` comme
variables d'environnement/secrets de la plateforme, jamais en dur dans le code.

## 9. Prochaines évolutions possibles

- Ajouter un outil `search_web()` pour enrichir les posts avec des infos récentes
- Ajouter une mémoire persistante (JSON ou SQLite) pour éviter les répétitions de sujets
- Ajouter un outil qui formate directement le texte pour LinkedIn (emojis, structure)
- Dockeriser le tout pour un déploiement propre (cohérent avec ton profil DevOps)
