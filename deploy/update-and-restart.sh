#!/bin/bash
set -e

echo "=== Auto Comment Worker Update and Restart ==="

# Navigate to project directory
cd /var/www/auto-comment-worker

# Pull latest changes
echo "Pulling latest changes..."
git pull origin main

# Restart the service
echo "Restarting auto-comment-worker service..."
sudo systemctl restart auto-comment-worker

# Wait a moment for service to start
sleep 2

# Check service status
echo "Checking service status..."
sudo systemctl status auto-comment-worker --no-pager

# Show recent logs
echo ""
echo "=== Recent service logs ==="
sudo journalctl -u auto-comment-worker -n 20 --no-pager

echo ""
echo "=== Update complete ==="
