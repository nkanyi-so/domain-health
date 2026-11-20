#!/bin/bash
# `make deploy-backend`: build the image with Cloud Build and deploy it to Cloud Run.
#
# At most one instance, none when idle, billed per request. Open at the platform level because
# the frontend cannot mint Google tokens; every route refuses at the app level. The only secret
# the service gets is the proxy secret. No model key is set, and the image has no model library.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/cloud-common.sh

TAG="$(git rev-parse --short HEAD)"
[ -z "$(git status --porcelain -- backend prompts evals/settings.toml)" ] \
  || die "commit the backend first: the image is tagged with the commit it was built from"

say "building $IMAGE:$TAG"
gcloud builds submit . --config=backend/cloudbuild.yaml --substitutions="_IMAGE=$IMAGE:$TAG" \
  --service-account="projects/$PROJECT/serviceAccounts/$BUILD_EMAIL" --quiet

say "deploying"
gcloud run deploy "$SERVICE" --image="$IMAGE:$TAG" --region="$REGION" \
  --service-account="$RUNTIME_EMAIL" --allow-unauthenticated \
  --min-instances=0 --max-instances=1 --concurrency=20 --cpu=1 --memory=512Mi --timeout=60 \
  --cpu-throttling \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT,GCP_REGION=$REGION,SERVICE_URL=$SERVICE_URL,INVOKER_EMAIL=$INVOKER_EMAIL,TASKS_QUEUE=$QUEUE" \
  --set-secrets="PROXY_SECRET=proxy-secret:latest" --quiet

say "deployed: $SERVICE_URL"
