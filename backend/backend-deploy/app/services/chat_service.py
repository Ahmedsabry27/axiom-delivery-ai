import logging

from app.core.openai_client import client

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
You are Axiom Delivery AI.

You assist:

- Product Owners
- Scrum Masters
- Project Managers
- Business Analysts
- Solution Architects
- Developers

Always:

- Be professional
- Be concise
- Explain step by step
- Generate Jira user stories
- Generate acceptance criteria
- Generate meeting summaries
- Help with AI, SAP, AEM, APIs and Agile.
"""


class ChatService:

    def ask(self, message: str) -> str:

        logger.info("Incoming request")

        try:

            response = client.responses.create(
                model="gpt-4.1-mini",
                input=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": message,
                    },
                ],
            )

            logger.info("OpenAI response generated.")

            return response.output_text

        except Exception:
            logger.exception("OpenAI request failed.")
            raise


chat_service = ChatService()