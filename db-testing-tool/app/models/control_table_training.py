"""ControlTableTraining model stub."""
from sqlalchemy import Column, Integer, String, Text
from app.database import Base


class ControlTableTraining(Base):
    """Control table training model - stub for unblocking app startup."""
    __tablename__ = "control_table_training"
    
    id = Column(Integer, primary_key=True)
    target_table = Column(String(255), nullable=False)
    training_data = Column(Text, nullable=True)
    rules_count = Column(Integer, default=0)
