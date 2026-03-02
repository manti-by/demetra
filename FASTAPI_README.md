# Demetra FastAPI Ticket Creation API

This FastAPI application provides an HTTP API to process raw text with Groq AI and automatically create structured Linear tickets.

## Features

- **Text Processing**: Uses Groq's LLM to intelligently parse raw text into structured ticket components
- **Linear Integration**: Automatically creates Linear tickets with proper formatting
- **Structured Output**: Organizes content into:
  - Clear, actionable title
  - Detailed description
  - Technical requirements
  - Acceptance criteria
- **Priority Management**: Supports Linear priority levels
- **Project Assignment**: Optional project assignment for tickets

## Setup

### 1. Install Dependencies

```bash
# Install the updated dependencies
uv sync --all-extras --dev
```

### 2. Environment Variables

Ensure you have the following environment variables set:

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your actual API keys
# Required for Linear integration
LINEAR_API_KEY=your_linear_api_key
LINEAR_TEAM_ID=your_linear_team_id

# Required for Groq integration
GROQ_API_KEY=your_groq_api_key

# Optional: Linear project ID for auto-assignment
LINEAR_PROJECT_ID=your_default_project_id
```

### 3. Run the API Server

#### Development Mode

```bash
# Basic usage
python run_api.py

# Development mode with auto-reload
python run_api.py --reload

# Custom host/port
python run_api.py --host localhost --port 8080

# Using Make commands
make api          # Production mode
make api-dev      # Development with auto-reload
```

#### Production Mode (Systemd Service)

For production deployment, use the systemd service:

```bash
# Install the systemd service
make service-install

# Start the service
make service-start

# Check service status
make service-status

# View logs
make service-logs
```

See [SYSTEMD_SETUP.md](SYSTEMD_SETUP.md) for detailed production setup instructions.

### 4. Access the API

The API will be available at:
- Main API: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- OpenAPI spec: `http://localhost:8000/openapi.json`

## API Usage

### Create a Ticket

**POST** `/create-ticket`

Send raw text to be processed and converted into a Linear ticket.

#### Request Body

```json
{
  "text": "Raw text describing the feature/issue/requirement",
  "project_id": "optional_linear_project_id",
  "priority": 2
}
```

#### Priority Levels
- `0` - No priority
- `1` - Urgent
- `2` - High (default)
- `3` - Normal
- `4` - Low

#### Response

```json
{
  "success": true,
  "ticket_id": "linear_issue_id",
  "ticket_identifier": "DEV-123",
  "error": null
}
```

### Example Usage

#### Using curl

```bash
curl -X POST "http://localhost:8000/create-ticket" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "We need to implement user authentication with JWT tokens, password reset, and email verification. The system should be secure with rate limiting and proper session management.",
    "priority": 2
  }'
```

#### Using Python

```python
import aiohttp
import asyncio
import json

async def create_ticket():
    payload = {
        "text": "Implement a new dashboard with real-time data visualization for user metrics",
        "priority": 2
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "http://localhost:8000/create-ticket",
            json=payload
        ) as response:
            result = await response.json()
            print(json.dumps(result, indent=2))

asyncio.run(create_ticket())
```

#### Test Script

Run the included test script:

```bash
python test_api.py
```

## How It Works

1. **Text Reception**: The API receives raw text via POST request
2. **Groq Processing**: The text is sent to Groq's LLM with a specialized prompt that:
   - Extracts the main requirement/issue
   - Creates a clear, actionable title
   - Structures the description
   - Identifies technical requirements
   - Defines acceptance criteria
3. **Linear Creation**: A GraphQL mutation creates the Linear ticket with:
   - Structured description with markdown formatting
   - Proper sections for requirements and criteria
   - Assigned priority and optional project
4. **Response**: Returns the created ticket details or error information

## API Endpoints

- `GET /` - API information and available endpoints
- `GET /health` - Health check endpoint
- `POST /create-ticket` - Main ticket creation endpoint
- `GET /docs` - Interactive API documentation
- `GET /openapi.json` - OpenAPI specification

## Error Handling

The API includes comprehensive error handling for:
- Missing environment variables
- Groq API failures
- Linear API errors
- Invalid input data
- Network connectivity issues

## Development

### Running Tests

```bash
# Run the test script
python test_api.py

# Or use pytest if you add tests to the tests/ directory
uv run pytest tests/
```

### Code Structure

- `fastapi_app.py` - Main FastAPI application
- `run_api.py` - Server startup script
- `test_api.py` - API testing script
- Uses existing Demetra services:
  - `demetra.services.graphql` - Linear GraphQL integration
  - `demetra.settings` - Configuration management

## Integration with Existing Workflow

This API complements the existing Demetra workflow:
- **Existing**: Processes existing Linear tickets through OpenCode/Cursor
- **New API**: Creates new Linear tickets from raw text input
- Both use the same Linear integration and configuration

## Security Considerations

- API keys are loaded from environment variables
- No authentication is implemented (add as needed)
- Input validation via Pydantic models
- Error messages don't expose sensitive information

## Future Enhancements

Potential improvements:
- Authentication/authorization
- Webhook support for incoming text
- Batch ticket creation
- Custom prompts per project
- Integration with other text sources (Slack, email, etc.)
- Ticket templates and customization