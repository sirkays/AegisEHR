#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install production dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Run database migrations
python manage.py migrate

# Seed initial demo accounts, patients, clinicians, and records
python manage.py seed_data || true
