import enum


class KeyStatus(str, enum.Enum):
    ACTIVE = "active"
    COOLDOWN = "cooldown" 
    EXHAUSTED = "exhausted"  
    DISABLED = "disabled" 


class ProviderType(str, enum.Enum):
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    GROQ = "groq"