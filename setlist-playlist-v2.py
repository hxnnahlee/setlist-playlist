import base64
import requests
from flask import Flask, redirect, request, session
import os
from dotenv import load_dotenv

app = Flask(__name__)
app.secret_key = "dev"  # required for session
load_dotenv()


CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SETLIST_API_KEY = os.getenv("SETLIST_API_KEY")

if not CLIENT_ID or not CLIENT_SECRET:
    raise Exception("Missing Spotify credentials")

if not SETLIST_API_KEY:
    raise Exception("Missing Setlist API key")

REDIRECT_URI = "http://127.0.0.1:5000/callback"

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"


@app.route("/")
def home():
    return """
    <html>
      <head>
        <title>Setlist → Playlist</title>
        <style>
          body {
            font-family: Arial;
            text-align: center;
            margin-top: 100px;
            background: #fff9fb;
          }
          input {
            padding: 10px;
            width: 250px;
            border-radius: 8px;
            border: 1px solid #ddd;
          }
          button {
            padding: 10px 16px;
            border-radius: 8px;
            border: none;
            background: #e11d48;
            color: white;
            cursor: pointer;
          }
        </style>
      </head>
      <body>
        <h2>🎶 Setlist → Spotify Playlist</h2>

        <form action="/create-playlist" method="get">
          <input name="artistName" placeholder="enter artist (e.g. drake)" />
          <br><br>
          <button type="submit">create playlist</button>
        </form>

        <br><br>

        <a href="/login">login with spotify</a>
      </body>
    </html>
    """


# 🔐 login
@app.route("/login")
def login():
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

    return '<a href="/create-playlist?artistName=beyonce">create playlist</a>'

@app.route("/create-playlist")
def create_playlist():
    access_token = session.get("access_token")

    if not access_token:
        return redirect("/login")

    artist_name = request.args.get("artistName")


    setlist_headers = {
        "Accept": "application/json",
        "x-api-key": SETLIST_API_KEY
    }

    # 🔍 get artist mbid
    artist_res = requests.get(
        "https://api.setlist.fm/rest/1.0/search/artists",
        headers=setlist_headers,
        params={"artistName": artist_name}
    )

    artists = artist_res.json().get("artist", [])
    if not artists:
        return {"error": "artist not found"}, 404

    artists = artist_res.json().get("artist", [])

    # normalize helper
    def normalize(name):
        return name.lower().strip().replace("é", "e")

    target = normalize(artist_name)

    # filter exact matches only
    filtered = [
        a for a in artists
        if normalize(a["name"]) == target
    ]

    if not filtered:
        return {"error": "exact artist not found"}, 404

    mbid = filtered[0]["mbid"]

    # 🎤 get setlists
    setlist_res = requests.get(
        f"https://api.setlist.fm/rest/1.0/artist/{mbid}/setlists",
        headers=setlist_headers
    )
    print(setlist_res, flush=True)

    setlists = setlist_res.json().get("setlist", [])

    if not setlists:
        return {"error": artists}, 404

    # 🎤 find first setlist with actual songs
    selected_setlist = None

    for s in setlists:
        sets = s.get("sets", {}).get("set", [])
        songs = []

        for set_block in sets:
            songs.extend([song["name"] for song in set_block.get("song", [])])

        if songs:
            selected_setlist = s
            break

    # 🚨 if none found
    if not selected_setlist:
        return """
        <h3>no populated setlist found 😢</h3>
        <a href="/">try another artist</a>
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
    user_id = user_res.json()["id"]

    # 🎧 create playlist
    playlist_res = requests.post(
        f"https://api.spotify.com/v1/users/{user_id}/playlists",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        },
        json={
            "name": f"{artist_name} Setlist",
            "public": True
        }
    )

    if playlist_res.status_code != 201:
        return {
            "error": "failed to create playlist",
            "details": playlist_res.text
        }, 500
    playlist_id = playlist_res.json()["id"]

    # ➕ add songs
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

        # 🚨 check search request
        if search_res.status_code != 200:
            return {
                "error": "spotify search failed",
                "song": song,
                "details": search_res.text
            }, 500

        data = search_res.json()
        tracks = data.get("tracks", {}).get("items", [])

        if not tracks:
            print(f"skipping song (not found): {song}", flush=True)
            continue

        track_uri = tracks[0]["uri"]

        add_res = requests.post(
            f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            json={"uris": [track_uri]}
        )

        # 🚨 check add-to-playlist request
        if add_res.status_code not in (200, 201):
            return {
                "error": "failed to add song to playlist",
                "song": song,
                "details": add_res.text
            }, 500

    return f"""
    <h2>playlist created 🎉</h2>
    <p>artist: {artist_name}</p>
    <a href="/">go back</a>
    """
if __name__ == "__main__":
    app.run(debug=True)