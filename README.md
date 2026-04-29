# Archive Telegram Bot

Telegram Archive Bot - Educational content management system with AI assistance.

## Features

- File organization by categories and subjects
- AI-powered Q&A system
- User favorites and ratings
- Search functionality
- Subscription notifications
- File request system
- Admin panel

## Setup

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file:
```bash
cp .env.example .env
```

4. Edit `.env` with your credentials:
```
BOT_TOKEN=your_bot_token
OWNER_ID=your_telegram_user_id
ARCHIVE_CHANNEL_ID=your_channel_id
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
GROQ_API_KEY=your_groq_api_key
AI_PROVIDER=groq
```

5. Run the bot:
```bash
python bot.py
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| BOT_TOKEN | Your Telegram bot token | Yes |
| OWNER_ID | Your Telegram user ID | Yes |
| ARCHIVE_CHANNEL_ID | Channel ID for archive | Yes |
| SUPABASE_URL | Supabase project URL | Yes |
| SUPABASE_KEY | Supabase API key | Yes |
| GROQ_API_KEY | Groq API key (for AI) | No |
| AI_PROVIDER | AI provider: groq or openai | No |

## Commands

- `/start` - Start the bot
- `/search` - Search files
- `/ask` - Ask a question
- `/ai` - AI assistant
- `/favorites` - Your favorites
- `/stats` - Statistics
- `/help` - Help

## Tech Stack

- Python 3.11+
- Telegram Bot API
- Supabase
- Groq AI

## License

MIT
