import base64
import html
import time
import urllib.parse
import requests
from flask import Flask, redirect, request, session
import os
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = "dev"  # required for session
load_dotenv()


CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SETLIST_API_KEY = os.getenv("SETLIST_API_KEY")

if not CLIENT_ID or not CLIENT_SECRET:
    raise Exception("Missing Spotify credentials")

if not SETLIST_API_KEY:
    raise Exception("Missing Setlist API key")

REDIRECT_URI = "http://127.0.0.1:5000/callback"

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"


STYLES = """
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
      *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

      body {
        font-family: 'Quicksand', sans-serif;
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #faf7f4;
      }

      .card {
        position: relative;
        width: 420px;
        padding: 48px 44px;
        background: #ddd6fe;
        border: 1px solid #c4b5fd;
        border-radius: 28px;
        text-align: center;
        box-shadow: 0 8px 32px rgba(109, 40, 217, 0.18), 0 2px 8px rgba(109,40,217,0.08);
      }

      h1 {
        color: #3b0764;
        font-size: 1.9rem;
        font-weight: 700;
        letter-spacing: -0.2px;
        margin-bottom: 6px;
      }

      .subtitle {
        color: #6d28d9;
        font-size: 0.875rem;
        font-weight: 500;
        margin-bottom: 36px;
      }

      input[type=text], input:not([type]) {
        width: 100%;
        padding: 13px 16px;
        background: #fff;
        border: 1.5px solid #c4b5fd;
        border-radius: 14px;
        color: #3b0764;
        font-family: 'Quicksand', sans-serif;
        font-size: 0.9rem;
        font-weight: 500;
        outline: none;
        transition: border-color 0.2s;
      }
      input::placeholder { color: #a78bfa; }
      input:focus { border-color: #7c3aed; }

      .btn {
        display: block;
        width: 100%;
        padding: 13px;
        margin-top: 10px;
        background: linear-gradient(135deg, #a855f7 0%, #7c3aed 100%);
        border: none;
        border-radius: 14px;
        color: #fff;
        font-family: 'Quicksand', sans-serif;
        font-size: 0.92rem;
        font-weight: 700;
        cursor: pointer;
        text-decoration: none;
        letter-spacing: 0.3px;
        transition: opacity 0.15s, transform 0.1s, box-shadow 0.2s;
        box-shadow: 0 4px 20px rgba(139, 92, 246, 0.35);
      }
      .btn:hover { opacity: 0.9; transform: translateY(-2px); box-shadow: 0 6px 24px rgba(139, 92, 246, 0.5); }
      .btn:active { transform: translateY(0); }

      .btn-ghost {
        display: inline-block;
        margin-top: 18px;
        color: #7c3aed;
        font-size: 0.82rem;
        font-weight: 600;
        text-decoration: none;
        transition: color 0.2s;
      }
      .btn-ghost:hover { color: #3b0764; }

      .error {
        margin-top: 18px;
        color: #be123c;
        font-size: 0.85rem;
        font-weight: 500;
      }

      .success-icon { font-size: 3rem; margin-bottom: 14px; }

      .artist-name {
        color: #6d28d9;
        font-size: 0.875rem;
        margin-top: 6px;
        margin-bottom: 28px;
        font-weight: 500;
      }
    </style>
"""

@app.route("/")
def home():
    error = request.args.get("error", "")
    error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
    return f"""
    <html>
      <head><title>Setlist → Playlist</title>{STYLES}</head>
      <body>
        <div class="card">
          <h1>setlist → playlist</h1>
          <p class="subtitle">turn a live setlist into a spotify playlist</p>
          <form action="/create-playlist" method="get">
            <input name="artistName" placeholder="✦ artist name" autocomplete="off" />
            <button class="btn" type="submit">create playlist 🎧</button>
          </form>
          <a class="btn-ghost" href="/login">connect spotify 🔗</a>
          {error_html}
        </div>
      </body>
    </html>
    """


# 🔐 login
@app.route("/login")
def login():
    artist_name = request.args.get("artistName", "")
    if artist_name:
        session["artist_name"] = artist_name

    scope = "playlist-modify-public playlist-modify-private"

    return redirect(
        f"{SPOTIFY_AUTH_URL}?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&scope={scope}"
        f"&redirect_uri={REDIRECT_URI}"
    )


