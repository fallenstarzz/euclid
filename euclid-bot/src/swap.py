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

    def _determine_chains_for_tokens(self, token_in: str, token_out: str) -> Tuple[str, str]:
        """Map token pair to source/destination chain uids."""
        tin = (token_in or "").lower()
        tout = (token_out or "").lower()
        if tin == "phrs" and tout == "eth":
            return "pharos", "unichain"
        if tin == "eth" and tout == "phrs":
            return "unichain", "pharos"
        if tin == "stt":
            return "somnia", "plume"
        if tout == "stt":
            return "plume", "somnia"
        return "plume", "plume"

    def _build_asset_in(self, token_in: str) -> Dict[str, Any]:
        """Build GraphQL-structured asset_in for native tokens (phrs/eth/plume/stt)."""
        t = (token_in or "").lower()
        native_tokens = {"plume", "stt", "phrs", "eth", "native"}
        if t in native_tokens:
            denom = "plume" if t == "native" else t
            return {
                "token": denom,
                "token_type": {
                    "__typename": "NativeTokenType",
                    "native": {
                        "__typename": "NativeToken",
                        "denom": denom
                    }
                }
            }
        # Fallback smart token
        return {
            "token": token_in,
            "token_type": {
                "__typename": "SmartTokenType",
                "smart": {
                    "__typename": "SmartToken",
                    "contract_address": token_in
                }
            }
        }

    def track_swap_immediate(self, source_chain: str, tx_hash: str, meta: str) -> bool:
        """Immediately register swap with backend tracking using meta."""
        try:
            payload = {
                "chain": source_chain,
                "tx_hash": tx_hash,
                "meta": meta
            }
            resp = self.session.post(self.track_endpoint, json=payload, timeout=20)
            if resp.status_code == 200:
                self.logger.info("[TRACK] Immediate backend tracking submitted")
                return True
            self.logger.warning(f"[TRACK] Backend tracking failed: {resp.status_code} - {resp.text}")
            return False
        except Exception as e:
            self.logger.warning(f"[TRACK] Immediate tracking error: {e}")
            return False

    def poll_cross_chain_status(self, tx_hash: str, source_chain: str, timeout_seconds: int = 120, interval_seconds: int = 5) -> Dict[str, Any]:
        """
        Best-effort IBC status polling via transactions filter endpoint.
        Returns a dict with basic status fields.
        """
        end_time = time.time() + max(10, timeout_seconds)
        last_status = {"status": "pending"}
        verify_url = f"{self.api_base}/api/v1/intract/transactions/filter"

        while time.time() < end_time:
            try:
                # Try GET by wallet address first
                params = {"wallet_address": self.wallet.get_address().lower()}
                r = self.session.get(verify_url, params=params, timeout=20)
                if r.status_code == 200:
                    data = r.json()
                    items = data.get('data') or data.get('transactions') or []
                    for tx in items:
                        h1 = (tx.get('txn_hash') or tx.get('hash') or '').lower()
                        if h1 == (tx_hash or '').lower():
                            # Found entry
                            status = (tx.get('status') or 'pending').lower()
                            last_status = {"status": status, "raw": tx}
                            self.logger.info(f"[IBC] Status: {status}")
                            if status in ("success", "completed", "confirm", "confirmed"):
                                return last_status
                            break
                # Fallback POST by address for some variants
                r2 = self.session.post(verify_url, json={"address": self.wallet.get_address().lower(), "limit": 50}, timeout=20)
                if r2.status_code == 200:
                    data2 = r2.json()
                    items2 = data2.get('data') or data2.get('transactions') or []
                    for tx in items2:
                        h2 = (tx.get('txn_hash') or tx.get('hash') or '').lower()
                        if h2 == (tx_hash or '').lower():
                            status = (tx.get('status') or 'pending').lower()
                            last_status = {"status": status, "raw": tx}
                            self.logger.info(f"[IBC] Status: {status}")
                            if status in ("success", "completed", "confirm", "confirmed"):
                                return last_status
                            break
            except Exception:
                pass

            time.sleep(interval_seconds)
        return last_status

    def execute_cross_chain_swap(self, token_in: str, token_out: str, amount_in: int) -> Optional[str]:
        """
        Execute PHRS ↔ ETH cross-chain swaps (Pharos ↔ Unichain) with meta tracking.
        amount_in is wei of the source/native token.
        """
        try:
            # 1) Route discovery
            self.logger.info(f"[ROUTE] {token_in.upper()} → {token_out.upper()} for {amount_in} wei")
            route_payload = {
                "external": True,
                "token_in": token_in,
                "token_out": token_out,
                "amount_in": str(amount_in),
                "chain_uids": []
            }
            route_resp = self.session.post(
                f"{self.config['api_base']}/api/v1/routes?limit=10",
                json=route_payload,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json",
                    "Origin": "https://testnet.euclidswap.io",
                    "Referer": "https://testnet.euclidswap.io/",
                    "User-Agent": "Mozilla/5.0"
                },
                timeout=30
            )
            if route_resp.status_code != 200:
                self.logger.error(f"[ROUTE] Failed: {route_resp.status_code} - {route_resp.text}")
                return None
            route_data = route_resp.json()
            if not route_data.get("paths"):
                self.logger.warning("[ROUTE] No paths returned")
                return None
            best_path = route_data["paths"][0]["path"][0]
            expected_out = best_path["amount_out"]
            route_tokens = best_path["route"]
            self.logger.info(f"[ROUTE] Path: {' -> '.join(route_tokens)} | expected_out={expected_out}")

            # 2) Build execute payload
            source_chain, dest_chain = self._determine_chains_for_tokens(token_in, token_out)
            asset_in = self._build_asset_in(token_in)
            execute_payload = {
                "amount_in": str(amount_in),
                "asset_in": asset_in,
                "slippage": "500",
                "sender": {
                    "address": self.wallet.get_address().lower(),
                    "chain_uid": source_chain
                },
                "cross_chain_addresses": [{
                    "user": {
                        "address": self.wallet.get_address().lower(),
                        "chain_uid": dest_chain
                    },
                    "limit": {"less_than_or_equal": expected_out}
                }],
                "swap_path": {
                    "path": [{
                        "route": route_tokens,
                        "dex": best_path.get("dex", "euclid"),
                        "amount_in": str(amount_in),
                        "amount_out": expected_out,
                        "chain_uid": "vsl",
                        "amount_out_for_hops": best_path.get("amount_out_for_hops", [])
                    }]
                },
                "partnerFee": {"partner_fee_bps": 10, "recipient": ""}
            }

            exec_resp = self.session.post(
                self.swap_endpoint,
                json=execute_payload,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Content-Type": "application/json",
                    "Origin": "https://testnet.euclidswap.io",
                    "Referer": "https://testnet.euclidswap.io/",
                    "User-Agent": "Mozilla/5.0"
                },
                timeout=45
            )
            if exec_resp.status_code != 200:
                self.logger.error(f"[EXECUTE] Failed: {exec_resp.status_code} - {exec_resp.text}")
                return None
            exec_data = exec_resp.json()
            meta = exec_data.get("meta", "")
            if not exec_data.get("msgs"):
                self.logger.error("[EXECUTE] Missing msgs in response")
                return None

            # 3) Submit transaction on source chain
            self.logger.info("[TX] Submitting transaction to source chain")
            tx_hash = self.wallet.execute_swap_transaction(exec_data, token_in, wait_for_receipt=True)
            if not tx_hash:
                self.logger.error("[TX] Submission failed")
                return None
            self.logger.info(f"[TX] Sent: {tx_hash}")

            # 4) Immediate backend tracking with meta
            self.track_swap_immediate(source_chain, tx_hash, meta)

            # 5) Register for frontend history/points
            try:
                self.wallet.register_swap_to_intract(tx_hash, source_chain)
            except Exception:
                pass

            # Skipping IBC detailed polling to avoid slow UX

            return tx_hash
        except Exception as e:
            self.logger.error(f"[CROSS-CHAIN] Execution error: {e}")
            return None
        
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
            self.logger.info(f"[DEBUG] build_swap_transaction called:")
            self.logger.info(f"[DEBUG] - Token In: {token_in}")
            self.logger.info(f"[DEBUG] - Token Out: {token_out}")
            self.logger.info(f"[DEBUG] - Amount: {amount_in} wei")
            self.logger.info(f"[DEBUG] - Route Data Provided: {route_data is not None}")
            
            # First calculate route if not provided
            if not route_data:
                self.logger.info(f"[DEBUG] Calculating route...")
                route_data = self.calculate_swap_route(token_in, token_out, int(amount_in))
                if not route_data:
                    self.logger.error(f"[DEBUG] BUILD FAILURE: calculate_swap_route returned None")
                    self.logger.error(f"[DEBUG] - Token In: {token_in}")
                    self.logger.error(f"[DEBUG] - Token Out: {token_out}")
                    self.logger.error(f"[DEBUG] - Amount: {amount_in} wei")
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
            self.logger.info(f"[DEBUG] Starting {direction_display} swap execution...")
            
            # Build swap transaction
            self.logger.info(f"[DEBUG] Step 1: Building transaction data...")
            swap_data = self.build_swap_transaction(token_in, token_out, amount)
            
            if not swap_data:
                self.logger.error(f"[DEBUG] FAILURE POINT 1: build_swap_transaction returned None")
                self.logger.error(f"[DEBUG] - Token In: {token_in}")
                self.logger.error(f"[DEBUG] - Token Out: {token_out}")
                self.logger.error(f"[DEBUG] - Amount: {amount} wei")
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
                    self.logger.error(f"[DEBUG] FAILURE POINT 2: Transaction confirmation failed/timeout")
                    self.logger.error(f"[DEBUG] - TX Hash: {tx_hash}")
                    self.logger.error(f"[DEBUG] - Direction: {direction_display}")
                    return None
            else:
                # This is swap data from API - execute real transaction
                self.logger.info(f"[DEBUG] Step 2: Swap data received from API, executing...")
                
                try:
                    # Execute the real transaction using wallet manager with network switching
                    self.logger.info(f"[DEBUG] Step 3: Calling wallet.execute_swap_transaction...")
                    tx_hash = self.wallet.execute_swap_transaction(swap_data, token_in)
                    
                    if not tx_hash:
                        self.logger.error(f"[DEBUG] FAILURE POINT 3: wallet.execute_swap_transaction returned None")
                        self.logger.error(f"[DEBUG] - Direction: {direction_display}")
                        return None
                    
                    # Wait for confirmation
                    self.logger.info(f"[DEBUG] Step 4: Waiting for confirmation of TX: {tx_hash[:10]}...")
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
                        self.logger.error(f"[DEBUG] FAILURE POINT 4: Transaction confirmation failed/timeout")
                        self.logger.error(f"[DEBUG] - TX Hash: {tx_hash}")
                        self.logger.error(f"[DEBUG] - Direction: {direction_display}")
                        self.logger.error(f"[DEBUG] - Receipt: {receipt}")
                        if receipt:
                            self.logger.error(f"[DEBUG] - Status: {receipt.get('status')}")
                            self.logger.error(f"[DEBUG] - Block: {receipt.get('blockNumber')}")
                        return None
                        
                except Exception as e:
                    self.logger.error(f"[DEBUG] FAILURE POINT 5: Exception during transaction execution")
                    self.logger.error(f"[DEBUG] - Direction: {direction_display}")
                    self.logger.error(f"[DEBUG] - Exception: {e}")
                    self.logger.error(f"[DEBUG] - Exception Type: {type(e).__name__}")
                    import traceback
                    self.logger.error(f"[DEBUG] - Traceback: {traceback.format_exc()}")
                    return None
                
        except Exception as e:
            self.logger.error(f"[DEBUG] FAILURE POINT 6: Exception in _execute_bi_directional_swap")
            self.logger.error(f"[DEBUG] - Direction: {direction_display}")
            self.logger.error(f"[DEBUG] - Exception: {e}")
            self.logger.error(f"[DEBUG] - Exception Type: {type(e).__name__}")
            import traceback
            self.logger.error(f"[DEBUG] - Traceback: {traceback.format_exc()}")
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
