import base64
import difflib
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

REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://127.0.0.1:5000/callback")

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"


STYLES = """
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🎵</text></svg>">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Figtree:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
      *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

      body {
        font-family: 'Figtree', sans-serif;
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
        border-radius: 4px;
        text-align: center;
        box-shadow: 0 8px 32px rgba(109, 40, 217, 0.18), 0 2px 8px rgba(109,40,217,0.08);
      }

      h1 {
        font-family: 'DM Serif Display', serif;
        color: #3b0764;
        font-size: 2rem;
        font-weight: 400;
        letter-spacing: -0.3px;
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
        border-radius: 4px;
        color: #3b0764;
        font-family: 'Figtree', sans-serif;
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
        border-radius: 4px;
        color: #fff;
        font-family: 'Figtree', sans-serif;
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

      .connected {
        margin-top: 18px;
        color: #6d28d9;
        font-size: 0.82rem;
        font-weight: 600;
      }

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

      .loading-overlay {
        display: none;
        position: fixed;
        inset: 0;
        background: #faf7f4;
        z-index: 100;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 20px;
      }
      .loading-overlay.active { display: flex; }
      .loading-overlay h2 { color: #3b0764; font-size: 1.5rem; font-weight: 700; }
      .loading-overlay p  { color: #6d28d9; font-size: 0.875rem; font-weight: 500; }
      .dots span {
        display: inline-block;
        width: 10px; height: 10px;
        margin: 0 4px;
        background: #a855f7;
        border-radius: 50%;
        animation: bounce 1.2s infinite ease-in-out;
      }
      .dots span:nth-child(2) { animation-delay: 0.2s; }
      .dots span:nth-child(3) { animation-delay: 0.4s; }
      @keyframes bounce {
        0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
        40%            { transform: scale(1);   opacity: 1; }
      }
    </style>
"""

