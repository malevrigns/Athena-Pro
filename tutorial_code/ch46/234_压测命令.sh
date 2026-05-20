# 50 并发用户,持续 5 分钟,逐步爬坡
locust -f tests/load/locustfile.py \
    --host http://athena-staging.internal \
    --users 50 \
    --spawn-rate 5 \
    --run-time 5m \
    --headless \
    --html report.html