from fastapi import FastAPI, Request, Form, HTTPException
import httpx
import os
import secrets
import logging
from itertools import count
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ticket-service")

app = FastAPI()

MATTERMOST_URL = os.environ["MATTERMOST_URL"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
SLASH_TOKEN = os.environ["SLASH_TOKEN"]
CALLBACK_URL = os.environ["CALLBACK_URL"]

http_client: httpx.AsyncClient
_ticket_counter = count(1)


def next_ticket_id():
    num = next(_ticket_counter)
    return f"Ticket-{datetime.now().strftime('%Y%m%d')}-{num:04d}"


@app.on_event("startup")
async def startup():
    global http_client
    http_client = httpx.AsyncClient()
    log.info("Service demarre - %s", MATTERMOST_URL)


@app.on_event("shutdown")
async def shutdown():
    await http_client.aclose()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/ticket")
async def open_ticket_dialog(
    token: str = Form(...),
    trigger_id: str = Form(...),
):
    """Slash command /ticket -> ouvre le formulaire"""

    if not secrets.compare_digest(token, SLASH_TOKEN):
        raise HTTPException(401)

    try:
        resp = await http_client.post(
            f"{MATTERMOST_URL}/api/v4/actions/dialogs/open",
            json={
                "trigger_id": trigger_id,
                "url": f"{CALLBACK_URL}/ticket/submit",
                "dialog": {
                    "title": "Nouveau ticket",
                    "elements": [
                        {
                            "display_name": "Cluster vSphere",
                            "name": "cluster",
                            "type": "select",
                            "options": [
                                {"text": "Cluster Production", "value": "prod-cluster"},
                                {"text": "Cluster Dev/Test", "value": "dev-cluster"},
                                {"text": "Cluster DMZ", "value": "dmz-cluster"},
                            ],
                            "optional": False,
                        },
                        {
                            "display_name": "VM / Ressource",
                            "name": "resource",
                            "type": "text",
                            "optional": False,
                        },
                        {
                            "display_name": "Probleme",
                            "name": "problem",
                            "type": "textarea",
                            "optional": False,
                        },
                        {
                            "display_name": "Infos reseau (IP, ports...)",
                            "name": "network",
                            "type": "textarea",
                            "optional": True,
                        },
                    ],
                    "submit_label": "Creer",
                },
            },
            headers={"Authorization": f"Bearer {BOT_TOKEN}"},
        )
        if resp.status_code != 200:
            log.error("Echec ouverture dialog: %s %s", resp.status_code, resp.text)
    except httpx.HTTPError as e:
        log.error("Erreur connexion Mattermost (dialog): %s", e)

    return {}


@app.post("/ticket/submit")
async def handle_submission(request: Request):
    """Formulaire soumis -> poste le ticket en thread"""

    data = await request.json()
    if data.get("cancelled"):
        return {}

    sub = data["submission"]
    user = data["user_id"]
    channel = data["channel_id"]
    ticket_id = next_ticket_id()

    network_info = f"\n**Reseau:** {sub['network']}" if sub.get("network") else ""

    message = f"""### {ticket_id} - Ticket de <@{user}>

**Cluster:** `{sub['cluster']}`
**Ressource:** `{sub['resource']}`
**Probleme:** {sub['problem']}{network_info}
"""

    try:
        resp = await http_client.post(
            f"{MATTERMOST_URL}/api/v4/posts",
            json={
                "channel_id": channel,
                "message": message,
                "props": {"is_ticket": True, "ticket_id": ticket_id},
            },
            headers={"Authorization": f"Bearer {BOT_TOKEN}"},
        )
        if resp.status_code == 201:
            log.info("Ticket %s cree par %s dans %s", ticket_id, user, channel)
        else:
            log.error("Echec creation ticket: %s %s", resp.status_code, resp.text)
            return {}
    except httpx.HTTPError as e:
        log.error("Erreur connexion Mattermost (post): %s", e)
        return {}

    try:
        await http_client.post(
            f"{MATTERMOST_URL}/api/v4/posts/ephemeral",
            json={
                "user_id": user,
                "post": {
                    "channel_id": channel,
                    "message": f"Ticket **{ticket_id}** cree.",
                },
            },
            headers={"Authorization": f"Bearer {BOT_TOKEN}"},
        )
    except httpx.HTTPError as e:
        log.warning("Echec envoi confirmation ephemere: %s", e)

    return {}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