@app.route("/")
def home():
    error = request.args.get("error", "")
    error_html = f'<p class="error">{html.escape(error)}</p>' if error else ""
    is_connected = bool(session.get("access_token"))
    spotify_html = (
        '<p class="connected">spotify connected ✓</p><a class="btn-ghost" href="/logout">log out</a>'
        if is_connected else
        '<a class="btn-ghost" href="/login">connect spotify 🔗</a>'
    )
    return f"""
    <html>
      <head><title>Setlist → Playlist</title>{STYLES}</head>
      <body>
        <div class="card">
          <h1>setlist → playlist</h1>
          <p class="subtitle">turn a setlist into a spotify playlist</p>
          <form id="mainForm" action="/create-playlist" method="get">
            <input name="artistName" placeholder="✦ artist name" autocomplete="off" />
            <button class="btn" type="submit">create playlist 🎧</button>
          </form>
          {spotify_html}
          {error_html}
        </div>

        <div class="loading-overlay" id="loader">
          <div class="dots">
            <span></span><span></span><span></span>
          </div>
          <h2>building your playlist</h2>
        </div>

        <script>
          document.getElementById('mainForm').addEventListener('submit', function() {{
            document.getElementById('loader').classList.add('active');
          }});
        </script>
      </body>
    </html>
    """


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

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
    if not artist_name:
        return redirect("/")
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
        if artist_res.status_code == 429:
            return redirect("/?error=Too+many+requests+—+please+try+again+in+a+moment")
        if artist_res.status_code != 200:
            print(f"[setlist.fm] artist search failed — status={artist_res.status_code} body={artist_res.text[:300]}", flush=True)
            return redirect("/?error=Setlist.fm+search+failed")

        data = artist_res.json()
        artists = data.get("artist", [])

        if not artists:
            break

        for a in artists:
            if a["mbid"] in seen:
                continue
            score = difflib.SequenceMatcher(None, normalize(a["name"]), target).ratio()
            if score >= 0.8:
                seen.add(a["mbid"])
                mbids.append((score, a["mbid"]))

        total = data.get("total", 0)
        items_per_page = data.get("itemsPerPage", 30)
        if page * items_per_page >= total:
            break

        page += 1
        time.sleep(1)

    mbids.sort(reverse=True)  # best match first
    mbids = [mbid for _, mbid in mbids]

    if not mbids:
        return redirect("/?error=Artist+not+found+on+setlist.fm")

    # 🎤 try each matching mbid until we find one with setlists
    setlists = []
    for mbid in mbids:
        setlist_res = requests.get(
            f"https://api.setlist.fm/rest/1.0/artist/{mbid}/setlists",
            headers=setlist_headers
        )
        if setlist_res.status_code == 200:
            setlists = setlist_res.json().get("setlist", [])
            if setlists:
                print(f"[setlist.fm] found {len(setlists)} setlists for mbid={mbid}", flush=True)
                break
        elif setlist_res.status_code == 429:
            return redirect("/?error=Too+many+requests+—+please+try+again+in+a+moment")
        else:
            print(f"[setlist.fm] setlists failed — mbid={mbid} status={setlist_res.status_code} body={setlist_res.text[:200]}", flush=True)
        time.sleep(1)

    if not setlists:
        return redirect("/?error=No+setlists+found+for+this+artist")

    # 🎤 find first setlist with at least 4 songs
    selected_setlist = None
    for s in setlists:
        songs = []
        for set_block in s.get("sets", {}).get("set", []):
            songs.extend([song["name"] for song in set_block.get("song", [])])
        if len(songs) >= 4:
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

    # 🎶 extract songs (keep full objects to access cover artist)
    songs = []
    for s in selected_setlist.get("sets", {}).get("set", []):
        for song in s.get("song", []):
            songs.append(song)

    def spotify_expired(res):
        if res.status_code == 401:
            session.pop("access_token", None)
            session["artist_name"] = artist_name
            return True
        return False

    # 👤 get Spotify user
    user_res = requests.get(
        "https://api.spotify.com/v1/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    if spotify_expired(user_res):
        return redirect(f"/login?artistName={urllib.parse.quote_plus(artist_name)}")
    if user_res.status_code == 403:
        print(f"[spotify] 403 on /me — body={user_res.text[:200]}", flush=True)
        return redirect("/?error=Your+Spotify+account+isn%27t+authorized+for+this+app+yet")
    if user_res.status_code != 200:
        print(f"[spotify] /me failed — status={user_res.status_code} body={user_res.text[:200]}", flush=True)
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
    if spotify_expired(playlist_res):
        return redirect(f"/login?artistName={urllib.parse.quote_plus(artist_name)}")
    if playlist_res.status_code != 201:
        print(f"[spotify] create playlist failed — status={playlist_res.status_code} body={playlist_res.text[:200]}", flush=True)
        return redirect("/?error=Failed+to+create+Spotify+playlist")
    playlist_data = playlist_res.json()
    playlist_id = playlist_data["id"]
    playlist_url = playlist_data.get("external_urls", {}).get("spotify", "")

    # ➕ search for each song and collect URIs
    track_uris = []
    for song in songs:
        song_name = song["name"]
        search_artist = song.get("cover", {}).get("name") or artist_name
        search_res = requests.get(
            "https://api.spotify.com/v1/search",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "q": f"track:{song_name} artist:{search_artist}",
                "type": "track",
                "limit": 1
            }
        )
        if search_res.status_code != 200:
            print(f"search failed for: {song_name}", flush=True)
            continue

        tracks = search_res.json().get("tracks", {}).get("items", [])
        if tracks:
            track_uris.append(tracks[0]["uri"])
        else:
            print(f"not found on Spotify: {song_name} by {search_artist}", flush=True)

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

    return redirect(f"/success?artist={urllib.parse.quote_plus(artist_name)}&playlist={urllib.parse.quote_plus(playlist_url)}")


@app.route("/success")
def success():
    artist_name = request.args.get("artist", "")
    playlist_url = request.args.get("playlist", "")
    open_btn = f'<a class="btn" href="{html.escape(playlist_url)}" target="_blank">open in spotify 🎧</a>' if playlist_url else ""
    return f"""
    <html>
      <head><title>Playlist created!</title>{STYLES}</head>
      <body>
        <div class="card">
          <h1>playlist created!</h1>
          <p class="artist-name">{html.escape(artist_name)} ✨</p>
          {open_btn}
          <a class="btn" href="/">make another 💜</a>
        </div>
      </body>
    </html>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)