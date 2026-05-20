# models package
# Import all models to ensure they're registered with SQLAlchemy Base
from app.models.agent_profile import *
from app.models.control_table_training import *
from app.models.credential_profile import *
from app.models.datasource import *
from app.models.mapping_rule import *
from app.models.regression_lab import *
from app.models.schema_object import *
from app.models.test_case import *
from app.models.tfs_workitem import *
from app.models.tfs_test_management import *

