"""
uploader.py - limpo e com publish_at funcionando
"""
import os
import json
import pickle
from pathlib import Path

CHANNELS_FILE = "channels.json"
TOKENS_DIR    = "yt_tokens"


def load_channels() -> list:
    if not os.path.exists(CHANNELS_FILE):
        return []
    try:
        with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_channels(channels: list):
    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False, indent=2)


def add_channel(name: str, logo_path: str = "") -> dict:
    channels = load_channels()
    if len(channels) >= 5:
        raise ValueError("Limite de 5 canais atingido.")
    channel = {"id": f"ch_{len(channels)+1}", "name": name,
                "logo_path": logo_path, "authenticated": False}
    channels.append(channel)
    save_channels(channels)
    return channel


def remove_channel(channel_id: str):
    channels = [c for c in load_channels() if c["id"] != channel_id]
    save_channels(channels)
    token_path = os.path.join(TOKENS_DIR, f"{channel_id}.pkl")
    if os.path.exists(token_path):
        os.remove(token_path)


def update_channel(channel_id: str, **kwargs):
    channels = load_channels()
    for c in channels:
        if c["id"] == channel_id:
            c.update(kwargs)
    save_channels(channels)


def is_authenticated(channel_id: str) -> bool:
    return os.path.exists(os.path.join(TOKENS_DIR, f"{channel_id}.pkl"))


def get_authenticated_service(channel_id: str, client_secrets_path: str):
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError("pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
              "https://www.googleapis.com/auth/youtube.readonly"]

    os.makedirs(TOKENS_DIR, exist_ok=True)
    token_path = os.path.join(TOKENS_DIR, f"{channel_id}.pkl")
    creds = None

    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except:
            creds = None

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
        creds = flow.run_local_server(port=0, prompt="consent")
        with open(token_path, "wb") as f:
            pickle.dump(creds, f)

    update_channel(channel_id, authenticated=True)
    return build("youtube", "v3", credentials=creds)


def upload_video(
    channel_id: str,
    client_secrets_path: str,
    video_path: str,
    title: str,
    description: str = "",
    tags: list = None,
    category_id: str = "22",
    privacy: str = "public",
    made_for_kids: bool = False,
    publish_at: str = "",
) -> dict:
    """
    Faz upload do video para o canal.
    publish_at: ISO 8601 ex: "2026-04-18T15:00:00Z"
    Se publish_at for informado, o video fica privado ate o horario.
    """
    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError:
        raise ImportError("pip install google-api-python-client")

    service = get_authenticated_service(channel_id, client_secrets_path)

    # Agendamento: forcar privado ate o horario
    status_body = {
        "privacyStatus": "private" if publish_at else privacy,
        "madeForKids": made_for_kids,
        "selfDeclaredMadeForKids": made_for_kids,
    }
    if publish_at:
        status_body["publishAt"] = publish_at

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": status_body,
    }

    media = MediaFileUpload(
        video_path,
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 5,
    )

    print(f"[uploader] Enviando: {title[:50]} | canal: {channel_id}")
    request = service.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[uploader] {int(status.progress()*100)}%")

    video_id = response.get("id")
    url = f"https://youtube.com/shorts/{video_id}"
    print(f"[uploader] Publicado: {url}")
    return {"id": video_id, "url": url}


def get_channel_info(channel_id: str, client_secrets_path: str) -> dict:
    try:
        service = get_authenticated_service(channel_id, client_secrets_path)
        resp = service.channels().list(part="snippet", mine=True).execute()
        items = resp.get("items", [])
        if items:
            snippet = items[0]["snippet"]
            return {
                "youtube_name": snippet.get("title", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
            }
    except Exception as e:
        print(f"[uploader] get_channel_info erro: {e}")
    return {}
