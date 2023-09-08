import base64
import random
import string

from flask import Flask, redirect, request, make_response, render_template
import requests
from urllib.parse import quote

app = Flask(__name__)

# todo , clients secrets
CLIENT_ID = 'X'
CLIENT_SECRET = 'X'
REDIRECT_URI = 'http://127.0.0.1:5000/callback'


def generate_random_string(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


@app.route('/')
def home():
    return "<p>Hello, World!</p>"


@app.route('/authorize')
def authorize():
    state = generate_random_string(16)
    scope = "playlist-modify-public playlist-modify-private"
    response = make_response(redirect(
        f'https://accounts.spotify.com/authorize?response_type=code&client_id={CLIENT_ID}&scope={scope}&redirect_uri={REDIRECT_URI}&state={state}'))
    response.set_cookie('spotify_auth_state', state)
    print(response.data)
    return response


@app.route('/callback')
def callback():
    code = request.args.get('code') or None
    state = request.args.get('state') or None
    stored_state = request.cookies.get('spotify_auth_state') or None

    if state is None or state != stored_state:
        return redirect(f'/#error=state_mismatch')
    else:
        auth_options = {
            'url': 'https://accounts.spotify.com/api/token',
            'data': {
                'code': code,
                'redirect_uri': REDIRECT_URI,
                'grant_type': 'authorization_code',
            },
            'headers': {
                'Authorization': f'Basic {base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode("utf-8")).decode("utf-8")}',
            },
            'json': True,
        }

        response = requests.post(**auth_options)

        if response.status_code == 200:
            access_token = response.json()['access_token']
            refresh_token = response.json()['refresh_token']

            options = {
                'url': 'https://api.spotify.com/v1/me',
                'headers': {
                    'Authorization': f'Bearer {access_token}',
                }
            }
            response = requests.get(**options)

            return {
                "access_token": access_token,
                "refresh_token": refresh_token
            }
        else:
            return "<p>Error getting response from Spotify</p>"


@app.route('/create-playlist')
def create_playlist():
    setlist_url_artists = "https://api.setlist.fm/rest/1.0/search/artists"

    # Spotify API URL
    spotify_url = "https://api.spotify.com/v1/users"
    spotify_url_add_playlists_songs = "https://api.spotify.com/v1/playlists"

    # Setlist.fm API key
    setlist_api_key = "fdWm07co_W95TJt1rRV1qFG189A15zSql2Bh"

    # Spotify API key
    spotify_api_key = request.headers.get('access-token')

    # Spotify user ID
    spotify_user_id = "hxnnahlee"

    # Setlist.fm API request headers
    setlist_headers = {
        "Accept": "application/json",
        "x-api-key": setlist_api_key
    }

    # Spotify API request headers
    spotify_headers = {
        'Authorization': f'Bearer {spotify_api_key}',
        "Content-Type": "application/json"
    }

    artist_query_params = {
        "artistName": request.args.get('artistName')
    }

    artists_response = requests.get(
        setlist_url_artists, headers=setlist_headers, params=artist_query_params
    )

    mbid = ""
    if artists_response.status_code == 200:
        # print(artists_response.json().get("artist"))
        # TODO: FIX THIS DO NOT GRAB FIRST ARTIST
        fetched_artists_list = artists_response.json().get("artist")
        filtered_artists_list = [
            artist for artist in fetched_artists_list if artist.get('name').lower().strip() == artist_query_params.get("artistName").lower().strip()]
        print(filtered_artists_list)
        mbid = filtered_artists_list[0].get("mbid")

        print(mbid)
    else:
        print("Error looking up artist")

    # Setlist.fm API URL
    setlist_url = f"https://api.setlist.fm/rest/1.0/artist/{mbid}/setlists"

    # Make a request to the Setlist.fm API to get the list of setlists for a specified artist
    setlist_response = requests.get(
        setlist_url, headers=setlist_headers)

    # Grab the array of setlists (ie, from all concerts) from the original response
    setlists = setlist_response.json()["setlist"]

    # Filter out any setlists that have empty sets..
    setlists_filtered = [
        setlst for setlst in setlists if setlst.get('sets') and setlst.get('sets').get('set')]

    # For now grab the first setlist....
    # TODO fix this.
    selected_setlist = setlists_filtered[0]

    # Create a list of songs from the setlist
    songs = []

    # TODO FIX THIS, DO NOT JUST GRAB THE FIRST SET, MUST GO THRU ALL SETS AND ADD SONGS FROM ALL SETS
    for song in selected_setlist.get('sets').get('set')[0].get('song'):
        songs.append(song["name"])

    print(songs)

    # Create a new playlist in Spotify
    playlist_data = {
        "name": artist_query_params.get("artistName") + " Setlist",
        "description": artist_query_params.get("artistName") + " Setlist",
        "public": True
    }

    playlists_url = spotify_url + "/" + spotify_user_id + "/playlists"
    playlist_response = requests.post(
        playlists_url, headers=spotify_headers, json=playlist_data)

    # Get the playlist ID from the response
    playlist_id = playlist_response.json()["id"]

    # Add the songs to the playlist
    for song in songs:
        search_url = "https://api.spotify.com/v1/search"
        search_params = {
            "q": quote('track:' + song + ' artist:' + artist_query_params.get("artistName")),
            "type": "track",
            "limit": 50
        }
        print('track:' + song + ' artist:' +
              artist_query_params.get("artistName"))

        # Search for the track with the given artist
        search_response = requests.get(
            search_url, headers=spotify_headers, params=search_params)

        # List of song objects
        track_list = search_response.json()["tracks"]["items"]

        # Get the correct song that matches the title and artist
        # TODO: FIGURE OUT WHY SEARCH API SOMETIMES DOESN'T RETURN THE RIGHT SONG AT ALL
        track = next(
            (track for track in track_list if track["name"].lower().strip() == song.lower().strip(
            ) and track["artists"][0]["name"].lower().strip() == artist_query_params.get("artistName").lower().strip()),
            None)
        print(track)
        if track:
            requests.post(spotify_url_add_playlists_songs + "/" + playlist_id + "/tracks",
                          headers=spotify_headers, json={"uris": [track["uri"]]})
        else:
            print("Couldn't find track " + song + ", skipping")
            for track in track_list:
                print(track["name"])
                print(track["name"].lower().strip())
                # print(song)
                # print(song.lower().strip())
                print(track["artists"][0]["name"])
                print(track["artists"][0]["name"].lower().strip())
            continue

    print("Playlist created successfully!")

    return ""


if __name__ == '__main__':
    app.run()
