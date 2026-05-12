"""TFS Test Management model stub."""
from sqlalchemy import Column, Integer, String, Text
from app.database import Base


class TfsTestManagement(Base):
    """TFS test management model - stub for unblocking app startup."""
    __tablename__ = "tfs_test_management"
    
    id = Column(Integer, primary_key=True)
    test_plan_id = Column(Integer, nullable=True)
    test_suite_id = Column(Integer, nullable=True)
    test_case_id = Column(Integer, nullable=True)
    status = Column(String(50), default="Not Run")
