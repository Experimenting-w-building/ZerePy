import logging
import os
from typing import Dict, Any
from dotenv import load_dotenv, set_key
from openai import OpenAI
from src.connections.base_connection import BaseConnection, Action, ActionParameter

logger = logging.getLogger(__name__)


class GitHubConnectionError(Exception):
    """Base exception for GitHub connection errors"""

    pass


class GitHubConfigurationError(GitHubConnectionError):
    """Raised when there are configuration/credential issues"""

    pass


class GitHubAPIError(GitHubConnectionError):
    """Raised when GitHub API requests fail"""

    pass


class GitHubConnection(BaseConnection):
    def __init__(self, config: Dict[str, Any]):
        logger.info("Initializing GitHub connection...")
        super().__init__(config)
        self._client = None

    @property
    def is_llm_provider(self) -> bool:
        return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        # TODO: Implement validation once we know more what is required
        return config

    def register_actions(self) -> None:
        """Register available GitHub actions"""
        self.actions = {
            "get-repo-updates": Action(
                name="generate-text",
                parameters=[
                    ActionParameter(
                        "prompt", True, str, "The input prompt for text generation"
                    ),
                    ActionParameter(
                        "system_prompt", True, str, "System prompt to guide the model"
                    ),
                    ActionParameter("model", False, str, "Model to use for generation"),
                ],
                description="Retrieves updates for a GitHub repository",
            ),
            "analyze-fork": Action(
                name="analyze-fork",
                parameters=[
                    ActionParameter(
                        "model", True, str, "Model name to check availability"
                    )
                ],
                description="Analyze a GitHub fork",
            ),
            #  TODO: check if requirements is same as get-repo-updates?
            "track-changes": Action(
                name="track-changes",
                parameters=[],
                description="Tracks changes in a GitHub repository",
            ),
        }

    def _get_client(self) -> OpenAI:
        """Get or create GitHub client"""
        if not self._client:
            api_key = os.getenv("GITHUB_ACCESS_TOKEN")
            if not api_key:
                raise GitHubConfigurationError(
                    "OpenAI API key not found in environment"
                )
            self._client = OpenAI(api_key=api_key)
        return self._client

    def configure(self) -> bool:
        """Sets up GitHub API authentication"""
        print("\n🤖 GitHub API SETUP")

        if self.is_configured():
            print("\GitHub API is already configured.")
            response = input("Do you want to reconfigure? (y/n): ")
            if response.lower() != "y":
                return True

        print("\n📝 To get your GitHub Access Token:")
        print("1. Go to https://platform.openai.com/account/api-keys")
        print("2. Create a new project or open an existing one.")
        print(
            "3. In your project settings, navigate to the API keys section and create a new API key"
        )

        api_key = input("\nEnter your OpenAI API key: ")

        try:
            if not os.path.exists(".env"):
                with open(".env", "w") as f:
                    f.write("")

            set_key(".env", "OPENAI_API_KEY", api_key)

            # Validate the API key by trying to list models
            client = OpenAI(api_key=api_key)
            client.models.list()

            print("\n✅ OpenAI API configuration successfully saved!")
            print("Your API key has been stored in the .env file.")
            return True

        except Exception as e:
            logger.error(f"Configuration failed: {e}")
            return False

    def is_configured(self, verbose=False) -> bool:
        """Check if OpenAI API key is configured and valid"""
        try:
            load_dotenv()
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return False

            client = OpenAI(api_key=api_key)
            client.models.list()
            return True

        except Exception as e:
            if verbose:
                logger.debug(f"Configuration check failed: {e}")
            return False

    def generate_text(
        self, prompt: str, system_prompt: str, model: str = None, **kwargs
    ) -> str:
        """Generate text using OpenAI models"""
        try:
            client = self._get_client()

            # Use configured model if none provided
            if not model:
                model = self.config["model"]

            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            )

            return completion.choices[0].message.content

        except Exception as e:
            raise GitHubAPIError(f"Text generation failed: {e}")

    def check_model(self, model, **kwargs):
        try:
            client = self._get_client
            try:
                client.models.retrieve(model=model)
                # If we get here, the model exists
                return True
            except Exception:
                return False
        except Exception as e:
            raise GitHubAPIError(e)

    def list_models(self, **kwargs) -> None:
        """List all available OpenAI models"""
        try:
            client = self._get_client()
            response = client.models.list().data

            fine_tuned_models = [
                model
                for model in response
                if model.owned_by in ["organization", "user", "organization-owner"]
            ]

            logger.info("\nGPT MODELS:")
            logger.info("1. gpt-3.5-turbo")
            logger.info("2. gpt-4")
            logger.info("3. gpt-4-turbo")
            logger.info("4. gpt-4o")
            logger.info("5. gpt-4o-mini")

            if fine_tuned_models:
                logger.info("\nFINE-TUNED MODELS:")
                for i, model in enumerate(fine_tuned_models):
                    logger.info(f"{i + 1}. {model.id}")

        except Exception as e:
            raise GitHubAPIError(f"Listing models failed: {e}")

    def perform_action(self, action_name: str, kwargs) -> Any:
        """Execute a Twitter action with validation"""
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
