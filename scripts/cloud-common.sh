# Shared by infra.sh, deploy-backend.sh and seed.sh. Sourced, not run.
#
# Every gcloud call goes through the `domain-health` configuration. The machine's default
# configuration belongs to other work and is never used, changed or read.
export CLOUDSDK_ACTIVE_CONFIG_NAME=domain-health
export CLOUDSDK_CORE_DISABLE_PROMPTS=1

REGION="${GCP_REGION:-us-central1}"
SERVICE=domain-health
QUEUE=domain-health-daily
JOB=domain-health-daily
REPOSITORY=domain-health
RUNTIME_ACCOUNT=dh-runtime
INVOKER_ACCOUNT=dh-invoker
BUILD_ACCOUNT=dh-build
SECRETS="proxy-secret session-secret admin-passphrase"

say() { printf '%s\n' "$*"; }
die() { printf 'stopped: %s\n' "$*" >&2; exit 1; }

PROJECT="$(gcloud config get-value project 2>/dev/null)"
[ -n "$PROJECT" ] || die "the domain-health gcloud configuration names no project"
# The project named in .env must be the one the configuration points at: nothing is
# ever written to a project that only one of the two names.
[ -n "${GCP_PROJECT_ID:-}" ] || die "GCP_PROJECT_ID is not set: put it in .env (see .env.example)"
[ "$GCP_PROJECT_ID" = "$PROJECT" ] || die "GCP_PROJECT_ID and the domain-health configuration name different projects"

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
RUNTIME_EMAIL="$RUNTIME_ACCOUNT@$PROJECT.iam.gserviceaccount.com"
INVOKER_EMAIL="$INVOKER_ACCOUNT@$PROJECT.iam.gserviceaccount.com"
BUILD_EMAIL="$BUILD_ACCOUNT@$PROJECT.iam.gserviceaccount.com"
# Cloud Run's deterministic URL: known before the first deploy, so the service can be told its
# own address (the audience of every machine token) in one deploy.
SERVICE_URL="https://$SERVICE-$PROJECT_NUMBER.$REGION.run.app"
IMAGE="$REGION-docker.pkg.dev/$PROJECT/$REPOSITORY/$SERVICE"
