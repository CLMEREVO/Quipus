from fastapi import FastAPI
from pydantic import BaseModel
# 导入队长写的大模型清洗函数（假设保存在同目录的 llm_service.py 中）
from test_ai import clean_notification_text

app = FastAPI(title="Quipus Backend", description="智能信息去噪与聚合系统后端")

class NotificationRequest(BaseModel):
    text: str

@app.get("/")
def read_root():
    return {"message": "Quipus Backend is running successfully!"}

@app.post("/api/clean-notification")
def clean_notification(data: NotificationRequest):
    raw_text = data.text
    
    # 真正调用队长的大模型函数进行清洗！
    processed_data = clean_notification_text(raw_text)
    
    return {
        "status": "success",
        "raw_text": raw_text,
        "processed_result": processed_data
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)