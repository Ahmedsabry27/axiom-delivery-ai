from app.database.session import SessionLocal
from app.repositories.conversation_repository import conversation_repository

db = SessionLocal()

conversation = conversation_repository.create(
    db=db,
    title="My First Conversation",
)

print(conversation.id)
print(conversation.title)

db.close()
