#!/bin/sh
# Scripts d'exécution des tâches planifiées pour Jelani Backend
# Usage en crontab ou via un orchestrateur de conteneurs (Render Cron Job, Kubernetes CronJob, etc.)
#
# Exemples :
# * * * * * cd /app && ./scripts/run_cron_tasks.sh expire-bookings >> /var/log/jelani-cron.log 2>&1
# 0 * * * * cd /app && ./scripts/run_cron_tasks.sh wallet-audit >> /var/log/jelani-cron.log 2>&1

set -e

TASK="${1:-expire-bookings}"

case "$TASK" in
    "expire-bookings")
        echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Running expire-bookings..."
        flask --app app expire-bookings
        ;;
    "wallet-audit")
        echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Running wallet-audit..."
        flask --app app wallet-audit --expire-stale-topups
        ;;
    *)
        echo "Unknown task: $TASK. Available: expire-bookings, wallet-audit"
        exit 1
        ;;
esac
