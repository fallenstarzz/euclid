#!/usr/bin/env python3
"""
Euclid Swap Bot - Main Entry Point
Fully automated swap execution and points tracking for Euclid testnet
"""

import os
import sys
import io
import time
import logging
import traceback
import json
import re
import random
from datetime import datetime
from typing import Optional

# FIXED: Return to clean UI logging (issue resolved)
logging.basicConfig(
    level=logging.CRITICAL,  # Only critical errors for clean UI
    format='%(message)s'
)

# Suppress ALL internal logs for clean interface
logging.getLogger('web3').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.getLogger('requests').setLevel(logging.CRITICAL)
logging.getLogger('src.wallet').setLevel(logging.CRITICAL)
logging.getLogger('src.swap').setLevel(logging.CRITICAL)
logging.getLogger('src.tracker').setLevel(logging.CRITICAL)
logging.getLogger('src.session').setLevel(logging.CRITICAL)
logging.getLogger('src.adaptive_swap_executor').setLevel(logging.CRITICAL)
logging.getLogger('modules.swap_plume_to_stt').setLevel(logging.CRITICAL)
logging.getLogger('modules.swap_stt_to_plume').setLevel(logging.CRITICAL)
logging.getLogger('modules.swap_orchestrator').setLevel(logging.CRITICAL)
# Fix SSL environment issue
os.environ.pop('SSLKEYLOGFILE', None)
os.environ.pop('SSL_KEY_LOG_FILE', None)

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.wallet import WalletManager
from src.swap import SwapExecutor
from src.adaptive_swap_executor import AdaptiveSwapExecutor
from src.tracker import PointsTracker
from modules import SwapOrchestrator
from src.session import SessionManager
from src.somnia_connector import SomniaChainConnector
from src.adaptive_config import AdaptiveConfigManager
from src.adaptive_amount_manager import AdaptiveConfiguration, AdaptiveMode, SwapResult
from src.adaptive_ui import AdaptiveUI
from src.minimal_ui import ui, Colors
from src.utils import (
    load_config, load_tokens, load_env_file,
    validate_private_key
)
from colorama import Fore, Style, init

init(autoreset=True)

# --- Compatibility stubs for legacy UI helpers (no-ops to avoid linter warnings) ---
def print_banner():
    pass

def calculate_next_swap_time(interval_minutes, randomization):
    from datetime import datetime, timedelta
    return datetime.now() + timedelta(minutes=interval_minutes)

def wait_with_countdown(seconds, label):
    pass

def format_timestamp():
    from datetime import datetime
    return datetime.now().isoformat()

def print_wallet_status(status):
    pass

def print_session_status(status):
    pass

def print_status_header():
    pass

def print_final_stats(perf, points_status):
    pass

def setup_referral(session=None):
    """Add referral code to session for point credits"""
    referral_config_file = 'referral_config.json'
    
    try:
        # Check if we have saved referral
        if os.path.exists(referral_config_file):
            with open(referral_config_file, 'r') as f:
                config = json.load(f)
                saved_code = config.get('referral_code')
                if saved_code:
                    use_saved = input("[REFERRAL] Use saved referral " + saved_code + "? (y/n): ").strip().lower()
                    if use_saved == 'y':
                        referral_code = saved_code
                    else:
                        referral_code = input("[REFERRAL] Enter new referral code (EUCL######) or skip: ").strip()
                else:
                    referral_code = input("[REFERRAL] Enter referral code (EUCL######) or skip: ").strip()
        else:
            referral_code = input("[REFERRAL] Enter referral code (EUCL######) or skip: ").strip()
    except Exception:
        referral_code = input("[REFERRAL] Enter referral code (EUCL######) or skip: ").strip()
    
    # Validate and apply referral code
    if referral_code and re.match(r'^EUCL\d{6}$', referral_code):
        # Save referral code
        referral_data = {
            'referral_code': referral_code,
            'activated_at': datetime.now().isoformat(),
            'domain': '.euclidswap.io'
        }
        
        try:
            with open(referral_config_file, 'w') as f:
                json.dump(referral_data, f, indent=2)
        except Exception as e:
            print(f"{Fore.RED}[WARNING]{Style.RESET_ALL} Could not save referral config: " + str(e))
        
        print(f"{Fore.GREEN}[OK]{Style.RESET_ALL} Referral " + referral_code + " activated! Points will be credited to referrer.")
        return referral_code
    elif referral_code:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Invalid referral code format. Should be EUCL followed by 6 digits (e.g., EUCL544822)")
        return None
    else:
        print(f"{Fore.BLUE}[INFO]{Style.RESET_ALL} No referral code entered. Continuing without referral...")
        return None

