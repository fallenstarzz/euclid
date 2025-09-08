"""
Adaptive Swap Executor
Integrates the adaptive amount manager with swap execution
"""

import logging
from typing import Dict, Any, Optional, Tuple
from .swap import SwapExecutor
from .adaptive_amount_manager import (
    AdaptiveAmountManager, AdaptiveConfiguration, 
    SwapResult, AdaptiveMode, AdaptivePhase
)
from .adaptive_config import create_error_classifier

class AdaptiveSwapExecutor(SwapExecutor):
    """
    Enhanced SwapExecutor with intelligent adaptive amount management
    """
    
    def __init__(self, wallet, config: Dict[str, Any], adaptive_config: Optional[AdaptiveConfiguration] = None):
        """Initialize adaptive swap executor"""
        super().__init__(wallet, config)
        
        # Initialize adaptive manager
        self.adaptive_manager = None
        if adaptive_config:
            self.adaptive_manager = AdaptiveAmountManager(adaptive_config)
        
        # Error classifier
        self.classify_error = create_error_classifier()
        
        # Enhanced logging
        self.logger = logging.getLogger(__name__)
        
    def set_adaptive_configuration(self, adaptive_config: AdaptiveConfiguration):
        """Set or update adaptive configuration"""
        self.adaptive_manager = AdaptiveAmountManager(adaptive_config)
        self.logger.info(f"[ADAPTIVE] Configuration updated - Mode: {adaptive_config.mode.value}")
    
    def execute_adaptive_swap(self, token_pair, base_amount: Optional[str] = None) -> Tuple[Optional[str], SwapResult]:
        """
        Execute swap with adaptive amount management
        
        Args:
            token_pair: Token pair for swap (tuple or dict)
            base_amount: Optional base amount override
            
        Returns:
            Tuple of (transaction_hash, SwapResult)
        """
        if not self.adaptive_manager:
            # Fallback to original implementation
            self.logger.warning("[ADAPTIVE] No adaptive manager configured, using original swap")
            tx_hash = super().execute_swap(token_pair, base_amount)
            result = SwapResult(
                success=tx_hash is not None,
                tx_hash=tx_hash,
                amount_used=float(base_amount or "1000000000000000000") / 10**18
            )
            return tx_hash, result
        
        # Get current adaptive amount  
        current_amount = self.adaptive_manager.get_current_amount()  # Always in PLUME terms
        
        # Convert amount based on token pair direction
        if isinstance(token_pair, tuple):
            token_in = token_pair[0]
            if token_in.lower() == "stt":
                # STT → PLUME: Convert PLUME target to STT input amount  
                actual_input_amount = current_amount * 0.29  # PLUME to STT conversion
                amount_wei = str(int(actual_input_amount * 10**18))
            else:
                # PLUME → STT: Use amount as-is
                amount_wei = self.adaptive_manager.get_current_amount_wei()
        else:
            # Fallback for other token pair formats
            amount_wei = self.adaptive_manager.get_current_amount_wei()
        
        # Show current status with correct token display
        if isinstance(token_pair, tuple) and token_pair[0].lower() == "stt":
            # STT → PLUME: Show STT amount and phase
            stt_amount = current_amount * 0.29
            phase = self.adaptive_manager.config.current_phase.value.upper()
            
            # Add attempt info for ascending phase
            status_parts = [f"[{phase}]"]
            
            if self.adaptive_manager.config.current_phase.value == "ascending":
                attempt_info = f"Attempt: {self.adaptive_manager.config.increment_attempts + 1}/{self.adaptive_manager.config.max_increment_attempts}"
                status_parts.append(f"Amount: {stt_amount:.3f} STT")
                status_parts.append(attempt_info)
            else:
                status_parts.append(f"Amount: {stt_amount:.3f} STT")
            
            status = " | ".join(status_parts)
        else:
            # PLUME → STT: Use default display
            status = self.adaptive_manager.get_status_display()
            
        self.logger.info(f"[ADAPTIVE] {status}")
        
        try:
            # Execute swap with current amount
            if isinstance(token_pair, tuple) and token_pair[0].lower() == "stt":
                actual_amount = current_amount * 0.29
                token_symbol = "STT"
            else:
                actual_amount = current_amount
                token_symbol = "PLUME"
            
            self.logger.info(f"[SWAP] Attempting with {actual_amount:.3f} {token_symbol} ({amount_wei} wei)")
            
            # Use parent class method with adaptive amount
            tx_hash = super().execute_swap(token_pair, amount_wei)
            
            if tx_hash:
                # Swap successful
                swap_result = SwapResult(
                    success=True,
                    tx_hash=tx_hash,
                    amount_used=current_amount
                )
                
                # Get token symbol from pair
                token_in_symbol = token_pair[0].upper()
                self.logger.info(f"[ADAPTIVE] ✅ Swap successful with {current_amount:.3f} {token_in_symbol}")
                
            else:
                # Swap failed - classify error
                error_type, should_adjust = self.classify_error("Swap execution failed", None)
                
                swap_result = SwapResult(
                    success=False,
                    error_type=error_type,
                    error_message="Swap execution failed",
                    amount_used=current_amount
                )
                
                token_in_symbol = token_pair[0].upper()
                self.logger.warning(f"[ADAPTIVE] ❌ Swap failed with {current_amount:.3f} {token_in_symbol} - {error_type}")
            
            # Process result with adaptive manager
            new_amount, amount_changed = self.adaptive_manager.process_swap_result(swap_result)
            
            if amount_changed:
                token_in_symbol = token_pair[0].upper()
                self.logger.info(f"[ADAPTIVE] Amount adjusted: {current_amount:.3f} → {new_amount:.3f} {token_in_symbol}")
            
            return tx_hash, swap_result
            
        except Exception as e:
            # Handle exceptions with error classification
            error_message = str(e)
            error_type, should_adjust = self.classify_error(error_message)
            
            swap_result = SwapResult(
                success=False,
                error_type=error_type,
                error_message=error_message,
                amount_used=current_amount
            )
            
            self.logger.error(f"[ADAPTIVE] Exception during swap: {error_message}")
            
            # Process exception result
            new_amount, amount_changed = self.adaptive_manager.process_swap_result(swap_result)
            
            if amount_changed:
                token_in_symbol = token_pair[0].upper() if token_pair else "TOKEN"
                self.logger.info(f"[ADAPTIVE] Amount adjusted after exception: {current_amount:.3f} → {new_amount:.3f} {token_in_symbol}")
            
            return None, swap_result
    
    def execute_swap_with_retry(self, token_pair, max_retries: int = 3) -> Tuple[Optional[str], SwapResult]:
        """
        Execute swap with retry logic and adaptive adjustments
        
        Args:
            token_pair: Token pair for swap
            max_retries: Maximum retry attempts
            
        Returns:
            Tuple of (transaction_hash, final_SwapResult)
        """
        last_result = None
        
        for attempt in range(max_retries + 1):
            try:
                tx_hash, result = self.execute_adaptive_swap(token_pair)
                
                if result.success:
                    self.logger.info(f"[ADAPTIVE] Swap succeeded on attempt {attempt + 1}")
                    return tx_hash, result
                
                last_result = result
                
                # Check if we should retry based on error type
                if not self.adaptive_manager.should_adjust_amount(result):
                    self.logger.info(f"[ADAPTIVE] Infrastructure error detected, retrying without adjustment")
                    continue
                
                # If this was the last attempt, don't wait
                if attempt < max_retries:
                    self.logger.info(f"[ADAPTIVE] Retry {attempt + 1}/{max_retries} in 2 seconds...")
                    import time
                    time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"[ADAPTIVE] Retry attempt {attempt + 1} failed: {e}")
                last_result = SwapResult(
                    success=False,
                    error_type="RETRY_EXCEPTION",
                    error_message=str(e),
                    amount_used=self.adaptive_manager.get_current_amount()
                )
        
        self.logger.error(f"[ADAPTIVE] All {max_retries + 1} attempts failed")
        return None, last_result or SwapResult(False, error_type="MAX_RETRIES_EXCEEDED")
    
    def get_adaptive_status(self) -> Dict[str, Any]:
        """Get comprehensive adaptive system status"""
        if not self.adaptive_manager:
            return {"mode": "disabled", "error": "No adaptive manager configured"}
        
        stats = self.adaptive_manager.get_detailed_statistics()
        
        # Add executor-specific stats
        stats.update({
            "executor": {
                "wallet_address": self.wallet.get_address(),
                "connected": True,
                "api_base": self.config["api_base"]
            }
        })
        
        return stats
    
    def get_adaptive_recommendations(self) -> Dict[str, Any]:
        """Get recommendations for improving adaptive performance"""
        if not self.adaptive_manager:
            return {}
        
        stats = self.adaptive_manager.get_detailed_statistics()
        recommendations = []
        
        # Analyze performance and suggest improvements
        success_rate = stats.get('success_rate', 0)
        total_adjustments = stats.get('total_adjustments', 0)
        phase_transitions = stats.get('phase_transitions', 0)
        
        if success_rate < 70:
            recommendations.append({
                "type": "performance",
                "message": f"Low success rate ({success_rate:.1f}%). Consider increasing increment step or stability threshold.",
                "severity": "high"
            })
        
        if total_adjustments > stats.get('total_swaps', 0) * 0.5:
            recommendations.append({
                "type": "stability",
                "message": "High adjustment frequency. Consider increasing stability threshold for more stable operation.",
                "severity": "medium"
            })
        
        if phase_transitions > 10 and stats.get('optimal_amount') is None:
            recommendations.append({
                "type": "optimization",
                "message": "Many phase transitions without finding optimal amount. Consider adjusting increment step or enabling manual optimization.",
                "severity": "medium"
            })
        
        # Positive feedback
        if stats.get('optimal_amount') and stats.get('tokens_saved', 0) > 0:
            savings_pct = stats.get('savings_percentage', 0)
            recommendations.append({
                "type": "success",
                "message": f"Excellent! Found optimal amount with {savings_pct:.1f}% token savings. System is performing well.",
                "severity": "info"
            })
        
        return {
            "recommendations": recommendations,
            "performance_score": min(100, max(0, success_rate + (stats.get('tokens_saved', 0) * 10))),
            "optimization_status": "optimal" if stats.get('optimal_amount') else "searching"
        }
    
    def reset_adaptive_state(self):
        """Reset adaptive system to initial state"""
        if self.adaptive_manager:
            self.adaptive_manager.reset_to_initial_state()
            self.logger.info("[ADAPTIVE] System reset to initial state")
    
    def export_adaptive_data(self) -> Dict[str, Any]:
        """Export adaptive system data for analysis or backup"""
        if not self.adaptive_manager:
            return {}
        
        return {
            "configuration": self.adaptive_manager.export_configuration(),
            "statistics": self.adaptive_manager.get_detailed_statistics(),
            "recommendations": self.get_adaptive_recommendations(),
            "export_timestamp": int(time.time())
        }
    
    def is_adaptive_mode_enabled(self) -> bool:
        """Check if adaptive mode is enabled"""
        return (self.adaptive_manager and 
                self.adaptive_manager.config.mode == AdaptiveMode.ADAPTIVE)
    
    def get_current_phase(self) -> str:
        """Get current adaptive phase"""
        if not self.adaptive_manager:
            return "disabled"
        return self.adaptive_manager.config.current_phase.value
    
    def get_savings_summary(self) -> Dict[str, Any]:
        """Get savings summary for user display"""
        if not self.adaptive_manager:
            return {"mode": "disabled"}
        
        stats = self.adaptive_manager.get_detailed_statistics()
        optimal = stats.get('optimal_amount')
        
        if optimal and optimal < 1.0:
            savings_per_swap = 1.0 - optimal
            total_savings = stats.get('tokens_saved', 0)
            savings_percentage = (savings_per_swap / 1.0) * 100
            
            return {
                "mode": "adaptive",
                "optimal_amount": optimal,
                "savings_per_swap": savings_per_swap,
                "total_savings": total_savings,
                "savings_percentage": savings_percentage,
                "status": "optimal_found"
            }
        else:
            return {
                "mode": "adaptive",
                "status": "searching",
                "current_amount": stats.get('current_amount', 1.0),
                "attempts": stats.get('total_adjustments', 0)
            }

import time
