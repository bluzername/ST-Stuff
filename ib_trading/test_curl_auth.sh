#!/bin/bash
# IB Client Portal Authentication Test Script (curl-based)
# 
# This script demonstrates the correct authentication handshake sequence
# using curl commands with proper cookie and session token handling.

set -e

BASE_URL="https://localhost:5000/v1/api"
COOKIE_JAR="cp_auth_test.jar"
VERBOSE=false
MANUAL_LOGIN=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -m|--manual-login)
            MANUAL_LOGIN=true
            shift
            ;;
        -u|--base-url)
            BASE_URL="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -v, --verbose      Enable verbose output"
            echo "  -m, --manual-login Prompt for manual login"
            echo "  -u, --base-url     Base URL (default: https://localhost:5000/v1/api)"
            echo "  -h, --help         Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${YELLOW}[DEBUG]${NC} $1"
    fi
}

# Create fresh cookie jar
rm -f "$COOKIE_JAR"

log_info "Starting IB Client Portal Authentication Test (curl-based)"
log_info "Base URL: $BASE_URL"
log_info "Cookie jar: $COOKIE_JAR"

echo
log_info "=== Step 1: Test Gateway Connection ==="

# Test tickle endpoint
log_info "Testing /tickle endpoint..."
TICKLE_RESPONSE=$(curl -sk -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
    -X GET "$BASE_URL/tickle" 2>/dev/null)

if [ $? -eq 0 ]; then
    log_success "Gateway is accessible"
    log_debug "Tickle response: $TICKLE_RESPONSE"
else
    log_error "Gateway not accessible"
    exit 1
fi

# Test initial auth status
log_info "Testing /iserver/auth/status..."
AUTH_RESPONSE=$(curl -sk -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
    -X GET "$BASE_URL/iserver/auth/status" 2>/dev/null)

if [ $? -eq 0 ]; then
    AUTHENTICATED=$(echo "$AUTH_RESPONSE" | grep -o '"authenticated":[^,}]*' | cut -d':' -f2)
    log_info "Initial auth status: $AUTH_RESPONSE"
    
    if [ "$AUTHENTICATED" = "true" ]; then
        log_success "Already authenticated!"
        exit 0
    fi
else
    log_error "Auth status check failed"
    exit 1
fi

echo
log_info "=== Step 2: SSO Validation ==="

# Test SSO validation
log_info "Testing /sso/validate..."
SSO_RESPONSE=$(curl -sk -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
    -X GET "$BASE_URL/sso/validate" 2>/dev/null)

if [ $? -eq 0 ]; then
    SSO_RESULT=$(echo "$SSO_RESPONSE" | grep -o '"RESULT":[^,}]*' | cut -d':' -f2)
    log_debug "SSO response: $SSO_RESPONSE"
    
    if [ "$SSO_RESULT" = "true" ]; then
        USER_NAME=$(echo "$SSO_RESPONSE" | grep -o '"USER_NAME":"[^"]*"' | cut -d':' -f2 | tr -d '"')
        log_success "SSO validation successful - User: $USER_NAME"
    else
        log_error "SSO validation failed - user not logged in via browser"
        
        if [ "$MANUAL_LOGIN" = true ]; then
            log_info "Please login via browser at https://localhost:5000"
            log_info "Press Enter to continue after login..."
            read -r
            
            # Retry SSO validation
            SSO_RESPONSE=$(curl -sk -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
                -X GET "$BASE_URL/sso/validate" 2>/dev/null)
            SSO_RESULT=$(echo "$SSO_RESPONSE" | grep -o '"RESULT":[^,}]*' | cut -d':' -f2)
            
            if [ "$SSO_RESULT" != "true" ]; then
                log_error "SSO validation still failed after manual login"
                exit 1
            fi
            
            log_success "SSO validation successful after manual login"
        else
            log_info "Use --manual-login flag to prompt for browser login"
            exit 1
        fi
    fi
else
    log_error "SSO validation request failed"
    exit 1
fi

echo
log_info "=== Step 3: Session Initialization ==="

# Try session initialization
log_info "Testing /iserver/auth/ssodh/init..."
INIT_RESPONSE=$(curl -sk -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
    -X POST "$BASE_URL/iserver/auth/ssodh/init" \
    -H "Content-Type: application/json" 2>/dev/null)

