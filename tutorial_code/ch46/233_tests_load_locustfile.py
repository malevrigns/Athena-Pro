"""Athena 压测 - 模拟真实用户行为"""
import json
import random
import time

from locust import HttpUser, task, between, events


# 压测用的问题池(50 个典型问题)
QUESTIONS = json.load(open("tests/load/question_bank.json"))


class AthenaUser(HttpUser):
    """模拟一个用户的完整使用流。"""
    wait_time = between(2, 8)            # 用户行为间隔
    
    def on_start(self):
        self.user_id = f"loadtest-{random.randint(1, 100000)}"
    
    @task(10)
    def submit_and_stream(self):
        """主流量:提交研究任务,订阅 SSE,等结果。"""
        question = random.choice(QUESTIONS)
        
        # 1) 创建任务
        with self.client.post(
            "/v1/research",
            json={"question": question, "user_id": self.user_id},
            catch_response=True,
            name="POST /v1/research",
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"create failed: {resp.status_code}")
                return
            task_id = resp.json()["task_id"]
        
        # 2) 订阅 SSE,等完成或超时
        t0 = time.perf_counter()
        with self.client.get(
            f"/v1/research/{task_id}/stream",
            stream=True,
            catch_response=True,
            name="GET /v1/research/[id]/stream",
            timeout=300,
        ) as resp:
            done = False
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("event: done"):
                    done = True
                    break
                if line.startswith("event: error"):
                    resp.failure("graph error")
                    return
                if time.perf_counter() - t0 > 180:
                    resp.failure("client timeout 180s")
                    return
            
            if done:
                resp.success()
                # 记录端到端延迟
                events.request.fire(
                    request_type="E2E",
                    name="research_complete",
                    response_time=int((time.perf_counter() - t0) * 1000),
                    response_length=0,
                    exception=None,
                )
    
    @task(1)
    def healthz(self):
        self.client.get("/healthz", name="GET /healthz")