# Soul Codespace Automator 🤖☁️

> A powerful Telegram-based manager for deploying and monitoring GitHub Codespaces at scale — fully automated, always online.

---

## ✨ What It Does

Soul Codespace Automator handles the **entire infrastructure pipeline** — from GitHub token ingestion to 24/7 uptime monitoring — through a simple Telegram bot interface. No manual setup. No babysitting. Just deploy and go.

---

## 🚀 Key Features

| Feature | Description |
|---|---|
| **All-in-One Deployment** | Automates repo creation, file uploads (`soul` binary + `soul.py`), and codespace initialization end-to-end |
| **Persistent Monitoring** | Background service polls codespace status every 5 minutes and auto-restarts any offline instances |
| **DevContainer Integration** | Auto-configures Ubuntu-based environments with Python 3 and all required dependencies |
| **Multi-Token Support** | Bulk-upload tokens via `.txt` file to scale infrastructure across multiple GitHub accounts instantly |

---

## 📋 Prerequisites

Make sure the following are installed and available on your host machine before proceeding:

- **GitHub CLI (`gh`)** — must be installed and authenticated (`gh auth login`)
- **Git** — required for repo cloning and pushing
- **Python 3.8+**

---

## 🛠 Setup

### 1. Configure the Bot

Open `soul_manager.py` and insert your Telegram bot token:

```python
BOT_TOKEN = "your-telegram-bot-token-here"
```

> 💡 Get a token by messaging [@BotFather](https://t.me/BotFather) on Telegram.

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Manager

```bash
python soul_manager.py
```

---

## 🎮 Usage

1. Open Telegram and send `/start` to your bot.
2. Provide your GitHub Personal Access Tokens (PATs) — either one at a time or via a `.txt` bulk upload.
3. Upload the `soul` executable and the `soul.py` controller script.
4. The bot will automatically:
   - Create repositories for each token
   - Deploy **2 codespaces per token**
   - Launch the background monitoring thread

That's it — your infrastructure is live and being watched.

---

## 🗂 Project Structure

```
soul-codespace-manager/
├── soul_manager.py       # Main Telegram bot + orchestration logic
├── soul.py               # Codespace controller script
├── soul                  # Compiled binary (uploaded per deployment)
├── requirements.txt      # Python dependencies
└── README.md
```

---

## 🚢 Deployment

### Pre-flight Checklist

- [ ] Remove or env-var your `BOT_TOKEN` before committing
- [ ] Ensure `gh` CLI is authenticated on the host
- [ ] Verify `soul` binary has execute permissions (`chmod +x soul`)

### Clone the Repository

```bash
git clone https://github.com/vikrant-project/soul-codespace-manager
cd soul-codespace-manager
```

### Push Changes

```bash
git init
git add .
git commit -m "Initial commit: GitHub Codespace Management Infrastructure"
git remote add origin https://soulcrack-spoofs-admin@bitbucket.org/soulcrack-spoofs/soul-codespace-manager.git
git push -u origin master
```

---

## ⚙️ How It Works

```
User (Telegram)
      │
      ▼
soul_manager.py  ──► GitHub API (via PAT)
      │                   │
      │              Creates Repo
      │              Uploads Files
      │              Starts Codespace
      │
      ▼
Monitor Thread (every 5 min)
      │
      ├── Codespace Online? ──► ✅ Continue
      └── Codespace Offline? ──► 🔄 Auto-restart
```

---

## ⚠️ Legal Disclaimer

This tool is intended for **educational purposes and legitimate infrastructure management** only. Users are solely responsible for ensuring their usage complies with [GitHub's Terms of Service](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service), particularly regarding Codespace usage limits and automation policies.

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

<p align="center">Built with ☕ and too many terminal windows open</p>
