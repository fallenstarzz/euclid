"""
Enhanced UI System for Adaptive Amount Management
Provides comprehensive status displays and user feedback
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional
from colorama import Fore, Style
from .adaptive_amount_manager import AdaptiveMode, AdaptivePhase

class AdaptiveUI:
    """Enhanced UI for adaptive amount system"""
    
    @staticmethod
    def print_adaptive_banner():
        """Print adaptive system banner"""
        print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{' ' * 20}EUCLID SWAP BOT - INTELLIGENT ADAPTIVE SYSTEM{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{' ' * 35}Version 2.0{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
    
    @staticmethod
    def print_phase_status(phase: AdaptivePhase, current_amount: float, additional_info: str = ""):
        """Print current phase status with visual indicators"""
        phase_colors = {
            AdaptivePhase.ASCENDING: Fore.YELLOW,
            AdaptivePhase.STABLE: Fore.GREEN,
            AdaptivePhase.DESCENDING: Fore.BLUE,
            AdaptivePhase.FIXED: Fore.WHITE
        }
        
        phase_icons = {
            AdaptivePhase.ASCENDING: "📈",
            AdaptivePhase.STABLE: "⚖️",
            AdaptivePhase.DESCENDING: "📉",
            AdaptivePhase.FIXED: "🔒"
        }
        
        color = phase_colors.get(phase, Fore.WHITE)
        icon = phase_icons.get(phase, "❓")
        
        phase_name = phase.value.upper()
        status_line = f"{color}[{phase_name}]{Style.RESET_ALL} {icon} Amount: {current_amount:.3f} PLUME"
        
        if additional_info:
            status_line += f" | {additional_info}"
        
        print(status_line)
    
    @staticmethod
    def print_swap_attempt(attempt_num: int, amount: float, max_attempts: Optional[int] = None):
        """Print swap attempt information"""
        attempt_display = f"[ATTEMPT {attempt_num}"
        if max_attempts:
            attempt_display += f"/{max_attempts}"
        attempt_display += "]"
        
        print(f"{Fore.CYAN}{attempt_display}{Style.RESET_ALL} Trying {amount:.3f} PLUME...")
    
    @staticmethod
    def print_swap_result(success: bool, amount: float, execution_time: float, 
                         error_type: Optional[str] = None, tx_hash: Optional[str] = None):
        """Print swap result with appropriate formatting"""
        if success:
            print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} ✅ Swap completed in {execution_time:.2f}s with {amount:.3f} PLUME")
            if tx_hash:
                print(f"{Fore.BLUE}[TX]{Style.RESET_ALL} Hash: {tx_hash}")
        else:
            print(f"{Fore.RED}[FAILED]{Style.RESET_ALL} ❌ Swap failed after {execution_time:.2f}s")
            if error_type:
                print(f"{Fore.WHITE}[REASON]{Style.RESET_ALL} {error_type}")
    
    @staticmethod
    def print_amount_adjustment(old_amount: float, new_amount: float, reason: str = ""):
        """Print amount adjustment information"""
        direction = "↑" if new_amount > old_amount else "↓"
        change = abs(new_amount - old_amount)
        
        color = Fore.YELLOW if new_amount > old_amount else Fore.BLUE
        
        adjustment_line = f"{color}[ADJUSTMENT]{Style.RESET_ALL} {direction} {old_amount:.3f} → {new_amount:.3f} PLUME"
        adjustment_line += f" ({change:+.3f})"
        
        if reason:
            adjustment_line += f" | {reason}"
        
        print(adjustment_line)
    
    @staticmethod
    def print_phase_transition(from_phase: AdaptivePhase, to_phase: AdaptivePhase, 
                             amount: float, reason: str = ""):
        """Print phase transition information"""
        from_color = {
            AdaptivePhase.ASCENDING: Fore.YELLOW,
            AdaptivePhase.STABLE: Fore.GREEN,
            AdaptivePhase.DESCENDING: Fore.BLUE,
            AdaptivePhase.FIXED: Fore.WHITE
        }
        
        to_color = from_color
        
        from_name = from_phase.value.upper()
        to_name = to_phase.value.upper()
        
        transition_line = f"{Fore.MAGENTA}[TRANSITION]{Style.RESET_ALL} "
        transition_line += f"{from_color.get(from_phase, Fore.WHITE)}{from_name}{Style.RESET_ALL} → "
        transition_line += f"{to_color.get(to_phase, Fore.WHITE)}{to_name}{Style.RESET_ALL} "
        transition_line += f"at {amount:.3f} PLUME"
        
        if reason:
            transition_line += f" | {reason}"
        
        print(transition_line)
    
    @staticmethod
    def print_optimization_found(optimal_amount: float, initial_amount: float, 
                               total_savings: float, swaps_count: int):
        """Print optimization success message"""
        savings_per_swap = initial_amount - optimal_amount
        savings_percentage = (savings_per_swap / initial_amount) * 100
        
        print(f"\n{Fore.GREEN}{'🎉 ' * 20}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}[OPTIMIZATION COMPLETE]{Style.RESET_ALL} 🎯 Optimal amount found!")
        print(f"{Fore.GREEN}[OPTIMAL]{Style.RESET_ALL} Using {optimal_amount:.3f} PLUME (down from {initial_amount:.3f})")
        print(f"{Fore.GREEN}[SAVINGS]{Style.RESET_ALL} {savings_per_swap:.3f} PLUME per swap ({savings_percentage:.1f}% reduction)")
        print(f"{Fore.GREEN}[TOTAL SAVED]{Style.RESET_ALL} {total_savings:.3f} PLUME over {swaps_count} swaps")
        print(f"{Fore.GREEN}{'🎉 ' * 20}{Style.RESET_ALL}\n")
    
    @staticmethod
    def print_adaptive_statistics_dashboard(stats: Dict[str, Any]):
        """Print comprehensive adaptive statistics dashboard"""
        print(f"\n{Fore.CYAN}╔═══════════════════════════════════════════════════════════════════╗{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{' ' * 20}ADAPTIVE AMOUNT OPTIMIZATION DASHBOARD{' ' * 20}║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}╠═══════════════════════════════════════════════════════════════════╣{Style.RESET_ALL}")
        
        # Mode and Phase
        mode = stats.get('mode', 'unknown').upper()
        phase = stats.get('current_phase', 'unknown').upper()
        current_amount = stats.get('current_amount', 0)
        
        mode_color = Fore.GREEN if mode == 'ADAPTIVE' else Fore.WHITE
        print(f"{Fore.CYAN}║{Style.RESET_ALL} Mode:           {mode_color}{mode:<20}{Style.RESET_ALL}{Fore.CYAN}║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL} Current Phase:  {Fore.YELLOW}{phase:<20}{Style.RESET_ALL}{Fore.CYAN}║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL} Current Amount: {Fore.GREEN}{current_amount:<20.3f}{Style.RESET_ALL}{Fore.CYAN}║{Style.RESET_ALL}")
        
        # Optimal Amount (show savings only if above minimum)
        optimal_amount = stats.get('optimal_amount')
        current_amount = stats.get('current_amount', 1.0)
        initial_amount = stats.get('initial_amount', 1.0)
        
        if optimal_amount:
            # Show savings percentage only if current amount is above initial amount
            if current_amount > initial_amount:
                savings_pct = stats.get('savings_percentage', 0)
                print(f"{Fore.CYAN}║{Style.RESET_ALL} Optimal Found:  {Fore.GREEN}{optimal_amount:.3f} PLUME ({savings_pct:.1f}% savings){Style.RESET_ALL}{Fore.CYAN}║{Style.RESET_ALL}")
            else:
                print(f"{Fore.CYAN}║{Style.RESET_ALL} Optimal Found:  {Fore.GREEN}{optimal_amount:.3f} PLUME{' ' * 20}{Style.RESET_ALL}{Fore.CYAN}║{Style.RESET_ALL}")
        else:
            print(f"{Fore.CYAN}║{Style.RESET_ALL} Optimal Found:  {Fore.YELLOW}Searching...{' ' * 10}{Style.RESET_ALL}{Fore.CYAN}║{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}╠═══════════════════════════════════════════════════════════════════╣{Style.RESET_ALL}")
        
        # Performance Stats
        total_swaps = stats.get('total_swaps', 0)
        successful_swaps = stats.get('successful_swaps', 0)
        failed_swaps = stats.get('failed_swaps', 0)
        success_rate = stats.get('success_rate', 0)
        
        print(f"{Fore.CYAN}║{Style.RESET_ALL} Performance:                                              {Fore.CYAN}║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   Total Swaps:     {Fore.BLUE}{total_swaps:<10}{Style.RESET_ALL}                          {Fore.CYAN}║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   Successful:      {Fore.GREEN}{successful_swaps:<10}{Style.RESET_ALL}                          {Fore.CYAN}║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   Failed:          {Fore.RED}{failed_swaps:<10}{Style.RESET_ALL}                          {Fore.CYAN}║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   Success Rate:    {Fore.GREEN}{success_rate:<10.1f}%{Style.RESET_ALL}                       {Fore.CYAN}║{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}╠═══════════════════════════════════════════════════════════════════╣{Style.RESET_ALL}")
        
        # Adaptive Behavior
        total_adjustments = stats.get('total_adjustments', 0)
        phase_transitions = stats.get('phase_transitions', 0)
        uptime = stats.get('uptime_formatted', 'Unknown')
        
        print(f"{Fore.CYAN}║{Style.RESET_ALL} Adaptive Behavior:                                        {Fore.CYAN}║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   Adjustments:     {Fore.YELLOW}{total_adjustments:<10}{Style.RESET_ALL}                          {Fore.CYAN}║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   Phase Changes:   {Fore.MAGENTA}{phase_transitions:<10}{Style.RESET_ALL}                          {Fore.CYAN}║{Style.RESET_ALL}")
        print(f"{Fore.CYAN}║{Style.RESET_ALL}   Uptime:          {Fore.BLUE}{uptime:<20}{Style.RESET_ALL}              {Fore.CYAN}║{Style.RESET_ALL}")
        
        # Savings Information (only for amounts above minimum)
        current_amount = stats.get('current_amount', 1.0)
        initial_amount = stats.get('initial_amount', 1.0)
        
        if optimal_amount and current_amount > initial_amount:
            tokens_saved = stats.get('tokens_saved', 0)
            print(f"{Fore.CYAN}╠═══════════════════════════════════════════════════════════════════╣{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║{Style.RESET_ALL} Savings:                                                  {Fore.CYAN}║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║{Style.RESET_ALL}   Tokens Saved:    {Fore.GREEN}{tokens_saved:<10.3f} PLUME{Style.RESET_ALL}                  {Fore.CYAN}║{Style.RESET_ALL}")
            print(f"{Fore.CYAN}║{Style.RESET_ALL}   Efficiency Gain: {Fore.GREEN}{savings_pct:<10.1f}%{Style.RESET_ALL}                       {Fore.CYAN}║{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}╚═══════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}\n")
    
    @staticmethod
    def print_phase_history(phase_history: list, max_entries: int = 5):
        """Print recent phase history"""
        if not phase_history:
            return
        
        print(f"\n{Fore.CYAN}[PHASE HISTORY]{Style.RESET_ALL} Recent transitions:")
        
        recent_history = phase_history[-max_entries:]
        
        for i, transition in enumerate(recent_history, 1):
            from_phase = transition.get('from', 'unknown').upper()
            to_phase = transition.get('to', 'unknown').upper()
            amount = transition.get('amount', 0)
            timestamp = transition.get('timestamp', 0)
            
            # Format timestamp
            time_str = datetime.fromtimestamp(timestamp).strftime('%H:%M:%S') if timestamp else 'Unknown'
            
            print(f"  {i}. {time_str} | {from_phase} → {to_phase} | {amount:.3f} PLUME")
    
    @staticmethod
    def print_recommendations(recommendations: Dict[str, Any]):
        """Print system recommendations"""
        recs = recommendations.get('recommendations', [])
        if not recs:
            return
        
        print(f"\n{Fore.CYAN}[RECOMMENDATIONS]{Style.RESET_ALL} System suggestions:")
        
        severity_colors = {
            'high': Fore.RED,
            'medium': Fore.YELLOW,
            'low': Fore.BLUE,
            'info': Fore.GREEN
        }
        
        for i, rec in enumerate(recs, 1):
            severity = rec.get('severity', 'info')
            message = rec.get('message', 'No message')
            rec_type = rec.get('type', 'general')
            
            color = severity_colors.get(severity, Fore.WHITE)
            print(f"  {i}. {color}[{severity.upper()}]{Style.RESET_ALL} {message}")
        
        # Performance score
        score = recommendations.get('performance_score', 0)
        if score > 0:
            score_color = Fore.GREEN if score >= 80 else Fore.YELLOW if score >= 60 else Fore.RED
            print(f"\n{Fore.CYAN}[SCORE]{Style.RESET_ALL} Performance: {score_color}{score:.0f}/100{Style.RESET_ALL}")
    
    @staticmethod
    def print_configuration_summary(config: Dict[str, Any]):
        """Print current configuration summary"""
        print(f"\n{Fore.WHITE}[CONFIGURATION]{Style.RESET_ALL} Current Settings:")
        
        settings = config.get('settings', {})
        print(f"├─ Initial Amount: {config.get('initial_amount', 1.0)} PLUME")
        print(f"├─ Current Amount: {config.get('current_amount', 1.0)} PLUME")
        print(f"├─ Increment Step: {settings.get('increment_step', 0.05)} PLUME")
        print(f"├─ Stability Threshold: {settings.get('stability_threshold', 5)} swaps")
        print(f"├─ Max Ceiling: {settings.get('max_ceiling', 1.0)} PLUME")
        print(f"├─ Min Floor: {settings.get('min_floor', 0.1)} PLUME")
        print(f"└─ Descending Mode: {'Enabled' if settings.get('enable_descending', True) else 'Disabled'}")
    
    @staticmethod
    def print_realtime_status_line(stats: Dict[str, Any]):
        """Print compact real-time status line"""
        mode = stats.get('mode', 'unknown').upper()
        phase = stats.get('current_phase', 'unknown').upper()
        amount = stats.get('current_amount', 0)
        success_rate = stats.get('success_rate', 0)
        
        phase_icons = {
            'ASCENDING': '📈',
            'STABLE': '⚖️',
            'DESCENDING': '📉',
            'FIXED': '🔒'
        }
        
        icon = phase_icons.get(phase, '❓')
        
        status_line = f"{Fore.CYAN}[ADAPTIVE]{Style.RESET_ALL} {icon} {phase} | "
        status_line += f"{amount:.3f} PLUME | "
        status_line += f"Success: {success_rate:.1f}%"
        
        # Add savings info if available
        if stats.get('optimal_amount') and stats.get('savings_percentage'):
            savings_pct = stats.get('savings_percentage', 0)
            status_line += f" | Savings: {savings_pct:.1f}%"
        
        print(status_line)
    
    @staticmethod
    def print_error_classification(error_type: str, should_adjust: bool, error_message: str):
        """Print error classification information"""
        adjust_text = "WILL ADJUST" if should_adjust else "NO ADJUSTMENT"
        adjust_color = Fore.YELLOW if should_adjust else Fore.BLUE
        
        print(f"{Fore.WHITE}[ERROR TYPE]{Style.RESET_ALL} {error_type}")
        print(f"{adjust_color}[ACTION]{Style.RESET_ALL} {adjust_text}")
        if error_message:
            print(f"{Fore.WHITE}[MESSAGE]{Style.RESET_ALL} {error_message}")
    
    @staticmethod
    def print_startup_configuration(config_dict: Dict[str, Any]):
        """Print startup configuration in an attractive format"""
        print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}{' ' * 25}CONFIGURATION{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
        
        mode = config_dict.get('mode', 'unknown').upper()
        initial_amount = config_dict.get('initial_amount', 1.0)
        
        mode_color = Fore.GREEN if mode == 'ADAPTIVE' else Fore.WHITE
        print(f"{Fore.BLUE}[MODE]{Style.RESET_ALL} {mode_color}{mode}{Style.RESET_ALL}")
        print(f"{Fore.BLUE}[AMOUNT]{Style.RESET_ALL} {initial_amount} PLUME")
        
        if mode == 'ADAPTIVE':
            settings = config_dict.get('settings', {})
            print(f"{Fore.BLUE}[RANGE]{Style.RESET_ALL} {settings.get('min_floor', initial_amount)} - {settings.get('max_ceiling', 1.0)} PLUME")
            print(f"{Fore.BLUE}[INCREMENT]{Style.RESET_ALL} {settings.get('increment_step', 0.05)} PLUME per adjustment")
            print(f"{Fore.BLUE}[STABILITY]{Style.RESET_ALL} {settings.get('stability_threshold', 5)} successful swaps required")
            print(f"{Fore.BLUE}[OPTIMIZATION]{Style.RESET_ALL} {'Enabled' if settings.get('enable_descending', True) else 'Disabled'}")
            
            if config_dict.get('optimal_amount'):
                optimal = config_dict.get('optimal_amount')
                savings_pct = ((1.0 - optimal) / 1.0) * 100
                print(f"{Fore.GREEN}[OPTIMAL]{Style.RESET_ALL} {optimal} PLUME ({savings_pct:.1f}% savings)")
        
        print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
    
    @staticmethod 
    def clear_line():
        """Clear current line (for dynamic updates)"""
        print("\r" + " " * 80 + "\r", end="")
    
    @staticmethod
    def print_waiting_status(seconds_remaining: int, phase: str, amount: float):
        """Print waiting status with countdown"""
        status = f"{Fore.BLUE}[WAIT]{Style.RESET_ALL} Next swap in {seconds_remaining}s | "
        status += f"{phase.upper()} phase | {amount:.3f} PLUME"
        print(f"\r{status}", end="", flush=True)
        
        if seconds_remaining == 0:
            print()  # New line when countdown finishes
