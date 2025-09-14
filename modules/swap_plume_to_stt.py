"""
PLUME → STT Specialist Module
Single Responsibility: EXCLUSIVELY handles PLUME to STT swaps
No knowledge of reverse swaps, no direction variables, no toggle functions
"""

import logging
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal

class PlumeToSttSwapper:
    """
    Dedicated PLUME → STT swap handler
    ONLY knows about forward swaps, completely isolated from reverse logic
    """
    
    def __init__(self, wallet_manager, swap_executor, adaptive_manager=None):
        """Initialize PLUME→STT specialist"""
        self.wallet = wallet_manager
        self.swap_executor = swap_executor
        self.adaptive_manager = adaptive_manager
        self.logger = logging.getLogger(f"{__name__}.PlumeToStt")
        
        # Module identity - NEVER changes
        self.swap_direction = "PLUME_TO_STT"
        self.input_token = "plume"
        self.output_token = "stt"
        self.network = "plume"  # Always executes on Plume network
        
        # Simple state tracking
        self.total_swaps = 0
        self.successful_swaps = 0
        self.last_swap_amount = 0.0
        
        self.logger.info("[MODULE] PLUME→STT Specialist initialized")
    
    def check_balance_sufficient(self, required_amount: float) -> Tuple[bool, float]:
        """
        Check if PLUME balance is sufficient for swap
        
        Args:
            required_amount: Required PLUME amount in ETH
            
        Returns:
            Tuple of (is_sufficient, current_balance)
        """
        try:
            # Get PLUME balance from Plume network
            current_balance = float(self.wallet.get_balance())
            
            # Add small buffer for gas fees (0.001 PLUME)
            required_with_gas = required_amount + 0.001
            
            is_sufficient = current_balance >= required_with_gas
            
            self.logger.info(f"[BALANCE CHECK] PLUME: {current_balance:.6f}, Required: {required_with_gas:.6f}, Sufficient: {is_sufficient}")
            
            return is_sufficient, current_balance
            
        except Exception as e:
            self.logger.error(f"[ERROR] Balance check failed: {e}")
            return False, 0.0
    
    def execute_swap(self, amount: Optional[float] = None) -> Dict[str, Any]:
        """
        Execute PLUME → STT swap
        
        Args:
            amount: Amount in PLUME to swap (uses adaptive if None)
            
        Returns:
            Dict with swap result details
        """
        self.total_swaps += 1
        
        try:
            # Determine swap amount
            if amount is None and self.adaptive_manager:
                swap_amount = self.adaptive_manager.get_current_amount()
            elif amount is not None:
                swap_amount = amount
            else:
                swap_amount = 0.5  # Default fallback
            
            self.logger.info(f"[SWAP #{self.total_swaps}] Executing PLUME→STT: {swap_amount:.6f} PLUME")
            
            # Pre-flight balance check
            is_sufficient, current_balance = self.check_balance_sufficient(swap_amount)
            if not is_sufficient:
                error_result = {
                    "success": False,
                    "error_type": "INSUFFICIENT_BALANCE",
                    "error_message": f"Insufficient PLUME balance: {current_balance:.6f} < {swap_amount + 0.001:.6f}",
                    "current_balance": current_balance,
                    "required_amount": swap_amount,
                    "swap_direction": self.swap_direction
                }
                self.logger.warning(f"[FAIL] {error_result['error_message']}")
                return error_result
            
            # Execute the swap using existing swap executor
            token_pair = (self.input_token, self.output_token)
            
            if self.adaptive_manager:
                # Use adaptive swap executor
                tx_hash, swap_result = self.swap_executor.execute_adaptive_swap(token_pair)
            else:
                # Use regular swap executor
                amount_wei = str(int(swap_amount * 10**18))
                tx_hash = self.swap_executor.execute_swap(token_pair, amount_wei)
                swap_result = None
            
            if tx_hash:
                # Swap successful
                self.successful_swaps += 1
                self.last_swap_amount = swap_amount
                
                success_result = {
                    "success": True,
                    "transaction_hash": tx_hash,
                    "swap_amount": swap_amount,
                    "swap_direction": self.swap_direction,
                    "input_token": self.input_token.upper(),
                    "output_token": self.output_token.upper(),
                    "network": self.network,
                    "module_stats": {
                        "total_swaps": self.total_swaps,
                        "successful_swaps": self.successful_swaps,
                        "success_rate": (self.successful_swaps / self.total_swaps) * 100
                    }
                }
                
                if swap_result:
                    success_result["adaptive_result"] = swap_result.__dict__
                
                self.logger.info(f"[SUCCESS] PLUME→STT completed: {tx_hash}")
                return success_result
            else:
                # Swap failed
                error_result = {
                    "success": False,
                    "error_type": "SWAP_EXECUTION_FAILED",
                    "error_message": "Swap execution returned no transaction hash",
                    "swap_amount": swap_amount,
                    "swap_direction": self.swap_direction,
                    "module_stats": {
                        "total_swaps": self.total_swaps,
                        "successful_swaps": self.successful_swaps,
                        "success_rate": (self.successful_swaps / self.total_swaps) * 100 if self.total_swaps > 0 else 0
                    }
                }
                
                self.logger.error(f"[FAIL] PLUME→STT execution failed")
                return error_result
                
        except Exception as e:
            # Unexpected error
            error_result = {
                "success": False,
                "error_type": "UNEXPECTED_ERROR",
                "error_message": str(e),
                "swap_direction": self.swap_direction,
                "module_stats": {
                    "total_swaps": self.total_swaps,
                    "successful_swaps": self.successful_swaps,
                    "success_rate": (self.successful_swaps / self.total_swaps) * 100 if self.total_swaps > 0 else 0
                }
            }
            
            self.logger.error(f"[ERROR] PLUME→STT unexpected error: {e}")
            return error_result
    
    def get_status(self) -> Dict[str, Any]:
        """Get current module status"""
        return {
            "module_name": "PLUME→STT Specialist",
            "swap_direction": self.swap_direction,
            "input_token": self.input_token.upper(),
            "output_token": self.output_token.upper(),
            "network": self.network,
            "total_swaps": self.total_swaps,
            "successful_swaps": self.successful_swaps,
            "success_rate": (self.successful_swaps / self.total_swaps) * 100 if self.total_swaps > 0 else 0,
            "last_swap_amount": self.last_swap_amount,
            "adaptive_enabled": self.adaptive_manager is not None
        }
    
    def reset_stats(self):
        """Reset module statistics"""
        self.total_swaps = 0
        self.successful_swaps = 0
        self.last_swap_amount = 0.0
        self.logger.info("[RESET] Module statistics reset")
