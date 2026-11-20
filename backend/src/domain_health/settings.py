"""What the deployed service reads from its environment. Nothing here is a model key: the
service is built with recorded model output only."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # The Google Cloud project and region the service runs in.
    gcp_project_id: str
    gcp_region: str = "us-central1"
    # This service's own public URL: the audience of every machine token, and where tasks call.
    service_url: str
    # The service account Scheduler and Tasks call as.
    invoker_email: str
    tasks_queue: str = "domain-health-daily"
    # Shared with the frontend's server routes. From Secret Manager.
    proxy_secret: SecretStr
    # Optional. Empty on the hosted demo, which then sends no alert.
    slack_webhook_url: SecretStr | None = None
