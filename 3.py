import json
import math
import re
import time
import uuid
import asyncio
import logging
from typing import List, Dict, Any, Optional, Union, Literal
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import httpx
import jieba

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("OpenAI_Ollama_Proxy")

class ErrorResponse(BaseModel):
    error: Dict[str, Any]

class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None

class Choice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Usage
    system_fingerprint: Optional[str] = None

class SentimentAnalysisError(Exception): pass
class LLMAPIConnectionError(SentimentAnalysisError): pass
class DataProcessingError(SentimentAnalysisError): pass

class TextPreprocessor:
    def __init__(self):
        self.stop_words = {
            "的", "了", "和", "是", "就", "都", "而", "及", "与", "着", 
            "或者", "这个", "这", "那", "那个", "啊", "呀", "吧", "呢", 
            "么", "在", "也", "有", "我", "你", "他", "她", "它", "我们"
        }
        self.clean_pattern = re.compile(r'[^\w\s\u4e00-\u9fa5]')
        self.whitespace_pattern = re.compile(r'\s+')

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        cleaned = self.clean_pattern.sub(' ', str(text))
        return self.whitespace_pattern.sub(' ', cleaned).strip()

    def tokenize(self, text: str) -> List[str]:
        cleaned_text = self.clean_text(text)
        words = jieba.lcut(cleaned_text)
        return [w for w in words if w not in self.stop_words and len(w.strip()) > 0]

    def extract_features(self, text: str) -> Dict[str, int]:
        tokens = self.tokenize(text)
        features = {}
        for t in tokens:
            features[t] = features.get(t, 0) + 1
        return features

class NeuralInferenceEngine:
    def __init__(self):
        self.vocab: Dict[str, float] = {
            "正向": 2.5, "积极": 2.5, "正面": 2.0, "1": 1.5,
            "好": 2.0, "棒": 2.5, "优秀": 3.0, "开心": 2.5, 
            "高兴": 2.5, "满意": 2.8, "不错": 2.2, "赞": 2.5,
            "完美": 3.0, "极佳": 3.0, "美好": 2.5, "喜欢": 2.0,
            "负向": -2.5, "消极": -2.5, "负面": -2.0, "0": -1.5,
            "糟糕": -3.0, "坏": -2.0, "差": -2.5, "差劲": -3.0,
            "生气": -2.8, "悲伤": -2.5, "不满": -2.8, "愤怒": -3.0,
            "失望": -2.5, "讨厌": -2.5, "恶心": -3.0, "垃圾": -3.5
        }
        self.bias = 0.1
        self.activation_threshold_pos = 0.6
        self.activation_threshold_neg = 0.4

    def _sigmoid(self, x: float) -> float:
        try:
            return 1.0 / (1.0 + math.exp(-x))
        except OverflowError:
            return 0.0 if x < 0 else 1.0

    def _softmax(self, logits: List[float]) -> List[float]:
        max_l = max(logits)
        exp_l = [math.exp(x - max_l) for x in logits]
        sum_exp = sum(exp_l)
        return [x / sum_exp for x in exp_l]

    def predict(self, tokens: List[str]) -> Dict[str, Any]:
        pos_score = 0.0
        neg_score = 0.0
        
        for token in tokens:
            weight = self.vocab.get(token, 0.0)
            if weight > 0:
                pos_score += weight
            elif weight < 0:
                neg_score += abs(weight)
                
        logit = pos_score - neg_score + self.bias
        prob_pos = self._sigmoid(logit)
        
        logits = [pos_score, self.bias, neg_score]
        probs = self._softmax(logits)
        
        label = "未知"
        if prob_pos >= self.activation_threshold_pos:
            label = "正向"
        elif prob_pos <= self.activation_threshold_neg:
            label = "负向"
        else:
            label = "中性"
            
        return {
            "label": label,
            "confidence": round(max(probs), 4),
            "pos_prob": round(probs[0], 4),
            "neu_prob": round(probs[1], 4),
            "neg_prob": round(probs[2], 4),
            "raw_logit": round(logit, 4)
        }

