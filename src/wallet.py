"""
Wallet Management Module
Handles private key operations, signing, and balance management
"""

import os
import json
from typing import Optional, Dict, Any
from decimal import Decimal
from web3 import Web3
from eth_account import Account
from eth_account.signers.local import LocalAccount
from colorama import Fore, Style
import logging

class WalletManager:
    """Secure wallet operations for Euclid bot with multi-network support"""
    
    def __init__(self, private_key: str, rpc_url: str):
        """Initialize wallet with private key and multi-network RPC connections"""
        self.logger = logging.getLogger(__name__)
        
        # Network configurations
        self.networks = {
            "plume": {
                "rpc_url": "https://testnet-rpc.plume.org",
                "chain_id": 98867,
                "name": "Plume Testnet",
                "native_token": "PLUME"
            },
            "somnia": {
                "rpc_url": "https://dream-rpc.somnia.network/",
                "chain_id": 50312,
                "name": "Somnia Network",
                "native_token": "STT"
            }
        }
        
        # Setup default Web3 connection (Plume)
        self.current_network = "plume"
        self.w3_connections = {}
        
        # Initialize all network connections
        for network_name, network_config in self.networks.items():
            try:
                w3 = Web3(Web3.HTTPProvider(network_config["rpc_url"]))
                if w3.is_connected():
                    self.w3_connections[network_name] = w3
                    self.logger.info(f"[SUCCESS] Connected to {network_config['name']}")
                else:
                    self.logger.warning(f"[WARNING] Failed to connect to {network_config['name']}")
            except Exception as e:
                self.logger.error(f"[ERROR] {network_config['name']} connection failed: {e}")
        
        # Set primary connection to Plume (default)
        self.w3 = self.w3_connections.get("plume")
        if not self.w3:
            raise ConnectionError("Failed to connect to default Plume network")
        
        # Validate and format private key
        from .utils import validate_private_key
        try:
            formatted_key = validate_private_key(private_key)
            self.account: LocalAccount = Account.from_key(formatted_key)
            self.address = self.account.address
            self.logger.info(f"[SUCCESS] Multi-network wallet loaded: {self.address}")
        except Exception as e:
            raise ValueError(f"Invalid private key: {e}")
        
        # Cache for balances and nonces per network
        self._balance_cache = {}
        self._nonce_cache = {}
    
    def switch_network(self, token_type: str):
        """Switch active network based on token type"""
        if token_type.lower() == "stt":
            target_network = "somnia"
        else:
            target_network = "plume"
            
        if target_network != self.current_network:
            if target_network in self.w3_connections:
                self.w3 = self.w3_connections[target_network]
                self.current_network = target_network
                network_info = self.networks[target_network]
                self.logger.info(f"[NETWORK SWITCH] Switched to {network_info['name']} for {token_type.upper()} transactions")
                return True
            else:
                self.logger.error(f"[ERROR] Network {target_network} not available")
                return False
        return True
        
    def get_address(self) -> str:
        """Get wallet address"""
        return self.address
    
    def get_balance(self, token_address: Optional[str] = None, force_refresh: bool = False) -> Decimal:
        """
        Get balance for ETH or ERC20 token with cross-chain handling
        
        Args:
            token_address: Token contract address (None for ETH)
            force_refresh: Skip cache and fetch fresh balance
        """
        cache_key = token_address or "ETH"
        
        if not force_refresh and cache_key in self._balance_cache:
            return self._balance_cache[cache_key]
        
        try:
            # Skip balance check for cross-chain tokens
            if token_address and token_address.lower() in ['stt', 'somnia']:
                return Decimal('0')  # Return 0 for cross-chain tokens
                
            if token_address is None or token_address.lower() in ["native", "plume", "eth"]:
                # Get native token balance (ETH/PLUME)
                balance_wei = self.w3.eth.get_balance(self.address)
                balance = Decimal(self.w3.from_wei(balance_wei, 'ether'))
            else:
                # ERC20 token balance
                from web3 import Web3
                if not Web3.is_address(token_address):
                    return Decimal('0')
                    
                token_contract = self.w3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=self._get_erc20_abi()
                )
                balance_raw = token_contract.functions.balanceOf(self.address).call()
                decimals = token_contract.functions.decimals().call()
                balance = Decimal(balance_raw) / Decimal(10 ** decimals)
            
            # Cache the balance
            self._balance_cache[cache_key] = balance
            return balance
            
        except Exception:
            # Silent error - return 0
            return Decimal('0')
    
    def get_nonce(self, force_refresh: bool = False) -> int:
        """Get current nonce for transaction on active network"""
        network_key = self.current_network
        if not force_refresh and network_key in self._nonce_cache:
            return self._nonce_cache[network_key]
        
        try:
            nonce = self.w3.eth.get_transaction_count(self.address, 'pending')
            self._nonce_cache[network_key] = nonce
            return nonce
        except Exception as e:
            self.logger.error(f"[ERROR] Failed to get nonce on {self.current_network}: {e}")
            return 0
    
    def increment_nonce(self):
        """Increment cached nonce after sending transaction on active network"""
        network_key = self.current_network
        if network_key in self._nonce_cache:
            self._nonce_cache[network_key] += 1
    
    def sign_transaction(self, transaction: Dict[str, Any]) -> str:
        """
        Sign a transaction and return the raw transaction hex
        
        Args:
            transaction: Transaction dict with to, value, data, gas, gasPrice, nonce
            
        Returns:
            Signed transaction hex string
        """
        try:
            # Ensure nonce is set
            if 'nonce' not in transaction:
                transaction['nonce'] = self.get_nonce()
            
            # Sign transaction
            signed_txn = self.account.sign_transaction(transaction)
            return signed_txn.raw_transaction.hex()
            
        except Exception as e:
            self.logger.error(f"[ERROR] Failed to sign transaction: {e}")
            raise
    
    def send_transaction(self, transaction: Dict[str, Any]) -> str:
        """
        Sign and broadcast transaction
        
        Args:
            transaction: Transaction dict
            
        Returns:
            Transaction hash
        """
        try:
            # Sign transaction
            raw_tx = self.sign_transaction(transaction)
            
            # Broadcast
            tx_hash = self.w3.eth.send_raw_transaction(raw_tx)
            tx_hash_hex = tx_hash.hex()
            
            # Update nonce cache
            self.increment_nonce()
            
            self.logger.info(f"📤 Transaction sent: {tx_hash_hex}")
            return tx_hash_hex
            
        except Exception as e:
            self.logger.error(f"[ERROR] Failed to send transaction: {e}")
            raise
    
    def wait_for_confirmation(self, tx_hash: str, timeout: int = 300) -> Optional[Dict]:
        """
        Wait for transaction confirmation
        
        Args:
            tx_hash: Transaction hash to wait for
            timeout: Maximum wait time in seconds
            
        Returns:
            Transaction receipt or None if timeout
        """
        try:
            self.logger.info(f"[WAIT] Waiting for confirmation: {tx_hash}")
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
            
            if receipt.status == 1:
                self.logger.info(f"[SUCCESS] Transaction confirmed in block {receipt.blockNumber}")
                # Clear balance cache to force refresh
                self._balance_cache.clear()
                return receipt
            else:
                self.logger.error(f"[ERROR] Transaction reverted: {tx_hash}")
                self.logger.error(f"[ERROR] Block: {receipt.blockNumber}")
                self.logger.error(f"[ERROR] Gas used: {receipt.gasUsed}")
                
                # Try to get revert reason
                try:
                    tx = self.w3.eth.get_transaction(tx_hash)
                    self.logger.error(f"[ERROR] Transaction details: {tx}")
                except:
                    pass
                    
                return receipt  # Return the receipt even if failed for analysis
                
        except Exception as e:
            self.logger.error(f"[ERROR] Confirmation timeout or error: {e}")
            return None
    
    def estimate_gas(self, transaction: Dict[str, Any]) -> int:
        """Estimate gas for transaction"""
        try:
            gas_estimate = self.w3.eth.estimate_gas(transaction)
            # Add 20% buffer
            return int(gas_estimate * 1.2)
        except Exception as e:
            self.logger.warning(f"⚠️ Gas estimation failed: {e}")
            return 200000  # Default gas limit
    
    def get_gas_price(self) -> int:
        """Get current gas price"""
        try:
            return self.w3.eth.gas_price
        except Exception as e:
            self.logger.warning(f"⚠️ Gas price fetch failed: {e}")
            return self.w3.to_wei('10', 'gwei')  # Default 10 gwei
    
    def approve_token(self, token_address: str, spender_address: str, amount: Optional[int] = None) -> str:
        """
        Approve token spending
        
        Args:
            token_address: Token contract address
            spender_address: Address to approve
            amount: Amount to approve (None for unlimited)
            
        Returns:
            Transaction hash
        """
        try:
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=self._get_erc20_abi()
            )
            
            # Use max approval if amount not specified
            if amount is None:
                amount = 2**256 - 1
            
            # Build approval transaction
            transaction = token_contract.functions.approve(
                spender_address, amount
            ).build_transaction({
                'from': self.address,
                'gas': 100000,
                'gasPrice': self.get_gas_price(),
                'nonce': self.get_nonce()
            })
            
            # Send transaction
            tx_hash = self.send_transaction(transaction)
            self.logger.info(f"🔓 Token approval sent: {tx_hash}")
            return tx_hash
            
        except Exception as e:
            self.logger.error(f"[ERROR] Token approval failed: {e}")
            raise
    
    def check_allowance(self, token_address: str, spender_address: str) -> Decimal:
        """Check current token allowance"""
        try:
            # Native tokens don't need allowance
            if token_address.lower() in ["native", "plume", "eth"]:
                return Decimal('999999999')  # Unlimited for native tokens
                
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=self._get_erc20_abi()
            )
            
            allowance = token_contract.functions.allowance(
                self.address, spender_address
            ).call()
            
            decimals = token_contract.functions.decimals().call()
            return Decimal(allowance) / Decimal(10 ** decimals)
            
        except Exception as e:
            self.logger.error(f"[ERROR] Allowance check failed: {e}")
            return Decimal('0')
    
    def _get_erc20_abi(self) -> list:
        """Get minimal ERC20 ABI"""
        return [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function"
            },
            {
                "constant": False,
                "inputs": [
                    {"name": "_spender", "type": "address"},
                    {"name": "_value", "type": "uint256"}
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function"
            },
            {
                "constant": True,
                "inputs": [
                    {"name": "_owner", "type": "address"},
                    {"name": "_spender", "type": "address"}
                ],
                "name": "allowance",
                "outputs": [{"name": "", "type": "uint256"}],
                "type": "function"
            }
        ]
    
    def get_status(self) -> Dict[str, Any]:
        """Get wallet status summary"""
        return {
            "address": self.address,
            "eth_balance": float(self.get_balance()),
            "nonce": self.get_nonce(),
            "connected": self.w3.is_connected()
        }
    
    def execute_swap_transaction(self, swap_data: Dict[str, Any], token_in: str = "plume") -> str:
        """
        Execute swap transaction from Euclid API response with dynamic network switching
        
        Args:
            swap_data: Response from Euclid API containing msgs array
            token_in: Input token type to determine network ("stt" or "plume")
            
        Returns:
            str: Real transaction hash from blockchain
        """
        try:
            if not swap_data or 'msgs' not in swap_data:
                raise ValueError("Invalid swap data: missing msgs")
            
            # Switch to appropriate network based on input token
            self.switch_network(token_in)
            network_info = self.networks[self.current_network]
            
            # Extract transaction parameters from API response
            msg = swap_data['msgs'][0]
            
            self.logger.info(f"[PROCESS] Extracting transaction parameters for {token_in.upper()} swap...")
            
            # Build transaction dictionary
            transaction = {
                'from': self.address,
                'to': Web3.to_checksum_address(msg['to']),
                'data': msg['data'],
                'value': int(msg['value'], 16),
                'gas': 800000,  # Increased gas limit for complex swaps
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.get_nonce(),
                'chainId': self.w3.eth.chain_id  # Use active network's chain ID
            }
            
            self.logger.info(f"[PROCESS] Network: {network_info['name']} (Chain ID: {network_info['chain_id']})")
            self.logger.info(f"[PROCESS] Gas fee will be paid in: {network_info['native_token']}")
            self.logger.info(f"[PROCESS] Signing transaction to {transaction['to']}")
            self.logger.info(f"[PROCESS] Value: {transaction['value']} wei")
            self.logger.info(f"[PROCESS] Gas: {transaction['gas']}")
            self.logger.info(f"[PROCESS] Gas Price: {transaction['gasPrice']} wei")
            
            # Try to estimate gas for better accuracy
            try:
                estimated_gas = self.w3.eth.estimate_gas({
                    'from': transaction['from'],
                    'to': transaction['to'],
                    'data': transaction['data'],
                    'value': transaction['value']
                })
                # Add 20% buffer to estimated gas
                transaction['gas'] = int(estimated_gas * 1.2)
                self.logger.info(f"[PROCESS] Gas estimated: {estimated_gas}, using: {transaction['gas']}")
            except Exception as e:
                self.logger.warning(f"[WARNING] Gas estimation failed: {e}, using default: {transaction['gas']}")
            
            # Sign transaction with private key
            signed_tx = self.account.sign_transaction(transaction)
            
            self.logger.info(f"[PROCESS] Broadcasting to {network_info['name']}...")
            
            # Send to blockchain
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = tx_hash.hex()
            
            # Ensure proper 0x prefix format
            if not tx_hash_hex.startswith('0x'):
                tx_hash_hex = '0x' + tx_hash_hex
            
            # Update nonce cache
            self.increment_nonce()
            
            self.logger.info(f"[SUCCESS] Transaction submitted to {network_info['name']}: {tx_hash_hex}")
            
            # Wait for confirmation and return hash
            self.wait_for_confirmation(tx_hash_hex)
            
            return tx_hash_hex
            
        except Exception as e:
            self.logger.error(f"[ERROR] Transaction execution failed: {e}")
            raise

    def register_swap_to_intract(self, tx_hash: str, chain_uid: str = "plume") -> bool:
        """
        Register successful swap to Intract tracking system for points.
        This is REQUIRED for points to be awarded.
        
        Args:
            tx_hash: The blockchain transaction hash (must be confirmed on-chain first)
            chain_uid: The chain identifier (default "plume" for Plume testnet)
            
        Returns:
            bool: True if registration successful, False otherwise
            
        Note: Without this call, swaps will succeed on blockchain but earn NO POINTS
        """
        try:
            import requests
            
            url = "https://testnet.euclidswap.io/api/intract-track"
            
            payload = {
                "chain_uid": chain_uid,
                "tx_hash": tx_hash,
                "type": "swap",
                "wallet_address": self.address.lower()
            }
            
            headers = {
                "Content-Type": "application/json",
                "Origin": "https://testnet.euclidswap.io",
                "Referer": "https://testnet.euclidswap.io/swap",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "x-app-version": "2.0.0"
            }
            
            self.logger.info(f"[INTRACT] Registering transaction for points: {tx_hash}")
            
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("message") == "Transaction queued for processing":
                    self.logger.info("[SUCCESS] Transaction registered to Intract system")
                    return True
                else:
                    self.logger.warning(f"[WARNING] Unexpected Intract response: {result}")
                    return False
            else:
                self.logger.error(f"[ERROR] Intract registration failed: {response.status_code}")
                if response.text:
                    self.logger.error(f"[ERROR] Response: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"[ERROR] Failed to register with Intract: {e}")
            return False

    def verify_points_registration(self, tx_hash: str, max_retries: int = 3) -> dict:
        """
        Verify if transaction was successfully tracked for points
        
        Args:
            tx_hash: Transaction hash to verify
            max_retries: Maximum number of verification attempts
            
        Returns:
            dict: Transaction data if found, None otherwise
        """
        import requests
        import time
        
        verify_url = "https://testnet.api.euclidprotocol.com/api/v1/intract/transactions/filter"
        
        for attempt in range(max_retries):
            try:
                # Wait for Intract processing (5-30 seconds typically)
                if attempt > 0:
                    wait_time = 10 * attempt
                    self.logger.info(f"[WAIT] Waiting {wait_time}s for Intract processing...")
                    time.sleep(wait_time)
                
                params = {"wallet_address": self.address.lower()}
                response = requests.get(verify_url, params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Search for our transaction
                    for tx in data.get('data', []):
                        if tx.get('txn_hash', '').lower() == tx_hash.lower():
                            points = tx.get('operations', 'Unknown')
                            status = tx.get('status', 'Unknown')
                            self.logger.info(f"[VERIFIED] Transaction tracked - Status: {status}, Points: {points}")
                            return tx
                    
                    self.logger.warning(f"[PENDING] Transaction not yet in tracking system (attempt {attempt + 1}/{max_retries})")
                else:
                    self.logger.error(f"[ERROR] Verification failed: {response.status_code}")
                    
            except Exception as e:
                self.logger.error(f"[ERROR] Verification attempt failed: {e}")
        
        self.logger.warning("[WARNING] Points verification failed - transaction may still be processing")
        return None

    def get_total_points(self) -> dict:
        """
        Get total points and transaction statistics from Intract system
        
        Returns:
            dict: Statistics including total points, successful swaps, etc.
        """
        try:
            import requests
            
            verify_url = "https://testnet.api.euclidprotocol.com/api/v1/intract/transactions/filter"
            params = {"wallet_address": self.address.lower()}
            
            response = requests.get(verify_url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                total_swaps = data.get('total_count', 0)
                successful_swaps = 0
                total_points = 0
                
                for tx in data.get('data', []):
                    if tx.get('status') == 'success':
                        successful_swaps += 1
                        operations = tx.get('operations', '')
                        if 'astra:' in operations:
                            try:
                                points = int(operations.split(':')[1])
                                total_points += points
                            except (ValueError, IndexError):
                                pass
                
                return {
                    'total_swaps': total_swaps,
                    'successful_swaps': successful_swaps,
                    'total_points': total_points,
                    'success_rate': (successful_swaps / total_swaps * 100) if total_swaps > 0 else 0
                }
            else:
                self.logger.error(f"[ERROR] Failed to get statistics: {response.status_code}")
                return {'total_swaps': 0, 'successful_swaps': 0, 'total_points': 0, 'success_rate': 0}
                
        except Exception as e:
            self.logger.error(f"[ERROR] Failed to get statistics: {e}")
            return {'total_swaps': 0, 'successful_swaps': 0, 'total_points': 0, 'success_rate': 0}
