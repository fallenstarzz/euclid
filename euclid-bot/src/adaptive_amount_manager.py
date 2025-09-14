"""
Intelligent Adaptive Amount System for Euclid Swap Bot
Implements dual-phase optimization: ascending to find working amount, descending to minimize
"""

import json
import time
import logging
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
from enum import Enum
from colorama import Fore, Style

class AdaptivePhase(Enum):
    """Adaptive system phases"""
    ASCENDING = "ascending"
    STABLE = "stable"
    DESCENDING = "descending"
    FIXED = "fixed"

class AdaptiveMode(Enum):
    """Operation modes"""
    FIXED = "fixed"        # User input >= 1.0, no adjustments
    ADAPTIVE = "adaptive"  # User input < 1.0, intelligent adjustments

class SwapResult:
    """Represents the result of a swap attempt"""
    def __init__(self, success: bool, tx_hash: Optional[str] = None, error_type: Optional[str] = None, 
                 error_message: Optional[str] = None, amount_used: float = 0.0):
        self.success = success
        self.tx_hash = tx_hash
        self.error_type = error_type
        self.error_message = error_message
        self.amount_used = amount_used
        self.timestamp = time.time()

class AdaptiveConfiguration:
    """Configuration for adaptive amount system"""
    def __init__(self, initial_amount: float = 1.0, **kwargs):
        # User inputs
        self.initial_amount = initial_amount
        self.mode = AdaptiveMode.FIXED if initial_amount >= 1.0 else AdaptiveMode.ADAPTIVE
        
        # Adaptive settings (only active if mode = ADAPTIVE)
        self.increment_step = kwargs.get('increment_step', 0.1)  # Changed to 0.1
        self.decrement_step = kwargs.get('decrement_step', 0.1)  # Changed to 0.1
        self.stability_threshold = kwargs.get('stability_threshold', 5)
        self.max_increment_attempts = kwargs.get('max_increment_attempts', 5)
        self.max_ceiling = kwargs.get('max_ceiling', 1.0)
        self.min_floor = initial_amount  # Never go below user's input
        self.enable_descending = kwargs.get('enable_descending', True)
        
        # Runtime state
        self.current_amount = initial_amount
        self.current_phase = AdaptivePhase.FIXED if self.mode == AdaptiveMode.FIXED else AdaptivePhase.ASCENDING
        self.increment_attempts = 0
        self.consecutive_successes = 0
        self.last_working_amount = None
        self.optimization_history = []
        
        # Statistics
        self.total_adjustments = 0
        self.successful_amounts = []
        self.failed_amounts = []
        self.optimal_amount = None
        self.tokens_saved = 0.0
        self.phase_history = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            'initial_amount': self.initial_amount,
            'mode': self.mode.value,
            'increment_step': self.increment_step,
            'decrement_step': self.decrement_step,
            'stability_threshold': self.stability_threshold,
            'max_increment_attempts': self.max_increment_attempts,
            'max_ceiling': self.max_ceiling,
            'min_floor': self.min_floor,
            'enable_descending': self.enable_descending,
            'current_amount': self.current_amount,
            'current_phase': self.current_phase.value,
            'increment_attempts': self.increment_attempts,
            'consecutive_successes': self.consecutive_successes,
            'total_adjustments': self.total_adjustments,
            'optimal_amount': self.optimal_amount,
            'tokens_saved': self.tokens_saved
        }