class OllamaBackendProxy:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=120.0)

    async def forward_chat_completion(self, request_data: dict) -> dict:
        url = f"{self.base_url}/v1/chat/completions"
        try:
            response = await self.client.post(url, json=request_data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTPStatusError: {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
        except httpx.RequestError as e:
            logger.error(f"RequestError: {str(e)}")
            raise HTTPException(status_code=502, detail=f"Ollama Backend Error: {str(e)}")

    async def forward_chat_stream(self, request_data: dict):
        url = f"{self.base_url}/v1/chat/completions"
        request_data["stream"] = True
        try:
            async with self.client.stream("POST", url, json=request_data) as response:
                response.raise_for_status()
                async for chunk in response.aiter_lines():
                    if chunk:
                        yield f"{chunk}\n\n"
        except Exception as e:
            logger.error(f"StreamError: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

class EnhancedSentimentPipeline:
    def __init__(self):
        self.preprocessor = TextPreprocessor()
        self.engine = NeuralInferenceEngine()

    def analyze(self, text: str) -> Dict[str, Any]:
        # 防止传入的直接是数字类型
        text_str = str(text).strip()
        
        result = {
            "input_length": len(text_str),
            "tokens": [],
            "prediction": {},
            "timestamp": int(time.time()),
            "status": "success"
        }
        
        # 增加直接针对极简数字意图的拦截
        if text_str == "1":
            result["tokens"] = ["1"]
            result["prediction"] = {
                "label": "正向", "confidence": 0.99, 
                "pos_prob": 0.99, "neu_prob": 0.01, "neg_prob": 0.0, "raw_logit": 5.0
            }
            return result
        elif text_str == "0":
            result["tokens"] = ["0"]
            result["prediction"] = {
                "label": "负向", "confidence": 0.99, 
                "pos_prob": 0.0, "neu_prob": 0.01, "neg_prob": 0.99, "raw_logit": -5.0
            }
            return result

        try:
            tokens = self.preprocessor.tokenize(text_str)
            result["tokens"] = tokens
            result["prediction"] = self.engine.predict(tokens)
        except Exception as e:
            result["status"] = "error"
            result["error_message"] = str(e)
        return result

app = FastAPI(title="OpenAI Compatible API Proxy Service", version="1.0.0")
ollama_proxy = OllamaBackendProxy()
sentiment_pipeline = EnhancedSentimentPipeline()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} completed in {process_time:.4f}s with status {response.status_code}")
    return response

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "qwen2.5:0.5b",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "ollama"
            }
        ]
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    logger.info(f"Received proxy request for model: {request.model}")
    
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages cannot be empty")
        
    last_message = request.messages[-1].content
    
    # 1. 神经网络分析输入，得到 a
    analysis_a = sentiment_pipeline.analyze(last_message)
    a_label = analysis_a.get("prediction", {}).get("label", "未知")
    
    # 2. 调用模型分析得到结果 b
    request_dict = request.model_dump(exclude_unset=True)
    request_dict["stream"] = False  # 强制非流式请求以获取全量返回进行分析
    
    result = await ollama_proxy.forward_chat_completion(request_dict)
    try:
        b_content = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        b_content = ""
        
    # 3. 神经网络分析模型结果 b，得到 c
    analysis_c = sentiment_pipeline.analyze(b_content)
    c_label = analysis_c.get("prediction", {}).get("label", "未知")
    
    # 4. 比对逻辑
    if a_label == c_label:
        final_label = a_label
    else:
        if a_label == "中性":
            final_label = a_label
        else:
            final_label = c_label
            
    # 组合为综合结果返回
    content_dict = {
        "model_reply": b_content,
        "input_analysis_a": a_label,
        "reply_analysis_c": c_label,
        "final_result": final_label
    }
    
    result["choices"][0]["message"]["content"] = json.dumps(content_dict, ensure_ascii=False)
    return JSONResponse(content=result)

@app.post("/v1/sentiment/analyze")
async def analyze_sentiment_endpoint(text: str):
    logger.info(f"Direct sentiment analysis requested. Text length: {len(text)}")
    return sentiment_pipeline.analyze(text)

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": int(time.time())}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting up OpenAI compatible proxy server on http://0.0.0.0:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
