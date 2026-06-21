import os

from app.config import get_settings

# Force mock mode and clear Groq API keys for all test sessions
os.environ["CPV_MOCK_MODE"] = "true"
os.environ["CPV_GROQ_API_KEY"] = ""
os.environ["GROQ_API_KEY"] = ""

# Clear the lru_cache for settings to ensure these changes are applied
get_settings.cache_clear()
