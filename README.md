# NextViper Music Backend Service

A high-performance music streaming and discovery backend built **100% in pure NextViper**.

## Features

- **Built in NextViper 1.0.0 (Apex)**: Zero external web frameworks or other runtime languages.
- **YouTube Music InnerTube Integration**: Native querying and JSON parsing of YouTube Music tracks, artists, video IDs, and thumbnails.
- **RESTful Endpoints**:
  - `GET /health` — Service health & NextViper runtime metadata
  - `GET /api/search?q=<query>` — Searches tracks with video ID, title, artist, and album art
  - `GET /api/resolve?id=<videoId>` — Resolves player playback stream formats

## Running Locally

```bash
# Check syntax
nextviper check src/server.nv

# Run the server
nextviper run src/server.nv
```

Server runs on `http://0.0.0.0:8080`.

## Docker Build & Deployment

```bash
docker build -t nextviper-music-backend .
docker run -p 8080:8080 nextviper-music-backend
```
