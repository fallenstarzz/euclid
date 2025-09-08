"""
🛠️ Utility Functions
Helper functions for logging, formatting, and common operations
"""

import os
import json
import time
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from colorama import Fore, Style, init
from decimal import Decimal

# Initialize colorama
init(autoreset=True)

def setup_logging(config: Dict[str, Any]) -> logging.Logger:
    """Setup logging configuration"""
    log_level = getattr(logging, config.get("logging", {}).get("level", "INFO"))
    log_file = config.get("logging", {}).get("file", "logs/bot.log")
    
    # Create logs directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Setup logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def load_config(config_path: str = "config/config.json") -> Dict[str, Any]:
    """Load configuration from JSON file"""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file not found: {config_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {e}")

def load_tokens(tokens_path: str = "config/tokens.json") -> Dict[str, Any]:
    """Load token configuration"""
    try:
        with open(tokens_path, 'r') as f:
            tokens = json.load(f)
        return tokens
    except FileNotFoundError:
        raise FileNotFoundError(f"Tokens file not found: {tokens_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in tokens file: {e}")

def format_timestamp(timestamp: Optional[float] = None) -> str:
    """Format timestamp for display"""
    if timestamp is None:
        timestamp = time.time()
    
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def format_duration(seconds: float) -> str:
    """Format duration in human readable format"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"

def format_address(address: str, length: int = 8) -> str:
    """Format address for display"""
    if len(address) <= length:
        return address
    return f"{address[:length//2]}...{address[-length//2:]}"

def format_hash(tx_hash: str, length: int = 10) -> str:
    """Format transaction hash for display"""
    if len(tx_hash) <= length:
        return tx_hash
    return f"{tx_hash[:length]}..."

def format_amount(amount: Decimal, decimals: int = 4) -> str:
    """Format amount for display"""
    return f"{amount:.{decimals}f}"

def format_percentage(value: float) -> str:
    """Format percentage for display"""
    return f"{value:.1f}%"

def print_banner():
    """Print bot banner"""
    banner = f"""
{Fore.CYAN}
╔══════════════════════════════════════════════════════════════╗
║                  EUCLID SWAP BOT v1.0                   ║
║                                                              ║
║  {Fore.YELLOW}[TRACK] Fully Automated Swap Execution{Fore.CYAN}                      ║
║  {Fore.GREEN}[AMOUNT] Automatic Points Tracking{Fore.CYAN}                          ║
║  {Fore.MAGENTA}[SWAP] 24/7 Continuous Operation{Fore.CYAN}                          ║
║  {Fore.BLUE}🛡️  Secure Wallet Management{Fore.CYAN}                           ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
{Style.RESET_ALL}"""
    print(banner)

def print_status_header():
    """Print status header"""
    print(f"\n{Fore.BLUE}{'='*70}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}[STATS] BOT STATUS DASHBOARD{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'='*70}{Style.RESET_ALL}")

def print_wallet_status(wallet_info: Dict[str, Any]):
    """Print wallet status"""
    print(f"\n{Fore.YELLOW}💳 WALLET STATUS{Style.RESET_ALL}")
    print(f"   Address: {Fore.GREEN}{format_address(wallet_info['address'], 12)}{Style.RESET_ALL}")
    print(f"   ETH Balance: {Fore.GREEN}{wallet_info['eth_balance']:.4f} ETH{Style.RESET_ALL}")
    print(f"   Nonce: {Fore.BLUE}{wallet_info['nonce']}{Style.RESET_ALL}")
    print(f"   Connected: {Fore.GREEN if wallet_info['connected'] else Fore.RED}{'[OK]' if wallet_info['connected'] else '[ERROR]'}{Style.RESET_ALL}")

def print_points_status(points_info: Dict[str, Any]):
    """Print points tracking status"""
    print(f"\n{Fore.YELLOW}[TRACK] POINTS STATUS{Style.RESET_ALL}")
    print(f"   Total Points: {Fore.GREEN}{points_info['total_points']}{Style.RESET_ALL}")
    print(f"   Successful: {Fore.GREEN}{points_info['successful_submissions']}{Style.RESET_ALL}")
    print(f"   Failed: {Fore.RED}{points_info['failed_submissions']}{Style.RESET_ALL}")
    print(f"   Success Rate: {Fore.GREEN}{points_info['success_rate']:.1f}%{Style.RESET_ALL}")

def print_session_status(session_info: Dict[str, Any]):
    """Print session status"""
    print(f"\n{Fore.YELLOW}[SECURE] SESSION STATUS{Style.RESET_ALL}")
    
    if session_info['status'] == 'no_session':
        print(f"   Status: {Fore.RED}[ERROR] No Session{Style.RESET_ALL}")
    elif session_info['status'] == 'expired':
        print(f"   Status: {Fore.RED}[ERROR] Expired{Style.RESET_ALL}")
    else:
        print(f"   Status: {Fore.GREEN}[OK] Active{Style.RESET_ALL}")
        print(f"   Time Left: {Fore.BLUE}{session_info['time_left_hours']:.1f}h{Style.RESET_ALL}")
        print(f"   Cookies: {Fore.BLUE}{session_info['cookie_count']}{Style.RESET_ALL}")

def generate_random_delay(min_seconds: int, max_seconds: int) -> int:
    """Generate random delay for anti-detection"""
    return random.randint(min_seconds, max_seconds)

def calculate_next_swap_time(interval_minutes: int, randomization: Dict[str, Any]) -> datetime:
    """Calculate next swap time with optional randomization"""
    base_delay = interval_minutes * 60
    
    if randomization.get("enabled", False):
        min_delay = randomization.get("min_delay", 300)
        max_delay = randomization.get("max_delay", 900)
        random_delay = generate_random_delay(min_delay, max_delay)
        total_delay = base_delay + random_delay
    else:
        total_delay = base_delay
    
    return datetime.now() + timedelta(seconds=total_delay)

def wait_with_countdown(seconds: int, message: str = "Next operation"):
    """Wait with countdown display"""
    end_time = datetime.now() + timedelta(seconds=seconds)
    
    while datetime.now() < end_time:
        remaining = (end_time - datetime.now()).total_seconds()
        
        if remaining <= 0:
            break
        
        mins, secs = divmod(int(remaining), 60)
        hours, mins = divmod(mins, 60)
        
        if hours > 0:
            time_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
        else:
            time_str = f"{mins:02d}:{secs:02d}"
        
        print(f"\r{Fore.BLUE}[WAIT] {message} in: {time_str}{Style.RESET_ALL}", end="", flush=True)
        time.sleep(1)
    
    print(f"\r{' ' * 50}\r", end="")  # Clear countdown line

def validate_ethereum_address(address: str) -> bool:
    """Validate Ethereum address format"""
    if not address.startswith('0x'):
        return False
    
    if len(address) != 42:
        return False
    
    try:
        int(address[2:], 16)
        return True
    except ValueError:
        return False

def validate_private_key(private_key: str) -> bool:
    """Validate private key format"""
    # Remove 0x prefix if present
    if private_key.startswith('0x'):
        private_key = private_key[2:]
    
    if len(private_key) != 64:
        return False
    
    try:
        int(private_key, 16)
        return True
    except ValueError:
        return False

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division with default value"""
    if denominator == 0:
        return default
    return numerator / denominator

def retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    """Retry function with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            
            delay = base_delay * (2 ** attempt)
            print(f"{Fore.YELLOW}[WARN] Attempt {attempt + 1} failed, retrying in {delay}s...{Style.RESET_ALL}")
            time.sleep(delay)

def load_env_file(env_path: str = ".env") -> Dict[str, str]:
    """Load environment variables from .env file"""
    env_vars = {}
    
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    except FileNotFoundError:
        pass  # .env file is optional
    
    return env_vars

def ensure_directory_exists(directory: str):
    """Ensure directory exists, create if not"""
    os.makedirs(directory, exist_ok=True)

class PerformanceMonitor:
    """Monitor bot performance metrics"""
    
    def __init__(self):
        self.start_time = time.time()
        self.swap_times = []
        self.submission_times = []
        self.error_count = 0
    
    def record_swap_time(self, duration: float):
        """Record swap execution time"""
        self.swap_times.append(duration)
    
    def record_submission_time(self, duration: float):
        """Record points submission time"""
        self.submission_times.append(duration)
    
    def record_error(self):
        """Record an error"""
        self.error_count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        uptime = time.time() - self.start_time
        
        return {
            "uptime_seconds": uptime,
            "uptime_formatted": format_duration(uptime),
            "total_swaps": len(self.swap_times),
            "total_submissions": len(self.submission_times),
            "total_errors": self.error_count,
            "avg_swap_time": sum(self.swap_times) / len(self.swap_times) if self.swap_times else 0,
            "avg_submission_time": sum(self.submission_times) / len(self.submission_times) if self.submission_times else 0,
            "error_rate": self.error_count / max(1, len(self.swap_times)) * 100
        }

def print_final_stats(performance: PerformanceMonitor, points_info: Dict[str, Any]):
    """Print final bot statistics"""
    stats = performance.get_stats()
    
    print(f"\n{Fore.CYAN}[STATS] FINAL STATISTICS{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'='*50}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}⏱️  Total Uptime: {stats['uptime_formatted']}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}[SWAP] Total Swaps: {stats['total_swaps']}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}📤 Total Submissions: {stats['total_submissions']}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}[AMOUNT] Total Points: {points_info['total_points']}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}[OK] Success Rate: {points_info['success_rate']:.1f}%{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[STATS] Avg Swap Time: {stats['avg_swap_time']:.1f}s{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}[STATS] Avg Submission Time: {stats['avg_submission_time']:.1f}s{Style.RESET_ALL}")
    print(f"{Fore.RED}[ERROR] Total Errors: {stats['total_errors']}{Style.RESET_ALL}")
    print(f"{Fore.BLUE}{'='*50}{Style.RESET_ALL}")

def validate_transaction_hash(tx_hash: str) -> bool:
    """
    Validate transaction hash format to ensure it's real
    
    Args:
        tx_hash: Transaction hash to validate
        
    Returns:
        bool: True if valid real transaction hash
    """
    if not tx_hash:
        return False
    
    # Normalize hash (add 0x prefix if missing)
    if not tx_hash.startswith('0x'):
        tx_hash = '0x' + tx_hash
    
    # Check format: 66 characters with 0x prefix (64 hex chars + 2 for 0x)
    if len(tx_hash) != 66:
        return False
    
    if not tx_hash.startswith('0x'):
        return False
    
    # Reject simulation hashes
    if 'simulated' in tx_hash.lower():
        return False
    
    # Check that it's valid hex
    try:
        int(tx_hash, 16)
        return True
    except ValueError:
        return False

def validate_private_key(private_key: str) -> str:
    """
    Validate and format private key
    
    Args:
        private_key: Raw private key string
        
    Returns:
        str: Formatted private key with 0x prefix
    """
    if not private_key:
        raise ValueError("Private key is required")
    
    # Clean the key
    key = private_key.strip()
    
    # Remove 0x prefix if present for validation
    if key.startswith('0x'):
        key = key[2:]
    
    # Validate length
    if len(key) != 64:
        raise ValueError(f"Private key must be 64 characters, got {len(key)}")
    
    # Validate hex format
    try:
        int(key, 16)
    except ValueError:
        raise ValueError("Private key must be valid hex")
    
    # Return with 0x prefix
    return f"0x{key}"
