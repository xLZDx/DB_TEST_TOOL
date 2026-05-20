"""TFS WorkItem model stub."""
from sqlalchemy import Column, Integer, String, Text
from app.database import Base


class TfsWorkItem(Base):
    """TFS work item model - stub for unblocking app startup."""
    __tablename__ = "tfs_workitems"
    
    id = Column(Integer, primary_key=True)
    tfs_id = Column(Integer, nullable=True)
    title = Column(String(255), nullable=False)
    work_item_type = Column(String(50), nullable=True)
    state = Column(String(50), default="New")
    url = Column(Text, nullable=True)
