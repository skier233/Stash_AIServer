#!/bin/bash

# Generate self-signed certificate for HTTPS
# This script creates SSL certificates for local/development use

echo "🔒 Setting up HTTPS for StashAI Server..."

# Create ssl directory
mkdir -p ssl

# Generate private key
openssl genrsa -out ssl/server.key 2048

# Generate certificate signing request
openssl req -new -key ssl/server.key -out ssl/server.csr -subj "/C=US/ST=State/L=City/O=StashAI/CN=10.0.0.154"

# Generate self-signed certificate
openssl x509 -req -days 365 -in ssl/server.csr -signkey ssl/server.key -out ssl/server.crt

# Set proper permissions
chmod 600 ssl/server.key
chmod 644 ssl/server.crt

echo "✅ SSL certificates generated:"
echo "  - Private key: ssl/server.key"
echo "  - Certificate: ssl/server.crt"
echo ""
echo "⚠️  Note: This is a self-signed certificate."
echo "   Your browser will show a security warning - click 'Advanced' and 'Proceed'."
echo ""
echo "🚀 Start HTTPS server with: docker-compose -f docker-compose.https.yml up -d"