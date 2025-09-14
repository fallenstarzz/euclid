"""
Comprehensive Logging System for Adaptive Amount Management
Provides detailed logging, analytics, and performance tracking
"""

import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class AdaptiveLogEntry:
    """Single log entry for adaptive behavior"""
    timestamp: float
    swap_id: int
    phase: str
    amount: float
    action: str  # 'swap_attempt', 'adjustment', 'phase_transition', 'optimization_found'
    success: bool
    execution_time: float
    error_type: Optional[str]
    error_message: Optional[str]
    tx_hash: Optional[str]
    additional_data: Optional[Dict[str, Any]]

class AdaptiveLogger:
    """
    Comprehensive logging system for adaptive amount management
    Tracks all adaptive behavior, performance metrics, and optimization progress
    """
    
    def __init__(self, log_dir: str = "logs", wallet_address: str = "unknown"):
        """Initialize adaptive logger"""
        self.log_dir = Path(log_dir)
        self.wallet_address = wallet_address[:10] if wallet_address != "unknown" else "unknown"
        
        # Create log directory
        self.log_dir.mkdir(exist_ok=True)
        
        # Log files
        self.session_id = self._generate_session_id()
        self.adaptive_log_file = self.log_dir / f"adaptive_{self.wallet_address}_{self.session_id}.json"
        self.performance_log_file = self.log_dir / f"performance_{self.wallet_address}_{self.session_id}.csv"
        self.analytics_file = self.log_dir / f"analytics_{self.wallet_address}.json"
        
        # In-memory storage
        self.log_entries: List[AdaptiveLogEntry] = []
        self.session_start_time = time.time()
        self.swap_counter = 0
        
        # Performance tracking
        self.performance_metrics = {
            'total_swaps': 0,
            'successful_swaps': 0,
            'failed_swaps': 0,
            'total_adjustments': 0,
            'phase_transitions': 0,
            'optimization_events': 0,
            'total_execution_time': 0,
            'average_execution_time': 0,
            'tokens_saved': 0,
            'efficiency_gained': 0
        }
        
        # Setup logging
        self.logger = logging.getLogger(f"adaptive_logger_{self.session_id}")
        self.logger.setLevel(logging.INFO)
        
        # File handler for detailed logs
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_dir / f"adaptive_detailed_{self.session_id}.log")
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        
        self.logger.info(f"Adaptive logging session started: {self.session_id}")
        self._initialize_performance_csv()
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _initialize_performance_csv(self):
        """Initialize CSV file with headers"""
        headers = [
            "timestamp", "swap_id", "phase", "amount", "action", "success",
            "execution_time", "error_type", "tx_hash", "cumulative_savings"
        ]
        
        with open(self.performance_log_file, 'w') as f:
            f.write(','.join(headers) + '\n')
    
    def log_swap_attempt(self, phase: str, amount: float, swap_id: Optional[int] = None) -> int:
        """
        Log swap attempt start
        
        Args:
            phase: Current adaptive phase
            amount: Swap amount being attempted
            swap_id: Optional swap ID (auto-generated if not provided)
            
        Returns:
            swap_id for tracking this attempt
        """
        if swap_id is None:
            self.swap_counter += 1
            swap_id = self.swap_counter
        
        entry = AdaptiveLogEntry(
            timestamp=time.time(),
            swap_id=swap_id,
            phase=phase,
            amount=amount,
            action='swap_attempt',
            success=False,  # Will be updated when result is known
            execution_time=0,
            error_type=None,
            error_message=None,
            tx_hash=None,
            additional_data={'attempt_start': True}
        )
        
        self.log_entries.append(entry)
        self.logger.info(f"Swap #{swap_id} attempt started - Phase: {phase}, Amount: {amount}")
        
        return swap_id
    
    def log_swap_result(self, swap_id: int, success: bool, execution_time: float,
                       tx_hash: Optional[str] = None, error_type: Optional[str] = None,
                       error_message: Optional[str] = None):
        """
        Log swap attempt result
        
        Args:
            swap_id: ID of the swap attempt
            success: Whether swap was successful
            execution_time: Time taken to execute
            tx_hash: Transaction hash if successful
            error_type: Error type if failed
            error_message: Error message if failed
        """
        # Find the original entry and update it
        for entry in reversed(self.log_entries):
            if entry.swap_id == swap_id and entry.action == 'swap_attempt':
                entry.success = success
                entry.execution_time = execution_time
                entry.tx_hash = tx_hash
                entry.error_type = error_type
                entry.error_message = error_message
                break
        
        # Update performance metrics
        self.performance_metrics['total_swaps'] += 1
        if success:
            self.performance_metrics['successful_swaps'] += 1
        else:
            self.performance_metrics['failed_swaps'] += 1
        
        self.performance_metrics['total_execution_time'] += execution_time
        self.performance_metrics['average_execution_time'] = (
            self.performance_metrics['total_execution_time'] / 
            self.performance_metrics['total_swaps']
        )
        
        # Log to CSV
        self._write_to_csv(entry)
        
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(f"Swap #{swap_id} {status} - Time: {execution_time:.2f}s")
        if not success and error_type:
            self.logger.warning(f"Swap #{swap_id} error: {error_type} - {error_message}")
    
    def log_amount_adjustment(self, old_amount: float, new_amount: float, 
                            reason: str, phase: str):
        """
        Log amount adjustment
        
        Args:
            old_amount: Previous amount
            new_amount: New amount
            reason: Reason for adjustment
            phase: Current phase
        """
        entry = AdaptiveLogEntry(
            timestamp=time.time(),
            swap_id=self.swap_counter,
            phase=phase,
            amount=new_amount,
            action='adjustment',
            success=True,
            execution_time=0,
            error_type=None,
            error_message=None,
            tx_hash=None,
            additional_data={
                'old_amount': old_amount,
                'change': new_amount - old_amount,
                'reason': reason
            }
        )
        
        self.log_entries.append(entry)
        self.performance_metrics['total_adjustments'] += 1
        
        direction = "↑" if new_amount > old_amount else "↓"
        change = abs(new_amount - old_amount)
        self.logger.info(f"Amount adjusted {direction} {old_amount} → {new_amount} (+{change:.3f}) - {reason}")
        
        self._write_to_csv(entry)
    
    def log_phase_transition(self, from_phase: str, to_phase: str, amount: float, reason: str = ""):
        """
        Log phase transition
        
        Args:
            from_phase: Previous phase
            to_phase: New phase
            amount: Current amount
            reason: Reason for transition
        """
        entry = AdaptiveLogEntry(
            timestamp=time.time(),
            swap_id=self.swap_counter,
            phase=to_phase,
            amount=amount,
            action='phase_transition',
            success=True,
            execution_time=0,
            error_type=None,
            error_message=None,
            tx_hash=None,
            additional_data={
                'from_phase': from_phase,
                'to_phase': to_phase,
                'reason': reason
            }
        )
        
        self.log_entries.append(entry)
        self.performance_metrics['phase_transitions'] += 1
        
        self.logger.info(f"Phase transition: {from_phase.upper()} → {to_phase.upper()} at {amount} - {reason}")
        
        self._write_to_csv(entry)
    
    def log_optimization_found(self, optimal_amount: float, initial_amount: float,
                             savings_per_swap: float, total_savings: float):
        """
        Log optimization discovery
        
        Args:
            optimal_amount: Optimal amount found
            initial_amount: Initial amount used
            savings_per_swap: Savings per individual swap
            total_savings: Total savings accumulated
        """
        entry = AdaptiveLogEntry(
            timestamp=time.time(),
            swap_id=self.swap_counter,
            phase='optimal',
            amount=optimal_amount,
            action='optimization_found',
            success=True,
            execution_time=0,
            error_type=None,
            error_message=None,
            tx_hash=None,
            additional_data={
                'initial_amount': initial_amount,
                'savings_per_swap': savings_per_swap,
                'total_savings': total_savings,
                'efficiency_gain': (savings_per_swap / initial_amount) * 100
            }
        )
        
        self.log_entries.append(entry)
        self.performance_metrics['optimization_events'] += 1
        self.performance_metrics['tokens_saved'] = total_savings
        self.performance_metrics['efficiency_gained'] = (savings_per_swap / initial_amount) * 100
        
        self.logger.info(f"🎯 OPTIMIZATION FOUND: {optimal_amount} PLUME (was {initial_amount})")
        self.logger.info(f"💰 SAVINGS: {savings_per_swap:.3f} per swap, {total_savings:.3f} total")
        
        self._write_to_csv(entry)
    
    def _write_to_csv(self, entry: AdaptiveLogEntry):
        """Write entry to CSV file"""
        with open(self.performance_log_file, 'a') as f:
            csv_line = f"{entry.timestamp},{entry.swap_id},{entry.phase},{entry.amount},"
            csv_line += f"{entry.action},{entry.success},{entry.execution_time},"
            csv_line += f"{entry.error_type or ''},{entry.tx_hash or ''},"
            csv_line += f"{self.performance_metrics['tokens_saved']}\n"
            f.write(csv_line)
    
    def get_session_analytics(self) -> Dict[str, Any]:
        """Get comprehensive session analytics"""
        session_duration = time.time() - self.session_start_time
        
        # Calculate success rate
        total_swaps = self.performance_metrics['total_swaps']
        success_rate = 0
        if total_swaps > 0:
            success_rate = (self.performance_metrics['successful_swaps'] / total_swaps) * 100
        
        # Calculate swap frequency
        swaps_per_hour = 0
        if session_duration > 0:
            swaps_per_hour = total_swaps / (session_duration / 3600)
        
        # Phase distribution
        phase_counts = {}
        for entry in self.log_entries:
            if entry.action == 'swap_attempt':
                phase_counts[entry.phase] = phase_counts.get(entry.phase, 0) + 1
        
        # Error distribution
        error_counts = {}
        for entry in self.log_entries:
            if not entry.success and entry.error_type:
                error_counts[entry.error_type] = error_counts.get(entry.error_type, 0) + 1
        
        # Amount distribution
        amounts_used = [entry.amount for entry in self.log_entries if entry.action == 'swap_attempt']
        min_amount = min(amounts_used) if amounts_used else 0
        max_amount = max(amounts_used) if amounts_used else 0
        avg_amount = sum(amounts_used) / len(amounts_used) if amounts_used else 0
        
        return {
            'session': {
                'session_id': self.session_id,
                'wallet_address': self.wallet_address,
                'start_time': self.session_start_time,
                'duration_seconds': session_duration,
                'duration_formatted': self._format_duration(session_duration)
            },
            'performance': {
                **self.performance_metrics,
                'success_rate': success_rate,
                'swaps_per_hour': swaps_per_hour,
                'avg_execution_time': self.performance_metrics['average_execution_time']
            },
            'distribution': {
                'phases': phase_counts,
                'errors': error_counts,
                'amounts': {
                    'min': min_amount,
                    'max': max_amount,
                    'average': avg_amount,
                    'range': max_amount - min_amount
                }
            },
            'optimization': {
                'events': self.performance_metrics['optimization_events'],
                'tokens_saved': self.performance_metrics['tokens_saved'],
                'efficiency_gained': self.performance_metrics['efficiency_gained']
            }
        }
    
    def save_session_data(self):
        """Save session data to persistent storage"""
        try:
            # Save detailed log entries
            with open(self.adaptive_log_file, 'w') as f:
                json.dump([asdict(entry) for entry in self.log_entries], f, indent=2)
            
            # Save analytics
            analytics = self.get_session_analytics()
            with open(self.analytics_file, 'w') as f:
                json.dump(analytics, f, indent=2)
            
            self.logger.info(f"Session data saved - Entries: {len(self.log_entries)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save session data: {e}")
            return False
    
    def load_previous_analytics(self) -> Optional[Dict[str, Any]]:
        """Load analytics from previous sessions"""
        try:
            if self.analytics_file.exists():
                with open(self.analytics_file, 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            self.logger.error(f"Failed to load previous analytics: {e}")
            return None
    
    def get_performance_summary(self) -> str:
        """Get formatted performance summary"""
        analytics = self.get_session_analytics()
        
        summary = f"\n{'='*60}\n"
        summary += f"          ADAPTIVE SYSTEM PERFORMANCE SUMMARY\n"
        summary += f"{'='*60}\n"
        
        # Session info
        summary += f"Session ID: {analytics['session']['session_id']}\n"
        summary += f"Duration: {analytics['session']['duration_formatted']}\n"
        summary += f"Wallet: {analytics['session']['wallet_address']}...\n\n"
        
        # Performance
        perf = analytics['performance']
        summary += f"PERFORMANCE:\n"
        summary += f"├─ Total Swaps: {perf['total_swaps']}\n"
        summary += f"├─ Successful: {perf['successful_swaps']} ({perf['success_rate']:.1f}%)\n"
        summary += f"├─ Failed: {perf['failed_swaps']}\n"
        summary += f"├─ Avg Execution: {perf['avg_execution_time']:.2f}s\n"
        summary += f"├─ Adjustments: {perf['total_adjustments']}\n"
        summary += f"└─ Phase Changes: {perf['phase_transitions']}\n\n"
        
        # Optimization
        opt = analytics['optimization']
        if opt['tokens_saved'] > 0:
            summary += f"OPTIMIZATION:\n"
            summary += f"├─ Tokens Saved: {opt['tokens_saved']:.3f} PLUME\n"
            summary += f"├─ Efficiency Gain: {opt['efficiency_gained']:.1f}%\n"
            summary += f"└─ Optimization Events: {opt['events']}\n\n"
        
        # Amount distribution
        amounts = analytics['distribution']['amounts']
        summary += f"AMOUNT USAGE:\n"
        summary += f"├─ Range: {amounts['min']:.3f} - {amounts['max']:.3f} PLUME\n"
        summary += f"├─ Average: {amounts['average']:.3f} PLUME\n"
        summary += f"└─ Spread: {amounts['range']:.3f} PLUME\n\n"
        
        summary += f"{'='*60}\n"
        
        return summary
    
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
    
    def export_for_analysis(self, export_path: Optional[str] = None) -> str:
        """Export all data for external analysis"""
        if export_path is None:
            export_path = self.log_dir / f"adaptive_export_{self.session_id}.json"
        
        export_data = {
            'metadata': {
                'export_timestamp': time.time(),
                'session_id': self.session_id,
                'wallet_address': self.wallet_address,
                'total_entries': len(self.log_entries)
            },
            'analytics': self.get_session_analytics(),
            'raw_entries': [asdict(entry) for entry in self.log_entries],
            'performance_metrics': self.performance_metrics
        }
        
        try:
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            self.logger.info(f"Data exported to: {export_path}")
            return str(export_path)
            
        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            raise
    
    def cleanup_old_logs(self, days_to_keep: int = 7):
        """Clean up old log files"""
        cutoff_time = time.time() - (days_to_keep * 24 * 3600)
        
        cleaned_count = 0
        for log_file in self.log_dir.glob("adaptive_*"):
            if log_file.stat().st_mtime < cutoff_time:
                try:
                    log_file.unlink()
                    cleaned_count += 1
                except Exception as e:
                    self.logger.warning(f"Failed to delete old log {log_file}: {e}")
        
        if cleaned_count > 0:
            self.logger.info(f"Cleaned up {cleaned_count} old log files")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - save data automatically"""
        self.save_session_data()
        if exc_type:
            self.logger.error(f"Session ended with exception: {exc_type.__name__}: {exc_val}")
        else:
            self.logger.info("Session ended normally")