class EuclidBot:
    """Main Euclid Swap Bot class with Intelligent Adaptive Amount System"""
    
    def __init__(self):
        """Initialize the bot with adaptive amount capabilities"""
        self.config = None
        self.tokens = None
        self.wallet = None
        self.swap_executor = None
        self.points_tracker = None
        self.session_manager = None
        self.referral_code = None
        
        # Adaptive Amount System
        self.adaptive_config_manager = None
        self.adaptive_config = None
        self.adaptive_swap_executor = None
        
        # STT Real-time Balance Connector
        self.stt_connector = None
        
        # Bot state
        self.running = False
        self.swap_count = 0
        self.last_swap_time = None
        
        # Dual-Module Auto-Switch System (Clean Architecture)
        self.swap_orchestrator = None  # Will be initialized after wallet/executor setup
        
        # Bi-directional swap state management
        self.swap_state = {
            "current_direction": "plume_to_stt",
            "last_swap_direction": None,
            "consecutive_fails": {
                "plume_to_stt": 0,
                "stt_to_plume": 0
            },
            "balances": {
                "plume": 0,
                "stt": 0
            },
            "total_swaps": {
                "plume_to_stt": 0,
                "stt_to_plume": 0
            }
        }
        
        # Balance thresholds for bi-directional operation
        self.thresholds = {
            "plume": {
                "minimum_swap": 1.0,  # 1 PLUME minimum for swap
                "gas_reserve": 0.1,   # Reserve for gas fees
                "effective_minimum": 1.1  # minimum + gas reserve
            },
            "stt": {
                "minimum_swap": 0.213,  # Approximately 1 PLUME worth
                "buffer": 1.1  # 10% buffer for slippage
            }
        }
        
    def initialize(self):
        """Initialize bot components silently"""
        try:
            # Load configuration
            self.config = load_config()
            self.tokens = load_tokens()
            
            # Load environment variables
            env_vars = load_env_file()
            
            # Get private key
            private_key = env_vars.get('PRIVATE_KEY') or os.getenv('PRIVATE_KEY')
            if not private_key:
                print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} No private key found in .env file or environment")
                return False
            
            if not validate_private_key(private_key):
                print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Invalid private key format")
                return False
            
            # Initialize wallet without emoji logs
            self.wallet = WalletManager(private_key, self.config["rpc_url"])
            
            # Load session silently if cookies exist in .env
            self.session_manager = SessionManager(self.config)
            
            # Try to load cookies from .env first
            cookies = {}
            if self.session_manager.load_session_from_env():
                cookies = self.session_manager.get_session_cookies()
            
            # Do not prompt for cookies here; proceed with whatever was loaded
            
            # Initialize components silently
            self.points_tracker = PointsTracker(self.config, cookies)
            self.swap_executor = SwapExecutor(self.wallet, self.config)
            
            # Silently load saved referral and apply
            try:
                if os.path.exists('referral_config.json'):
                    with open('referral_config.json', 'r') as f:
                        ref = json.load(f)
                        code = ref.get('referral_code')
                        if code:
                            self.referral_code = code
                self.apply_referral_to_sessions()
            except Exception:
                pass
            
            return True
        except Exception as e:
            print(f"[ERROR] Initialization failed: {e}")
            return False

    def _setup_adaptive_configuration(self) -> Optional[AdaptiveConfiguration]:
        """Setup adaptive amount configuration through user interaction"""
        try:
            # Check for saved configuration first
            if self.adaptive_config_manager.prompt_use_saved_configuration():
                saved_config = self.adaptive_config_manager.load_saved_configuration()
                if saved_config:
                    print(f"{Fore.GREEN}[ADAPTIVE]{Style.RESET_ALL} Using saved configuration")
                    return saved_config
            
            # Get configuration from user
            adaptive_config, should_continue = self.adaptive_config_manager.prompt_user_for_configuration()
            
            if not should_continue:
                print(f"{Fore.YELLOW}[ADAPTIVE]{Style.RESET_ALL} Configuration cancelled")
                return None
            
            return adaptive_config
            
        except Exception as e:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Adaptive configuration failed: {e}")
            return None
    
    # Complex auto-switch logic REMOVED - replaced by clean Orchestrator architecture
    # See modules/swap_orchestrator.py for intelligent switching logic
    
    # Helper methods REMOVED - orchestrator provides all direction logic

    def display_adaptive_dashboard(self):
        """Display comprehensive adaptive statistics dashboard"""
        if not self.adaptive_swap_executor:
            return
        
        try:
            stats = self.adaptive_swap_executor.get_adaptive_status()
            recommendations = self.adaptive_swap_executor.get_adaptive_recommendations()
            
            # Print main dashboard
            AdaptiveUI.print_adaptive_statistics_dashboard(stats)
            
            # Print orchestrator statistics  
            print(f"\n{Fore.CYAN}[ORCHESTRATOR] Statistics:{Style.RESET_ALL}")
            if self.swap_orchestrator:
                comprehensive_stats = self.swap_orchestrator.get_comprehensive_status()
                orch_stats = comprehensive_stats.get("orchestrator", {})
                module_stats = comprehensive_stats.get("all_modules", {})
                
                current_direction = orch_stats.get('current_direction', 'UNKNOWN').replace('_TO_', ' → ')
                print(f"├─ Current Direction: {current_direction}")
                print(f"├─ Direction Switches: {orch_stats.get('total_switches', 0)}")
                print(f"├─ PLUME → STT Swaps: {module_stats.get('plume_to_stt', {}).get('successful_swaps', 0)}")
                print(f"└─ STT → PLUME Swaps: {module_stats.get('stt_to_plume', {}).get('successful_swaps', 0)}")
            else:
                print("├─ Orchestrator not initialized")
            
            # Print phase history if available
            phase_history = stats.get('phase_history', [])
            if phase_history:
                AdaptiveUI.print_phase_history(phase_history)
            
            # Print recommendations
            AdaptiveUI.print_recommendations(recommendations)
            
            # Print configuration summary
            AdaptiveUI.print_configuration_summary(stats)
            
        except Exception as e:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to display adaptive dashboard: {e}")

    def apply_referral_to_sessions(self):
        """Apply referral code to all sessions"""
        if not self.referral_code:
            return
        
        try:
            # Apply to swap executor session
            if hasattr(self.swap_executor, 'session'):
                self.swap_executor.session.cookies.set(
                    'euclid_referral_code', 
                    self.referral_code,
                    domain='.euclidswap.io'
                )
                self.swap_executor.session.headers['Referer'] = 'https://testnet.euclidswap.io/swap?ref=' + self.referral_code
                pass  # Suppress verbose referral messages
            
            # Apply to points tracker sessions
            if hasattr(self.points_tracker, 'frontend_session'):
                self.points_tracker.frontend_session.cookies.set(
                    'euclid_referral_code', 
                    self.referral_code,
                    domain='.euclidswap.io'
                )
                self.points_tracker.frontend_session.headers['Referer'] = 'https://testnet.euclidswap.io/swap?ref=' + self.referral_code
                pass  # Suppress verbose referral messages
            
            if hasattr(self.points_tracker, 'backend_session'):
                self.points_tracker.backend_session.cookies.set(
                    'euclid_referral_code', 
                    self.referral_code,
                    domain='.euclidswap.io'
                )
                self.points_tracker.backend_session.headers['Referer'] = 'https://testnet.euclidswap.io/swap?ref=' + self.referral_code
                pass  # Suppress verbose referral messages
                
        except Exception as e:
            print(f"{Fore.RED}[WARNING]{Style.RESET_ALL} Could not apply referral to all sessions: " + str(e))

            
    def get_real_time_stt_balance(self) -> float:
        """Get real-time STT balance dari Somnia chain"""
        try:
            if self.stt_connector and self.stt_connector.connected:
                result = self.stt_connector.get_stt_balance(self.wallet.address)
                
                if result["success"]:
                    balance = result["balance"]["formatted"]
                    return balance
                else:
                    print(f"⚠️  STT query failed: {result.get('error')}")
            
            # Fallback ke tracker estimation
            try:
                estimated = self.points_tracker.get_stt_balance(self.wallet.address)
                return estimated
            except:
                return 0.0
            
        except Exception as e:
            print(f"❌ STT balance query failed: {e}")
            return 0.0

    def run_continuous_loop(self):
        """Run continuous swap loop using clean Dual-Module Architecture"""
        if not self.swap_orchestrator:
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Orchestrator not initialized!")
            return
        
        swap_count = 0
        
        # Clean header and configuration - following exact specifications
        ui.display_header()
        
        # Get configuration data for display
        mode = 'Adaptive' if self.adaptive_config and self.adaptive_config.mode == AdaptiveMode.ADAPTIVE else 'Fixed'
        amount = str(self.adaptive_config.current_amount) if self.adaptive_config else '1.0'
        
        # Build amount range display
        amount_range = None
        if self.adaptive_config and self.adaptive_config.mode == AdaptiveMode.ADAPTIVE:
            amount_range = f"{self.adaptive_config.min_floor}-{self.adaptive_config.max_ceiling}"
        
        # Display compact configuration
        ui.display_config(
            wallet_address=self.wallet.address,
            mode=mode,
            amount=amount,
            amount_range=amount_range,
            referral=self.referral_code
        )
        
        # Display initial balances
        plume_balance = float(self.wallet.get_balance())
        stt_balance = self.get_real_time_stt_balance()
        
        # Get points if available
        points = 0
        try:
            stats = self.points_tracker.get_statistics(self.wallet.address)
            points = stats.get('total_points', 0)
        except:
            pass
            
        # Initialize balance tracking with SAFE values
        # Set initial values to 0 to avoid huge changes on first display
        ui.last_plume_balance = 0  # Will calculate change from 0 initially
        ui.last_stt_balance = 0    # Will calculate change from 0 initially  
        ui.last_points = points
        
        # Display initial balances without changes
        print(Colors.colorize_brackets(f"[PLUME-REAL] PLUME: {plume_balance:.4f} Real-time!"))
        print(Colors.colorize_brackets(f"[STT-REAL] STT: {stt_balance:.6f} Real-time!"))
        ui.display_points_with_change(points)
        
        # NOW set the baseline values for future change calculations
        ui.last_plume_balance = plume_balance
        ui.last_stt_balance = stt_balance
        
        self.running = True
        
        # Main loop - user's preferred format with complete information
        while self.running:
            try:
                swap_count += 1
                
                # Get current direction for clear display
                current_direction = self.swap_orchestrator.get_current_direction().replace('_TO_', ' → ')
                
                # Show processing with direction - user's format: [SWAP #742] PLUME → STT
                ui.display_swap_processing(swap_count, current_direction)
                
                # Execute swap
                start_time = time.time()
                swap_result = self.swap_orchestrator.execute_swap()
                execution_time = time.time() - start_time
                
                # Handle results - user's preferred complete format
                if swap_result.get("success", False):
                    tx_hash = swap_result.get("transaction_hash")
                    
                    # Ensure TX hash is available
                    if not tx_hash:
                        tx_hash = "TX_HASH_NOT_AVAILABLE"
                    
                    # Determine explorer URL
                    swap_direction = swap_result.get("swap_direction", "")
                    if "STT_TO_PLUME" in swap_direction:
                        explorer_url = f"https://shannon-explorer.somnia.network/tx/{tx_hash}"
                    else:
                        explorer_url = f"https://testnet-explorer.plume.org/tx/{tx_hash}"
                    
                    # Display success with full TX info - user's format
                    ui.display_swap_success(execution_time, tx_hash, explorer_url)
                    
                    # Get updated balances
                    plume_balance = float(self.wallet.get_balance())
                    stt_balance = self.get_real_time_stt_balance()
                    
                    # Get points
                    total_points = 0
                    try:
                        stats = self.points_tracker.get_statistics(self.wallet.address)
                        total_points = stats.get('total_points', 0)
                    except:
                        pass
                    
                    # Display balance with changes - user's format
                    ui.display_balance_with_changes(plume_balance, stt_balance)
                    
                    # Display points with change - user's format
                    ui.display_points_with_change(total_points)
                    
                    # Get orchestrator stats
                    orch_stats = swap_result.get("orchestrator_stats", {})
                    total_swaps = orch_stats.get("successful_swaps", 0) + orch_stats.get("failed_swaps", 0)
                    success_rate = orch_stats.get("success_rate", 0)
                    
                    # Display stats - user's format
                    ui.display_stats_line(total_swaps, success_rate)
                    
                    # Wait with message - user's format
                    next_delay = random.randint(3, 6)
                    ui.display_wait_message(next_delay)
                    
                    # Display separator between swaps
                    ui.display_swap_separator()
                    
                    time.sleep(next_delay)
                    
                else:
                    # Handle failure - user's format
                    error_type = swap_result.get("error_type", "UNKNOWN")
                    error_message = swap_result.get("error_message", "Unknown error")
                    
                    # Clean error message based on type - user's preferred format
                    if error_type == "INSUFFICIENT_BALANCE":
                        clean_error = "Insufficient balance"
                    elif error_type == "INSUFFICIENT_STT_BALANCE":
                        clean_error = "Insufficient STT balance"
                    elif error_type == "NO_ROUTE_FOUND":
                        clean_error = "No route found"
                    elif error_type == "SWAP_EXECUTION_FAILED":
                        clean_error = "Swap execution failed"
                    else:
                        # For other errors, truncate if too long
                        clean_error = error_message[:50] + "..." if len(error_message) > 50 else error_message
                    
                    ui.display_swap_failed(clean_error)
                    
                    # Get updated balances
                    plume_balance = float(self.wallet.get_balance())
                    stt_balance = self.get_real_time_stt_balance()
                    
                    # Get points
                    total_points = 0
                    try:
                        stats = self.points_tracker.get_statistics(self.wallet.address)
                        total_points = stats.get('total_points', 0)
                    except:
                        pass
                    
                    # Display balance with changes - user's format
                    ui.display_balance_with_changes(plume_balance, stt_balance)
                    
                    # Display points with change - user's format
                    ui.display_points_with_change(total_points)
                    
                    # Get orchestrator stats for retry delay
                    orch_stats = swap_result.get("orchestrator_stats", {})
                    total_swaps = orch_stats.get("successful_swaps", 0) + orch_stats.get("failed_swaps", 0)
                    success_rate = orch_stats.get("success_rate", 0)
                    consecutive_failures = orch_stats.get("consecutive_failures", 0)
                    
                    # Display stats - user's format
                    ui.display_stats_line(total_swaps, success_rate)
                    
                    # Wait with message - user's format
                    retry_delay = 3 + (consecutive_failures * 2)
                    ui.display_wait_message(retry_delay)
                    
                    # Display separator between swaps
                    ui.display_swap_separator()
                    
                    time.sleep(retry_delay)
                
            except KeyboardInterrupt:
                # Clean session summary - exactly as specified
                comprehensive_stats = self.swap_orchestrator.get_comprehensive_status()
                orch_stats = comprehensive_stats.get("orchestrator", {})
                
                # Get final balances
                final_plume = float(self.wallet.get_balance())
                final_stt = self.get_real_time_stt_balance()
                
                # Get final points
                points_earned = 0
                try:
                    stats = self.points_tracker.get_statistics(self.wallet.address)
                    points_earned = stats.get('total_points', 0)
                except:
                    pass
                
                # Calculate session duration
                session_duration = time.time() - ui.start_time
                
                # Display clean session summary - exactly as specified
                ui.display_session_summary(
                    total_swaps=orch_stats.get('total_swaps_executed', 0),
                    successful=orch_stats.get('successful_swaps', 0),
                    duration_seconds=session_duration,
                    final_plume=final_plume,
                    final_stt=final_stt,
                    points_earned=points_earned
                )
                
                # Clean exit
                self.running = False
                break
                
            except Exception as e:
                # Simple error handling - let orchestrator manage complexity
                print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Unexpected error: {str(e)[:100]}")
                
                # Get current statistics from orchestrator
                orch_stats = self.swap_orchestrator.get_orchestrator_stats()
                print(f"{Fore.BLUE}[STATUS]{Style.RESET_ALL} Success: {orch_stats.get('successful_swaps', 0)} | Failed: {orch_stats.get('failed_swaps', 0)}")
                
                print(f"{Fore.BLUE}[WAIT]{Style.RESET_ALL} Retrying in 5 seconds...")
                time.sleep(5)
            
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}Bot shutdown complete{Style.RESET_ALL}")
        
    def run(self):
        """Main bot entry point with detailed initialization"""
        # Clean initialization - remove all verbose messages  
        if not self.initialize():
            print(Colors.colorize_brackets("[ERROR] Failed to initialize bot"))
            return
        
        # Run interactive menu
        self.run_menu()

    def run_menu(self):
        """Interactive menu for selecting swap routes in the specified order."""
        try:
            print("\n" + "=" * 58)
            print(" EUCLID PROTOCOL BOT v2.0")
            print(" Cross-Chain Swap Automation")
            print("=" * 58)
            print(f"Connected: {self.wallet.get_address()[:6]}...{self.wallet.get_address()[-4:]} | Network: Multi-Chain\n")

            print("SELECT YOUR SWAP:")
            print("-" * 58)
            print("  1) PLUME → STT   (Same Network - Fast)")
            print("  2) STT → PLUME   (Same Network - Fast)")
            print("  3) PHRS → ETH    (Cross-Chain: Pharos → Unichain)")
            print("  4) ETH → PHRS    (Cross-Chain: Unichain → Pharos)")
            print("  5) Exit")

            choice = input("\nEnter choice [1-5]: ").strip()

            if choice == "1":
                # PLUME → STT
                # Live source balance
                plume_bal = self._get_native_balance("plume")
                print(Colors.colorize_brackets(f"[BALANCE] Source PLUME: {plume_bal:.6f}"))
                default_amt = 0.1
                amt_str = input(f"Amount PLUME (default {default_amt}): ").strip()
                amount = float(amt_str) if amt_str else default_amt
                amount_wei = int(amount * 10**18)
                # Route preview
                preview = self._preview_route("plume", "stt", amount_wei)
                if preview:
                    route_str, out_float = preview
                    print(Colors.colorize_brackets(f"[STATS] Route: {route_str} | Expect: {out_float:.6f} STT"))
                    proceed = input("Proceed? (y/N): ").strip().lower()
                    if proceed != 'y':
                        print("Cancelled.")
                        return
                # Contextual adaptive config
                cfg = self._configure_amount_context("PLUME", amount)
                mode, count = self._select_execution_mode()
                self._execute_swaps_generic("plume", "stt", False, cfg.current_amount, mode, count)

            elif choice == "2":
                # STT → PLUME
                stt_bal = self._get_native_balance("stt")
                print(Colors.colorize_brackets(f"[BALANCE] Source STT: {stt_bal:.6f}"))
                default_amt = 0.01
                amt_str = input(f"Amount STT (default {default_amt}): ").strip()
                amount = float(amt_str) if amt_str else default_amt
                amount_wei = int(amount * 10**18)
                preview = self._preview_route("stt", "plume", amount_wei)
                if preview:
                    route_str, out_float = preview
                    print(Colors.colorize_brackets(f"[STATS] Route: {route_str} | Expect: {out_float:.6f} PLUME"))
                    proceed = input("Proceed? (y/N): ").strip().lower()
                    if proceed != 'y':
                        print("Cancelled.")
                        return
                cfg = self._configure_amount_context("STT", amount)
                mode, count = self._select_execution_mode()
                self._execute_swaps_generic("stt", "plume", False, cfg.current_amount, mode, count)

            elif choice == "3":
                # PHRS → ETH
                phrs_bal = self._get_native_balance("phrs")
                print(Colors.colorize_brackets(f"[BALANCE] Source PHRS: {phrs_bal:.6f}"))
                default_amt = 0.1
                amt_str = input(f"Amount PHRS (default {default_amt}): ").strip()
                amount = float(amt_str) if amt_str else default_amt
                amount_wei = int(amount * 10**18)
                preview = self._preview_route("phrs", "eth", amount_wei)
                if preview:
                    route_str, out_float = preview
                    print(Colors.colorize_brackets(f"[STATS] Route: {route_str} | Expect: {out_float:.6f} ETH"))
                    proceed = input("Proceed? (y/N): ").strip().lower()
                    if proceed != 'y':
                        print("Cancelled.")
                        return
                cfg = self._configure_amount_context("PHRS", amount)
                mode, count = self._select_execution_mode()
                self._execute_swaps_generic("phrs", "eth", True, cfg.current_amount, mode, count)

            elif choice == "4":
                # ETH → PHRS
                eth_bal = self._get_native_balance("eth")
                print(Colors.colorize_brackets(f"[BALANCE] Source ETH: {eth_bal:.6f}"))
                default_amt = 0.01
                amt_str = input(f"Amount ETH (default {default_amt}): ").strip()
                amount = float(amt_str) if amt_str else default_amt
                amount_wei = int(amount * 10**18)
                preview = self._preview_route("eth", "phrs", amount_wei)
                if preview:
                    route_str, out_float = preview
                    print(Colors.colorize_brackets(f"[STATS] Route: {route_str} | Expect: {out_float:.6f} PHRS"))
                    proceed = input("Proceed? (y/N): ").strip().lower()
                    if proceed != 'y':
                        print("Cancelled.")
                        return
                cfg = self._configure_amount_context("ETH", amount)
                mode, count = self._select_execution_mode()
                self._execute_swaps_generic("eth", "phrs", True, cfg.current_amount, mode, count)

            else:
                print("Goodbye.")
                return

        except Exception as e:
            print(Colors.colorize_brackets(f"[ERROR] {str(e)[:120]}"))

    def _get_native_balance(self, token: str) -> float:
        """Switch to the token's network and get native balance."""
        try:
            self.wallet.switch_network(token)
            bal = float(self.wallet.get_balance())
            return bal
        except Exception:
            return 0.0

    def _preview_route(self, token_in: str, token_out: str, amount_wei: int):
        """Fetch route and expected output for preview."""
        try:
            data = self.swap_executor.calculate_swap_route(token_in, token_out, amount_wei)
            if not data or not data.get("paths"):
                return None
            path = data["paths"][0]["path"][0]
            route_tokens = path.get("route", [])
            amount_out = path.get("amount_out", "0")
            out_float = int(amount_out) / 1e18
            route_str = " → ".join(route_tokens)
            return route_str, out_float
        except Exception:
            return None

    def _configure_amount_context(self, token_label: str, default_amount: float):
        """Prompt adaptive configuration in context of selected token, token-agnostic storage."""
        try:
            from src.adaptive_config import AdaptiveConfigManager
            mgr = AdaptiveConfigManager()
            print(f"\nConfigure adaptive settings for {token_label} swaps")
            use_saved = mgr.prompt_use_saved_configuration()
            if use_saved:
                cfg = mgr.load_saved_configuration()
                if cfg:
                    return cfg
            # Quick choice: fixed/adaptive
            mode_choice = input("Mode: 1) Fixed  2) Adaptive [default 2]: ").strip()
            if mode_choice == '1' and default_amount >= 0.1:
                from src.adaptive_amount_manager import AdaptiveConfiguration
                return AdaptiveConfiguration(initial_amount=default_amount)
            # Advanced adaptive prompt
            cfg, ok = mgr.prompt_user_for_configuration(token_label)
            if ok and cfg:
                return cfg
        except Exception:
            pass
        # Fallback fixed
        from src.adaptive_amount_manager import AdaptiveConfiguration
        return AdaptiveConfiguration(initial_amount=default_amount)

    def _select_execution_mode(self):
        """Ask for execution mode and optional count."""
        print("\nExecution mode:")
        print("  1) Single swap")
        print("  2) Multiple swaps")
        print("  3) Continuous mode")
        choice = input("Choose [1-3] (default 1): ").strip()
        if choice == '2':
            try:
                cnt = int(input("Number of swaps: ").strip())
                return 2, max(1, cnt)
            except Exception:
                return 2, 3
        elif choice == '3':
            return 3, 0
        return 1, 1

    def _execute_swaps_generic(self, token_in: str, token_out: str, cross_chain: bool, amount_tokens: float, mode: int, count: int):
        """Execute swaps per selected mode using appropriate executor."""
        try:
            def do_one(a_tokens: float):
                a_wei = int(a_tokens * 10**18)
                if cross_chain:
                    return self.swap_executor.execute_cross_chain_swap(token_in, token_out, a_wei)
                else:
                    return self.swap_executor.execute_swap(token_in=token_in, token_out=token_out, amount=str(a_wei))

            if mode == 1:
                ui.display_swap_processing(1, f"{token_in.upper()} → {token_out.upper()}")
                start_t = time.time()
                tx = do_one(amount_tokens)
                if tx:
                    confirm_t = time.time() - start_t
                    explorer = self._explorer_url_for_tx(tx, token_in)
                    ui.display_swap_success(confirm_t, tx, explorer)
                else:
                    ui.display_swap_failed("Swap failed")
                ui.display_swap_separator()
                return

            if mode == 2:
                ok = 0
                ui.display_mode_banner(continuous=False, session_total=0, grand_total=0)
                for i in range(count):
                    ui.display_swap_processing(i+1, f"{token_in.upper()} → {token_out.upper()}")
                    start_t = time.time()
                    tx = do_one(amount_tokens)
                    if tx:
                        ok += 1
                        confirm_t = time.time() - start_t
                        explorer = self._explorer_url_for_tx(tx, token_in)
                        ui.display_swap_success(confirm_t, tx, explorer)
                        ui.display_stats_line(ok + (count - (i+1)), (ok / (i+1)) * 100)
                    else:
                        ui.display_swap_failed(f"Swap #{i+1} failed")
                    ui.display_swap_separator()
                print(Colors.colorize_brackets(f"[STATS] Completed: {ok}/{count}"))
                return

            # Continuous mode
            i = 0
            ui.display_mode_banner(continuous=True, session_total=0, grand_total=0)
            n = 0
            while True:
                i += 1
                n += 1
                ui.display_swap_processing(i, f"{token_in.upper()} → {token_out.upper()}")
                start_t = time.time()
                tx = do_one(amount_tokens)
                if tx:
                    confirm_t = time.time() - start_t
                    explorer = self._explorer_url_for_tx(tx, token_in)
                    ui.display_swap_success(confirm_t, tx, explorer)
                else:
                    ui.display_swap_failed(f"Swap #{i} failed")
                ui.display_swap_separator()
                cont = input("Continue? (Y/n): ").strip().lower()
                if cont == 'n':
                    break
        except KeyboardInterrupt:
            print("Stopped.")
        except Exception as e:
            print(Colors.colorize_brackets(f"[ERROR] {str(e)[:120]}"))

    def _explorer_url_for_tx(self, tx_hash: str, token_in: str) -> str:
        """Choose explorer based on source chain token."""
        t = (token_in or '').lower()
        if t in ['plume', 'native']:
            return f"https://testnet-explorer.plume.org/tx/{tx_hash}"
        if t in ['stt', 'somnia']:
            return f"https://shannon-explorer.somnia.network/tx/{tx_hash}"
        if t in ['phrs', 'pharos']:
            return f"https://explorer.pharos.network/tx/{tx_hash}"
        if t in ['eth', 'unichain']:
            return f"https://testnet.uniscan.xyz/tx/{tx_hash}"
        return tx_hash
    
    def run_original_mode(self):
        """Original bot execution mode with full UI"""
        print_banner()
        self.display_startup_info()
        
        self.running = True
        self.logger.info("[START] Starting main execution loop...")
        
        try:
            while self.running:
                # Check session validity
                if not self.session_manager.refresh_session_if_needed():
                    self.logger.warning("[WARN] Session refresh failed - continuing anyway")
                
                # Execute swap cycle
                success = self.execute_swap_cycle()
                
                if success:
                    self.swap_count += 1
                    self.last_swap_time = datetime.now()
                
                # Display status
                self.display_status()
                
                # Calculate next swap time
                next_swap_time = calculate_next_swap_time(
                    self.config["swap_interval_minutes"],
                    self.config.get("randomization", {})
                )
                
                # Wait until next swap
                wait_seconds = int((next_swap_time - datetime.now()).total_seconds())
                if wait_seconds > 0:
                    wait_with_countdown(wait_seconds, "Next swap")
                
        except KeyboardInterrupt:
            self.logger.info("[STOP] Bot stopped by user")
        except Exception as e:
            self.logger.error(f"[ERROR] Fatal error: {e}")
            self.logger.error(traceback.format_exc())
        finally:
            self.shutdown()
    
    def execute_swap_cycle(self):
        """Execute a complete swap and points tracking cycle"""
        try:
            # Get token pair
            token_pairs = self.config["token_pairs"]
            if not token_pairs:
                self.logger.error("[ERROR] No token pairs configured")
                return False
            
            token_pair = token_pairs[0]  # Use first pair for now
            
            # Calculate swap amount
            swap_amount = self.swap_executor.calculate_optimal_amount(token_pair)
            
            self.logger.info(f"[SWAP] Starting swap cycle #{self.swap_count + 1}")
            
            # Record start time
            swap_start = time.time()
            
            # Execute swap
            tx_hash = self.swap_executor.execute_swap(token_pair, swap_amount)
            
            if not tx_hash:
                self.logger.error("[ERROR] Swap execution failed")
                self.performance.record_error()
                return False
            
            # Validate transaction hash
            from src.utils import validate_transaction_hash
            if not validate_transaction_hash(tx_hash):
                self.logger.error(f"[ERROR] Invalid transaction hash received: {tx_hash}")
                self.logger.error("[ERROR] This indicates the transaction was not executed on blockchain")
                self.performance.record_error()
                return False
            
            # Record swap time
            swap_duration = time.time() - swap_start
            self.performance.record_swap_time(swap_duration)

            self.logger.info(f"[SUCCESS] Real swap completed in {swap_duration:.1f}s")
            self.logger.info(f"[SUCCESS] Transaction hash: {tx_hash}")
            
            # Points registration is now handled within swap execution
            # Get updated statistics from wallet manager
            stats = self.wallet.get_total_points()
            
            self.logger.info(f"[STATS] Total Points: {stats['total_points']} | Success Rate: {stats['success_rate']:.1f}%")

            return True
            
        except Exception as e:
            self.logger.error(f"[ERROR] Swap cycle failed: {e}")
            self.performance.record_error()
            return False
    
    def display_startup_info(self):
        """Display startup information"""
        print(f"\n{Fore.CYAN}[START] BOT STARTUP INFO{Style.RESET_ALL}")
        print(f"{Fore.BLUE}{'='*50}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}📅 Started: {format_timestamp()}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}💳 Wallet: {self.wallet.get_address()}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}🔗 Chain: {self.config['chain'].upper()}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[SWAP] Interval: {self.config['swap_interval_minutes']} minutes{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[AMOUNT] Amount: {self.config['swap_amount']} wei{Style.RESET_ALL}")
        
        # Display token pairs
        for i, pair in enumerate(self.config["token_pairs"]):
            print(f"{Fore.YELLOW}🔀 Pair {i+1}: {pair['symbol_a']} ↔ {pair['symbol_b']}{Style.RESET_ALL}")
        
        print(f"{Fore.BLUE}{'='*50}{Style.RESET_ALL}")
        
        # Initial status check
        wallet_status = self.wallet.get_status()
        print_wallet_status(wallet_status)
        
        session_info = self.session_manager.get_session_info()
        print_session_status(session_info)
        
        input(f"\n{Fore.CYAN}Press Enter to start bot...{Style.RESET_ALL}")
    
    def display_status(self):
        """Display current bot status"""
        print_status_header()
        
        # Performance stats
        stats = self.performance.get_stats()
        print(f"\n{Fore.YELLOW}[DATA] PERFORMANCE{Style.RESET_ALL}")
        print(f"   Uptime: {Fore.GREEN}{stats['uptime_formatted']}{Style.RESET_ALL}")
        print(f"   Swaps: {Fore.GREEN}{stats['total_swaps']}{Style.RESET_ALL}")
        print(f"   Errors: {Fore.RED}{stats['total_errors']}{Style.RESET_ALL}")
        print(f"   Success Rate: {Fore.GREEN}{100 - stats['error_rate']:.1f}%{Style.RESET_ALL}")
        
        # Wallet status
        wallet_status = self.wallet.get_status()
        print_wallet_status(wallet_status)
        
        # Points status from wallet manager (Intract integration)
        points_stats = self.wallet.get_total_points()
        print(f"\n{Fore.YELLOW}[TRACK] POINTS STATUS{Style.RESET_ALL}")
        print(f"   Total Points: {Fore.GREEN}{points_stats['total_points']}{Style.RESET_ALL}")
        print(f"   Successful: {Fore.GREEN}{points_stats['successful_swaps']}{Style.RESET_ALL}")
        print(f"   Total Tracked: {Fore.BLUE}{points_stats['total_swaps']}{Style.RESET_ALL}")
        print(f"   Success Rate: {Fore.GREEN}{points_stats['success_rate']:.1f}%{Style.RESET_ALL}")
        
        # Session status
        session_info = self.session_manager.get_session_info()
        print_session_status(session_info)
        
        # Last swap info
        if self.last_swap_time:
            time_since = (datetime.now() - self.last_swap_time).total_seconds()
            print(f"\n{Fore.YELLOW}🕐 TIMING{Style.RESET_ALL}")
            print(f"   Last Swap: {Fore.BLUE}{int(time_since//60)}m {int(time_since%60)}s ago{Style.RESET_ALL}")
        
        print(f"{Fore.BLUE}{'='*70}{Style.RESET_ALL}")
    
    def shutdown(self):
        """Clean shutdown of the bot"""
        self.running = False
        
        self.logger.info("[STOP] Shutting down bot...")
        
        # Display final statistics
        points_status = self.points_tracker.get_status()
        print_final_stats(self.performance, points_status)
        
        # Cleanup
        if self.session_manager:
            # Optionally save session for next run
            pass
        
        self.logger.info("👋 Bot shutdown complete")
        print(f"\n{Fore.CYAN}👋 Thank you for using Euclid Swap Bot!{Style.RESET_ALL}")

def main():
    """Main entry point"""
    try:
        bot = EuclidBot()
        bot.run()
    except Exception as e:
        print(f"{Fore.RED}[ERROR] Fatal error: {e}{Style.RESET_ALL}")
        print(f"{Fore.RED}Stack trace: {traceback.format_exc()}{Style.RESET_ALL}")
        sys.exit(1)

if __name__ == "__main__":
    main()
