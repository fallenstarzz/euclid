"""
Clean, Minimal, and Professional UI for Euclid Bot
Implements exact specifications for clean, business-like interface
"""

import sys
import time
import re
from datetime import datetime

class Colors:
    """Professional color palette - applied ONLY to bracketed text"""
    
    # Professional muted colors
    GREEN = '\033[92m'    # Success
    RED = '\033[91m'      # Error
    CYAN = '\033[96m'     # Swap numbers
    YELLOW = '\033[93m'   # Status
    BLUE = '\033[94m'     # Info headers
    RESET = '\033[0m'
    
    @staticmethod
    def colorize_brackets(text):
        """Apply color only to bracketed text based on keywords"""
        
        # Color mapping for different bracket contents
        color_map = {
            'SUCCESS': Colors.GREEN,
            'ERROR': Colors.RED,
            'FAIL': Colors.RED,
            'SWAP': Colors.CYAN,
            'STATUS': Colors.YELLOW,
            'BALANCE': Colors.BLUE,
            'PLUME-REAL': Colors.BLUE,
            'STT-REAL': Colors.BLUE,
            'STATS': Colors.BLUE,
            'WALLET': Colors.BLUE,
            'MODE': Colors.BLUE,
            'REFERRAL': Colors.BLUE,
            'EXPLORER': Colors.BLUE,
            'POINTS': Colors.BLUE,
            'WAIT': Colors.YELLOW,
            'TX': Colors.CYAN,
        }
        
        def replace_bracket(match):
            bracket_content = match.group(1)
            for keyword, color in color_map.items():
                if keyword in bracket_content.upper():
                    return f"{color}[{bracket_content}]{Colors.RESET}"
            return match.group(0)  # No color if no keyword match
        
        return re.sub(r'\[([^\]]+)\]', replace_bracket, text)

class CleanUI:
    """Clean UI with Complete Information - User's Preferred Format"""
    
    def __init__(self):
        self.start_time = time.time()
        self.last_plume_balance = 0
        self.last_stt_balance = 0  
        self.last_points = 0
    
    def format_address(self, address):
        """Format address as 0xCAE3...AF0f"""
        if len(address) >= 10:
            return f"{address[:6]}...{address[-4:]}"
        return address
    
    def format_amount(self, amount, decimals=4):
        """Format amount with appropriate decimal places"""
        if isinstance(amount, str):
            amount = float(amount)
        return f"{amount:.{decimals}f}"
    
    def format_duration(self, seconds):
        """Format duration in human readable format"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.0f}m {seconds%60:.0f}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours:.0f}h {minutes:.0f}m"
    
    # === USER'S PREFERRED FORMAT FUNCTIONS ===
    
    def display_header(self):
        """Clean header"""
        print("EUCLID SWAP BOT v2.0 | Plume Testnet")
        print("=====================================")
    
    def display_config(self, wallet_address, mode, amount, amount_range, referral):
        """Compact configuration display"""
        formatted_addr = self.format_address(wallet_address)
        
        print(Colors.colorize_brackets(f"[WALLET] {formatted_addr}"))
        
        if amount_range:
            # Make token-agnostic as user requested
            print(Colors.colorize_brackets(f"[MODE] {mode}: {amount} tokens (Range: {amount_range})"))
        else:
            print(Colors.colorize_brackets(f"[MODE] {mode}: {amount} tokens"))
            
        if referral and referral != 'None':
            print(Colors.colorize_brackets(f"[REFERRAL] {referral}"))
        print()
    
    def display_swap_processing(self, swap_num, direction):
        """Show processing with direction - user's format: [SWAP #742] PLUME → STT"""
        print(Colors.colorize_brackets(f"[SWAP #{swap_num}] {direction} - Initiating swap..."))
    
    def display_swap_success(self, duration, tx_hash, explorer_url):
        """Show success - user's format with full TX hash and explorer"""
        print(Colors.colorize_brackets(f"[SUCCESS] Transaction confirmed in {duration:.2f}s"))
        print(Colors.colorize_brackets(f"[TX] Hash: {tx_hash}"))
        print(Colors.colorize_brackets(f"[TX] Explorer: {explorer_url}"))
    
    def display_swap_failed(self, error_msg):
        """Show failure - user's format"""
        print(Colors.colorize_brackets(f"[ERROR] {error_msg}"))
    
    def display_balance_with_changes(self, plume_balance, stt_balance):
        """Balance with changes - user's format with BOTH real-time"""
        # Calculate changes (only if we have previous values and they're reasonable)
        plume_change = 0
        stt_change = 0
        
        if self.last_plume_balance > 0 and abs(plume_balance - self.last_plume_balance) < 100:
            plume_change = plume_balance - self.last_plume_balance
            
        if self.last_stt_balance > 0 and abs(stt_balance - self.last_stt_balance) < 100:
            stt_change = stt_balance - self.last_stt_balance
        
        # Format changes
        plume_change_str = f" ({plume_change:+.4f})" if abs(plume_change) > 0.0001 else ""
        stt_change_str = f" ({stt_change:+.6f})" if abs(stt_change) > 0.000001 else ""
        
        # Both balances are now real-time
        print(Colors.colorize_brackets(f"[PLUME-REAL] PLUME: {plume_balance:.4f}{plume_change_str} Real-time!"))
        print(Colors.colorize_brackets(f"[STT-REAL] STT: {stt_balance:.6f}{stt_change_str} Real-time!"))
        
        # Update last values
        self.last_plume_balance = plume_balance
        self.last_stt_balance = stt_balance
    
    def display_points_with_change(self, total_points):
        """Points - user's format: [POINTS] Total: 0 (+0)"""
        points_change = total_points - self.last_points if self.last_points >= 0 else 0
        change_str = f" ({points_change:+})" if points_change != 0 else " (+0)"
        
        print(Colors.colorize_brackets(f"[POINTS] Total: {total_points}{change_str}"))
        
        # Update last value
        self.last_points = total_points
    
    def display_stats_line(self, total, success_rate):
        """Stats - user's format: [STATS] Swaps: 0 | Success Rate: 100.0%"""
        print(Colors.colorize_brackets(f"[STATS] Swaps: {total} | Success Rate: {success_rate:.1f}%"))
    
    def display_wait_message(self, seconds):
        """Wait - user's format: [WAIT] Next swap in 3 seconds..."""
        print(Colors.colorize_brackets(f"[WAIT] Next swap in {seconds} seconds..."))
    
    def display_swap_separator(self):
        """Display separator between swaps - user's preferred format"""
        print("----------------------------------------------------------------------")
    
    def display_session_summary(self, total_swaps, successful, duration_seconds, 
                              final_plume, final_stt, points_earned=0):
        """Session summary"""
        print("Session Summary")
        print("=" * 15)
        
        success_rate = (successful / total_swaps * 100) if total_swaps > 0 else 0
        duration = self.format_duration(duration_seconds)
        
        print(f"Total: {total_swaps} swaps ({successful} successful)")  
        print(f"Duration: {duration}")
        print(f"Final: PLUME: {final_plume:.4f} | STT: {final_stt:.6f}")
        
        if points_earned > 0:
            print(f"Points earned: {points_earned}")

# Global instance
ui = CleanUI()
