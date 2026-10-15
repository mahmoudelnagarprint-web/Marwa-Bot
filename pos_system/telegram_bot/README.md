# Telegram Queue Bot

This folder contains a standalone Telegram polling bot for Phase 2+3 only:

- Telegram Bot
- Online Queue in Google Sheets
- No local POS import yet
- No write to `pos_data.db`

## Files

- `bot.py`: polling bot, commands, and `/neworder` conversation flow
- `sheets_queue.py`: Google Sheets queue reader/writer
- `config.py`: safe `.env.telegram` loader

## Environment

The real token is stored only in:

- `G:\ai\Elnagar POS\.env.telegram`

The example file is:

- `G:\ai\Elnagar POS\.env.telegram.example`

## Commands

- `/start`
- `/help`
- `/orders_today`
- `/client <name_or_phone>`
- `/products [query]`
- `/neworder`

## New Order Flow

1. Ask client name
2. Ask client phone
3. Ask client type: `Retail` or `Wholesale`
4. Ask products and quantities
5. Pick price by client type:
   - `Retail` -> `retail_price`
   - `Wholesale` -> `wholesale_price`
6. Ask paid amount
7. Ask notes
8. Accept photos
9. On confirmation, write to Google Sheets queue only

## Product Input Format

Send one item per line:

```text
Product Name x 2
Unknown Product x 1 @ 150
```

Notes:

- Known products read price from the `products` tab
- Unknown products are still accepted
- If a product is unknown, the bot keeps it in `items_json`
- Unknown products are marked with `needs_review=true` inside the queued JSON payload

## Queue Tabs

Required tabs:

- `telegram_inbox`
- `telegram_images`

The code auto-creates tabs and headers if they are missing or empty.

## Run

Install dependency:

```powershell
py -3 -m pip install "python-telegram-bot>=21.9,<22"
```

Healthcheck:

```powershell
py -3 telegram_bot\bot.py --healthcheck
```

Preview `/start` and `/help` output locally:

```powershell
py -3 telegram_bot\bot.py --smoke-test-handlers
```

Create a demo queue row only:

```powershell
py -3 telegram_bot\bot.py --smoke-test-queue
```

Run polling for 30 seconds:

```powershell
py -3 telegram_bot\bot.py --poll-seconds 30
```

Run normally:

```powershell
py -3 telegram_bot\bot.py
```
