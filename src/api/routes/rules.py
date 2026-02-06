from typing import List

from fastapi import APIRouter, HTTPException, Depends
from src.api.dependencies import get_config
from src.api.models import RuleCreate, RuleUpdate, RuleResponse
from src.review.rules_manager import RulesManager
from src.utils.config import AppConfig

router = APIRouter()

def get_rules_manager(config: AppConfig = Depends(get_config)) -> RulesManager:
    """Dependency to get rules manager instance."""
    return RulesManager(config.data_dir / "overrides" / "rules.db")

@router.get("/", response_model=List[RuleResponse])
def list_rules(manager: RulesManager = Depends(get_rules_manager)):
    """List all automation rules."""
    return manager.get_all_rules()

@router.post("/", response_model=RuleResponse)
def create_rule(rule: RuleCreate, manager: RulesManager = Depends(get_rules_manager)):
    """Create a new automation rule."""
    return manager.add_rule(rule)

@router.put("/{rule_id}", response_model=RuleResponse)
def update_rule(rule_id: int, rule: RuleUpdate, manager: RulesManager = Depends(get_rules_manager)):
    """Update an existing automation rule."""
    updated = manager.update_rule(rule_id, rule)
    if not updated:
        raise HTTPException(status_code=404, detail="Rule not found")
    return updated

@router.delete("/{rule_id}")
def delete_rule(rule_id: int, manager: RulesManager = Depends(get_rules_manager)):
    """Delete an automation rule."""
    success = manager.delete_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "success"}
