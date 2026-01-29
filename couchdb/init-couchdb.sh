#!/bin/bash
# CouchDB Initialization Script
# Run this after CouchDB container is up to configure JWT, CORS, and create database

set -e

# Configuration from environment
COUCHDB_URL="${COUCHDB_URL:-http://localhost:5984}"
COUCHDB_USER="${COUCHDB_ADMIN_USER:-admin}"
COUCHDB_PASS="${COUCHDB_ADMIN_PASSWORD}"
JWT_SECRET="${JWT_SECRET_KEY}"
DATABASE_NAME="wishwithme"

# Use curl auth flag instead of embedding credentials in URL
CURL_AUTH="--user ${COUCHDB_USER}:${COUCHDB_PASS}"

echo "=== CouchDB Initialization ==="
echo "URL: ${COUCHDB_URL}"
echo "Database: ${DATABASE_NAME}"

# Validate required environment variables
if [ -z "$COUCHDB_PASS" ]; then
    echo "ERROR: COUCHDB_ADMIN_PASSWORD must be set"
    exit 1
fi

if [ -z "$JWT_SECRET" ] || [ ${#JWT_SECRET} -lt 32 ]; then
    echo "ERROR: JWT_SECRET_KEY must be set and at least 32 characters long"
    exit 1
fi

# Wait for CouchDB to be ready
echo ""
echo "Waiting for CouchDB to be ready..."
until curl -sf "${COUCHDB_URL}/" > /dev/null 2>&1; do
    echo "  CouchDB not ready, waiting..."
    sleep 2
done
echo "CouchDB is ready!"

# Finish single-node setup if needed
echo ""
echo "Ensuring single-node setup is complete..."
curl -sf ${CURL_AUTH} -X POST "${COUCHDB_URL}/_cluster_setup" \
    -H "Content-Type: application/json" \
    -d '{"action": "enable_single_node", "bind_address": "0.0.0.0", "port": 5984}' \
    2>/dev/null || echo "  (already configured)"

# Configure CORS via API
echo ""
echo "Configuring CORS..."
curl -sf ${CURL_AUTH} -X PUT "${COUCHDB_URL}/_node/_local/_config/cors/origins" \
    -d '"https://wishwith.me, https://api.wishwith.me, http://localhost:9000, http://localhost:9100"' || true
curl -sf ${CURL_AUTH} -X PUT "${COUCHDB_URL}/_node/_local/_config/cors/credentials" \
    -d '"true"' || true
curl -sf ${CURL_AUTH} -X PUT "${COUCHDB_URL}/_node/_local/_config/cors/methods" \
    -d '"GET, PUT, POST, HEAD, DELETE, OPTIONS"' || true
curl -sf ${CURL_AUTH} -X PUT "${COUCHDB_URL}/_node/_local/_config/cors/headers" \
    -d '"accept, authorization, content-type, origin, referer, x-csrf-token"' || true
echo "  CORS configured"

# Set JWT secret
echo ""
echo "Configuring JWT authentication..."
curl -sf ${CURL_AUTH} -X PUT "${COUCHDB_URL}/_node/_local/_config/jwt_keys/hmac:_default" \
    -d "\"${JWT_SECRET}\"" \
    && echo "  JWT secret configured" \
    || echo "  Failed to configure JWT secret"

# Configure JWT auth settings
curl -sf ${CURL_AUTH} -X PUT "${COUCHDB_URL}/_node/_local/_config/jwt_auth/required_claims" \
    -d '"exp,sub"' || true

# Create database if it doesn't exist
echo ""
echo "Creating database '${DATABASE_NAME}'..."
curl -sf ${CURL_AUTH} -X PUT "${COUCHDB_URL}/${DATABASE_NAME}" \
    && echo "  Database created" \
    || echo "  Database already exists"

# Create Mango indexes for access-based queries
echo ""
echo "Creating indexes..."

# Index on access field (for filtered replication)
curl -sf ${CURL_AUTH} -X POST "${COUCHDB_URL}/${DATABASE_NAME}/_index" \
    -H "Content-Type: application/json" \
    -d '{
        "index": {
            "fields": ["access"]
        },
        "name": "access-index",
        "type": "json"
    }' && echo "  access-index created"

# Index on type field
curl -sf ${CURL_AUTH} -X POST "${COUCHDB_URL}/${DATABASE_NAME}/_index" \
    -H "Content-Type: application/json" \
    -d '{
        "index": {
            "fields": ["type"]
        },
        "name": "type-index",
        "type": "json"
    }' && echo "  type-index created"

