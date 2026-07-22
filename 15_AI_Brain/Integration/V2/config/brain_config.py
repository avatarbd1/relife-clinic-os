import os
from pathlib import Path


class BrainConfig:


    def __init__(self):

        self.sheet_id = os.getenv(
            "GOOGLE_SHEET_ID",
            ""
        )

        self.credentials = os.getenv(
            "GOOGLE_CREDENTIALS_PATH",
            "credentials.json"
        )


    def status(self):

        return {

            "sheet_id_available":
            bool(self.sheet_id),

            "credentials_available":
            Path(self.credentials).exists(),

            "credentials_path":
            self.credentials

        }



if __name__ == "__main__":

    config = BrainConfig()

    print("="*40)
    print("AI BRAIN CONFIG STATUS")
    print("="*40)

    print(config.status())
