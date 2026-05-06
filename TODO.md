# TODO

- [ ] Fix fuzzy artist search — current `SequenceMatcher` logic produces bad matches or misses artists
- [ ] If Spotify can't find a single song in a setlist (empty result), fall back to the next acceptable setlist (4+ songs) instead of creating a blank playlist
- [ ] Delete the empty Spotify playlist if no tracks end up being found (playlist is created before the song search loop, so a blank one gets orphaned)
- [x] Show the Spotify playlist link on the success page so the user can click through to it directly