# Composite index for type + access
curl -sf ${CURL_AUTH} -X POST "${COUCHDB_URL}/${DATABASE_NAME}/_index" \
    -H "Content-Type: application/json" \
    -d '{
        "index": {
            "fields": ["type", "access"]
        },
        "name": "type-access-index",
        "type": "json"
    }' && echo "  type-access-index created"

# Index for pending items (item resolver)
curl -sf ${CURL_AUTH} -X POST "${COUCHDB_URL}/${DATABASE_NAME}/_index" \
    -H "Content-Type: application/json" \
    -d '{
        "index": {
            "fields": ["type", "status"]
        },
        "name": "type-status-index",
        "type": "json"
    }' && echo "  type-status-index created"

# Index for wishlist items
curl -sf ${CURL_AUTH} -X POST "${COUCHDB_URL}/${DATABASE_NAME}/_index" \
    -H "Content-Type: application/json" \
    -d '{
        "index": {
            "fields": ["wishlist_id", "type"]
        },
        "name": "wishlist-type-index",
        "type": "json"
    }' && echo "  wishlist-type-index created"

# Index for marks by item
curl -sf ${CURL_AUTH} -X POST "${COUCHDB_URL}/${DATABASE_NAME}/_index" \
    -H "Content-Type: application/json" \
    -d '{
        "index": {
            "fields": ["item_id", "type"]
        },
        "name": "item-type-index",
        "type": "json"
    }' && echo "  item-type-index created"

# Create design document with views
echo ""
echo "Creating design document..."

DESIGN_DOC='{
    "_id": "_design/app",
    "views": {
        "by_type": {
            "map": "function(doc) { if(doc.type) emit(doc.type, null); }"
        },
        "pending_items": {
            "map": "function(doc) { if(doc.type === \"item\" && doc.status === \"pending\") emit(doc._id, {wishlist_id: doc.wishlist_id, source_url: doc.source_url}); }"
        },
        "items_by_wishlist": {
            "map": "function(doc) { if(doc.type === \"item\") emit(doc.wishlist_id, null); }"
        },
        "marks_by_item": {
            "map": "function(doc) { if(doc.type === \"mark\") emit(doc.item_id, doc.quantity); }",
            "reduce": "_sum"
        },
        "shares_by_token": {
            "map": "function(doc) { if(doc.type === \"share\" && !doc.revoked) emit(doc.token, null); }"
        },
        "users_by_email": {
            "map": "function(doc) { if(doc.type === \"user\" && doc.email) emit(doc.email.toLowerCase(), null); }"
        }
    },
    "language": "javascript"
}'

# Try to create, if exists get rev and update
RESPONSE=$(curl -sf ${CURL_AUTH} -X PUT "${COUCHDB_URL}/${DATABASE_NAME}/_design/app" \
    -H "Content-Type: application/json" \
    -d "${DESIGN_DOC}" 2>&1) && echo "  Design document created" || {
    # Get current revision and update
    REV=$(curl -sf ${CURL_AUTH} "${COUCHDB_URL}/${DATABASE_NAME}/_design/app" | python3 -c "import sys,json; print(json.load(sys.stdin).get('_rev',''))" 2>/dev/null)
    if [ -n "$REV" ]; then
        curl -sf ${CURL_AUTH} -X PUT "${COUCHDB_URL}/${DATABASE_NAME}/_design/app?rev=${REV}" \
            -H "Content-Type: application/json" \
            -d "${DESIGN_DOC}" && echo "  Design document updated"
    else
        echo "  Failed to create/update design document"
    fi
}

# Verify setup
echo ""
echo "=== Verification ==="
echo "Database info:"
curl -sf ${CURL_AUTH} "${COUCHDB_URL}/${DATABASE_NAME}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  doc_count: {d.get(\"doc_count\", 0)}')"

echo ""
echo "Indexes:"
curl -sf ${CURL_AUTH} "${COUCHDB_URL}/${DATABASE_NAME}/_index" | python3 -c "import sys,json; d=json.load(sys.stdin); [print(f'  - {i[\"name\"]}') for i in d.get('indexes', [])]"

echo ""
echo "=== CouchDB initialization complete ==="
