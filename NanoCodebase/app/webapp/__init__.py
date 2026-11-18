"""Public interface for the web app link.

Pushes robot state / expressions to the BrainCharge web app so its face screen
follows the robot, and polls the webapp inbox for settings (ui.settings).

Example:
    from app.webapp import WebAppEvents, RobotState, Expression
"""

from .service import DisabledWebAppEvents, Expression, RobotState, WebAppEvents
__all__ = ["WebAppEvents", "DisabledWebAppEvents", "RobotState", "Expression"]
