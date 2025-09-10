#!/usr/bin/env python3
"""
Interactive Brokers Client Portal Authentication Test Script

This script demonstrates the correct authentication handshake sequence
for the IB Client Portal REST API, including proper session management.

Usage:
    python test_auth_handshake.py [--verbose] [--manual-login]
"""

import requests
import json
import time
import argparse
import sys
from pathlib import Path
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings for self-signed certs
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

class IBAuthTester:
    def __init__(self, base_url="https://localhost:5000/v1/api", verbose=False):
        self.base_url = base_url.rstrip('/')
        self.verbose = verbose
        self.session = requests.Session()
        self.session.verify = False
        
        # Setup headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'IBAuthTester/1.0',
            'Accept': 'application/json'
        })
        
        self.session_tokens = {}
        
    def log(self, msg, level="INFO"):
        if self.verbose or level in ["ERROR", "SUCCESS"]:
            prefix = {
                "INFO": "[INFO]",
                "DEBUG": "[DEBUG]", 
                "ERROR": "[ERROR]",
                "SUCCESS": "[SUCCESS]"
            }.get(level, "[INFO]")
            print(f"{prefix} {msg}")
    
    def make_request(self, method, endpoint, **kwargs):
        """Make HTTP request and capture session tokens"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        self.log(f"{method} {url}", "DEBUG")
        if self.verbose and 'json' in kwargs:
            self.log(f"Request body: {json.dumps(kwargs['json'], indent=2)}", "DEBUG")
        
        try:
            response = self.session.request(method, url, **kwargs)
            
            self.log(f"Response: {response.status_code} {response.reason}", "DEBUG")
            
            # Capture session tokens
            cst = response.headers.get('X-IBKR-CST') or response.headers.get('x-ibkr-cst')
            secured = response.headers.get('X-IBKR-Secured') or response.headers.get('x-ibkr-secured')
            
            if cst:
                self.session.headers['X-IBKR-CST'] = cst
                self.session_tokens['cst'] = cst
                self.log(f"Captured CST token: {cst[:20]}...", "DEBUG")
                
            if secured:
                self.session.headers['X-IBKR-Secured'] = secured
                self.session_tokens['secured'] = secured
                self.log(f"Captured Secured token: {secured[:20]}...", "DEBUG")
            
            if self.verbose:
                # Show interesting response headers
                headers_to_show = ['Set-Cookie', 'X-IBKR-CST', 'X-IBKR-Secured']
                for header in headers_to_show:
                    if header in response.headers:
                        value = response.headers[header]
                        if len(value) > 100:
                            value = value[:100] + "..."
                        self.log(f"{header}: {value}", "DEBUG")
            
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError:
                    return {"text": response.text}
            else:
                response.raise_for_status()
                
        except Exception as e:
            self.log(f"Request failed: {e}", "ERROR")
            return None
    
    def test_gateway_connection(self):
        """Test basic gateway connectivity"""
        self.log("=== Testing Gateway Connection ===")
        
        # 1. Test tickle endpoint
        self.log("1. Testing /tickle endpoint...")
        tickle_response = self.make_request('GET', 'tickle')
        
        if tickle_response:
            self.log("✓ Gateway is accessible", "SUCCESS")
            if self.verbose:
                self.log(f"Tickle response: {json.dumps(tickle_response, indent=2)}", "DEBUG")
        else:
            self.log("✗ Gateway not accessible", "ERROR")
            return False
        
        # 2. Test auth status (should be false initially)
        self.log("2. Testing /iserver/auth/status...")
        auth_status = self.make_request('GET', 'iserver/auth/status')
        
        if auth_status:
            authenticated = auth_status.get('authenticated', False)
            connected = auth_status.get('connected', False) 
            competing = auth_status.get('competing', False)
            
            self.log(f"Auth Status - Authenticated: {authenticated}, Connected: {connected}, Competing: {competing}")
            
            if authenticated:
                self.log("✓ Already authenticated!", "SUCCESS")
                return True
        
        return True
    
    def test_sso_validation(self):
        """Test SSO validation (requires browser login)"""
        self.log("=== Testing SSO Validation ===")
        
        self.log("3. Testing /sso/validate...")
        sso_response = self.make_request('GET', 'sso/validate')
        
        if sso_response:
            if sso_response.get('RESULT') is True:
                user_name = sso_response.get('USER_NAME', 'Unknown')
                expires = sso_response.get('EXPIRES', 0)
                self.log(f"✓ SSO validation successful - User: {user_name}, Expires: {expires}s", "SUCCESS")
                return True
            else:
                self.log("✗ SSO validation failed - user not logged in via browser", "ERROR")
                return False
        else:
            self.log("✗ SSO validation request failed", "ERROR")
            return False
    
    def test_session_initialization(self):
        """Test iserver session initialization"""
        self.log("=== Testing Session Initialization ===")
        
        self.log("4. Testing /iserver/auth/ssodh/init...")
        init_response = self.make_request('POST', 'iserver/auth/ssodh/init')
        
        if init_response:
            if self.verbose:
                self.log(f"Init response: {json.dumps(init_response, indent=2)}", "DEBUG")
                
            if init_response.get('authenticated'):
                self.log("✓ Session initialized and authenticated", "SUCCESS")
                return True
            else:
                self.log(f"✗ Session initialization failed: {init_response}", "ERROR")
                return False
        else:
            self.log("✗ Session initialization request failed", "ERROR")
            return False
    
    def test_reauthenticate_flow(self):
        """Test the reauthenticate flow"""
        self.log("=== Testing Reauthenticate Flow ===")
        
        self.log("5. Triggering /iserver/reauthenticate...")
        reauth_response = self.make_request('POST', 'iserver/reauthenticate')
        
        if reauth_response:
            self.log(f"Reauthenticate response: {reauth_response}")
            
            if reauth_response.get('message') == 'triggered':
                self.log("✓ Reauthenticate triggered successfully", "SUCCESS")
                
                # Poll for authentication
                self.log("6. Polling for authentication (60s timeout)...")
                max_attempts = 30
                attempt = 0
                
                while attempt < max_attempts:
                    attempt += 1
                    time.sleep(2)
                    
                    status = self.make_request('GET', 'iserver/auth/status')
                    if status and status.get('authenticated'):
                        self.log(f"✓ Authentication successful after {attempt * 2}s", "SUCCESS")
                        return True
                    
                    if attempt % 10 == 0:
                        self.log(f"Still waiting for auth... (attempt {attempt}/30)")
                
                self.log("✗ Authentication timeout - please complete login in browser", "ERROR")
                return False
            else:
                self.log(f"✗ Unexpected reauthenticate response: {reauth_response}", "ERROR")
                return False
        else:
            self.log("✗ Reauthenticate request failed", "ERROR")
            return False
    
    def verify_final_authentication(self):
        """Final verification of authentication status"""
        self.log("=== Final Authentication Verification ===")
        
        # Check auth status one more time
        auth_status = self.make_request('GET', 'iserver/auth/status')
        if auth_status and auth_status.get('authenticated'):
            self.log("✓ Final verification: Successfully authenticated", "SUCCESS")
            
            # Try to get accounts to verify API access
            self.log("7. Testing authenticated API access...")
            accounts = self.make_request('GET', 'portfolio/accounts')
            
            if accounts:
                if isinstance(accounts, list) and len(accounts) > 0:
                    account_ids = [acc.get('accountId', acc.get('id', 'unknown')) for acc in accounts]
                    self.log(f"✓ API access verified - Accounts: {account_ids}", "SUCCESS")
                else:
                    self.log(f"✓ API accessible but no accounts found: {accounts}", "SUCCESS")
            else:
                self.log("✗ API access test failed", "ERROR")
                
            return True
        else:
            self.log("✗ Final verification failed - not authenticated", "ERROR")
            return False
    
    def show_session_info(self):
        """Display session information"""
        self.log("=== Session Information ===")
        self.log(f"Session tokens: {len(self.session_tokens)}")
        for name, token in self.session_tokens.items():
            self.log(f"  {name}: {token[:20]}..." if len(token) > 20 else f"  {name}: {token}")
        
        self.log(f"Cookies: {len(self.session.cookies)}")
        for cookie in self.session.cookies:
            self.log(f"  {cookie.name}: {cookie.value[:20]}..." if len(cookie.value) > 20 else f"  {cookie.name}: {cookie.value}")
    
    def run_full_test(self, manual_login=False):
        """Run the complete authentication test"""
        self.log("Starting IB Client Portal Authentication Test")
        
        # Step 1: Test basic connectivity
        if not self.test_gateway_connection():
            return False
        
        # Step 2: Test SSO validation (requires browser login)
        sso_success = self.test_sso_validation()
        
        if not sso_success:
            if manual_login:
                self.log("Please login via browser at https://localhost:5000 and press Enter to continue...")
                input()
                sso_success = self.test_sso_validation()
            else:
                self.log("Run with --manual-login to prompt for browser login")
                return False
        
        if not sso_success:
            return False
        
        # Step 3: Initialize session
        if not self.test_session_initialization():
            # If session init fails, try reauthenticate flow
            self.log("Session initialization failed, trying reauthenticate flow...")
            if not self.test_reauthenticate_flow():
                return False
        
        # Step 4: Final verification
        success = self.verify_final_authentication()
        
        if success:
            self.show_session_info()
            
        return success

def main():
    parser = argparse.ArgumentParser(
        description="Test IB Client Portal Authentication",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--manual-login', '-m', action='store_true',
                        help='Prompt for manual browser login if needed')
    parser.add_argument('--base-url', default='https://localhost:5000/v1/api',
                        help='Client Portal Gateway base URL')
    
    args = parser.parse_args()
    
    tester = IBAuthTester(args.base_url, args.verbose)
    
    if tester.run_full_test(args.manual_login):
        print("\n🎉 Authentication test completed successfully!")
        return 0
    else:
        print("\n❌ Authentication test failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())