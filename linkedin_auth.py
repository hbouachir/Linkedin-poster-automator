"""
Script one-shot pour obtenir un access token LinkedIn.

A lancer UNE SEULE FOIS (le token dure ~60 jours, il faudra refaire cette
étape pour en générer un nouveau une fois expiré).

Prérequis : avoir créé une app sur https://www.linkedin.com/developers/apps
et activé le produit "Share on LinkedIn".

Usage :
    export LINKEDIN_CLIENT_ID=...
    export LINKEDIN_CLIENT_SECRET=...
    python linkedin_auth.py
"""

import os
import webbrowser
import urllib.parse
import http.server
import requests

CLIENT_ID = os.environ["LINKEDIN_CLIENT_ID"]
CLIENT_SECRET = os.environ["LINKEDIN_CLIENT_SECRET"]
REDIRECT_URI = "http://localhost:8000/callback"
SCOPE = "openid profile w_member_social"

_received_code = {}


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            _received_code["code"] = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1>Autorisation reussie, tu peux fermer cet onglet.</h1>")
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):  # noqa: A002
        pass  # silence les logs HTTP par défaut


def main():
    auth_url = (
        "https://www.linkedin.com/oauth/v2/authorization?"
        + urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "scope": SCOPE,
            }
        )
    )
    print("Ouverture du navigateur pour autorisation LinkedIn...")
    print("Si le navigateur ne s'ouvre pas automatiquement, va sur cette URL :\n")
    print(auth_url, "\n")
    webbrowser.open(auth_url)

    server = http.server.HTTPServer(("localhost", 8000), CallbackHandler)
    print("En attente de l'autorisation dans le navigateur...")
    server.handle_request()  # bloque jusqu'à réception d'une requête

    code = _received_code.get("code")
    if not code:
        print("Erreur : aucun code reçu.")
        return

    token_resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token_resp.raise_for_status()
    token_data = token_resp.json()
    access_token = token_data["access_token"]

    # Récupère l'URN de l'utilisateur (nécessaire pour publier en son nom)
    userinfo_resp = requests.get(
        "https://api.linkedin.com/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    userinfo_resp.raise_for_status()
    person_urn = "urn:li:person:" + userinfo_resp.json()["sub"]

    print("\n=== Copie ces valeurs dans ton fichier .env ===\n")
    print(f"LINKEDIN_ACCESS_TOKEN={access_token}")
    print(f"LINKEDIN_PERSON_URN={person_urn}")
    print(f"\n(Ce token expire dans environ {token_data.get('expires_in', 0) // 86400} jours)")


if __name__ == "__main__":
    main()