if [ $? -eq 0 ]; then
    log_debug "Init response: $INIT_RESPONSE"
    INIT_AUTH=$(echo "$INIT_RESPONSE" | grep -o '"authenticated":[^,}]*' | cut -d':' -f2)
    
    if [ "$INIT_AUTH" = "true" ]; then
        log_success "Session initialized and authenticated"
        AUTHENTICATED=true
    else
        log_info "Session initialization did not authenticate, trying reauthenticate flow..."
        AUTHENTICATED=false
    fi
else
    log_error "Session initialization request failed"
    AUTHENTICATED=false
fi

# If not authenticated yet, try reauthenticate flow
if [ "$AUTHENTICATED" = false ]; then
    echo
    log_info "=== Step 4: Reauthenticate Flow ==="
    
    log_info "Triggering /iserver/reauthenticate..."
    REAUTH_RESPONSE=$(curl -sk -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
        -X POST "$BASE_URL/iserver/reauthenticate" \
        -H "Content-Type: application/json" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        log_debug "Reauthenticate response: $REAUTH_RESPONSE"
        REAUTH_MSG=$(echo "$REAUTH_RESPONSE" | grep -o '"message":"[^"]*"' | cut -d':' -f2 | tr -d '"')
        
        if [ "$REAUTH_MSG" = "triggered" ]; then
            log_success "Reauthenticate triggered successfully"
            
            # Poll for authentication (60 second timeout)
            log_info "Polling for authentication (60s timeout)..."
            for i in {1..30}; do
                sleep 2
                AUTH_STATUS=$(curl -sk -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
                    -X GET "$BASE_URL/iserver/auth/status" 2>/dev/null)
                
                POLL_AUTH=$(echo "$AUTH_STATUS" | grep -o '"authenticated":[^,}]*' | cut -d':' -f2)
                
                if [ "$POLL_AUTH" = "true" ]; then
                    log_success "Authentication successful after ${i}0 seconds"
                    AUTHENTICATED=true
                    break
                fi
                
                if [ $((i % 10)) -eq 0 ]; then
                    log_info "Still waiting for auth... (attempt $i/30)"
                fi
            done
            
            if [ "$AUTHENTICATED" != true ]; then
                log_error "Authentication timeout - please complete login in browser"
                exit 1
            fi
        else
            log_error "Unexpected reauthenticate response: $REAUTH_RESPONSE"
            exit 1
        fi
    else
        log_error "Reauthenticate request failed"
        exit 1
    fi
fi

echo
log_info "=== Step 5: Final Verification ==="

# Final auth status check
FINAL_STATUS=$(curl -sk -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
    -X GET "$BASE_URL/iserver/auth/status" 2>/dev/null)
FINAL_AUTH=$(echo "$FINAL_STATUS" | grep -o '"authenticated":[^,}]*' | cut -d':' -f2)

if [ "$FINAL_AUTH" = "true" ]; then
    log_success "Final verification: Successfully authenticated"
    
    # Test API access by getting accounts
    log_info "Testing authenticated API access..."
    ACCOUNTS_RESPONSE=$(curl -sk -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
        -X GET "$BASE_URL/portfolio/accounts" 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        log_success "API access verified"
        log_debug "Accounts response: $ACCOUNTS_RESPONSE"
    else
        log_error "API access test failed"
    fi
else
    log_error "Final verification failed - not authenticated"
    log_debug "Final status: $FINAL_STATUS"
    exit 1
fi

echo
log_info "=== Session Information ==="

# Show cookie jar contents
if [ -f "$COOKIE_JAR" ]; then
    COOKIE_COUNT=$(grep -c "^[^#]" "$COOKIE_JAR" 2>/dev/null || echo "0")
    log_info "Cookies saved: $COOKIE_COUNT"
    
    if [ "$VERBOSE" = true ]; then
        log_debug "Cookie jar contents:"
        cat "$COOKIE_JAR" | grep -v "^#" | while read line; do
            if [ ! -z "$line" ]; then
                NAME=$(echo "$line" | cut -f6)
                VALUE=$(echo "$line" | cut -f7)
                log_debug "  $NAME: ${VALUE:0:20}..."
            fi
        done
    fi
fi

echo
log_success "🎉 Authentication test completed successfully!"
log_info "Session data saved to: $COOKIE_JAR"
log_info "You can now use this cookie jar for authenticated API requests:"
log_info "  curl -sk -b '$COOKIE_JAR' -X GET '$BASE_URL/portfolio/accounts'"

# Clean up
if [ "$VERBOSE" != true ]; then
    rm -f "$COOKIE_JAR"
fi