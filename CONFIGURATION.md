# Configuration Guide

## Environment Variables

The Resume Agent uses environment variables for configuration. These can be set in a `.env` file or as system environment variables.

### Quick Start

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your configuration:
```bash
OPENAI_API_KEY=your-actual-api-key
OPENAI_BASE_URL=https://llm.gauravshivaprasad.com/v1
OPENAI_MODEL=o3
```

3. Run the application - it will automatically load `.env`

## Configuration Options

### OpenAI API Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | **Yes** | - | Your OpenAI API key or compatible API key |
| `OPENAI_BASE_URL` | No | `https://api.openai.com/v1` | API endpoint URL. Change for custom LLM servers |
| `OPENAI_MODEL` | No | `gpt-4` | Model name (e.g., `gpt-4`, `gpt-3.5-turbo`, `o3`) |

### LLM Behavior Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_TEMPERATURE` | No | `0.1` | Controls randomness (0-2). Lower = more consistent |
| `LLM_MAX_TOKENS` | No | `2000` | Maximum tokens in response |
| `LLM_TIMEOUT` | No | `60` | Request timeout in seconds |

### Application Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LOG_LEVEL` | No | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### Optional: Web Search

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TAVILY_API_KEY` | No | - | API key for Tavily search (for company research) |

## Using Custom LLM Endpoints

### Example: Local LLM Server

```bash
OPENAI_API_KEY=sk-local-key
OPENAI_BASE_URL=http://localhost:8000/v1
OPENAI_MODEL=llama-3
```

### Example: Custom Provider

```bash
OPENAI_API_KEY=your-provider-key
OPENAI_BASE_URL=https://llm.gauravshivaprasad.com/v1
OPENAI_MODEL=o3
LLM_TEMPERATURE=0
```

### Example: Standard OpenAI

```bash
OPENAI_API_KEY=sk-...your-openai-key...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4
```

## Configuration Loading

The application loads configuration in this order:

1. **Environment variables** (highest priority)
2. **`.env` file** in project root
3. **Default values** (lowest priority)

This means you can:
- Set everything in `.env` for development
- Override specific values with environment variables in production
- Use defaults for non-critical settings

## Validation

The application validates configuration on startup:

```python
from resume_agent.config import settings

# This will raise ValueError if configuration is invalid
settings.validate()
```

Validation checks:
- ✓ `OPENAI_API_KEY` is set
- ✓ `LLM_TEMPERATURE` is between 0 and 2
- ✓ `LLM_MAX_TOKENS` is positive
- ✓ `LLM_TIMEOUT` is positive

## Example Configurations

### For Data Analysis Resumes
```bash
OPENAI_MODEL=gpt-4
LLM_TEMPERATURE=0.1  # More consistent, less creative
LLM_MAX_TOKENS=1500
```

### For Creative/Design Resumes
```bash
OPENAI_MODEL=gpt-4
LLM_TEMPERATURE=0.3  # More creative wording
LLM_MAX_TOKENS=2000
```

### For Fast Testing
```bash
OPENAI_MODEL=gpt-3.5-turbo
LLM_MAX_TOKENS=1000
LLM_TIMEOUT=30
```

## Troubleshooting

### "OPENAI_API_KEY is required"
- Make sure you have a `.env` file in the project root
- Check that the `.env` file contains `OPENAI_API_KEY=your-key`
- Try setting it directly: `export OPENAI_API_KEY=your-key`

### "Connection Error" or "Timeout"
- Check `OPENAI_BASE_URL` is correct
- Increase `LLM_TIMEOUT` if using slow servers
- Verify your API key is valid

### Skills/Projects Not Generated
- Check logs for LLM errors
- Verify API key has sufficient credits/permissions
- Ensure model name is correct for your provider

### "Module not found: dotenv"
```bash
pip install python-dotenv
```

## Security Best Practices

1. **Never commit `.env` to version control**
   - `.env` is in `.gitignore`
   - Share `.env.example` instead

2. **Use different keys for different environments**
   ```bash
   # Development
   OPENAI_API_KEY=sk-dev-...
   
   # Production
   OPENAI_API_KEY=sk-prod-...
   ```

3. **Rotate API keys regularly**

4. **Use read-only or limited scope keys when possible**