class AdaptiveAmountManager:
    """
    Manages intelligent amount adjustments for optimal swap efficiency
    
    Implements dual-phase system:
    - Ascending Phase: Increase amount until successful (max 5 attempts)
    - Stable Phase: Confirm amount works with multiple successful swaps
    - Descending Phase: Find minimum viable amount to maximize efficiency
    """
    
    # Error classification
    AMOUNT_SENSITIVE_ERRORS = {
        'INSUFFICIENT_LIQUIDITY',
        'BELOW_MINIMUM_AMOUNT', 
        'SLIPPAGE_EXCEEDED',
        'ROUTE_NOT_FOUND',
        'PRICE_IMPACT_TOO_HIGH',
        'SWAP_AMOUNT_TOO_SMALL',
        'MINIMUM_RECEIVED_NOT_MET',
        'INSUFFICIENT_OUTPUT_AMOUNT'
    }
    
    INFRASTRUCTURE_ERRORS = {
        'NETWORK_TIMEOUT',
        'RPC_ERROR',
        'NONCE_ISSUE',
        'GAS_PRICE_HIGH',
        'INSUFFICIENT_GAS',
        'CONNECTION_ERROR',
        'TRANSACTION_TIMEOUT',
        'GENERAL_NETWORK_ERROR'
    }
    
    def __init__(self, config: Optional[AdaptiveConfiguration] = None):
        """Initialize adaptive amount manager"""
        self.config = config or AdaptiveConfiguration()
        self.logger = logging.getLogger(__name__)
        
        # Track performance
        self.start_time = time.time()
        self.total_swaps = 0
        self.successful_swaps = 0
        self.failed_swaps = 0
        self.phase_transitions = 0
        
    def should_adjust_amount(self, swap_result: SwapResult) -> bool:
        """
        Determine if amount should be adjusted based on error type
        
        Args:
            swap_result: Result of the swap attempt
            
        Returns:
            True if amount should be adjusted, False otherwise
        """
        if swap_result.success:
            return False
        
        if not swap_result.error_type:
            # If no error type specified, assume it's amount-sensitive for safety
            return self.config.mode == AdaptiveMode.ADAPTIVE
        
        error_type_upper = swap_result.error_type.upper()
        
        # Check if this is an amount-sensitive error
        for error in self.AMOUNT_SENSITIVE_ERRORS:
            if error in error_type_upper:
                return self.config.mode == AdaptiveMode.ADAPTIVE
        
        # Check if it's an infrastructure error (don't adjust)
        for error in self.INFRASTRUCTURE_ERRORS:
            if error in error_type_upper:
                return False
        
        # If error type is unknown, be conservative and adjust if in adaptive mode
        self.logger.warning(f"[ADAPTIVE] Unknown error type: {swap_result.error_type}, assuming amount-sensitive")
        return self.config.mode == AdaptiveMode.ADAPTIVE
    
    def get_current_amount(self) -> float:
        """Get current swap amount"""
        return self.config.current_amount
    
    def get_current_amount_wei(self) -> str:
        """Get current swap amount in wei"""
        amount_wei = int(self.config.current_amount * 10**18)
        return str(amount_wei)
    
    def process_swap_result(self, swap_result: SwapResult) -> Tuple[float, bool]:
        """
        Process swap result and adjust amount if needed
        
        Args:
            swap_result: Result of the swap attempt
            
        Returns:
            Tuple of (new_amount, amount_changed)
        """
        self.total_swaps += 1
        previous_amount = self.config.current_amount
        
        if swap_result.success:
            self.successful_swaps += 1
            self._handle_successful_swap(swap_result)
        else:
            self.failed_swaps += 1
            self._handle_failed_swap(swap_result)
        
        amount_changed = abs(self.config.current_amount - previous_amount) > 0.001
        if amount_changed:
            self.config.total_adjustments += 1
            self._log_adjustment(previous_amount, self.config.current_amount, swap_result)
        
        return self.config.current_amount, amount_changed
    
    def _handle_successful_swap(self, swap_result: SwapResult):
        """Handle successful swap based on current phase"""
        if self.config.mode == AdaptiveMode.FIXED:
            # No adjustments in fixed mode
            return
        
        if self.config.current_phase == AdaptivePhase.ASCENDING:
            # Found working amount, move to stable phase
            self.config.current_phase = AdaptivePhase.STABLE
            self.config.last_working_amount = self.config.current_amount
            self.config.consecutive_successes = 1
            self.config.increment_attempts = 0
            self._log_phase_transition(AdaptivePhase.ASCENDING, AdaptivePhase.STABLE)
            
            # Record successful amount
            if self.config.current_amount not in self.config.successful_amounts:
                self.config.successful_amounts.append(self.config.current_amount)
                
        elif self.config.current_phase == AdaptivePhase.STABLE:
            # Continue stability check
            self.config.consecutive_successes += 1
            
            if self.config.consecutive_successes >= self.config.stability_threshold:
                if (self.config.enable_descending and 
                    self.config.current_amount > self.config.min_floor):
                    # Ready to optimize, enter descending phase
                    self.config.current_phase = AdaptivePhase.DESCENDING
                    self.config.consecutive_successes = 0
                    
                    # Try lower amount
                    new_amount = max(
                        self.config.current_amount - self.config.decrement_step,
                        self.config.min_floor
                    )
                    self.config.current_amount = new_amount
                    self._log_phase_transition(AdaptivePhase.STABLE, AdaptivePhase.DESCENDING)
                else:
                    # Optimal amount found (at floor or descending disabled)
                    self.config.optimal_amount = self.config.current_amount
                    self._calculate_savings()
                    
        elif self.config.current_phase == AdaptivePhase.DESCENDING:
            # Lower amount works, continue optimization
            self.config.consecutive_successes += 1
            self.config.last_working_amount = self.config.current_amount
            
            if self.config.consecutive_successes >= self.config.stability_threshold:
                # Try even lower amount
                new_amount = max(
                    self.config.current_amount - self.config.decrement_step,
                    self.config.min_floor
                )
                
                if new_amount >= self.config.min_floor and new_amount < self.config.current_amount:
                    self.config.current_amount = new_amount
                    self.config.consecutive_successes = 0
                else:
                    # Reached optimal (at floor)
                    self.config.optimal_amount = self.config.current_amount
                    self._calculate_savings()
    
    def _handle_failed_swap(self, swap_result: SwapResult):
        """Handle failed swap based on current phase"""
        if self.config.mode == AdaptiveMode.FIXED:
            # No adjustments in fixed mode
            return
        
        # Only adjust if this is an amount-sensitive error
        if not self.should_adjust_amount(swap_result):
            self.logger.info(f"[ADAPTIVE] Infrastructure error detected, not adjusting amount: {swap_result.error_type}")
            return
        
        # Record failed amount
        if self.config.current_amount not in self.config.failed_amounts:
            self.config.failed_amounts.append(self.config.current_amount)
        
        if self.config.current_phase == AdaptivePhase.ASCENDING:
            # Need to increase amount
            self.config.increment_attempts += 1
            
            if self.config.increment_attempts >= self.config.max_increment_attempts:
                if self.config.current_amount >= self.config.max_ceiling:
                    # Hit ceiling, try descending from just below ceiling
                    self.config.current_phase = AdaptivePhase.DESCENDING
                    self.config.current_amount = self.config.max_ceiling - self.config.decrement_step
                    self.config.increment_attempts = 0
                    self.config.consecutive_successes = 0
                    self._log_phase_transition(AdaptivePhase.ASCENDING, AdaptivePhase.DESCENDING)
                else:
                    # Force to ceiling
                    self.config.current_amount = self.config.max_ceiling
                    self.config.increment_attempts = 0
            else:
                # Normal increment
                new_amount = min(
                    self.config.current_amount + self.config.increment_step,
                    self.config.max_ceiling
                )
                self.config.current_amount = new_amount
                
        elif self.config.current_phase == AdaptivePhase.STABLE:
            # Stability broken, return to ascending
            self.config.current_phase = AdaptivePhase.ASCENDING
            self.config.consecutive_successes = 0
            self.config.increment_attempts = 0
            self._log_phase_transition(AdaptivePhase.STABLE, AdaptivePhase.ASCENDING)
            
        elif self.config.current_phase == AdaptivePhase.DESCENDING:
            # Amount too low, revert to last working amount
            if self.config.last_working_amount:
                self.config.current_amount = self.config.last_working_amount
                self.config.current_phase = AdaptivePhase.STABLE
                self.config.consecutive_successes = 0
                self.config.optimal_amount = self.config.current_amount
                self._calculate_savings()
                self._log_phase_transition(AdaptivePhase.DESCENDING, AdaptivePhase.STABLE)
    
    def _log_phase_transition(self, from_phase: AdaptivePhase, to_phase: AdaptivePhase):
        """Log phase transitions"""
        self.phase_transitions += 1
        transition = {
            'from': from_phase.value,
            'to': to_phase.value,
            'timestamp': time.time(),
            'amount': self.config.current_amount
        }
        self.config.phase_history.append(transition)
        
        self.logger.info(f"[ADAPTIVE] Phase transition: {from_phase.value.upper()} → {to_phase.value.upper()} at {self.config.current_amount}")
    
    def _log_adjustment(self, old_amount: float, new_amount: float, swap_result: SwapResult):
        """Log amount adjustments"""
        direction = "↑" if new_amount > old_amount else "↓"
        change = abs(new_amount - old_amount)
        
        if swap_result.success:
            self.logger.info(f"[ADAPTIVE] Amount optimized {direction} {old_amount} → {new_amount} (+{change:.3f})")
        else:
            reason = swap_result.error_type or "Unknown error"
            self.logger.info(f"[ADAPTIVE] Amount adjusted {direction} {old_amount} → {new_amount} (+{change:.3f}) due to: {reason}")
    
    def _calculate_savings(self):
        """Calculate token savings compared to fixed 1.0 amount"""
        if self.config.optimal_amount and self.config.optimal_amount < 1.0:
            savings_per_swap = 1.0 - self.config.optimal_amount
            estimated_total_savings = savings_per_swap * self.successful_swaps
            self.config.tokens_saved = estimated_total_savings
            
            savings_percentage = (savings_per_swap / 1.0) * 100
            self.logger.info(f"[ADAPTIVE] Optimal amount found: {self.config.optimal_amount} PLUME")
            self.logger.info(f"[ADAPTIVE] Token savings: {savings_per_swap:.3f} per swap ({savings_percentage:.1f}%)")
            self.logger.info(f"[ADAPTIVE] Total estimated savings: {estimated_total_savings:.3f} PLUME")
    
    def get_status_display(self) -> str:
        """Get current status for display"""
        if self.config.mode == AdaptiveMode.FIXED:
            return f"[FIXED MODE] Using {self.config.current_amount:.3f} PLUME"
        
        phase = self.config.current_phase.value.upper()
        amount = self.config.current_amount
        
        status_parts = [f"[{phase}]", f"Amount: {amount:.3f} PLUME"]
        
        if self.config.current_phase == AdaptivePhase.ASCENDING:
            status_parts.append(f"Attempt: {self.config.increment_attempts + 1}/{self.config.max_increment_attempts}")
        elif self.config.current_phase == AdaptivePhase.STABLE:
            status_parts.append(f"Stability: {self.config.consecutive_successes}/{self.config.stability_threshold}")
        elif self.config.current_phase == AdaptivePhase.DESCENDING:
            status_parts.append(f"Optimizing: {self.config.consecutive_successes}/{self.config.stability_threshold}")
        
        if self.config.optimal_amount:
            savings = ((1.0 - self.config.optimal_amount) / 1.0) * 100
            status_parts.append(f"Optimal: {self.config.optimal_amount:.3f} ({savings:.1f}% saved)")
        
        return " | ".join(status_parts)
    
    def get_detailed_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics"""
        uptime = time.time() - self.start_time
        success_rate = (self.successful_swaps / max(1, self.total_swaps)) * 100
        
        stats = {
            # Basic stats
            'mode': self.config.mode.value,
            'current_phase': self.config.current_phase.value,
            'current_amount': self.config.current_amount,
            'initial_amount': self.config.initial_amount,
            'optimal_amount': self.config.optimal_amount,
            
            # Performance
            'total_swaps': self.total_swaps,
            'successful_swaps': self.successful_swaps,
            'failed_swaps': self.failed_swaps,
            'success_rate': round(success_rate, 2),
            'uptime_seconds': int(uptime),
            'uptime_formatted': self._format_duration(uptime),
            
            # Adaptive behavior
            'total_adjustments': self.config.total_adjustments,
            'phase_transitions': self.phase_transitions,
            'consecutive_successes': self.config.consecutive_successes,
            'increment_attempts': self.config.increment_attempts,
            
            # Savings
            'tokens_saved': self.config.tokens_saved,
            'savings_percentage': ((1.0 - (self.config.optimal_amount or 1.0)) / 1.0) * 100 if self.config.optimal_amount else 0,
            
            # History
            'successful_amounts': sorted(list(set(self.config.successful_amounts))),
            'failed_amounts': sorted(list(set(self.config.failed_amounts))),
            'phase_history': self.config.phase_history[-10:],  # Last 10 transitions
            
            # Configuration
            'settings': {
                'increment_step': self.config.increment_step,
                'stability_threshold': self.config.stability_threshold,
                'max_ceiling': self.config.max_ceiling,
                'min_floor': self.config.min_floor,
                'enable_descending': self.config.enable_descending
            }
        }
        
        return stats
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human readable format"""
        hours, remainder = divmod(int(seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def reset_to_initial_state(self):
        """Reset manager to initial state"""
        self.config.current_amount = self.config.initial_amount
        self.config.current_phase = AdaptivePhase.FIXED if self.config.mode == AdaptiveMode.FIXED else AdaptivePhase.ASCENDING
        self.config.increment_attempts = 0
        self.config.consecutive_successes = 0
        self.config.last_working_amount = None
        self.config.optimal_amount = None
        self.config.total_adjustments = 0
        self.config.tokens_saved = 0.0
        
        # Clear history but keep successful/failed amounts for learning
        self.config.phase_history.clear()
        
        self.logger.info("[ADAPTIVE] Reset to initial state")
    
    def export_configuration(self) -> Dict[str, Any]:
        """Export current configuration for saving"""
        return self.config.to_dict()
    
    def import_configuration(self, config_dict: Dict[str, Any]):
        """Import configuration from saved data"""
        try:
            # Update basic settings
            self.config.current_amount = config_dict.get('current_amount', self.config.initial_amount)
            self.config.optimal_amount = config_dict.get('optimal_amount')
            self.config.tokens_saved = config_dict.get('tokens_saved', 0.0)
            
            # Restore phase if in adaptive mode
            if self.config.mode == AdaptiveMode.ADAPTIVE:
                phase_value = config_dict.get('current_phase', 'ascending')
                try:
                    self.config.current_phase = AdaptivePhase(phase_value)
                except ValueError:
                    self.config.current_phase = AdaptivePhase.ASCENDING
            
            self.logger.info(f"[ADAPTIVE] Configuration imported successfully")
            
        except Exception as e:
            self.logger.error(f"[ADAPTIVE] Failed to import configuration: {e}")
            # Reset to safe defaults
            self.reset_to_initial_state()

def create_adaptive_configuration_from_user_input(initial_amount: float, **kwargs) -> AdaptiveConfiguration:
    """
    Create adaptive configuration from user input with validation
    
    Args:
        initial_amount: User's desired swap amount
        **kwargs: Additional configuration options
        
    Returns:
        Validated AdaptiveConfiguration instance
    """
    # Validate initial amount
    if initial_amount < 0.1:
        raise ValueError("Initial amount must be at least 0.1")
    
    # Validate other parameters
    increment_step = kwargs.get('increment_step', 0.05)
    if increment_step <= 0 or increment_step > 0.5:
        raise ValueError("Increment step must be between 0 and 0.5")
    
    stability_threshold = kwargs.get('stability_threshold', 5)
    if stability_threshold < 1 or stability_threshold > 20:
        raise ValueError("Stability threshold must be between 1 and 20")
    
    max_increment_attempts = kwargs.get('max_increment_attempts', 5)
    if max_increment_attempts < 1 or max_increment_attempts > 10:
        raise ValueError("Max increment attempts must be between 1 and 10")
    
    # Create configuration
    config = AdaptiveConfiguration(
        initial_amount=initial_amount,
        increment_step=increment_step,
        decrement_step=kwargs.get('decrement_step', increment_step),
        stability_threshold=stability_threshold,
        max_increment_attempts=max_increment_attempts,
        max_ceiling=kwargs.get('max_ceiling', 1.0),
        enable_descending=kwargs.get('enable_descending', True)
    )
    
    return config
