# 智造云智能销售中心

独立 PawApp。基于真实销售订单、客户与业绩数据完成销售BI汇总、RFM客户价值分层和销售业绩目标达成统计，所有结果进入可审阅工件等待人工确认。

## 验证

```bash
python -m unittest discover -s tests -v
python -m py_compile backend/main.py backend/sales_engine.py backend/sales_workflow.py
node --check ui/index.js
```
