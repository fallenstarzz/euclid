"""
Configuration Management for Adaptive Amount System
Handles user input, validation, and settings management
"""

import json
import os
import logging
from typing import Dict, Any, Optional, Tuple
from colorama import Fore, Style
from .adaptive_amount_manager import AdaptiveConfiguration, AdaptiveMode, create_adaptive_configuration_from_user_input

class AdaptiveConfigManager:
    """Manages adaptive amount configuration and user interface"""
    
    def __init__(self, config_file: str = "config/adaptive_config.json"):
        """Initialize configuration manager"""
        self.config_file = config_file
        self.logger = logging.getLogger(__name__)
        
    def prompt_user_for_configuration(self) -> Tuple[AdaptiveConfiguration, bool]:
        """
        Interactive prompt for adaptive amount configuration
        
        Returns:
            Tuple of (AdaptiveConfiguration, user_wants_to_continue)
        """
        try:
            print(f"\n{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}{' ' * 18}EUCLID SWAP BOT - AMOUNT CONFIGURATION{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{'='*70}{Style.RESET_ALL}")
            
            # Get initial amount from user
            while True:
                try:
                    amount_input = input(f"\n{Fore.YELLOW}Enter swap amount (minimum 0.1): {Style.RESET_ALL}").strip()
                    initial_amount = float(amount_input)
                    
                    if initial_amount < 0.1:
                        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Amount must be at least 0.1")
                        continue
                    
                    break
                    
                except ValueError:
                    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Please enter a valid number")
                    continue
            
            # Determine mode
            mode = AdaptiveMode.FIXED if initial_amount >= 1.0 else AdaptiveMode.ADAPTIVE
            
            print(f"\n{Fore.GREEN}✓ Amount: {initial_amount} PLUME{Style.RESET_ALL}")
            
            if mode == AdaptiveMode.FIXED:
                print(f"{Fore.BLUE}✓ Mode: FIXED (No auto-optimization){Style.RESET_ALL}")
                print(f"{Fore.WHITE}  - Amount ≥ 1.0 detected{Style.RESET_ALL}")
                print(f"{Fore.WHITE}  - Bot will always use {initial_amount} PLUME{Style.RESET_ALL}")
                print(f"{Fore.WHITE}  - No intelligent adjustments{Style.RESET_ALL}")
                
                # Simple confirmation for fixed mode
                while True:
                    confirm = input(f"\n{Fore.CYAN}Start bot with fixed amount? (y/n): {Style.RESET_ALL}").strip().lower()
                    if confirm in ['y', 'yes']:
                        config = AdaptiveConfiguration(initial_amount=initial_amount)
                        return config, True
                    elif confirm in ['n', 'no']:
                        return None, False
                    else:
                        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Please enter 'y' or 'n'")
            else:
                print(f"{Fore.GREEN}✓ Mode: ADAPTIVE (Auto-optimization enabled){Style.RESET_ALL}")
                print(f"{Fore.WHITE}  - Amount < 1.0 detected{Style.RESET_ALL}")
                print(f"{Fore.WHITE}  - Intelligent amount adjustment activated{Style.RESET_ALL}")
                print(f"{Fore.WHITE}  - Will find optimal amount automatically{Style.RESET_ALL}")
                
                return self._configure_adaptive_settings(initial_amount)
                
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}[CANCELLED]{Style.RESET_ALL} Configuration cancelled by user")
            return None, False
        except Exception as e:
            self.logger.error(f"Configuration error: {e}")
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Configuration failed: {e}")
            return None, False
    
    def _configure_adaptive_settings(self, initial_amount: float) -> Tuple[AdaptiveConfiguration, bool]:
        """Configure adaptive mode settings"""
        try:
            print(f"\n{Fore.CYAN}[ADAPTIVE MODE] Advanced Settings{Style.RESET_ALL}")
            print("Configure how the bot will optimize your swap amounts:")
            
            # Default settings
            settings = {
                'increment_step': 0.1,  # Changed to 0.1 for cleaner increments
                'stability_threshold': 5,
                'max_increment_attempts': 5,
                'enable_descending': True
            }
            
            print(f"\n{Fore.WHITE}Default Settings:{Style.RESET_ALL}")
            print(f"├─ Increment Step: {settings['increment_step']} tokens (increase by 0.1 on failure)")
            print(f"├─ Stability Threshold: {settings['stability_threshold']} swaps (successful swaps before optimization)")
            print(f"├─ Max Attempts: {settings['max_increment_attempts']} (maximum increases before hitting 1.0)")
            print(f"├─ Maximum Amount: 1.0 tokens (never exceed this)")
            print(f"├─ Minimum Amount: {initial_amount} tokens (your input - never go below)")
            print(f"└─ Descending Mode: {'Enabled' if settings['enable_descending'] else 'Disabled'} (optimize after finding working amount)")
            
            # Ask if user wants to modify settings
            while True:
                modify = input(f"\n{Fore.CYAN}Modify advanced settings? (y/n): {Style.RESET_ALL}").strip().lower()
                if modify in ['n', 'no']:
                    break
                elif modify in ['y', 'yes']:
                    settings = self._prompt_advanced_settings(settings)
                    break
                else:
                    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Please enter 'y' or 'n'")
            
            # Show final configuration
            print(f"\n{Fore.GREEN}[CONFIGURATION] Final Settings:{Style.RESET_ALL}")
            print(f"├─ Initial Amount: {initial_amount} tokens")
            print(f"├─ Increment Step: {settings['increment_step']} tokens")
            print(f"├─ Stability Required: {settings['stability_threshold']} successful swaps")
            print(f"├─ Max Attempts: {settings['max_increment_attempts']}")
            print(f"├─ Range: {initial_amount} - 1.0 tokens")
            print(f"└─ Optimization: {'Enabled' if settings['enable_descending'] else 'Disabled'}")
            
            print(f"\n{Fore.BLUE}[INFO] Adaptive Mode Behavior:{Style.RESET_ALL}")
            print(f"- Start with {initial_amount} tokens")
            print(f"- Increase by {settings['increment_step']} on errors ({initial_amount} → {initial_amount + settings['increment_step']:.1f} → {initial_amount + 2*settings['increment_step']:.1f}, etc.)")
            print(f"- After {settings['stability_threshold']} successful swaps, try to optimize down")
            print(f"- If minimum fails, immediately return to last working amount")
            print(f"- Range: {initial_amount} - 1.0 tokens")
            
            # Final confirmation
            while True:
                confirm = input(f"\n{Fore.CYAN}Start bot with these settings? (y/n): {Style.RESET_ALL}").strip().lower()
                if confirm in ['y', 'yes']:
                    # Create configuration
                    config = create_adaptive_configuration_from_user_input(
                        initial_amount=initial_amount,
                        **settings
                    )
                    
                    # Save configuration
                    self._save_configuration(config)
                    
                    return config, True
                elif confirm in ['n', 'no']:
                    return None, False
                else:
                    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Please enter 'y' or 'n'")
                    
        except Exception as e:
            self.logger.error(f"Adaptive configuration error: {e}")
            print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Adaptive configuration failed: {e}")
            return None, False
    
    def _prompt_advanced_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Prompt for advanced adaptive settings"""
        print(f"\n{Fore.CYAN}[ADVANCED] Configure Adaptive Settings{Style.RESET_ALL}")
        
        # Increment Step
        while True:
            try:
                current = settings['increment_step']
                new_step = input(f"Increment step [{current}]: ").strip()
                if not new_step:
                    break
                
                increment_step = float(new_step)
                if 0.01 <= increment_step <= 0.5:
                    settings['increment_step'] = increment_step
                    break
                else:
                    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Increment step must be between 0.01 and 0.5")
            except ValueError:
                print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Please enter a valid number")
        
        # Stability Threshold
        while True:
            try:
                current = settings['stability_threshold']
                new_threshold = input(f"Stability threshold (successful swaps) [{current}]: ").strip()
                if not new_threshold:
                    break
                
                threshold = int(new_threshold)
                if 1 <= threshold <= 20:
                    settings['stability_threshold'] = threshold
                    break
                else:
                    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Stability threshold must be between 1 and 20")
            except ValueError:
                print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Please enter a valid number")
        
        # Max Increment Attempts
        while True:
            try:
                current = settings['max_increment_attempts']
                new_attempts = input(f"Max increment attempts [{current}]: ").strip()
                if not new_attempts:
                    break
                
                attempts = int(new_attempts)
                if 1 <= attempts <= 10:
                    settings['max_increment_attempts'] = attempts
                    break
                else:
                    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Max attempts must be between 1 and 10")
            except ValueError:
                print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Please enter a valid number")
        
        # Descending Mode
        while True:
            current = "enabled" if settings['enable_descending'] else "disabled"
            enable_desc = input(f"Enable descending optimization? [{current}] (y/n): ").strip().lower()
            if not enable_desc:
                break
            elif enable_desc in ['y', 'yes']:
                settings['enable_descending'] = True
                break
            elif enable_desc in ['n', 'no']:
                settings['enable_descending'] = False
                break
            else:
                print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Please enter 'y' or 'n'")
        
        return settings
    
    def _save_configuration(self, config: AdaptiveConfiguration):
        """Save configuration to file"""
        try:
            # Ensure config directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            config_data = {
                'adaptive_amount': config.to_dict(),
                'saved_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'version': '1.0'
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            self.logger.info(f"[CONFIG] Saved adaptive configuration to {self.config_file}")
            
        except Exception as e:
            self.logger.error(f"[CONFIG] Failed to save configuration: {e}")
    
    def load_saved_configuration(self) -> Optional[AdaptiveConfiguration]:
        """Load saved configuration from file"""
        try:
            if not os.path.exists(self.config_file):
                return None
            
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
            
            adaptive_data = config_data.get('adaptive_amount', {})
            if not adaptive_data:
                return None
            
            # Create configuration from saved data
            config = AdaptiveConfiguration(
                initial_amount=adaptive_data.get('initial_amount', 1.0),
                increment_step=adaptive_data.get('increment_step', 0.05),
                decrement_step=adaptive_data.get('decrement_step', 0.05),
                stability_threshold=adaptive_data.get('stability_threshold', 5),
                max_increment_attempts=adaptive_data.get('max_increment_attempts', 5),
                enable_descending=adaptive_data.get('enable_descending', True)
            )
            
            # Restore runtime state if available
            config.current_amount = adaptive_data.get('current_amount', config.initial_amount)
            config.optimal_amount = adaptive_data.get('optimal_amount')
            config.tokens_saved = adaptive_data.get('tokens_saved', 0.0)
            
            self.logger.info(f"[CONFIG] Loaded adaptive configuration from {self.config_file}")
            return config
            
        except Exception as e:
            self.logger.error(f"[CONFIG] Failed to load configuration: {e}")
            return None
    
    def prompt_use_saved_configuration(self) -> bool:
        """Ask user if they want to use saved configuration"""
        try:
            saved_config = self.load_saved_configuration()
            if not saved_config:
                return False
            
            print(f"\n{Fore.CYAN}[SAVED CONFIG] Found previous adaptive configuration:{Style.RESET_ALL}")
            print(f"├─ Mode: {saved_config.mode.value.upper()}")
            print(f"├─ Initial Amount: {saved_config.initial_amount} PLUME")
            print(f"├─ Current Amount: {saved_config.current_amount} PLUME")
            
            if saved_config.optimal_amount:
                savings = ((1.0 - saved_config.optimal_amount) / 1.0) * 100
                print(f"├─ Optimal Found: {saved_config.optimal_amount} PLUME ({savings:.1f}% savings)")
            
            print(f"└─ Total Savings: {saved_config.tokens_saved:.3f} PLUME")
            
            while True:
                use_saved = input(f"\n{Fore.CYAN}Use saved configuration? (y/n): {Style.RESET_ALL}").strip().lower()
                if use_saved in ['y', 'yes']:
                    return True
                elif use_saved in ['n', 'no']:
                    return False
                else:
                    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Please enter 'y' or 'n'")
                    
        except Exception as e:
            self.logger.error(f"Error checking saved configuration: {e}")
            return False
    
    def get_quick_start_configuration(self, amount: float) -> AdaptiveConfiguration:
        """Get configuration for quick start without prompts"""
        return create_adaptive_configuration_from_user_input(
            initial_amount=amount,
            increment_step=0.05,
            stability_threshold=5,
            max_increment_attempts=5,
            enable_descending=True
        )

def create_error_classifier():
    """Create error classification utility"""
    from .adaptive_amount_manager import AdaptiveAmountManager
    
    def classify_swap_error(error_message: str, error_code: Optional[str] = None) -> Tuple[str, bool]:
        """
        Classify swap error and determine if amount adjustment is needed
        
        Args:
            error_message: Error message from swap
            error_code: Optional error code
            
        Returns:
            Tuple of (error_type, should_adjust_amount)
        """
        if not error_message:
            return "UNKNOWN_ERROR", False
        
        error_msg_upper = error_message.upper()
        
        # Check for amount-sensitive errors
        amount_keywords = [
            'INSUFFICIENT_LIQUIDITY', 'LIQUIDITY', 'SLIPPAGE', 'MINIMUM_AMOUNT',
            'ROUTE_NOT_FOUND', 'NO_ROUTE', 'PRICE_IMPACT', 'OUTPUT_AMOUNT',
            'SWAP_AMOUNT_TOO_SMALL', 'BELOW_MINIMUM', 'INSUFFICIENT_OUTPUT'
        ]
        
        for keyword in amount_keywords:
            if keyword in error_msg_upper:
                return keyword.replace('_', ' '), True
        
        # Check for infrastructure errors
        infra_keywords = [
            'TIMEOUT', 'NETWORK', 'RPC', 'NONCE', 'GAS', 'CONNECTION',
            'TRANSACTION_FAILED', 'REVERTED', 'REJECTED'
        ]
        
        for keyword in infra_keywords:
            if keyword in error_msg_upper:
                return keyword.replace('_', ' '), False
        
        # Default to amount-sensitive for unknown errors (conservative approach)
        return "UNKNOWN_AMOUNT_ERROR", True
    
    return classify_swap_error

import time
