from agent.state import WorldModel
from agent.roles import RoleManager
from agent.fsm import AgentFSM


class Player:
    def __init__(self, side, unum, role_manager, team_name="team"):
        self.side        = side
        self.unum        = unum
        self.team_name   = team_name
        self.role        = role_manager.get_role(unum)
        self.world_model = WorldModel()
        self.world_model.unum      = unum
        self.world_model.side      = side
        self.world_model.self_role = self.role
        self.fsm = AgentFSM(unum, self.role, role_manager, team_name)
