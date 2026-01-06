# Evergreen Bot (Controller Edition) 🌲

Evergreen is a dual-client system:
1.  **Controller Bot**: A Telegram Bot (`@YourBot`) that you talk to.
2.  **User Client**: A fully functional Userbot running on your account, managed by the Controller Bot.

## Features

*   **Interactive Login**: Log in to your User Account directly via the Bot Chat.
*   **Auto-Forwarding**: The User Client listens to source channels and forwards to destination channels.
*   **Remote Management**: Add/Remove rules via the Controller Bot.
*   **Persistence**: Sessions and Rules are stored in a database.

## Setup

### 1. Requirements

*   Python 3.7+
*   `API_ID` and `API_HASH` from [my.telegram.org](https://my.telegram.org).
*   `BOT_TOKEN` from [@BotFather](https://t.me/BotFather).

### 2. Installation

1.  Clone this repository.
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### 3. Configuration

Set the following environment variables (or create a `.env` file if you modify `config.py`):

*   `API_ID`: Your API ID.
*   `API_HASH`: Your API Hash.
*   `BOT_TOKEN`: Your Bot Token.

### 4. Running

```bash
python main.py
```

## Usage

Start a chat with your Controller Bot (`@YourBot`).

### Login
1.  Send `/login`.
2.  Bot asks for Phone Number (e.g., `+1234567890`).
3.  Bot asks for OTP (sent to your Telegram App).
4.  Bot asks for Password (if 2FA is on).
5.  **Success**: The User Client starts automatically.

### Commands
*   `/status`: Check if User Client is running.
*   `/add <src_id> <dest_id>`: Add a forwarding rule.
    *   Example: `/add -10012345678 -10087654321`
*   `/del <src_id> <dest_id>`: Remove a rule.
*   `/list`: List all rules.
*   `/logout`: Log out and stop the User Client.
*   `/help`: Show available commands.

## Architecture

*   `main.py`: Starts the Controller Bot.
*   `user_client.py`: Manages the background User Client process.
*   `plugins/auth.py`: Handles the login flow (Phone -> OTP -> Session).
*   `plugins/manager.py`: Bot commands for rules.
*   `plugins/forwarder.py`: The logic attached to the User Client.
