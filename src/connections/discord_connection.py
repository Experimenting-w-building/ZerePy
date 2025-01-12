import os
import logging
from typing import Dict, Any
from dotenv import set_key, load_dotenv
from src.connections.base_connection import BaseConnection, Action, ActionParameter
from src.helpers import print_h_bar
import requests
import json

logger = logging.getLogger("connections.twitter_connection")


class DiscordConnectionError(Exception):
    """Base exception for Discord connection errors"""

    pass


class DiscordConfigurationError(DiscordConnectionError):
    """Raised when there are configuration/credential issues"""

    pass


class DiscordAPIError(DiscordConnectionError):
    """Raised when Discord API requests fail"""

    pass


class DiscordConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.default_channel_id = config.get("default_channel_id")
        self.base_url = "https://discord.com/api/v10"

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Discord configuration from JSON"""
        required_fields = ["default_channel_id"]
        missing_fields = [field for field in required_fields if field not in config]

        if missing_fields:
            raise ValueError(
                f"Missing required configuration fields: {', '.join(missing_fields)}"
            )

        if (
            not isinstance(config["default_channel_id"], int)
            or config["default_channel_id"] <= 0
        ):
            raise ValueError("default_channel_id must be a positive integer")

        return config

    def register_actions(self) -> None:
        """Register available Discord actions"""
        self.actions = {
            "read-messages": Action(
                name="read-messages",
                parameters=[
                    ActionParameter(
                        "channel_id",
                        False,
                        str,
                        "The channel id to get messages from (default: config's default_channel_id)",
                    ),
                    ActionParameter(
                        "count",
                        False,
                        int,
                        "Number of messages to retrieve (default: 10)",
                    ),
                ],
                description="Get the latest tweets from a channel",
            ),
            "post-message": Action(
                name="post-message",
                parameters=[
                    ActionParameter(
                        "message", True, str, "Text content of the message"
                    ),
                    ActionParameter(
                        "channel_id",
                        False,
                        str,
                        "The channel id to get messages from (default: config's default_channel_id)",
                    ),
                ],
                description="Post a new message",
            ),
        }

    def configure(self) -> bool:
        """Sets up Discord API authentication"""
        print("\n🤖 DISCORD API SETUP")

        if self.is_configured():
            print("\nDiscord API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != "y":
                return True

        setup_instructions = [
            "\n📝 Discord AUTHENTICATION SETUP",
            "\nℹ️ To get your Discord API credentials:",
            "1. Follow Discord's API documention here: https://www.postman.com/discord-api/discord-api/collection/0d7xls9/discord-rest-api",
            "2. Copy the Discod token generated during the setup.",
        ]
        logger.info("\n".join(setup_instructions))
        print_h_bar()

        api_key = input("\nEnter your Discord token: ")

        try:
            self._test_connection(api_key)

            if not os.path.exists(".env"):
                with open(".env", "w") as f:
                    f.write("")

            set_key(".env", "DISCORD_TOKEN", api_key)

            print("\n✅ Discord API configuration successfully saved!")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose=False) -> bool:
        """Check if Discord API key is configured and valid"""
        try:
            load_dotenv()
            api_key = os.getenv("DISCORD_TOKEN")
            if not api_key:
                return False

            self._test_connection(api_key)
            return True
        except Exception as e:
            if verbose:
                logger.debug(f"Configuration check failed: {e}")
            return False

    def _test_connection(self, api_key: str) -> None:
        """Check if Discord is reachable"""
        try:
            response = self._get_request("/users/@me")
            print(f"🤖 Logged in as: {response['username']}")

        except Exception as e:
            raise DiscordConnectionError(f"Connection test failed: {e}")

    def read_messages(self, channel_id: int = None, count: int = 1, **kwargs) -> str:
        """Reading messages"""
        logger.debug("Sending a new message")

        channel_id = self.default_channel_id
        request_path = f"/channels/{channel_id}/messages?limit={count}"
        response = self._get_request(request_path)

        logger.info(f"Retrieved {len(response)} messages")

        return response

    def post_message(self, message: str, channel_id: int = None, **kwargs) -> dict:
        """Send a new message"""
        logger.debug("Sending a new message")

        channel_id = self.default_channel_id
        request_path = f"/channels/{channel_id}/messages"
        payload = f"content={message}"
        response = self._post_request(request_path, payload)

        logger.info("Message posted successfully")
        return response

    def _post_request(self, url_path: str, payload: str) -> dict:
        url = f"{self.base_url}{url_path}"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "Authorization": f"Bot {os.getenv('DISCORD_TOKEN')}",
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code != 200:
            raise DiscordAPIError(
                f"Failed to connect to Discord: {response.status_code} - {response.text}"
            )
        return json.loads(response.text)

    def _get_request(self, url_path: str) -> str:
        url = f"{self.base_url}{url_path}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bot {os.getenv('DISCORD_TOKEN')}",
        }
        response = requests.request("GET", url, headers=headers, data={})
        if response.status_code != 200:
            raise DiscordAPIError(
                f"Failed to connect to Discord: {response.status_code} - {response.text}"
            )
        return json.loads(response.text)

    def perform_action(self, action_name: str, kwargs) -> Any:
        if action_name not in self.actions:
            raise KeyError(f"Unknown action: {action_name}")

        action = self.actions[action_name]
        errors = action.validate_params(kwargs)
        if errors:
            raise ValueError(f"Invalid parameters: {', '.join(errors)}")

        # Call the appropriate method based on action name
        method_name = action_name.replace("-", "_")
        method = getattr(self, method_name)
        return method(**kwargs)
