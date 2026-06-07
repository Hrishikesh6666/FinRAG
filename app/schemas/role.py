from pydantic import BaseModel, Field
from typing import Optional, List


class PermissionCreate(BaseModel):
    name: str = Field(..., pattern=r"^[a-z_:]+$")
    description: Optional[str] = None


class RoleCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    description: Optional[str] = None
    permissions: List[str] = []   # permission names to attach


class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    permissions: List[str]

    model_config = {"from_attributes": True}


class AssignRoleRequest(BaseModel):
    user_id: int
    role_name: str


class UserRolesResponse(BaseModel):
    user_id: int
    username: str
    roles: List[str]
    permissions: List[str]
