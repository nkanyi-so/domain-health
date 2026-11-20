#!/bin/bash
# `make infra`: everything the service runs on, in the owner's Google Cloud project. Safe to run
# again: each thing is created only if it is not there, and settings are set to the same values.
#
# Firestore (Native, us-central1) with its TTL policies; the Cloud Tasks queue with its retry
# settings; two service accounts (one runs the service, one calls it); three secrets, made here
# with random values that are never printed; a $5 monthly budget alert; the image repository;
# and, once the service is deployed, the daily Cloud Scheduler job.
set -euo pipefail
cd "$(dirname "$0")/.."
. scripts/cloud-common.sh

say "project: $PROJECT, region: $REGION"

say "APIs"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  firestore.googleapis.com cloudtasks.googleapis.com cloudscheduler.googleapis.com \
  secretmanager.googleapis.com billingbudgets.googleapis.com iam.googleapis.com --quiet

say "Firestore"
if ! gcloud firestore databases describe --database='(default)' >/dev/null 2>&1; then
  # Its location is fixed for good. Allowed in advance: Native mode, us-central1.
  gcloud firestore databases create --database='(default)' --location="$REGION" --type=firestore-native --quiet
fi
# TTL: sandboxes (collection group `clients`, where only sandbox documents carry the field),
# cached live checks, and the per-address counters.
for group in clients live_checks counters; do
  gcloud firestore fields ttls update expires_at --collection-group="$group" --enable-ttl --async --quiet >/dev/null
done

say "service accounts"
for account in "$RUNTIME_ACCOUNT" "$INVOKER_ACCOUNT"; do
  gcloud iam service-accounts describe "$account@$PROJECT.iam.gserviceaccount.com" >/dev/null 2>&1 \
    || gcloud iam service-accounts create "$account" --display-name="domain-health $account" --quiet
done
# The one that runs the service: Firestore user, Tasks enqueuer, and may name the invoker on a
# task. Neither account is an owner or an editor.
for role in roles/datastore.user roles/cloudtasks.enqueuer; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member="serviceAccount:$RUNTIME_EMAIL" \
    --role="$role" --condition=None --quiet >/dev/null
done
gcloud iam service-accounts add-iam-policy-binding "$INVOKER_EMAIL" \
  --member="serviceAccount:$RUNTIME_EMAIL" --role=roles/iam.serviceAccountUser --quiet >/dev/null

say "secrets"
for secret in $SECRETS; do
  if ! gcloud secrets describe "$secret" >/dev/null 2>&1; then
    # A random value, straight from the generator into Secret Manager. Never shown or stored here.
    openssl rand -base64 36 | tr -d '\n' | gcloud secrets create "$secret" \
      --replication-policy=automatic --data-file=- --quiet >/dev/null
  fi
done
# The service reads only the proxy secret. The other two are the frontend's (Phase 5).
gcloud secrets add-iam-policy-binding proxy-secret --member="serviceAccount:$RUNTIME_EMAIL" \
  --role=roles/secretmanager.secretAccessor --quiet >/dev/null

say "queue"
if gcloud tasks queues describe "$QUEUE" --location="$REGION" >/dev/null 2>&1; then
  verb=update
else
  verb=create
fi
gcloud tasks queues "$verb" "$QUEUE" --location="$REGION" --max-attempts=5 \
  --min-backoff=10s --max-backoff=300s --max-doublings=4 --max-dispatches-per-second=1 \
  --max-concurrent-dispatches=2 --quiet >/dev/null

say "image repository"
gcloud artifacts repositories describe "$REPOSITORY" --location="$REGION" >/dev/null 2>&1 \
  || gcloud artifacts repositories create "$REPOSITORY" --repository-format=docker \
       --location="$REGION" --description="domain-health service images" --quiet

say "budget"
BILLING="$(gcloud billing projects describe "$PROJECT" --format='value(billingAccountName)' | sed 's|billingAccounts/||')"
[ -n "$BILLING" ] || die "the project has no billing account"
if ! gcloud billing budgets list --billing-account="$BILLING" --format='value(displayName)' | grep -qx 'domain-health monthly'; then
  gcloud billing budgets create --billing-account="$BILLING" --display-name='domain-health monthly' \
    --budget-amount=5USD --filter-projects="projects/$PROJECT_NUMBER" \
    --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0 --quiet >/dev/null
fi

say "scheduler"
if gcloud run services describe "$SERVICE" --region="$REGION" >/dev/null 2>&1; then
  if gcloud scheduler jobs describe "$JOB" --location="$REGION" >/dev/null 2>&1; then
    verb=update
  else
    verb=create
  fi
  # Once a day, 06:00 UTC. The token is Google-signed for the invoker, with the service's URL as
  # its audience: exactly what the service checks.
  gcloud scheduler jobs "$verb" http "$JOB" --location="$REGION" --schedule='0 6 * * *' \
    --time-zone='Etc/UTC' --uri="$SERVICE_URL/internal/dispatch" --http-method=POST \
    --oidc-service-account-email="$INVOKER_EMAIL" --oidc-token-audience="$SERVICE_URL" \
    --attempt-deadline=60s --max-retry-attempts=3 --quiet >/dev/null
  say "the daily job calls $SERVICE_URL/internal/dispatch"
else
  say "the service is not deployed yet: run make deploy-backend, then make infra again for the daily job"
fi
say "infra: done"
