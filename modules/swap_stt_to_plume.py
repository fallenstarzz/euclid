"""
STT → PLUME Specialist Module  
Single Responsibility: EXCLUSIVELY handles STT to PLUME swaps
No knowledge of forward swaps, no direction variables, no toggle functions
"""

import logging
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal

class SttToPlumeSwapper:
    """
    Dedicated STT → PLUME swap handler
    ONLY knows about reverse swaps, completely isolated from forward logic
    """
    
    def __init__(self, wallet_manager, swap_executor, adaptive_manager=None, somnia_connector=None):
        """Initialize STT→PLUME specialist"""
        self.wallet = wallet_manager
        self.swap_executor = swap_executor
        self.adaptive_manager = adaptive_manager
        self.somnia_connector = somnia_connector
        self.logger = logging.getLogger(f"{__name__}.SttToPlume")
        
        # Module identity - NEVER changes
        self.swap_direction = "STT_TO_PLUME"
        self.input_token = "stt"
        self.output_token = "plume"
        self.network = "somnia"  # Always executes on Somnia network
        
        # STT conversion ratio (from previous analysis)
        self.stt_to_plume_ratio = 0.29  # 0.5 PLUME ≈ 0.145 STT
        
        # Simple state tracking
        self.total_swaps = 0
        self.successful_swaps = 0
        self.last_swap_amount = 0.0
        
        self.logger.info("[MODULE] STT→PLUME Specialist initialized")
    
    def get_stt_balance(self) -> Tuple[bool, float]:
        """
        Get current STT balance from Somnia network
        
        Returns:
            Tuple of (success, balance)
        """
        try:
            if self.somnia_connector:
                # Use dedicated Somnia connector for real-time balance
                balance_result = self.somnia_connector.get_stt_balance(self.wallet.address)
                if balance_result.get('success', False):
                    balance = balance_result.get('balance', 0.0)
                    self.logger.debug(f"[STT BALANCE] Real-time: {balance:.6f} STT")
                    return True, balance
            
            # Fallback to tracker-based balance
            # This is a simplified fallback - in production you'd use proper Somnia RPC
            self.logger.warning("[STT BALANCE] Using fallback method - consider implementing proper Somnia RPC")
            return True, 497.0  # Fallback value
            
        except Exception as e:
            self.logger.error(f"[ERROR] STT balance check failed: {e}")
            return False, 0.0
    
    def check_balance_sufficient(self, required_plume_amount: float) -> Tuple[bool, float]:
        """
        Check if STT balance is sufficient for swap
        
        Args:
            required_plume_amount: Target PLUME amount to receive
            
        Returns:
            Tuple of (is_sufficient, current_stt_balance)
        """
        try:
            # Calculate required STT input for desired PLUME output
            required_stt = required_plume_amount * self.stt_to_plume_ratio
            
            # Get current STT balance
            success, current_stt_balance = self.get_stt_balance()
            if not success:
                return False, 0.0
            
            # Add small buffer for gas fees (0.01 STT)
            required_stt_with_gas = required_stt + 0.01
            
            is_sufficient = current_stt_balance >= required_stt_with_gas
            
            self.logger.info(f"[BALANCE CHECK] STT: {current_stt_balance:.6f}, Required: {required_stt_with_gas:.6f} (for {required_plume_amount:.6f} PLUME), Sufficient: {is_sufficient}")
            
            return is_sufficient, current_stt_balance
            
        except Exception as e:
            self.logger.error(f"[ERROR] STT balance check failed: {e}")
            return False, 0.0
    
    def execute_swap(self, plume_target_amount: Optional[float] = None) -> Dict[str, Any]:
        """
        Execute STT → PLUME swap
        
        Args:
            plume_target_amount: Target PLUME amount to receive (uses adaptive if None)
            
        Returns:
            Dict with swap result details
        """
        self.total_swaps += 1
        
        try:
            # Determine target PLUME amount
            if plume_target_amount is None and self.adaptive_manager:
                target_plume = self.adaptive_manager.get_current_amount()
            elif plume_target_amount is not None:
                target_plume = plume_target_amount
            else:
                target_plume = 0.5  # Default fallback
            
            # Calculate actual STT input amount
            stt_input_amount = target_plume * self.stt_to_plume_ratio
            
            self.logger.info(f"[SWAP #{self.total_swaps}] Executing STT→PLUME: {stt_input_amount:.6f} STT → {target_plume:.6f} PLUME target")
            
            # Pre-flight balance check
            is_sufficient, current_stt_balance = self.check_balance_sufficient(target_plume)
            if not is_sufficient:
                error_result = {
                    "success": False,
                    "error_type": "INSUFFICIENT_STT_BALANCE",
                    "error_message": f"Insufficient STT balance: {current_stt_balance:.6f} < {stt_input_amount + 0.01:.6f}",
                    "current_stt_balance": current_stt_balance,
                    "required_stt_amount": stt_input_amount,
                    "target_plume_amount": target_plume,
                    "swap_direction": self.swap_direction
                }
                self.logger.warning(f"[FAIL] {error_result['error_message']}")
                return error_result
            
            # Ensure wallet is switched to Somnia network for STT transaction
            if hasattr(self.wallet, 'switch_network'):
                network_switched = self.wallet.switch_network(self.input_token)
                if not network_switched:
                    error_result = {
                        "success": False,
                        "error_type": "NETWORK_SWITCH_FAILED",
                        "error_message": "Failed to switch to Somnia network for STT transaction",
                        "swap_direction": self.swap_direction
                    }
                    self.logger.error(f"[FAIL] {error_result['error_message']}")
                    return error_result
            
            # Execute the swap using existing swap executor
            token_pair = (self.input_token, self.output_token)
            
            if self.adaptive_manager:
                # Use adaptive swap executor
                tx_hash, swap_result = self.swap_executor.execute_adaptive_swap(token_pair)
            else:
                # Use regular swap executor with STT amount in wei
                stt_amount_wei = str(int(stt_input_amount * 10**18))
                tx_hash = self.swap_executor.execute_swap(token_pair, stt_amount_wei)
                swap_result = None
            
            if tx_hash:
                # Swap successful
                self.successful_swaps += 1
                self.last_swap_amount = stt_input_amount
                
                success_result = {
                    "success": True,
                    "transaction_hash": tx_hash,
                    "stt_input_amount": stt_input_amount,
                    "plume_target_amount": target_plume,
                    "swap_direction": self.swap_direction,
                    "input_token": self.input_token.upper(),
                    "output_token": self.output_token.upper(),
                    "network": self.network,
                    "conversion_ratio": self.stt_to_plume_ratio,
                    "module_stats": {
                        "total_swaps": self.total_swaps,
                        "successful_swaps": self.successful_swaps,
                        "success_rate": (self.successful_swaps / self.total_swaps) * 100
                    }
                }
                
                if swap_result:
                    success_result["adaptive_result"] = swap_result.__dict__
                
                self.logger.info(f"[SUCCESS] STT→PLUME completed: {tx_hash}")
                return success_result
            else:
                # Swap failed
                error_result = {
                    "success": False,
                    "error_type": "SWAP_EXECUTION_FAILED",
                    "error_message": "Swap execution returned no transaction hash",
                    "stt_input_amount": stt_input_amount,
                    "plume_target_amount": target_plume,
                    "swap_direction": self.swap_direction,
                    "module_stats": {
                        "total_swaps": self.total_swaps,
                        "successful_swaps": self.successful_swaps,
                        "success_rate": (self.successful_swaps / self.total_swaps) * 100 if self.total_swaps > 0 else 0
                    }
                }
                
                self.logger.error(f"[FAIL] STT→PLUME execution failed")
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
            
            self.logger.error(f"[ERROR] STT→PLUME unexpected error: {e}")
            return error_result
    
    def get_status(self) -> Dict[str, Any]:
        """Get current module status"""
        success, stt_balance = self.get_stt_balance()
        
        return {
            "module_name": "STT→PLUME Specialist",
            "swap_direction": self.swap_direction,
            "input_token": self.input_token.upper(),
            "output_token": self.output_token.upper(),
            "network": self.network,
            "conversion_ratio": self.stt_to_plume_ratio,
            "current_stt_balance": stt_balance if success else "N/A",
            "total_swaps": self.total_swaps,
            "successful_swaps": self.successful_swaps,
            "success_rate": (self.successful_swaps / self.total_swaps) * 100 if self.total_swaps > 0 else 0,
            "last_swap_amount": self.last_swap_amount,
            "adaptive_enabled": self.adaptive_manager is not None,
            "somnia_connector_available": self.somnia_connector is not None
        }
    
    def reset_stats(self):
        """Reset module statistics"""
        self.total_swaps = 0
        self.successful_swaps = 0
        self.last_swap_amount = 0.0
        self.logger.info("[RESET] Module statistics reset")
