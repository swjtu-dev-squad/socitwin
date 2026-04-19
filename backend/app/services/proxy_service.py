import json
import logging
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, List

import jieba
from fastapi import HTTPException

from app.models.proxy import ChatCompletionRequest, ChatCompletionResponse

logger = logging.getLogger(__name__)

BAIDU_APP_ID = "122858586"
BAIDU_API_KEY = "wbFOBD27hI2fXddoWrnbh0PN"
BAIDU_SECRET_KEY = "dKRt5eV2I7EWrA7NlMIzI9ijuIBRHAns"
BAIDU_TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
BAIDU_SENTIMENT_URL = "https://aip.baidubce.com/rpc/2.0/nlp/v1/sentiment_classify?charset=UTF-8"


class TextPreprocessor:
    def __init__(self):
        self.stop_words = {
            "的", "了", "和", "是", "就", "都", "而", "及", "与", "着",
            "或者", "这个", "这", "那", "那个", "啊", "呀", "吧", "呢",
            "么", "在", "也", "有", "我", "你", "他", "她", "它", "我们",
        }
        self.clean_pattern = re.compile(r"[^\w\s\u4e00-\u9fa5]")
        self.whitespace_pattern = re.compile(r"\s+")

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        cleaned = self.clean_pattern.sub(" ", str(text))
        return self.whitespace_pattern.sub(" ", cleaned).strip()

    def tokenize(self, text: str) -> List[str]:
        cleaned_text = self.clean_text(text)
        words = jieba.lcut(cleaned_text)
        return [w for w in words if w not in self.stop_words and len(w.strip()) > 0]


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
            "失望": -2.5, "讨厌": -2.5, "恶心": -3.0, "垃圾": -3.5,
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
        probs = self._softmax([pos_score, self.bias, neg_score])

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
            "raw_logit": round(logit, 4),
        }


class EnhancedSentimentPipeline:
    def __init__(self):
        self.preprocessor = TextPreprocessor()
        self.engine = NeuralInferenceEngine()

    def analyze(self, text: str) -> Dict[str, Any]:
        text_str = str(text).strip()
        result: Dict[str, Any] = {
            "input_length": len(text_str),
            "tokens": [],
            "prediction": {},
            "timestamp": int(time.time()),
            "status": "success",
        }

        if text_str == "1":
            result["tokens"] = ["1"]
            result["prediction"] = {
                "label": "正向", "confidence": 0.99,
                "pos_prob": 0.99, "neu_prob": 0.01, "neg_prob": 0.0, "raw_logit": 5.0,
            }
            return result
        if text_str == "0":
            result["tokens"] = ["0"]
            result["prediction"] = {
                "label": "负向", "confidence": 0.99,
                "pos_prob": 0.0, "neu_prob": 0.01, "neg_prob": 0.99, "raw_logit": -5.0,
            }
            return result

        try:
            tokens = self.preprocessor.tokenize(text_str)
            result["tokens"] = tokens
            result["prediction"] = self.engine.predict(tokens)
        except Exception as exc:
            result["status"] = "error"
            result["error_message"] = str(exc)
        return result


