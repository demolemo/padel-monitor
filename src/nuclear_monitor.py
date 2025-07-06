"""Nuclear option: Monitor ALL API endpoints for ANY changes."""

import aiohttp
import hashlib
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)


class NuclearMonitor:
    """Monitors all API endpoints and detects ANY changes."""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        # Base URLs
        self.agent_url = "https://tickets.mos.ru/widget/api/widget/agent_info?agent_id=museum1038"
        self.event_url = "https://tickets.mos.ru/widget/api/widget/getevents?event_id=65305&agent_uid=museum1038"
        self.sessions_base_url = "https://tickets.mos.ru/widget/api/widget/events/getperformances?event_id=65305&agent_uid=museum1038"
        
        # Store hashes for change detection
        self.previous_hashes = {}
        
    def get_moscow_time(self) -> datetime:
        """Get current Moscow time."""
        # Moscow is UTC+3
        moscow_tz = timezone(timedelta(hours=3))
        return datetime.now(moscow_tz)
    
    def get_monitoring_dates(self) -> list:
        """Get dates to monitor (today + 7 days ahead in Moscow time)."""
        moscow_now = self.get_moscow_time()
        today = moscow_now.date()
        
        dates = []
        for i in range(7):  # Today + 6 more days = 7 days total
            date = today + timedelta(days=i)
            dates.append(date.strftime('%Y-%m-%d'))
        
        return dates
    
    async def fetch_endpoint(self, session: aiohttp.ClientSession, url: str, endpoint_name: str) -> Dict[str, Any]:
        """Fetch data from an endpoint and return normalized result."""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    data = await response.json()
                    content_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
                    
                    return {
                        'success': True,
                        'endpoint': endpoint_name,
                        'url': url,
                        'status_code': response.status,
                        'data': data,
                        'content_hash': content_hash,
                        'timestamp': self.get_moscow_time().isoformat()
                    }
                else:
                    return {
                        'success': False,
                        'endpoint': endpoint_name,
                        'url': url,
                        'status_code': response.status,
                        'error': f'HTTP {response.status}',
                        'timestamp': self.get_moscow_time().isoformat()
                    }
                    
        except Exception as e:
            return {
                'success': False,
                'endpoint': endpoint_name,
                'url': url,
                'error': str(e),
                'timestamp': self.get_moscow_time().isoformat()
            }
    
    async def fetch_all_content(self) -> Dict[str, Any]:
        """Fetch content from all endpoints."""
        monitoring_dates = self.get_monitoring_dates()
        
        logger.info(f"Monitoring dates: {', '.join(monitoring_dates)}")
        
        # Build list of all endpoints to fetch
        endpoints_to_fetch = [
            ("agent_info", self.agent_url),
            ("event_info", self.event_url),
        ]
        
        # Add session endpoints for each date
        for date_str in monitoring_dates:
            endpoint_key = f"sessions_{date_str}"
            sessions_url = f"{self.sessions_base_url}&date={date_str}"
            endpoints_to_fetch.append((endpoint_key, sessions_url))
        
        # Fetch all endpoints
        endpoints_data = {}
        async with aiohttp.ClientSession(headers=self.headers) as session:
            # Fetch all endpoints concurrently
            tasks = []
            for endpoint_key, url in endpoints_to_fetch:
                task = self.fetch_endpoint(session, url, endpoint_key)
                tasks.append((endpoint_key, task))
            
            # Wait for all tasks to complete
            for endpoint_key, task in tasks:
                result = await task
                endpoints_data[endpoint_key] = result
        
        return endpoints_data
    
    def check_content_for_changes(self, endpoints_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check fetched content for changes and return change information."""
        changes_detected = []
        any_changes = False
        
        # Detect changes
        for endpoint_key, result in endpoints_data.items():
            if result['success']:
                current_hash = result['content_hash']
                previous_hash = self.previous_hashes.get(endpoint_key)
                
                if previous_hash is None:
                    # First run - store hash but don't alert
                    self.previous_hashes[endpoint_key] = current_hash
                    logger.info(f"Stored initial hash for {endpoint_key}: {current_hash[:8]}...")
                    
                elif previous_hash != current_hash:
                    # Change detected!
                    change_info = {
                        'endpoint': endpoint_key,
                        'url': result['url'],
                        'previous_hash': previous_hash[:8],
                        'current_hash': current_hash[:8],
                        'timestamp': result['timestamp']
                    }
                    changes_detected.append(change_info)
                    any_changes = True
                    
                    # Update stored hash
                    self.previous_hashes[endpoint_key] = current_hash
                    
                    logger.warning(f"CHANGE DETECTED: {endpoint_key}")
                    logger.warning(f"   URL: {result['url']}")
                    logger.warning(f"   Hash: {previous_hash[:8]} → {current_hash[:8]}")
                    
                else:
                    # No change
                    logger.debug(f"No change: {endpoint_key} ({current_hash[:8]})")
            
            else:
                logger.error(f"Failed to fetch {endpoint_key}: {result.get('error', 'Unknown error')}")
        
        return {
            'changes_detected': changes_detected,
            'any_changes': any_changes
        }
    
    async def check_all_endpoints(self) -> Dict[str, Any]:
        """Check all endpoints and detect changes."""
        moscow_time = self.get_moscow_time()
        monitoring_dates = self.get_monitoring_dates()
        
        logger.info(f"Moscow time: {moscow_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        # Fetch all content
        endpoints_data = await self.fetch_all_content()
        
        # Check for changes
        change_results = self.check_content_for_changes(endpoints_data)
        
        # Build final results
        results = {
            'check_time': moscow_time.isoformat(),
            'moscow_time_str': moscow_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'monitoring_dates': monitoring_dates,
            'endpoints': endpoints_data,
            'changes_detected': change_results['changes_detected'],
            'any_changes': change_results['any_changes']
        }
        
        return results
    
    def format_change_message(self, results: Dict[str, Any]) -> str:
        """Format a notification message for detected changes."""
        changes = results['changes_detected']
        
        if not changes:
            return "No changes"
        
        # Simple message as requested
        return f"""ПАДЛА ПАДЛА ПАДЛА

https://bilet.mos.ru/event/344458257/"""
    
    async def get_status_summary(self) -> str:
        """Get a summary of current monitoring status."""
        moscow_time = self.get_moscow_time()
        dates = self.get_monitoring_dates()
        
        return f"""Nuclear Monitor Status

Moscow Time: {moscow_time.strftime('%Y-%m-%d %H:%M:%S %Z')}
Monitoring Dates: {', '.join(dates)}
Endpoints Watched: 2 base + {len(dates)} sessions = {2 + len(dates)} total

Stored Hashes:
""" + "\n".join([f"   • {endpoint}: {hash_val[:8]}..." for endpoint, hash_val in self.previous_hashes.items()]) 