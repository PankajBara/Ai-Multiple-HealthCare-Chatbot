# Multi-Agent Medical Assistant

## Step-by-step run report

This report explains how to install, configure, run, and test the project. The application is a FastAPI web app with Gemini agents, local Qdrant-backed RAG, medical-image models, optional web search, and optional ElevenLabs voice features.

## 1. Requirements

- Linux, macOS, or Windows with WSL
- Python 3.11 recommended (the Docker image uses Python 3.11)
- Git
- Internet access during the first dependency/model download
- `ffmpeg` for microphone transcription and audio conversion when running outside Docker
- Docker Desktop or Docker Engine (only if using Docker)

The repository already contains the local Qdrant database and sample medical documents. A fresh clone may need to download the Hugging Face models on first startup.

## 2. Get the source code

```bash
git clone https://github.com/souvikmajumder26/Multi-Agent-Medical-Assistant.git
cd Multi-Agent-Medical-Assistant
```

All commands below must be run from this project root. The environment file must be a file named `.env` in this directory, not a directory named `.env`.

## 3. Configure API keys

Create or edit `.env` in the project root:

```env
# Required for all Gemini-powered routing and responses
GOOGLE_API_KEY=your_google_gemini_key
GEMINI_MODEL=gemini-3.6-flash

# Biomedical cross-encoder used by RAG reranking
RERANKER_MODEL=ncbi/MedCPT-Cross-Encoder

# Optional: microphone transcription and Play Voice
ELEVEN_LABS_API_KEY=your_elevenlabs_key

# Optional: current-information/web-search agent (PubMed is used; Tavily is not required)
TAVILY_API_KEY=your_tavily_key

# Optional contact address for NCBI requests (no API key required)
PUBMED_EMAIL=you@example.com

# Optional for public Hugging Face models
HUGGINGFACE_TOKEN=

# Optional: leave blank to use the local Qdrant database
QDRANT_URL=
QDRANT_API_KEY=
```

Where to obtain keys:

- Google Gemini: <https://aistudio.google.com/app/apikey>
- ElevenLabs: <https://elevenlabs.io/app/settings/api-keys>
- Tavily: <https://app.tavily.com/> (not required; the web-search agent uses PubMed)

Keep `.env` private. Never commit it or paste key values into chat, screenshots, or source files. `GOOGLE_API_KEY` is required for text chat. The ElevenLabs key is required only for voice input/output. PubMed access is free and does not require an API key; `PUBMED_EMAIL` is optional. Tavily is no longer required by the web-search agent.

### Model note

The consumer Gemini app may display “3.1 Pro”, but the Developer API uses a different identifier. The configured key was checked against the API catalog: `gemini-3.1-pro-preview` exists but currently has zero free-tier quota for this project. `gemini-3.6-flash` is the verified working model for this setup. To use Pro, enable billing or use a project/key with Pro quota, then set the API identifier exposed by `GET /v1beta/models`.

## 4. Option A — run directly with Python (recommended for development)

### 4.1 Install system audio support

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y ffmpeg
```

macOS:

```bash
brew install ffmpeg
```

Windows: install FFmpeg and add its `bin` directory to `PATH`.

### 4.2 Create and activate a virtual environment

Use the existing environment if this repository already contains `venv`:

```bash
source venv/bin/activate                 # Linux/macOS/WSL
```

For a new environment:

```bash
python3.11 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Windows PowerShell activation:

```powershell
venv\Scripts\Activate.ps1
```

If FastAPI reports a missing multipart package, install the pinned dependency:

```bash
pip install python-multipart==0.0.20
```

### 4.3 Start the application

```bash
source venv/bin/activate
python app.py
```

The server listens on `http://localhost:8000`. Leave this terminal open. Stop it with `Ctrl+C`.

If Hugging Face is unavailable but models are already cached locally, startup can be run in offline mode:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python app.py
```

Use offline mode only after the required local models have been downloaded.

## 5. Option B — run with Docker

There is a `Dockerfile` in this repository; no `docker-compose.yml` is required.

```bash
docker build -t medical-assistant .
docker run -d --name medical-assistant-app \
  -p 8000:8000 \
  --env-file .env \
  medical-assistant
