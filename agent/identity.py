"""Platform-user -> approver-identity mapping.

Deliberately NOT tied to MsgStack's Persona model: Persona there means a
buyer persona scoped to one canon domain (e.g. "CKO", "IT Director"), not a
system user — mapping a Slack user to a buyer persona would be a category
error. All this needs is a human-readable name to pass as `performed_by`
when logging a review action, so it lives in its own tiny store instead of
reaching into src/store.py.
"""

from __future__ import annotations

from sqlalchemy import Column, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from agent.config import settings

Base = declarative_base()


class AgentIdentity(Base):
    __tablename__ = "agent_identities"

    platform = Column(String, primary_key=True)  # "slack" | "teams"
    platform_user_id = Column(String, primary_key=True)
    display_name = Column(String, nullable=True)
    email = Column(String, nullable=True)


class IdentityStore:
    def __init__(self, db_url: str | None = None):
        self._engine = create_engine(db_url or settings.agent_identity_db_url)
        Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    def upsert(self, platform: str, platform_user_id: str, display_name: str | None = None,
               email: str | None = None) -> None:
        with self._Session() as s:
            existing = s.get(AgentIdentity, (platform, platform_user_id))
            if existing:
                if display_name:
                    existing.display_name = display_name
                if email:
                    existing.email = email
            else:
                s.add(AgentIdentity(
                    platform=platform,
                    platform_user_id=platform_user_id,
                    display_name=display_name,
                    email=email,
                ))
            s.commit()

    def resolve(self, platform: str, platform_user_id: str) -> str:
        """Return the best available label for `performed_by` — falls back to a
        platform-prefixed raw ID when nobody has mapped this user yet, so approval
        logging never fails for lack of an identity row."""
        with self._Session() as s:
            row = s.get(AgentIdentity, (platform, platform_user_id))
            if row and (row.display_name or row.email):
                return row.display_name or row.email
        return f"{platform}:{platform_user_id}"
