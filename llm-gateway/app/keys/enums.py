import enum


class KeyStatus(str, enum.Enum):
    ACTIVE = "active"
    COOLDOWN = "cooldown"  # temporarily rate-limited (429), will recover
    EXHAUSTED = "exhausted"  # daily quota confirmed used up, or manually disabled
    DISABLED = "disabled"  # manually turned off by an admin, never auto-selected


class ProviderType(str, enum.Enum):
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    # OPENAI = "openai"          # future
    # GITHUB_ACTIONS = "github_actions"  # future — different resource shape, see notes