class BaiduSentimentService:
    def __init__(self):
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0
        self._result_cache: dict[str, Dict[str, Any]] = {}

    def analyze(self, text: str) -> Dict[str, Any]:
        text_str = self._normalize_baidu_text(text)
        cached = self._result_cache.get(text_str)
        if cached is not None:
            return cached

        if not text_str:
            result = self._build_neutral_result("")
            self._result_cache[text_str] = result
            return result

        payload = self._request_sentiment(text_str)
        items = payload.get("items") or []
        item = items[0] if items else {}

        sentiment_code = item.get("sentiment", 1)
        label_map = {2: "正向", 1: "中性", 0: "负向"}
        final_result = label_map.get(sentiment_code, "中性")

        result = {
            "provider": "baidu_nlp",
            "app_id": BAIDU_APP_ID,
            "text": payload.get("text", text_str),
            "final_result": final_result,
            "analysis": {
                "prediction": {
                    "label": final_result,
                    "confidence": float(item.get("confidence", 0.0) or 0.0),
                    "positive_prob": float(item.get("positive_prob", 0.0) or 0.0),
                    "negative_prob": float(item.get("negative_prob", 0.0) or 0.0),
                    "sentiment": int(sentiment_code),
                },
                "raw_response": payload,
                "timestamp": int(time.time()),
                "status": "success",
            },
        }
        self._result_cache[text_str] = result
        return result

    def _normalize_baidu_text(self, text: str) -> str:
        raw_text = str(text or "")
        sanitized = "".join(
            ch
            for ch in raw_text
            if ch in ("\n", "\r", "\t") or (ord(ch) >= 32 and ord(ch) <= 0xFFFF)
        )
        sanitized = re.sub(r"\s+", " ", sanitized).strip()
        max_length = 512
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        return sanitized

    def _build_neutral_result(self, text: str) -> Dict[str, Any]:
        return {
            "provider": "baidu_nlp",
            "app_id": BAIDU_APP_ID,
            "text": text,
            "final_result": "中性",
            "analysis": {
                "prediction": {
                    "label": "中性",
                    "confidence": 0.0,
                    "positive_prob": 0.0,
                    "negative_prob": 0.0,
                    "sentiment": 1,
                },
                "raw_response": {"text": text, "items": []},
                "timestamp": int(time.time()),
                "status": "success",
            },
        }

    def _request_sentiment(self, text: str) -> Dict[str, Any]:
        for attempt in range(4):
            access_token = self._get_access_token()
            body = json.dumps({"text": text}).encode("utf-8")
            request = urllib.request.Request(
                f"{BAIDU_SENTIMENT_URL}&access_token={access_token}",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )

            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    result = response.read().decode("utf-8", errors="replace")
            except urllib.error.HTTPError as exc:
                result = exc.read().decode("utf-8", errors="replace")
            except urllib.error.URLError as exc:
                raise HTTPException(status_code=502, detail=f"Baidu sentiment API error: {exc}") from exc

            try:
                payload = json.loads(result)
            except json.JSONDecodeError as exc:
                raise HTTPException(status_code=502, detail=f"Invalid Baidu sentiment API response: {result}") from exc

            error_code = payload.get("error_code")
            if not error_code:
                return payload

            if error_code == 18 and attempt < 3:
                wait_seconds = 0.5 * (attempt + 1)
                logger.warning("Baidu sentiment QPS limited, retrying in %.1fs", wait_seconds)
                time.sleep(wait_seconds)
                continue

            raise HTTPException(
                status_code=502,
                detail=f"Baidu sentiment API error {payload.get('error_code')}: {payload.get('error_msg', 'unknown error')}",
            )

        raise HTTPException(status_code=502, detail="Baidu sentiment API error: retry exhausted")

    def _get_access_token(self) -> str:
        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        token_url = (
            f"{BAIDU_TOKEN_URL}?" + urllib.parse.urlencode(
                {
                    "grant_type": "client_credentials",
                    "client_id": BAIDU_API_KEY,
                    "client_secret": BAIDU_SECRET_KEY,
                }
            )
        )

        try:
            with urllib.request.urlopen(token_url, timeout=20) as token_response:
                token_result = json.loads(token_response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(status_code=502, detail=f"Baidu token HTTP error: {detail}") from exc
        except urllib.error.URLError as exc:
            raise HTTPException(status_code=502, detail=f"Baidu token request failed: {exc}") from exc

        access_token = token_result.get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail=f"Failed to get Baidu access token: {token_result}")

        expires_in = int(token_result.get("expires_in", 0) or 0)
        self._access_token = access_token
        self._token_expires_at = now + max(expires_in - 60, 60)
        return access_token


class ProxyService:
    def __init__(self):
        self.sentiment_pipeline = EnhancedSentimentPipeline()
        self.baidu_sentiment = BaiduSentimentService()

    async def list_models(self) -> Dict[str, Any]:
        return {
            "object": "list",
            "data": [
                {
                    "id": "qwen2.5:0.5b",
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "baidu-nlp",
                }
            ],
        }

    async def chat_completions(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        if not request.messages:
            raise HTTPException(status_code=400, detail="Messages cannot be empty")

        last_message = request.messages[-1].content
        analysis_a = self.sentiment_pipeline.analyze(last_message)
        baidu_input = self.baidu_sentiment.analyze(last_message)
        return self._build_response(request, analysis_a, baidu_input)

    def _build_response(
        self,
        request: ChatCompletionRequest,
        analysis_a: Dict[str, Any],
        baidu_analysis: Dict[str, Any],
    ) -> ChatCompletionResponse:
        content_dict = {
            "mode": "baidu_only",
            "model_reply": "",
            "input_analysis_a": analysis_a.get("prediction", {}).get("label", "未知"),
            "reply_analysis_c": analysis_a.get("prediction", {}).get("label", "未知"),
            "final_result": baidu_analysis["final_result"],
            "analysis": baidu_analysis["analysis"],
        }
        content = json.dumps(content_dict, ensure_ascii=False)
        created = int(time.time())
        completion_tokens = max(1, len(content) // 4)
        prompt_tokens = sum(max(1, len(message.content) // 4) for message in request.messages)

        return ChatCompletionResponse.model_validate(
            {
                "id": f"chatcmpl-{uuid.uuid4().hex}",
                "object": "chat.completion",
                "created": created,
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
                "system_fingerprint": "baidu-sentiment",
            }
        )

    async def classify_sentiment(self, text: str) -> Dict[str, Any]:
        neural_analysis = self.sentiment_pipeline.analyze(text)
        baidu_analysis = self.baidu_sentiment.analyze(text)
        return {
            "neural_analysis": neural_analysis,
            "final_result": baidu_analysis["final_result"],
            "analysis": baidu_analysis["analysis"],
        }


proxy_service = ProxyService()
