from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
# 导入队长写的大模型清洗函数
from test_ai import clean_notification_text

app = FastAPI(title="Quipus Backend", description="智能信息去噪与聚合系统后端")

# 🚨 核心：必须加上这段 CORS 中间件配置，允许前端跨域调用！
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 允许所有前端来源
    allow_credentials=True,
    allow_methods=["*"],      # 允许所有 HTTP 方法 (GET, POST, OPTIONS 等)
    allow_headers=["*"],      # 允许所有请求头
)

class NotificationRequest(BaseModel):
    text: str

@app.get("/")
def read_root():
    return {"message": "Quipus Backend is running successfully!"}

@app.post("/api/clean")
def clean_notification(data: NotificationRequest):
    raw_text = data.text
    
    # 调用大模型函数进行清洗
    processed_data = clean_notification_text(raw_text)
    
    return {
        "status": "success",
        "raw_text": raw_text,
        "processed_result": processed_data
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)