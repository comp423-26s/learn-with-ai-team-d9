"""Team-specific test routes for initial onboarding.

This module provides a minimal test route so each team can scaffold
their own routes and Pydantic models. The route below is intentionally
small and documented so it appears in OpenAPI /docs immediately.
"""

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Team"])


class TeamTestResponse(BaseModel):
    message: str
    team: str


@router.get(
    "/team/test",
    summary="Team test endpoint",
    response_model=TeamTestResponse,
    response_description="A simple test payload from the team's router.",
)
def team_test() -> TeamTestResponse:
    """Return a simple payload to verify the router is registered."""
    return TeamTestResponse(message="Hello from the team router", team="your-team")
