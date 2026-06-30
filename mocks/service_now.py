"""
Mock ServiceNow API
====================
Simulates ServiceNow REST API with OAuth2 authentication and ticket management.
Used by Agent 4 (Orchestration & Routing Agent) for MAP dispatch.
"""

import uuid
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class MockServiceNowAPI:
    """
    Simulates ServiceNow ITSM ticket creation and management.
    No real ServiceNow instance required - all state is in-memory.
    """

    def __init__(self):
        self._authenticated = False
        self._access_token: Optional[str] = None
        self._tickets: dict[str, dict] = {}
        self._oauth_config = {
            "client_id": "mock_client_id_anupalan",
            "client_secret": "mock_client_secret_anupalan",
            "scope": "read_write_incident",
        }

    def authenticate(self, client_id: str, client_secret: str) -> dict:
        """
        Simulate OAuth2 client_credentials authentication.
        
        Returns:
            dict with access_token and expires_in
        """
        if client_id == self._oauth_config["client_id"]:
            self._access_token = f"mock_token_{uuid.uuid4().hex[:16]}"
            self._authenticated = True
            logger.info("ServiceNow OAuth2 authentication successful")
            return {
                "access_token": self._access_token,
                "token_type": "Bearer",
                "expires_in": 3600,
            }
        raise PermissionError("Invalid OAuth2 credentials")

    def create_incident(
        self,
        short_description: str,
        description: str,
        assignment_group: str,
        priority: int = 3,
        category: str = "Compliance",
    ) -> dict:
        """
        Create a ServiceNow incident ticket for a MAP.
        
        Args:
            short_description: Ticket title
            description: Full ticket body with MAP details
            assignment_group: Department/team to assign
            priority: 1=Critical, 2=High, 3=Moderate, 4=Low
            category: Incident category
            
        Returns:
            dict with ticket number and sys_id
        """
        if not self._authenticated:
            raise PermissionError("Not authenticated. Call authenticate() first.")

        ticket_id = f"INC{uuid.uuid4().hex[:8].upper()}"
        sys_id = uuid.uuid4().hex

        ticket = {
            "number": ticket_id,
            "sys_id": sys_id,
            "short_description": short_description,
            "description": description,
            "assignment_group": assignment_group,
            "assigned_to": "",
            "priority": priority,
            "category": category,
            "state": "New",
            "opened_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "closed_at": None,
            "work_notes": [],
        }

        self._tickets[ticket_id] = ticket
        logger.info("Created ServiceNow ticket %s for %s", ticket_id, assignment_group)

        return {
            "number": ticket_id,
            "sys_id": sys_id,
            "state": "New",
            "url": f"https://canarabank.service-now.com/incident.do?sys_id={sys_id}",
        }

    def update_incident(self, ticket_id: str, updates: dict) -> dict:
        """Update an existing incident."""
        if ticket_id not in self._tickets:
            raise ValueError(f"Ticket {ticket_id} not found")

        ticket = self._tickets[ticket_id]
        ticket.update(updates)
        ticket["updated_at"] = datetime.utcnow().isoformat()

        if "work_note" in updates:
            ticket["work_notes"].append({
                "note": updates["work_note"],
                "timestamp": datetime.utcnow().isoformat(),
            })

        logger.info("Updated ticket %s: %s", ticket_id, updates)
        return ticket

    def close_incident(self, ticket_id: str, resolution: str = "Resolved") -> dict:
        """Close an incident after validation."""
        return self.update_incident(ticket_id, {
            "state": "Closed",
            "close_code": resolution,
            "closed_at": datetime.utcnow().isoformat(),
        })

    def get_incident(self, ticket_id: str) -> Optional[dict]:
        """Retrieve incident details."""
        return self._tickets.get(ticket_id)

    def list_incidents(self, state: Optional[str] = None) -> list[dict]:
        """List all incidents, optionally filtered by state."""
        tickets = list(self._tickets.values())
        if state:
            tickets = [t for t in tickets if t["state"] == state]
        return tickets
