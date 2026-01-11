# Multi-Provider LLM Configuration

The Resume Agent now supports multiple LLM providers with easy switching between them.

## Supported Providers

### 1. OpenAI (ChatGPT)
Use official OpenAI models like `gpt-4o-mini`, `gpt-4o`, `gpt-4-turbo`, etc.

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-proj-your-actual-openai-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

### 2. Custom Deployed Models
Use your own deployed models with OpenAI-compatible API.

```env
LLM_PROVIDER=custom
CUSTOM_API_KEY=your-custom-api-key
CUSTOM_BASE_URL=https://your-deployed-model.com/v1
CUSTOM_MODEL=your-model-name
```

### 3. Gemini (Future Support)
Google's Gemini models - coming soon!

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-pro
```

## Quick Start

1. **Copy the example env file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and set your provider:**
   - For ChatGPT: Set `LLM_PROVIDER=openai` and add your `OPENAI_API_KEY`
   - For custom model: Set `LLM_PROVIDER=custom` and configure `CUSTOM_*` variables

3. **Run the agent:**
   ```bash
   python ./tailor.py --jd ./jd.txt --resume_dir ./SWE_Resume_Template/ --profile ./profile.json --out_dir ./output/ --out_pdf ./output/final.pdf --company "CompanyName"
   ```

## Switching Between Providers

Just change the `LLM_PROVIDER` value in your `.env` file:

- `LLM_PROVIDER=openai` - Use ChatGPT
- `LLM_PROVIDER=custom` - Use your deployed model
- `LLM_PROVIDER=gemini` - Use Gemini (when implemented)

## Configuration Details

### OpenAI Settings
- **API Key**: Get from https://platform.openai.com/api-keys
- **Recommended Model**: `gpt-4o-mini` (fast, cost-effective)
- **Other Options**: `gpt-4o`, `gpt-4-turbo`

### Custom Model Settings
- **API Key**: Your deployment's authentication key
- **Base URL**: Must be OpenAI API-compatible
- **Model**: Your specific model identifier

### Common Settings (All Providers)
```env
LLM_TEMPERATURE=0.1      # Lower = more deterministic (0-2)
LLM_MAX_TOKENS=2000      # Maximum response length
LLM_TIMEOUT=60           # Request timeout in seconds
```

## Environment Variables Priority

1. Environment variables (set directly in shell)
2. `.env` file
3. Default values in `config.py`

## Security Notes

- **Never commit `.env` file** - it contains sensitive API keys
- Keep your API keys secure and rotate them regularly
- Use environment variables in production/CI environments
- The `.env.example` file is safe to commit (contains no real keys)

## Troubleshooting

### "OPENAI_API_KEY is required"
- Check that `LLM_PROVIDER` matches your configuration
- Verify the corresponding API key is set (`OPENAI_API_KEY`, `CUSTOM_API_KEY`, etc.)

### "Unknown LLM provider"
- Ensure `LLM_PROVIDER` is one of: `openai`, `custom`, `gemini`
- Check for typos in `.env` file

### Custom model not working
- Verify your custom endpoint is OpenAI API-compatible
- Check that `CUSTOM_BASE_URL` includes `/v1` suffix
- Test your API key with curl first

## Future Enhancements

- [ ] Google Gemini integration
- [ ] Anthropic Claude support
- [ ] Azure OpenAI support
- [ ] Local model support (Ollama, LM Studio)
