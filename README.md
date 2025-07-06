# Padel Monitor

Monitors padel court availability and sends Telegram notifications when the page changes.

## Setup

1. Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Install dependencies: `uv sync`
3. Copy `.env.example` to `.env` and fill in your values
4. Run: `uv run python main.py`

## Configuration

- `TELEGRAM_BOT_TOKEN`: Get from @BotFather
- `TELEGRAM_CHAT_ID`: Get your group chat ID
- `CHECK_INTERVAL`: How often to check in seconds (default: 10)

## Getting Chat ID

Add your bot to the group, then send a message and check:
`https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates` 