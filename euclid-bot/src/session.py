"""
[SECURE] Session Management Module
Handles authentication cookies and session persistence
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional
import base64
from cryptography.fernet import Fernet
from colorama import Fore, Style

class SessionManager:
    """Manages authentication sessions and cookies"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize session manager"""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Session storage
        self.session_file = "session.dat"
        self.cookies = {}
        self.session_created = None
        self.session_expires = None
        
        # Encryption
        self.cipher = None
        self._setup_encryption()
        
    def _setup_encryption(self):
        """Setup encryption for session storage"""
        try:
            key_file = ".session_key"
            
            if os.path.exists(key_file):
                with open(key_file, 'rb') as f:
                    key = f.read()
            else:
                key = Fernet.generate_key()
                with open(key_file, 'wb') as f:
                    f.write(key)
                self.logger.info("[KEY] Generated new session encryption key")
            
            self.cipher = Fernet(key)
            
        except Exception as e:
            self.logger.warning(f"[WARN] Encryption setup failed: {e}")
            self.cipher = None
    
    def load_session_from_env(self) -> bool:
        """Load session from environment variables"""
        try:
            # Load from .env file first
            from dotenv import load_dotenv
            load_dotenv()
            
            cookies = {}
            
            # Load cookies from environment
            env_cookies = {
                "intercom-session-gvbx42be": os.getenv("INTERCOM_SESSION"),
                "intercom-device-id-gvbx42be": os.getenv("INTERCOM_DEVICE_ID"),
                "__Host-next-auth.csrf-token": os.getenv("CSRF_TOKEN"),
                "__Secure-next-auth.callback-url": os.getenv("CALLBACK_URL")
            }
            
            # Filter out None values
            cookies = {k: v for k, v in env_cookies.items() if v}
            
            if cookies:
                self.cookies = cookies
                self.session_created = time.time()
                self.session_expires = self.session_created + (2 * 3600)  # 2 hours
                self.logger.info(f"[COOKIE] Loaded {len(cookies)} cookies from environment")
                return True
            else:
                self.logger.warning("[WARN] No cookies found in environment")
                return False
                
        except Exception as e:
            self.logger.error(f"[ERROR] Failed to load session from env: {e}")
            return False
    
    def save_session(self, cookies: Dict[str, str]) -> bool:
        """Save session cookies to encrypted file"""
        try:
            self.cookies = cookies
            self.session_created = time.time()
            self.session_expires = self.session_created + (2 * 3600)  # 2 hours
            
            session_data = {
                "cookies": cookies,
                "created": self.session_created,
                "expires": self.session_expires
            }
            
            # Encrypt and save
            if self.cipher:
                encrypted_data = self.cipher.encrypt(json.dumps(session_data).encode())
                with open(self.session_file, 'wb') as f:
                    f.write(encrypted_data)
            else:
                # Fallback: save as plain JSON (not recommended)
                with open(self.session_file, 'w') as f:
                    json.dump(session_data, f)
                self.logger.warning("[WARN] Session saved without encryption")
            
            self.logger.info(f"[SAVE] Session saved with {len(cookies)} cookies")
            return True
            
        except Exception as e:
            self.logger.error(f"[ERROR] Failed to save session: {e}")
            return False
    
    def load_session(self) -> bool:
        """Load session from encrypted file"""
        try:
            if not os.path.exists(self.session_file):
                self.logger.info("[FILE] No saved session found")
                return False
            
            # Load and decrypt
            if self.cipher:
                with open(self.session_file, 'rb') as f:
                    encrypted_data = f.read()
                decrypted_data = self.cipher.decrypt(encrypted_data)
                session_data = json.loads(decrypted_data.decode())
            else:
                # Fallback: load plain JSON
                with open(self.session_file, 'r') as f:
                    session_data = json.load(f)
            
            # Check if session is expired
            current_time = time.time()
            if current_time > session_data.get("expires", 0):
                self.logger.warning("[WARN] Saved session has expired")
                return False
            
            # Load session data
            self.cookies = session_data["cookies"]
            self.session_created = session_data["created"]
            self.session_expires = session_data["expires"]
            
            time_left = (self.session_expires - current_time) / 3600
            self.logger.info(f"[MOBILE] Loaded session with {len(self.cookies)} cookies ({time_left:.1f}h remaining)")
            return True
            
        except Exception as e:
            self.logger.error(f"[ERROR] Failed to load session: {e}")
            return False
    
    def is_session_valid(self) -> bool:
        """Check if current session is valid"""
        if not self.cookies:
            return False
        
        if not self.session_expires:
            return False
        
        return time.time() < self.session_expires
    
    def get_session_cookies(self) -> Dict[str, str]:
        """Get current session cookies"""
        return self.cookies.copy()
    
    def prompt_for_cookies(self) -> bool:
        """Interactive prompt for session cookies"""
        print(f"\n{Fore.YELLOW}[COOKIE] Session Setup Required{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Please provide your browser session cookies:{Style.RESET_ALL}")
        print(f"{Fore.BLUE}You can get these from DevTools -> Network tab -> Copy cookie header{Style.RESET_ALL}")
        
        while True:
            print(f"\n{Fore.GREEN}Enter cookie collection method:{Style.RESET_ALL}")
            print("1. [LIST] Paste full cookie header")
            print("2. [CONFIG] Enter cookies individually")
            print("3. [FILE] Load from .env file")
            print("4. [ERROR] Skip (may cause auth errors)")
            
            choice = input(f"\n{Fore.CYAN}Select option (1-4): {Style.RESET_ALL}").strip()
            
            if choice == "1":
                return self._parse_cookie_header()
            elif choice == "2":
                return self._enter_cookies_individually()
            elif choice == "3":
                return self.load_session_from_env()
            elif choice == "4":
                self.logger.warning("[WARN] Skipping cookie setup - authentication may fail")
                return False
            else:
                print(f"{Fore.RED}Invalid choice. Please select 1-4.{Style.RESET_ALL}")
    
    def _parse_cookie_header(self) -> bool:
        """Parse cookies from full header string"""
        try:
            print(f"\n{Fore.YELLOW}[LIST] Cookie Header Method:{Style.RESET_ALL}")
            print("1. Open https://testnet.euclidswap.io and connect wallet")
            print("2. Open DevTools (F12) -> Network tab")
            print("3. Refresh page -> Find request -> Headers -> Copy 'Cookie:' value")
            
            cookie_header = input(f"\n{Fore.CYAN}Paste cookie header: {Style.RESET_ALL}").strip()
            
            if not cookie_header:
                self.logger.error("[ERROR] No cookie header provided")
                return False
            
            # Parse cookies from header
            cookies = {}
            for cookie_pair in cookie_header.split(';'):
                if '=' in cookie_pair:
                    name, value = cookie_pair.strip().split('=', 1)
                    cookies[name] = value
            
            if len(cookies) < 2:
                self.logger.warning("[WARN] Very few cookies found - may be incomplete")
            
            self.logger.info(f"🔍 Parsed {len(cookies)} cookies")
            return self.save_session(cookies)
            
        except Exception as e:
            self.logger.error(f"[ERROR] Cookie parsing failed: {e}")
            return False
    
    def _enter_cookies_individually(self) -> bool:
        """Enter cookies one by one"""
        try:
            print(f"\n{Fore.YELLOW}[CONFIG] Individual Cookie Entry:{Style.RESET_ALL}")
            
            required_cookies = [
                "intercom-session-gvbx42be",
                "intercom-device-id-gvbx42be",
                "__Host-next-auth.csrf-token",
                "__Secure-next-auth.callback-url"
            ]
            
            cookies = {}
            
            for cookie_name in required_cookies:
                value = input(f"{Fore.BLUE}{cookie_name}: {Style.RESET_ALL}").strip()
                if value:
                    cookies[cookie_name] = value
                    print(f"{Fore.GREEN}[OK] Added{Style.RESET_ALL}")
                else:
                    print(f"{Fore.YELLOW}[WARN] Skipped{Style.RESET_ALL}")
            
            if cookies:
                self.logger.info(f"[CONFIG] Collected {len(cookies)} cookies")
                return self.save_session(cookies)
            else:
                self.logger.error("[ERROR] No cookies provided")
                return False
                
        except Exception as e:
            self.logger.error(f"[ERROR] Individual cookie entry failed: {e}")
            return False
    
    def refresh_session_if_needed(self) -> bool:
        """Check and refresh session if needed"""
        if self.is_session_valid():
            time_left = (self.session_expires - time.time()) / 3600
            if time_left > 0.5:  # More than 30 minutes left
                return True
        
        self.logger.warning("[WARN] Session expired or expiring soon")
        return self.prompt_for_cookies()
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get session information"""
        if not self.session_created:
            return {"status": "no_session"}
        
        current_time = time.time()
        time_left = max(0, self.session_expires - current_time) if self.session_expires else 0
        
        return {
            "status": "active" if self.is_session_valid() else "expired",
            "created": self.session_created,
            "expires": self.session_expires,
            "time_left_hours": time_left / 3600,
            "cookie_count": len(self.cookies)
        }
    
    def cleanup_session(self):
        """Clean up session files"""
        try:
            if os.path.exists(self.session_file):
                os.remove(self.session_file)
                self.logger.info("🧹 Session file cleaned up")
        except Exception as e:
            self.logger.error(f"[ERROR] Session cleanup failed: {e}")
    
    def export_session_for_backup(self) -> Optional[str]:
        """Export session as base64 string for backup"""
        try:
            if not self.cookies:
                return None
            
            session_data = {
                "cookies": self.cookies,
                "created": self.session_created,
                "expires": self.session_expires
            }
            
            json_str = json.dumps(session_data)
            encoded = base64.b64encode(json_str.encode()).decode()
            
            self.logger.info("📤 Session exported for backup")
            return encoded
            
        except Exception as e:
            self.logger.error(f"[ERROR] Session export failed: {e}")
            return None
    
    def import_session_from_backup(self, encoded_session: str) -> bool:
        """Import session from base64 backup"""
        try:
            json_str = base64.b64decode(encoded_session.encode()).decode()
            session_data = json.loads(json_str)
            
            self.cookies = session_data["cookies"]
            self.session_created = session_data["created"]
            self.session_expires = session_data["expires"]
            
            self.logger.info("📥 Session imported from backup")
            return True
            
        except Exception as e:
            self.logger.error(f"[ERROR] Session import failed: {e}")
            return False
