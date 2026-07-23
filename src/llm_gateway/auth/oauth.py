from authlib.integrations.starlette_client import OAuth

from llm_gateway.config import get_settings

_settings = get_settings()

oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=_settings.GOOGLE_CLIENT_ID,
    client_secret=_settings.GOOGLE_CLIENT_SECRET,
    client_kwargs={"scope": "openid email profile"},
)
