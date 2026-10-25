from storage import (
    TAB_TO_CATEGORY,
    clear,
    list_notifications,
    save_notification,
    stats,
    get_custom_rules,
    add_custom_rule,
    delete_custom_rule,
    reset_custom_rules,
)

# --- 自定义规则管理 API ---
class RuleRequest(BaseModel):
    app_keyword: str = ""
    text_keyword: str
    target_cat: str

@app.get("/api/rules")
def list_rules():
    return {"status": "success", "rules": get_custom_rules()}

@app.post("/api/rules")
def create_rule(data: RuleRequest):
    rule_id = add_custom_rule(data.app_keyword, data.text_keyword, data.target_cat)
    return {"status": "success", "id": rule_id}

@app.delete("/api/rules/{rule_id}")
def remove_rule(rule_id: int):
    delete_custom_rule(rule_id)
    return {"status": "success", "deleted_id": rule_id}

@app.post("/api/rules/reset")
def reset_rules():
    reset_custom_rules()
    return {"status": "success", "message": "已恢复默认规则"}