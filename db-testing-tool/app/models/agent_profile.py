"""Agent profile model stub."""
from sqlalchemy import Column, Integer, String, Text
from app.database import Base


class AgentProfile(Base):
    """Agent profile model - stub for unblocking app startup."""
    __tablename__ = "agent_profiles"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    config = Column(Text, nullable=True)
