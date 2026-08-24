from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router

app = FastAPI(
    title="Axiom Delivery AI API",
    description=(
        "API for enterprise delivery intelligence, governance, "
        "AI agents, and evidence-backed decision support."
    ),
    version="1.0.0",
)

# Allow the React frontend to communicate with the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(chat_router)


@app.get("/")
def root():
    return {
        "message": "Axiom Delivery AI is running."
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
