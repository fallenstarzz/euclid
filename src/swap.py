"""
Swap Execution Module
Handles swap building, execution, and monitoring
"""

import json
import time
import logging
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
import requests
from colorama import Fore, Style

from .wallet import WalletManager

class SwapExecutor:
    """Handles swap execution via Euclid API and blockchain"""
    
    def __init__(self, wallet: WalletManager, config: Dict[str, Any]):
        """Initialize swap executor"""
        self.wallet = wallet
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # API endpoints
        self.api_base = config["api_base"]
        self.swap_endpoint = f"{self.api_base}/api/v1/execute/astro/swap"
        self.track_endpoint = f"{self.api_base}/api/v1/txn/track/swap"
        
        # Session for API calls
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        
        # Swap state
        self.current_direction = "A_TO_B"  # A_TO_B or B_TO_A
        self.last_swap_details = {}
        
    def calculate_swap_route(self, token_in: str, token_out: str, amount_in: int) -> Optional[Dict[str, Any]]:
        """Calculate optimal swap route before executing"""
        try:
            self.logger.info(f"Calculating route for {amount_in} wei {token_in} -> {token_out}")
            
            payload = {
                "amount_in": str(amount_in),
                "chain_uids": [],  # Empty array for all chains
                "external": True,
                "token_in": token_in,  # "plume" for native
                "token_out": token_out  # "stt" or other token
            }
            
            response = requests.post(
                f"{self.config['api_base']}/api/v1/routes?limit=10",
                json=payload,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Content-Type": "application/json",
                    "Origin": "https://testnet.euclidswap.io",
                    "Referer": "https://testnet.euclidswap.io/",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "cross-site"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("paths") and len(data["paths"]) > 0:
                    best_route = data["paths"][0]
                    route_path = best_route['path'][0]['route']
                    expected_out = best_route['path'][0]['amount_out']
                    self.logger.info(f"Route found: {' -> '.join(route_path)}")
                    self.logger.info(f"Expected output: {expected_out} wei")
                    return data  # Return full data structure
                else:
                    self.logger.warning("No routes available")
                    return None
            else:
                self.logger.error(f"[ROUTE_CALC_ERROR] {response.status_code} - {response.text}")
                self.logger.error(f"[ROUTE_CALC_PAYLOAD] {json.dumps(payload, indent=2)}")
                return None
                
        except Exception as e:
            self.logger.error(f"Route calculation error: {e}")
            return None
        
    def build_swap_transaction(self, token_in: str, token_out: str, amount_in: str, route_data: Dict = None) -> Optional[Dict[str, Any]]:
        """
        Build swap transaction with complete GraphQL-structured payload
        
        Args:
            token_in: Input token address or "plume" for native
            token_out: Output token address or token symbol
            amount_in: Amount to swap (in wei)
            route_data: Pre-calculated route data
            
        Returns:
            Transaction data from API
        """
        try:
            # First calculate route if not provided
            if not route_data:
                route_data = self.calculate_swap_route(token_in, token_out, int(amount_in))
                if not route_data:
                    self.logger.error("Failed to calculate route")
                    return None
            
            # Extract route info from the corrected structure
            paths = route_data["paths"][0]
            path_info = paths["path"][0]
            expected_out = path_info["amount_out"]
            route_tokens = path_info["route"]
            
            self.logger.info(f"Building swap transaction with route: {' -> '.join(route_tokens)}")
            
            # Determine source and destination chains based on token types
            if token_in.lower() == "stt":
                # STT -> PLUME: source=somnia, dest=plume
                source_chain = "somnia"
                dest_chain = "plume"
            elif token_out.lower() == "stt":
                # PLUME -> STT: source=plume, dest=somnia  
                source_chain = "plume"
                dest_chain = "somnia"
            else:
                # Default fallback
                source_chain = "plume"
                dest_chain = "plume"
            
            # Build GraphQL-structured asset_in based on token type
            if token_in.lower() in ["plume", "native"]:
                # Native PLUME token
                asset_in = {
                    "token": "plume",
                    "token_type": {
                        "__typename": "NativeTokenType",
                        "native": {
                            "__typename": "NativeToken",
                            "denom": "plume"
                        }
                    }
                }
            elif token_in.lower() == "stt":
                # STT is a special cross-chain token from Somnia
                asset_in = {
                    "token": "stt",
                    "token_type": {
                        "__typename": "NativeTokenType",
                        "native": {
                            "__typename": "NativeToken", 
                            "denom": "stt"
                        }
                    }
                }
            else:
                # For other smart contract tokens
                asset_in = {
                    "token": token_in,
                    "token_type": {
                        "__typename": "SmartTokenType",
                        "smart": {
                            "__typename": "SmartToken",
                            "contract_address": token_in
                        }
                    }
                }
            
            # Build complete GraphQL-structured payload with TOP-LEVEL cross_chain_addresses
            payload = {
                "amount_in": str(amount_in),
                "asset_in": asset_in,
                "cross_chain_addresses": [{
                    "user": {
                        "address": self.wallet.get_address().lower(),
                        "chain_uid": dest_chain  # CRITICAL: destination chain
                    },
                    "limit": {
                        "less_than_or_equal": expected_out  # CRITICAL: from route calculation
                    }
                }],
                "sender": {
                    "address": self.wallet.get_address().lower(),
                    "chain_uid": source_chain  # Dynamic: "plume" or "somnia" based on input token
                },
                "slippage": "500",  # 5% in basis points
                "swap_path": {
                    "path": [{
                        "route": route_tokens,
                        "dex": path_info.get("dex", "euclid"),
                        "amount_in": str(amount_in),
                        "amount_out": expected_out,
                        "chain_uid": "vsl",  # VSL is always the intermediary chain for cross-chain swaps
                        "amount_out_for_hops": path_info.get("amount_out_for_hops", [])
                    }],
                    "total_price_impact": "0.00"
                },
                "partnerFee": {
                    "partner_fee_bps": 10,
                    "recipient": ""
                }
            }
            
            # Log payload for debugging
            self.logger.debug(f"GraphQL-structured payload: {json.dumps(payload, indent=2)}")
            
            response = self.session.post(
                f"{self.config['api_base']}/api/v1/execute/astro/swap",
                json=payload,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Content-Type": "application/json",
                    "Origin": "https://testnet.euclidswap.io",
                    "Referer": "https://testnet.euclidswap.io/",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
                    "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
                    "sec-ch-ua-mobile": "?0",
                    "sec-ch-ua-platform": '"Windows"',
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "cross-site"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                self.logger.info(f"Swap transaction built successfully")
                # Add expected output for tracking
                data["expected_amount_out"] = expected_out
                data["route_info"] = route_data
                return data
            else:
                self.logger.error(f"[SWAP_BUILD_ERROR] {response.status_code} - {response.text}")
                self.logger.error(f"[SWAP_BUILD_PAYLOAD] {json.dumps(payload, indent=2)}")
                return None
                
        except Exception as e:
            self.logger.error(f"Build error: {e}")
            return None
    
    def execute_simple_swap(self, token_in: str, token_out: str, amount_in: int) -> bool:
        """
        Execute complete swap using the discovered API flow: route calculation -> build -> execute
        
        Args:
            token_in: Input token ("plume" for native)
            token_out: Output token (e.g., "stt")
            amount_in: Amount in wei
            
        Returns:
            True if swap successful, False otherwise
        """
        try:
            # Step 1: Calculate optimal route
            self.logger.info(f"🧮 Step 1: Calculating route for {amount_in} wei {token_in} -> {token_out}")
            route_data = self.calculate_swap_route(token_in, token_out, amount_in)
            
            if not route_data:
                self.logger.error("[ERROR] Route calculation failed")
                return False
                
            # Extract route info for display
            path = route_data["path"][0]
            route_tokens = path["tokens"]
            expected_out = path["amount_out"]
            
            self.logger.info(f"📍 Route found: {' -> '.join(route_tokens)}")
            self.logger.info(f"[STATS] Expected output: {expected_out} wei")
            
            # Step 2: Build swap transaction
            self.logger.info(f"🔨 Step 2: Building swap transaction...")
            swap_data = self.build_swap_transaction(token_in, token_out, str(amount_in), route_data)
            
            if not swap_data:
                self.logger.error("[ERROR] Transaction build failed")
                return False
                
            # Step 3: Execute transaction
            self.logger.info(f"⚡ Step 3: Executing transaction...")
            
            # Extract transaction data
            tx_data = swap_data.get("transaction")
            if not tx_data:
                self.logger.error("[ERROR] No transaction data received")
                return False
                
            # Sign and send transaction
            tx_hash = self.wallet.send_transaction(tx_data)
            
            if tx_hash:
                self.logger.info(f"[OK] Swap executed! Hash: {tx_hash}")
                
                # Wait for confirmation
                if self.wallet.wait_for_confirmation(tx_hash):
                    self.logger.info(f"🎉 Transaction confirmed!")
                    
                    # Store for tracking
                    self.last_swap = {
                        "tx_hash": tx_hash,
                        "timestamp": time.time(),
                        "token_in": token_in,
                        "token_out": token_out,
                        "amount_in": amount_in,
                        "expected_out": expected_out,
                        "route": route_tokens
                    }
                    
                    return True
                else:
                    self.logger.warning("[WARN] Transaction confirmation timeout")
                    return False
            else:
                self.logger.error("[ERROR] Transaction execution failed")
                return False
                
        except Exception as e:
            self.logger.error(f"[ERROR] Swap execution failed: {e}")
            return False

    def execute_swap(self, token_pair=None, amount: str = None, direction=None, token_in=None, token_out=None) -> Optional[str]:
        """
        Execute a complete swap operation - supports both legacy and bi-directional modes
        
        Args:
            token_pair: Dict with token_a/token_b or tuple like ("plume", "stt") [LEGACY]
            amount: Amount to swap [LEGACY]
            direction: Swap direction for bi-directional mode [NEW]
            token_in: Input token for bi-directional mode [NEW]
            token_out: Output token for bi-directional mode [NEW]
            
        Returns:
            Transaction hash if successful, None otherwise
        """
        try:
            # Bi-directional mode (NEW)
            if token_in and token_out and amount:
                self.logger.info(f"[BI-DIRECTIONAL] Executing {token_in.upper()} -> {token_out.upper()}")
                return self._execute_bi_directional_swap(token_in, token_out, amount)
            
            # Legacy mode (OLD) - handle both dict and tuple formats
            if isinstance(token_pair, tuple):
                # Convert tuple to dict format for internal processing
                token_in_legacy, token_out_legacy = token_pair
                symbol_in, symbol_out = token_pair
                
                # For simplicity, use the token names as both addresses and symbols
                token_pair_dict = {
                    "token_a": token_in_legacy,
                    "token_b": token_out_legacy,
                    "symbol_a": symbol_in,
                    "symbol_b": symbol_out
                }
                token_pair = token_pair_dict
            
            # FIXED: Always do PLUME -> STT (A->B), no direction toggle
            token_in_legacy = token_pair["token_a"]
            token_out_legacy = token_pair["token_b"]
            symbol_in = token_pair["symbol_a"]
            symbol_out = token_pair["symbol_b"]
            
            self.logger.info(f"[LEGACY] Executing {symbol_in.upper()} -> {symbol_out.upper()}")
            return self._execute_bi_directional_swap(token_in_legacy, token_out_legacy, amount)
            
        except Exception as e:
            self.logger.error(f"[ERROR] Swap execution failed: {e}")
            return None
    
    def _execute_bi_directional_swap(self, token_in: str, token_out: str, amount: str) -> Optional[str]:
        """
        Internal method to execute bi-directional swap
        
        Args:
            token_in: Input token ("plume" or "stt")
            token_out: Output token ("stt" or "plume") 
            amount: Amount to swap in wei
            
        Returns:
            Transaction hash if successful, None otherwise
        """
        try:
            # Determine swap direction for logging
            direction_display = f"{token_in.upper()} → {token_out.upper()}"
            
            # Build swap transaction
            swap_data = self.build_swap_transaction(token_in, token_out, amount)
            
            if not swap_data:
                return None
            
            # Check if this is a simulated/quote response or actual transaction
            if "transaction" in swap_data:
                # Extract transaction details
                tx_data = swap_data["transaction"]
                
                # Prepare transaction for signing
                transaction = {
                    "to": tx_data.get("to"),
                    "value": int(tx_data.get("value", "0")),
                    "data": tx_data.get("data", "0x"),
                    "gas": self.config["gas_limit"],
                    "gasPrice": self.wallet.get_gas_price(),
                    "nonce": self.wallet.get_nonce()
                }
                
                # Send transaction
                tx_hash = self.wallet.send_transaction(transaction)
                
                # Wait for confirmation
                receipt = self.wallet.wait_for_confirmation(tx_hash, timeout=300)
                
                if receipt:
                    self.logger.info(f"[OK] {direction_display} swap confirmed: {tx_hash}")
                    return tx_hash
                else:
                    self.logger.error(f"[ERROR] {direction_display} swap failed or timeout: {tx_hash}")
                    return None
            else:
                # This is swap data from API - execute real transaction
                self.logger.info(f"[SUCCESS] {direction_display} swap data received from API")
                
                try:
                    # Execute the real transaction using wallet manager with network switching
                    self.logger.info(f"[PROCESS] Executing swap transaction for {token_in.upper()}...")
                    tx_hash = self.wallet.execute_swap_transaction(swap_data, token_in)
                    
                    # Wait for confirmation
                    self.logger.info("[WAIT] Waiting for transaction confirmation...")
                    receipt = self.wallet.wait_for_confirmation(tx_hash, timeout=300)
                    
                    if receipt and receipt.get('status') == 1:
                        self.logger.info(f"[SUCCESS] {direction_display} swap confirmed in block {receipt.get('blockNumber')}")
                        self.logger.info(f"[SUCCESS] Transaction hash: {tx_hash}")
                        
                        # ENHANCED: Register to Intract for points (BOTH DIRECTIONS)
                        # Determine correct chain_uid based on token input
                        if token_in.lower() == "stt":
                            chain_uid = "somnia"  # STT transactions on Somnia network
                            swap_type = "STT→PLUME"
                        else:
                            chain_uid = "plume"   # PLUME transactions on Plume network  
                            swap_type = "PLUME→STT"
                        
                        self.logger.info(f"[PROCESS] Registering {swap_type} swap for points...")
                        intract_success = self.wallet.register_swap_to_intract(tx_hash, chain_uid)
                        
                        if intract_success:
                            # Verify points registration
                            self.logger.info("[PROCESS] Verifying points registration...")
                            verification = self.wallet.verify_points_registration(tx_hash)
                            
                            if verification:
                                points = verification.get('operations', 'Unknown')
                                status = verification.get('status', 'Unknown')
                                self.logger.info(f"[SUCCESS] {swap_type} Points awarded: {points} (Status: {status})")
                            else:
                                self.logger.warning(f"[WARNING] {swap_type} Points verification pending - may take longer to process")
                        else:
                            self.logger.warning(f"[WARNING] {swap_type} swap successful but points registration failed")
                        
                        return tx_hash
                    else:
                        self.logger.error(f"[ERROR] {direction_display} transaction failed or reverted: {tx_hash}")
                        return None
                        
                except Exception as e:
                    self.logger.error(f"[ERROR] {direction_display} real transaction execution failed: {e}")
                    return None
                
        except Exception as e:
            self.logger.error(f"[ERROR] {direction_display} swap execution failed: {e}")
            return None
    
    def _ensure_token_approval(self, token_address: str, amount: str) -> bool:
        """Ensure token is approved for spending"""
        try:
            # Skip approval for ETH
            if token_address == "0x0000000000000000000000000000000000000000":
                return True
            
            # Check current allowance (using a common router address)
            router_address = "0x123...ROUTER_ADDRESS"  # Update with actual router
            allowance = self.wallet.check_allowance(token_address, router_address)
            required_amount = Decimal(amount) / Decimal(10**18)
            
            if allowance >= required_amount:
                self.logger.info("[OK] Token already approved")
                return True
            
            # Need approval
            self.logger.info("🔓 Approving token spending...")
            approve_tx = self.wallet.approve_token(token_address, router_address)
            
            # Wait for approval confirmation
            receipt = self.wallet.wait_for_confirmation(approve_tx, timeout=180)
            
            if receipt:
                self.logger.info("[OK] Token approval confirmed")
                return True
            else:
                self.logger.error("[ERROR] Token approval failed")
                return False
                
        except Exception as e:
            self.logger.error(f"[ERROR] Approval check failed: {e}")
            return False
    
    def get_swap_quote(self, token_in: str, token_out: str, amount_in: str) -> Optional[Dict[str, Any]]:
        """Get swap quote without executing"""
        try:
            # Similar to build_swap but for quote only
            payload = {
                "chain": self.config["chain"],
                "dex": self.config["dex"],
                "token_in": token_in,
                "token_out": token_out,
                "amount_in": amount_in,
                "slippage": self.config["slippage"],
                "sender": self.wallet.get_address(),
                "quote_only": True
            }
            
            response = self.session.post(
                self.swap_endpoint,
                json=payload,
                timeout=15
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.warning(f"[WARN] Quote failed: {response.status_code}")
                return None
                
        except Exception as e:
            self.logger.warning(f"[WARN] Quote error: {e}")
            return None
    
    def calculate_optimal_amount(self, token_pair: Dict[str, str]) -> str:
        """Calculate optimal swap amount based on balance"""
        try:
            # Get current token for swapping
            if self.current_direction == "A_TO_B":
                token_address = token_pair["token_a"]
                symbol = token_pair["symbol_a"]
            else:
                token_address = token_pair["token_b"]
                symbol = token_pair["symbol_b"]
            
            balance = self.wallet.get_balance(token_address, force_refresh=True)
            
            # Use configured amount or 10% of balance, whichever is smaller
            configured_amount = Decimal(self.config["swap_amount"]) / Decimal(10**18)
            balance_percentage = balance * Decimal("0.1")
            
            amount = min(configured_amount, balance_percentage)
            
            # Convert back to wei
            amount_wei = str(int(amount * Decimal(10**18)))
            
            self.logger.info(f"[AMOUNT] Calculated swap amount: {amount} {symbol} ({amount_wei} wei)")
            return amount_wei
            
        except Exception as e:
            self.logger.error(f"[ERROR] Amount calculation failed: {e}")
            return self.config["swap_amount"]
    
    def get_token_info(self, token_address: str) -> Dict[str, Any]:
        """Get token information"""
        try:
            # This would typically call a token info API
            # For now, return basic info
            return {
                "address": token_address,
                "symbol": "UNKNOWN",
                "decimals": 18,
                "balance": float(self.wallet.get_balance(token_address))
            }
        except Exception as e:
            self.logger.error(f"[ERROR] Token info failed: {e}")
            return {}
    
    def get_status(self) -> Dict[str, Any]:
        """Get swap executor status"""
        return {
            "current_direction": self.current_direction,
            "wallet_address": self.wallet.get_address(),
            "connected": True
        }
