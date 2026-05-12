"""IntelliTest – startup script."""
import uvicorn

if __name__ == "__main__":
    from app.config import settings
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.APP_PORT,
        reload=False,
        log_level="info",
    )
