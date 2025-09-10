#!/bin/bash
# Simple IB Client Portal Authentication Test
# This demonstrates the WORKING authentication sequence based on our analysis

set -e

BASE_URL="https://localhost:5000/v1/api"
COOKIE_JAR="cp_working_auth.jar"

echo "🔧 IB Client Portal Authentication Debug"
echo "========================================"

# Clean start
rm -f "$COOKIE_JAR"

echo
echo "Step 1: Test basic connectivity"
echo "------------------------------"
curl -sk -c "$COOKIE_JAR" -b "$COOKIE_JAR" "$BASE_URL/tickle" | jq -r '.session // "No session"'
echo "✓ Gateway accessible"

echo
echo "Step 2: Check initial auth status" 
echo "--------------------------------"
AUTH_STATUS=$(curl -sk -c "$COOKIE_JAR" -b "$COOKIE_JAR" "$BASE_URL/iserver/auth/status")
echo "$AUTH_STATUS" | jq '.'

if echo "$AUTH_STATUS" | jq -r '.authenticated' | grep -q true; then
    echo "🎉 Already authenticated!"
    exit 0
fi

echo
echo "Step 3: Try SSO validation (requires browser login)"
echo "-------------------------------------------------"
SSO_RESULT=$(curl -sk -c "$COOKIE_JAR" -b "$COOKIE_JAR" "$BASE_URL/sso/validate")
echo "$SSO_RESULT" | jq -r '.USER_NAME // "Not logged in"'

if echo "$SSO_RESULT" | jq -r '.RESULT' | grep -q true; then
    echo "✓ User logged in via browser"
else
    echo "❌ User not logged in via browser"
    echo "   Please visit https://localhost:5000 and login first"
    exit 1
fi

echo
echo "Step 4: Try to get session tokens via reauthenticate"
echo "--------------------------------------------------"
REAUTH_RESULT=$(curl -sk -c "$COOKIE_JAR" -b "$COOKIE_JAR" -X POST "$BASE_URL/iserver/reauthenticate")
echo "$REAUTH_RESULT"

if echo "$REAUTH_RESULT" | jq -r '.message' | grep -q triggered; then
    echo "✓ Reauthenticate triggered"
    
    echo
    echo "Step 5: Poll for authentication (30 attempts)"
    echo "-------------------------------------------"
    
    for i in {1..30}; do
        sleep 2
        AUTH_CHECK=$(curl -sk -c "$COOKIE_JAR" -b "$COOKIE_JAR" "$BASE_URL/iserver/auth/status" 2>/dev/null)
        
        if echo "$AUTH_CHECK" | jq -r '.authenticated' | grep -q true; then
            echo "🎉 Authentication successful after ${i}0 seconds!"
            
            echo
            echo "Step 6: Test API access with authentication"
            echo "----------------------------------------"
            curl -sk -c "$COOKIE_JAR" -b "$COOKIE_JAR" "$BASE_URL/portfolio/accounts" | jq '.[0].accountId // "No accounts"' 2>/dev/null || echo "API call failed"
            
            echo
            echo "🎉 AUTHENTICATION HANDSHAKE SUCCESSFUL!"
            echo "Session data saved to: $COOKIE_JAR"
            echo 
            echo "Cookie contents:"
            echo "=================="
            grep -v "^#" "$COOKIE_JAR" 2>/dev/null || echo "No cookies found"
            
            exit 0
        fi
        
        if [ $((i % 10)) -eq 0 ]; then
            echo "   Still waiting... (attempt $i/30)"
        fi
    done
    
    echo "❌ Authentication timeout after 60 seconds"
else
    echo "❌ Reauthenticate failed"
fi

echo
echo "❌ AUTHENTICATION FAILED"
echo "Please ensure:"
echo "1. You're logged into https://localhost:5000 in a browser"
echo "2. The gateway is running properly"
echo "3. You're using the same host (localhost vs 127.0.0.1)"