# 🔄 callback
@app.route("/callback")
def callback():
    code = request.args.get("code")

    auth_header = base64.b64encode(
        f"{CLIENT_ID}:{CLIENT_SECRET}".encode()
    ).decode()

    response = requests.post(
        SPOTIFY_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    data = response.json()

    session["access_token"] = data.get("access_token")

    artist_name = session.get("artist_name", "")
    encoded_name = urllib.parse.quote_plus(artist_name)
    return redirect(f"/create-playlist?artistName={encoded_name}")

@app.route("/create-playlist")
def create_playlist():
    artist_name = request.args.get("artistName", "").strip()

    if not artist_name:
        return redirect("/?error=Please+enter+an+artist+name")

    access_token = session.get("access_token")
    if not access_token:
        session["artist_name"] = artist_name
        return redirect(f"/login?artistName={urllib.parse.quote_plus(artist_name)}")

    def normalize(name):
        return name.lower().strip().replace("é", "e")

    setlist_headers = {
        "Accept": "application/json",
        "x-api-key": SETLIST_API_KEY
    }

    # 🔍 search for artist mbid, paginating until exact match found
    target = normalize(artist_name)
    # collect all mbids that exactly match the artist name across all pages
    mbids = []
    seen = set()
    page = 1

    while True:
        artist_res = requests.get(
            "https://api.setlist.fm/rest/1.0/search/artists",
            headers=setlist_headers,
            params={"artistName": artist_name, "p": page}
        )
        if artist_res.status_code != 200:
            print(f"setlist.fm error: {artist_res.status_code} {artist_res.text[:300]}", flush=True)
            return redirect("/?error=Setlist.fm+search+failed")

        data = artist_res.json()
        artists = data.get("artist", [])

        if not artists:
            break

        for a in artists:
            if normalize(a["name"]) == target and a["mbid"] not in seen:
                seen.add(a["mbid"])
                mbids.append(a["mbid"])

        total = data.get("total", 0)
        items_per_page = data.get("itemsPerPage", 30)
        if page * items_per_page >= total:
            break

        page += 1
        time.sleep(1)

    if not mbids:
        return redirect("/?error=Artist+not+found+on+setlist.fm")

    # 🎤 try each matching mbid until we find one with setlists
    setlists = []
    for mbid in mbids:
        print(f"trying mbid: {mbid}", flush=True)
        setlist_res = requests.get(
            f"https://api.setlist.fm/rest/1.0/artist/{mbid}/setlists",
            headers=setlist_headers
        )
        if setlist_res.status_code == 200:
            setlists = setlist_res.json().get("setlist", [])
            if setlists:
                print(f"found {len(setlists)} setlists for mbid {mbid}", flush=True)
                break
        time.sleep(1)

    if not setlists:
        return redirect("/?error=No+setlists+found+for+this+artist")

    # 🎤 find first setlist with actual songs
    selected_setlist = None
    for s in setlists:
        songs = []
        for set_block in s.get("sets", {}).get("set", []):
            songs.extend([song["name"] for song in set_block.get("song", [])])
        if songs:
            selected_setlist = s
            break

    if not selected_setlist:
        return f"""
        <html>
          <head><title>No setlist found</title>{STYLES}</head>
          <body>
            <div class="card">
              <div class="success-icon">🥺</div>
              <h1>no setlist found</h1>
              <p class="subtitle">couldn't find a recent setlist with songs</p>
              <a class="btn" href="/">try another artist 🔍</a>
            </div>
          </body>
        </html>
        """, 404

    # 🎶 extract songs
    songs = []
    for s in selected_setlist.get("sets", {}).get("set", []):
        for song in s.get("song", []):
            songs.append(song["name"])

    # 👤 get Spotify user
    user_res = requests.get(
        "https://api.spotify.com/v1/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    if user_res.status_code != 200:
        return redirect("/?error=Could+not+get+Spotify+user")
    user_id = user_res.json()["id"]

    # 🎧 create playlist
    playlist_res = requests.post(
        f"https://api.spotify.com/v1/users/{user_id}/playlists",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        },
        json={"name": f"{artist_name} Setlist", "public": True}
    )
    if playlist_res.status_code != 201:
        return redirect("/?error=Failed+to+create+Spotify+playlist")
    playlist_id = playlist_res.json()["id"]

    # ➕ search for each song and collect URIs
    track_uris = []
    for song in songs:
        search_res = requests.get(
            "https://api.spotify.com/v1/search",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "q": f"track:{song} artist:{artist_name}",
                "type": "track",
                "limit": 1
            }
        )
        if search_res.status_code != 200:
            print(f"search failed for: {song}", flush=True)
            continue

        tracks = search_res.json().get("tracks", {}).get("items", [])
        if tracks:
            track_uris.append(tracks[0]["uri"])
        else:
            print(f"not found on Spotify: {song}", flush=True)

    # add all tracks in one request (Spotify allows up to 100)
    if track_uris:
        add_res = requests.post(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json={"uris": track_uris[:100]}
        )
        if add_res.status_code not in (200, 201):
            return redirect("/?error=Failed+to+add+songs+to+playlist")

    return redirect(f"/success?artist={urllib.parse.quote_plus(artist_name)}")


@app.route("/success")
def success():
    artist_name = request.args.get("artist", "")
    return f"""
    <html>
      <head><title>Playlist created!</title>{STYLES}</head>
      <body>
        <div class="card">
          <h1>playlist created!</h1>
          <p class="artist-name">{html.escape(artist_name)} ✨</p>
          <a class="btn" href="/">make another 💜</a>
        </div>
      </body>
    </html>
    """

if __name__ == "__main__":
    app.run(debug=True)