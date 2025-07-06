#!/usr/bin/env python3
"""
Padel Court Monitoring System - Nuclear Edition

Monitors ALL API endpoints and sends notifications when ANY change is detected.
Uses Moscow time and monitors a full week ahead.
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta

from src.config import Config
from src.telegram_bot import TelegramNotifier
from src.nuclear_monitor import NuclearMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('padel_monitor.log')
    ]
)

# Reduce telegram bot logging noise
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('telegram.ext').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def main():
    """Main monitoring loop with nuclear detection."""
    logger.info("Starting Padel Court Monitor - Nuclear Edition")
    logger.info("MONITORING ALL ENDPOINTS FOR ANY CHANGES")
    logger.info("Week-ahead monitoring: 7 days of sessions")
    
    # Validate config
    try:
        Config.validate()
        logger.info("Configuration validated")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return
    
    # Initialize components
    telegram = TelegramNotifier(Config.TELEGRAM_BOT_TOKEN, Config.TELEGRAM_CHAT_ID)
    nuclear_monitor = NuclearMonitor()
    
    logger.info(f"Target endpoints:")
    logger.info(f"   • Agent info: {nuclear_monitor.agent_url}")
    logger.info(f"   • Event info: {nuclear_monitor.event_url}")
    logger.info(f"   • Sessions: {nuclear_monitor.sessions_base_url}&date=YYYY-MM-DD")
    logger.info(f"Check interval: {Config.CHECK_INTERVAL} seconds")
    
    # Start bot polling for ping commands
    try:
        await telegram.start_polling()
        logger.info("Bot polling started - ping/pong commands enabled")
    except Exception as e:
        logger.error(f"Failed to start bot polling: {e}")
        return
    
    # Send startup notification
    try:
        startup_message = "🎾 Padel monitor started"
        await telegram.send_message(startup_message)
        logger.info("Startup notification sent")
    except Exception as e:
        logger.error(f"Failed to send startup notification: {e}")
    
    # Log detailed status to terminal only
    startup_status = await nuclear_monitor.get_status_summary()
    logger.info(f"Detailed Status:\n{startup_status}")
    
    # Main monitoring loop
    logger.info("Starting nuclear monitoring loop...")
    
    last_notification_time = None
    
    try:
        while True:
            try:
                # Check all endpoints
                results = await nuclear_monitor.check_all_endpoints()
                
                # Log status
                moscow_time_str = results['moscow_time_str']
                moscow_time = nuclear_monitor.get_moscow_time()
                endpoints_checked = len(results['endpoints'])
                

                if results['any_changes']:
                    send_message = False
                    if last_notification_time is None:
                        send_message = True
                    elif moscow_time > last_notification_time + timedelta(minutes=1):
                        send_message = True

                    if send_message:
                        try:
                            message = nuclear_monitor.format_change_message(results)
                            await telegram.send_message(message)
                            logger.info("Change notification sent")
                            last_notification_time = moscow_time
                        except Exception as e:
                            logger.error(f"Failed to send notification: {e}")
                    else:
                        logger.info(f"Skipping notification - less than 1 minute since last update")
                else:
                    logger.info(f"No changes - {endpoints_checked} endpoints checked at {moscow_time_str}")

                # Log endpoint statuses (debug level)
                for endpoint_key, result in results['endpoints'].items():
                    if result['success']:
                        hash_preview = result['content_hash'][:8]
                        logger.debug(f"   {endpoint_key}: OK {hash_preview}...")
                    else:
                        error = result.get('error', 'Unknown error')
                        logger.warning(f"   {endpoint_key}: ERROR {error}")
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                
                # Try to send error notification
                try:
                    error_message = f"""🚨 Padel Monitor Error

⚠️ Error: {str(e)}
🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Monitor will continue running..."""
                    await telegram.send_message(error_message)
                except:
                    logger.error("Failed to send error notification")
            
            # Wait before next check
            await asyncio.sleep(Config.CHECK_INTERVAL)
            
    finally:
        # Cleanup
        logger.info("Shutting down...")
        try:
            await telegram.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Padel monitor stopped by user")
    except Exception as e:
        logger.error(f"Padel monitor crashed: {e}")
        sys.exit(1) 