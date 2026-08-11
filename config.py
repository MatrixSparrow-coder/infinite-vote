import os

# ==================== BOT CREDENTIALS ====================
API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# ==================== DATABASE ====================
MONGO_URI = os.environ.get("MONGO_URI", "")
DB_NAME = os.environ.get("DB_NAME", "InfiniteBot")

# ==================== OWNER ====================
# Single fixed owner - has silent super-admin access to every giveaway
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# ==================== MISC ====================
# Bot username without @ (used for generating deep links)
BOT_USERNAME = os.environ.get("BOT_USERNAME", "")

# Support contact shown in /help
SUPPORT_USERNAME = os.environ.get("SUPPORT_USERNAME", "Xzrie")

# Timezone offset for IST (UTC+5:30) — used for all giveaway timing
IST_OFFSET_HOURS = 5
IST_OFFSET_MINUTES = 30

# Port for the health-check web server (Render requirement)
PORT = int(os.environ.get("PORT", "8080"))
