# Demetra API

FastAPI server for creating Linear tickets from text using Groq LLM.

## Setup

```bash
uv sync --all-extras
```

## Run Locally

```bash
uv run uvicorn demetra.api:app --reload
```

## API Endpoint

**POST /ticket**

```bash
curl -X POST http://localhost:8000/ticket \
  -H "Content-Type: application/json" \
  -d '{"text": "Add user authentication to the app using OAuth2 with Google provider"}'
```

Optional `title` field:

```bash
curl -X POST http://localhost:8000/ticket \
  -H "Content-Type: application/json" \
  -d '{"text": "...", "title": "Custom Title"}'
```

## Response

```json
{
  "ticket_id": "abc123",
  "identifier": "DEMETRA-42",
  "title": "Add user authentication"
}
```

## Environment Variables

Required:
- `GROQ_API_KEY` - Groq API key for LLM
- `LINEAR_API_KEY` - Linear API key
- `LINEAR_TEAM_ID` - Linear team ID

Optional:
- `LINEAR_STATE_TODO_ID` - Default: Linear TODO state ID

## Systemd Installation

```bash
sudo cp demetra-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable demetra-api
sudo systemctl start demetra-api
```
