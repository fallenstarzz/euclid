"""
Swap Orchestrator - Intelligent Switch Manager
Single Responsibility: Monitor conditions and activate appropriate swap module
No swap logic, only switching decisions based on clear, deterministic rules
"""

import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

from .swap_plume_to_stt import PlumeToSttSwapper
from .swap_stt_to_plume import SttToPlumeSwapper

class SwapDirection(Enum):
    """Enum for swap directions"""
    PLUME_TO_STT = "PLUME_TO_STT"
    STT_TO_PLUME = "STT_TO_PLUME"

class SwitchReason(Enum):
    """Enum for switch reasons"""
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    INSUFFICIENT_STT_BALANCE = "INSUFFICIENT_STT_BALANCE"
    NO_ROUTE_FOUND = "NO_ROUTE_FOUND"
    SWAP_EXECUTION_FAILED = "SWAP_EXECUTION_FAILED"
    MANUAL_SWITCH = "MANUAL_SWITCH"
    INITIALIZATION = "INITIALIZATION"

class SwapOrchestrator:
    """
    Intelligent switch manager for dual-module swap system
    Monitors execution results and switches modules based on deterministic conditions
    """
    
    def __init__(self, wallet_manager, swap_executor, adaptive_manager=None, somnia_connector=None):
        """Initialize the orchestrator with both swap modules"""
        self.logger = logging.getLogger(f"{__name__}.SwapOrchestrator")
        
        # Initialize both specialist modules
        self.plume_to_stt = PlumeToSttSwapper(
            wallet_manager=wallet_manager,
            swap_executor=swap_executor,
            adaptive_manager=adaptive_manager
        )
        
        self.stt_to_plume = SttToPlumeSwapper(
            wallet_manager=wallet_manager,
            swap_executor=swap_executor,
            adaptive_manager=adaptive_manager,
            somnia_connector=somnia_connector
        )
        
        # Orchestrator state
        self.current_direction = SwapDirection.PLUME_TO_STT  # Start with PLUME→STT
        self.active_module = self.plume_to_stt
        
        # Switch tracking
        self.total_switches = 0
        self.switch_history: List[Dict[str, Any]] = []
        self.last_switch_time = 0
        self.switch_cooldown = 5  # Minimum 5 seconds between switches
        
        # Execution tracking
        self.total_swaps_executed = 0
        self.successful_swaps = 0
        self.failed_swaps = 0
        
        # Error tracking for intelligent switching
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3  # Switch after 3 consecutive failures
        
        self.logger.info("[ORCHESTRATOR] Intelligent Switch Manager initialized")
        self.logger.info(f"[ORCHESTRATOR] Starting with {self.current_direction.value} module")
    
    def _should_switch(self, swap_result: Dict[str, Any]) -> bool:
        """
        Determine if a switch should occur based on swap result
        
        Args:
            swap_result: Result from swap execution
            
        Returns:
            bool: True if switch should occur
        """
        if swap_result.get("success", False):
            # Success - no switch needed
            self.consecutive_failures = 0
            return False
        
        # Check for specific switch triggers
        error_type = swap_result.get("error_type", "")
        
        # Primary switch conditions (immediate switch)
        immediate_switch_errors = [
            "INSUFFICIENT_BALANCE",      # PLUME balance too low
            "INSUFFICIENT_STT_BALANCE",  # STT balance too low
            "NO_ROUTE_FOUND"             # Route calculation failed
        ]
        
        if error_type in immediate_switch_errors:
            self.logger.info(f"[SWITCH TRIGGER] Immediate switch triggered by: {error_type}")
            return True
        
        # Secondary condition: too many consecutive failures
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.logger.info(f"[SWITCH TRIGGER] Switch triggered by consecutive failures: {self.consecutive_failures}")
            return True
        
        return False
    
    def _perform_switch(self, reason: SwitchReason) -> bool:
        """
        Perform the actual module switch
        
        Args:
            reason: Reason for the switch
            
        Returns:
            bool: True if switch was successful
        """
        current_time = time.time()
        
        # Check cooldown to prevent rapid switching
        if current_time - self.last_switch_time < self.switch_cooldown:
            self.logger.warning(f"[SWITCH BLOCKED] Cooldown active, {self.switch_cooldown - (current_time - self.last_switch_time):.1f}s remaining")
            return False
        
        # Determine new direction
        if self.current_direction == SwapDirection.PLUME_TO_STT:
            new_direction = SwapDirection.STT_TO_PLUME
            new_module = self.stt_to_plume
            direction_display = "PLUME→STT to STT→PLUME"
        else:
            new_direction = SwapDirection.PLUME_TO_STT
            new_module = self.plume_to_stt
            direction_display = "STT→PLUME to PLUME→STT"
        
        # Record switch details
        switch_record = {
            "switch_number": self.total_switches + 1,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "from_direction": self.current_direction.value,
            "to_direction": new_direction.value,
            "reason": reason.value,
            "consecutive_failures": self.consecutive_failures
        }
        
        # Perform the switch
        self.current_direction = new_direction
        self.active_module = new_module
        self.total_switches += 1
        self.last_switch_time = current_time
        self.consecutive_failures = 0  # Reset failure count after switch
        
        # Record in history
        self.switch_history.append(switch_record)
        
        # Keep only last 10 switches in history
        if len(self.switch_history) > 10:
            self.switch_history = self.switch_history[-10:]
        
        self.logger.info(f"🔄 [SWITCH #{self.total_switches}] Changed direction: {direction_display}")
        self.logger.info(f"[SWITCH REASON] {reason.value}")
        
        return True
    
    def execute_swap(self, amount: Optional[float] = None) -> Dict[str, Any]:
        """
        Execute swap using current active module
        
        Args:
            amount: Amount to swap (module-specific interpretation)
            
        Returns:
            Dict with execution result and potential switching info
        """
        self.total_swaps_executed += 1
        
        # Execute swap with active module
        self.logger.info(f"[EXECUTE] Swap #{self.total_swaps_executed} via {self.current_direction.value} module")
        
        swap_result = self.active_module.execute_swap(amount)
        
        # Track success/failure
        if swap_result.get("success", False):
            self.successful_swaps += 1
        else:
            self.failed_swaps += 1
        
        # Check if switch is needed
        if self._should_switch(swap_result):
            # Determine switch reason from error type
            error_type = swap_result.get("error_type", "")
            if error_type == "INSUFFICIENT_BALANCE":
                switch_reason = SwitchReason.INSUFFICIENT_BALANCE
            elif error_type == "INSUFFICIENT_STT_BALANCE":
                switch_reason = SwitchReason.INSUFFICIENT_STT_BALANCE
            elif error_type == "NO_ROUTE_FOUND":
                switch_reason = SwitchReason.NO_ROUTE_FOUND
            elif error_type == "SWAP_EXECUTION_FAILED":
                switch_reason = SwitchReason.SWAP_EXECUTION_FAILED
            else:
                switch_reason = SwitchReason.SWAP_EXECUTION_FAILED  # Generic failure
            
            switch_success = self._perform_switch(switch_reason)
            
            # Add switch info to result
            swap_result["switch_triggered"] = True
            swap_result["switch_successful"] = switch_success
            swap_result["switch_reason"] = switch_reason.value
            swap_result["new_direction"] = self.current_direction.value
        else:
            swap_result["switch_triggered"] = False
        
        # Add orchestrator context
        swap_result["orchestrator_stats"] = self.get_orchestrator_stats()
        
        return swap_result
    
    def manual_switch(self) -> bool:
        """
        Manually trigger a direction switch
        
        Returns:
            bool: True if switch was successful
        """
        self.logger.info("[MANUAL SWITCH] Manual switch requested")
        return self._perform_switch(SwitchReason.MANUAL_SWITCH)
    
    def get_current_direction(self) -> str:
        """Get current swap direction as string"""
        return self.current_direction.value
    
    def get_current_module_status(self) -> Dict[str, Any]:
        """Get status of currently active module"""
        return self.active_module.get_status()
    
    def get_all_module_stats(self) -> Dict[str, Any]:
        """Get statistics from both modules"""
        return {
            "plume_to_stt": self.plume_to_stt.get_status(),
            "stt_to_plume": self.stt_to_plume.get_status()
        }
    
    def get_orchestrator_stats(self) -> Dict[str, Any]:
        """Get orchestrator-level statistics"""
        return {
            "current_direction": self.current_direction.value,
            "total_switches": self.total_switches,
            "total_swaps_executed": self.total_swaps_executed,
            "successful_swaps": self.successful_swaps,
            "failed_swaps": self.failed_swaps,
            "success_rate": (self.successful_swaps / self.total_swaps_executed * 100) if self.total_swaps_executed > 0 else 0,
            "consecutive_failures": self.consecutive_failures,
            "last_switch_time": self.last_switch_time,
            "switch_cooldown_remaining": max(0, self.switch_cooldown - (time.time() - self.last_switch_time))
        }
    
    def get_switch_history(self) -> List[Dict[str, Any]]:
        """Get recent switch history"""
        return self.switch_history.copy()
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive status of entire system"""
        return {
            "orchestrator": self.get_orchestrator_stats(),
            "current_module": self.get_current_module_status(),
            "all_modules": self.get_all_module_stats(),
            "switch_history": self.get_switch_history()
        }
    
    def reset_stats(self):
        """Reset all statistics"""
        self.total_swaps_executed = 0
        self.successful_swaps = 0
        self.failed_swaps = 0
        self.consecutive_failures = 0
        self.switch_history.clear()
        
        # Reset module stats
        self.plume_to_stt.reset_stats()
        self.stt_to_plume.reset_stats()
        
        self.logger.info("[RESET] All statistics reset")