```

Open <http://localhost:8000>.

Useful Docker commands:

```bash
docker logs -f medical-assistant-app
docker ps
docker stop medical-assistant-app
docker start medical-assistant-app
docker rm medical-assistant-app
```

The Docker image installs FFmpeg and other native libraries automatically. The initial image build can take a while because PyTorch and ML dependencies are large.

## 6. Verify that the server is running

Health check:

```bash
curl http://localhost:8000/health
```

Expected result:

```json
{"status":"healthy"}
```

Text chat test:

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"query":"What are common symptoms of anemia?"}'
```

The response should contain `status`, `response`, and `agent` fields. Responses may also include a structured `sources` array. RAG and PubMed citations in this array use clickable `url` values (PubMed entries also include title, journal, and publication date); the web interface renders these links in a separate **Sources** section so voice playback does not read URLs. You can also test with a simple message such as `Hello`.

## 7. Use the web interface

1. Open <http://localhost:8000>.
2. Type a question and press Enter or select Send.
3. Upload a PNG, JPG, or JPEG when requesting image analysis.
4. For image results requesting confirmation, select Yes or No in the human-validation panel.
5. Select **Play Voice Response** only after configuring a valid ElevenLabs key.

Sample images are in `sample_images/`:

- `sample_images/chest_x-ray_covid_and_normal/`
- `sample_images/skin_lesion_images/`

## 8. Add or rebuild RAG documents (optional)

The repository includes a local database under `data/qdrant_db` and parsed/document data. To ingest one document:

```bash
source venv/bin/activate
python ingest_rag_data.py --file ./data/raw/brain_tumors_ucni.pdf
```

To ingest every supported document in a directory:

```bash
python ingest_rag_data.py --dir ./data/raw
```

With Docker:

```bash
docker exec medical-assistant-app \
  python ingest_rag_data.py --dir ./data/raw
```

Document ingestion uses the configured Gemini model for some processing steps and may therefore consume API quota.

## 9. Troubleshooting

### “No reply”, HTTP 500, or HTTP 404 from `/chat`

- Check the terminal or `docker logs` output.
- Confirm `GOOGLE_API_KEY` is set and valid.
- Confirm `GEMINI_MODEL` is an API model identifier available to the key. `gemini-3.6-flash` is the known working value for this project.
- A 429 error means the Google project has exhausted its quota; wait, switch to an available model, or enable billing.

### “Play Voice” fails or shows “Voice failed”

- Set a valid `ELEVEN_LABS_API_KEY` and restart the server.
- The backend returns `401 Invalid API key` when the key is blank/invalid.
- Browser microphone permissions and FFmpeg are also required for voice recording/transcription.

### Port 8000 is already in use

Stop the previous process/container, or run the app on another port only after changing the configured API port and the URL used by the browser.

### Startup repeatedly contacts Hugging Face

The app checks model metadata at startup. Ensure the first startup has internet access; after models are cached, use the offline-mode command shown above when needed.

### Docker command cannot connect to Docker

Start Docker Desktop/Docker Engine and retry. The Python/venv method does not require Docker.

## 10. Current verified setup

- FastAPI URL: `http://localhost:8000`
- Gemini model: `gemini-3.6-flash`
- RAG reranker: `ncbi/MedCPT-Cross-Encoder`
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2` (local)
- Vector store: local Qdrant under `data/qdrant_db`
- Web search: PubMed/NCBI E-utilities (free, no Tavily key required)
- Response citations: `/chat` and `/upload` expose structured `sources`; the frontend renders validated, deduplicated HTTP(S) URLs as clickable citations and omits the section when no sources are returned
- Voice: disabled until a valid ElevenLabs key is supplied

This project provides assistance and model predictions, not a medical diagnosis. Results should be reviewed by a qualified healthcare professional.
