(function () {
  var Q = window.QwenPaw;
  if (!Q || !Q.host || !Q.host.React || !Q.registerRoutes) return;
  var React = Q.host.React, antd = Q.host.antd, h = React.createElement;
  function request(path, body) {
    return Q.host.fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) }).then(function (response) {
      return response.json().then(function (data) { if (!response.ok) throw new Error(data.detail || "操作失败"); return data; });
    });
  }
  function kpi(value, label) {
    return h(antd.Statistic, { title: label, value: value, precision: 2 });
  }
  function SalesStudio() {
    var biTextState = React.useState(""), biText = biTextState[0], setBiText = biTextState[1];
    var biResultState = React.useState(null), biResult = biResultState[0], setBiResult = biResultState[1];
    var crmTextState = React.useState(""), crmText = crmTextState[0], setCrmText = crmTextState[1];
    var crmResultState = React.useState(null), crmResult = crmResultState[0], setCrmResult = crmResultState[1];
    var perfTextState = React.useState(""), perfText = perfTextState[0], setPerfText = perfTextState[1];
    var perfResultState = React.useState(null), perfResult = perfResultState[0], setPerfResult = perfResultState[1];
    var reviewerState = React.useState(""), reviewer = reviewerState[0], setReviewer = reviewerState[1];
    var recentState = React.useState([]), recent = recentState[0], setRecent = recentState[1];
    var loadingState = React.useState(false), loading = loadingState[0], setLoading = loadingState[1];
    var message = antd.App.useApp().message;
    function parseJson(text, label) {
      var parsed;
      try { parsed = JSON.parse(text); } catch (err) { message.error(label + "必须是JSON数组"); return null; }
      if (!Array.isArray(parsed) || !parsed.length) { message.warning("请提供至少一条" + label); return null; }
      return parsed;
    }
    function loadRecent() {
      return Q.host.fetch("/zhiyun-sales-studio/artifacts").then(function (response) { return response.json(); })
        .then(function (data) { setRecent(data.artifacts || []); }).catch(function () {});
    }
    function runBi() {
      var orders = parseJson(biText, "销售订单");
      if (!orders) return;
      setLoading(true);
      request("/zhiyun-sales-studio/artifacts/bi", { orders: orders }).then(function (data) { setBiResult(data); message.success("已生成销售BI工件，等待审阅"); loadRecent(); })
        .catch(function (e) { message.error(e.message); }).finally(function () { setLoading(false); });
    }
    function runCrm() {
      var customers = parseJson(crmText, "客户数据");
      if (!customers) return;
      setLoading(true);
      request("/zhiyun-sales-studio/artifacts/customers", { customers: customers }).then(function (data) { setCrmResult(data); message.success("已生成客户价值工件，等待审阅"); loadRecent(); })
        .catch(function (e) { message.error(e.message); }).finally(function () { setLoading(false); });
    }
    function runPerf() {
      var records = parseJson(perfText, "业绩记录");
      if (!records) return;
      setLoading(true);
      request("/zhiyun-sales-studio/artifacts/performance", { records: records }).then(function (data) { setPerfResult(data); message.success("已生成业绩统计工件，等待审阅"); loadRecent(); })
        .catch(function (e) { message.error(e.message); }).finally(function () { setLoading(false); });
    }
    function decide(kind, action) {
      if (!reviewer.trim()) { message.warning("请输入审阅人"); return; }
      var result = kind === "bi" ? biResult : kind === "customers" ? crmResult : perfResult;
      if (!result) { message.warning("请先生成工件"); return; }
      request("/zhiyun-sales-studio/artifacts/" + result.id + "/reviews", { action: action, reviewer: reviewer }).then(function (data) {
        if (kind === "bi") setBiResult(data); else if (kind === "customers") setCrmResult(data); else setPerfResult(data);
        message.success(action === "accept" ? "工件已接受" : "工件已驳回"); loadRecent();
      }).catch(function (e) { message.error(e.message); });
    }
    function exportArtifact(result) {
      if (!result) return;
      window.open("/zhiyun-sales-studio/artifacts/" + result.id + "/export", "_blank");
    }
    function reviewRow(result, setResult, kind, title, countLabel) {
      return h("div", null,
        h(antd.Card, { size: "small", title: title + "（" + countLabel + "）", style: { marginTop: 16 }, extra: h(antd.Tag, { color: result.status === "accepted" ? "green" : result.status === "rejected" ? "red" : "orange" }, result.status) },
          h("div", { style: { display: "flex", gap: 8, marginTop: 8 } },
            h(antd.Input, { value: reviewer, onChange: function (e) { setReviewer(e.target.value); }, placeholder: "审阅人", style: { width: 180 } }),
            h(antd.Button, { type: "primary", onClick: function () { decide(kind, "accept"); } }, "接受"),
            h(antd.Button, { danger: true, onClick: function () { decide(kind, "reject"); } }, "驳回"),
            h(antd.Button, { disabled: result.status !== "accepted", onClick: function () { exportArtifact(result); } }, "导出")
          )
        )
      );
    }
    var biExample = '[{"date":"2026-07-01","product":"电机","category":"动力部件","region":"华东","quantity":40,"unit_price":320},{"date":"2026-07-15","product":"控制器","category":"电子部件","region":"华南","quantity":25,"unit_price":180},{"date":"2026-08-02","product":"电机","category":"动力部件","region":"华东","quantity":48,"unit_price":320}]';
    var crmExample = '[{"name":"广东超能","order_count":12,"total_spend":86000,"last_order_date":"2026-08-10"},{"name":"华东装备","order_count":3,"total_spend":15000,"last_order_date":"2026-03-01"}]';
    var perfExample = '[{"salesperson":"李工","revenue":450000,"orders":28,"target":400000},{"salesperson":"王工","revenue":310000,"orders":19,"target":450000}]';
    var intents = [
      { key: "bi", label: "销售BI分析" },
      { key: "crm", label: "客户价值分层" },
      { key: "perf", label: "销售业绩统计" }
    ];
    var activeState = React.useState("bi"), active = activeState[0], setActive = activeState[1];
    React.useEffect(function () { loadRecent(); }, []);
    return h("div", { style: { padding: 28, height: "100%", overflow: "auto", background: "#f7f8fa" } }, h("div", { style: { maxWidth: 1080, margin: "0 auto" } },
      h("h2", null, "智能销售中心"), h("p", { style: { color: "#667085" } }, "销售BI汇总、RFM客户价值分层、销售业绩目标达成与排名。"),
      h(antd.Tabs, { activeKey: active, onChange: setActive, items: intents.map(function (item) {
        return { key: item.key, label: item.label, children: item.key === "bi" ? (
          h("div", null,
            h(antd.Alert, { type: "info", showIcon: true, message: "销售BI", description: "粘贴真实订单JSON数组，每项含 date、product、category、region、quantity、unit_price。" }),
            h(antd.Input.TextArea, { style: { marginTop: 12 }, value: biText, rows: 8, onChange: function (e) { setBiText(e.target.value); }, placeholder: biExample }),
            h(antd.Button, { type: "primary", loading: loading, style: { marginTop: 12 }, onClick: runBi }, "分析并生成工件"),
            biResult ? h("div", null,
              h(antd.Row, { gutter: 16, style: { marginTop: 16 } },
                ["营收", "销量", "订单数", "客单价"].map(function (label, index) {
                  var value = [biResult.payload.kpis.revenue, biResult.payload.kpis.units, biResult.payload.kpis.orders, biResult.payload.kpis.avg_order_value][index];
                  return h(antd.Col, { span: 6, key: label }, h(antd.Card, { size: "small" }, kpi(value, label)));
                })
              ),
              biResult.payload.alerts.length ? h(antd.Alert, { style: { marginTop: 12 }, type: "warning", showIcon: true, message: "预警", description: biResult.payload.alerts.join("；") }) : null,
              h(antd.Card, { size: "small", title: "月度趋势", style: { marginTop: 12 } },
                h(antd.Table, { size: "small", rowKey: "month", dataSource: biResult.payload.by_month, pagination: false, columns: [
                  { title: "月份", dataIndex: "month" }, { title: "营收", dataIndex: "revenue" }, { title: "环比", dataIndex: "growth", render: function (v) { return v === undefined ? "-" : v + "%"; } }
                ] })
              ),
              h(antd.Card, { size: "small", title: "Top 产品", style: { marginTop: 12 } },
                h(antd.Table, { size: "small", rowKey: "product", dataSource: biResult.payload.top_products, pagination: false, columns: [
                  { title: "产品", dataIndex: "product" }, { title: "营收", dataIndex: "revenue" }, { title: "销量", dataIndex: "units" }, { title: "订单", dataIndex: "orders" }
                ] })
              ),
              reviewRow(biResult, setBiResult, "bi", "销售BI工件", biResult.payload.kpis.orders + " 单")
            ) : null
          )
        ) : item.key === "crm" ? (
          h("div", null,
            h(antd.Alert, { type: "info", showIcon: true, message: "客户价值分层", description: "粘贴客户JSON数组，每项含 name、order_count、total_spend、last_order_date。" }),
            h(antd.Input.TextArea, { style: { marginTop: 12 }, value: crmText, rows: 8, onChange: function (e) { setCrmText(e.target.value); }, placeholder: crmExample }),
            h(antd.Button, { type: "primary", loading: loading, style: { marginTop: 12 }, onClick: runCrm }, "分层并生成工件"),
            crmResult ? h("div", null,
              h(antd.Row, { gutter: 16, style: { marginTop: 16 } },
                ["VIP", "高价值", "普通", "待唤醒"].map(function (tier) {
                  return h(antd.Col, { span: 6, key: tier }, h(antd.Card, { size: "small" }, h(antd.Statistic, { title: tier, value: crmResult.payload.tiers[tier] || 0 })));
                })
              ),
              h(antd.Card, { size: "small", title: "客户明细", style: { marginTop: 12 } },
                h(antd.Table, { size: "small", rowKey: "name", dataSource: crmResult.payload.customers, pagination: { pageSize: 8 }, columns: [
                  { title: "客户", dataIndex: "name" }, { title: "RFM分", dataIndex: "score" },
                  { title: "层级", dataIndex: "tier", render: function (v) { return h(antd.Tag, { color: v === "VIP" ? "gold" : v === "高价值" ? "green" : v === "普通" ? "blue" : "orange" }, v); } },
                  { title: "流失风险", dataIndex: "churn_risk" },
                  { title: "建议", dataIndex: "suggestion", ellipsis: true }
                ] })
              ),
              reviewRow(crmResult, setCrmResult, "customers", "客户价值工件", crmResult.payload.count + " 位")
            ) : null
          )
        ) : (
          h("div", null,
            h(antd.Alert, { type: "info", showIcon: true, message: "销售业绩统计", description: "粘贴业绩JSON数组，每项含 salesperson、revenue、orders、target。" }),
            h(antd.Input.TextArea, { style: { marginTop: 12 }, value: perfText, rows: 8, onChange: function (e) { setPerfText(e.target.value); }, placeholder: perfExample }),
            h(antd.Button, { type: "primary", loading: loading, style: { marginTop: 12 }, onClick: runPerf }, "统计并生成工件"),
            perfResult ? h("div", null,
              h(antd.Alert, { style: { marginTop: 16 }, type: "info", showIcon: true, message: "整体达成率 " + perfResult.payload.summary.overall_attainment + "%", description: "总营收 " + perfResult.payload.summary.total_revenue + "，总目标 " + perfResult.payload.summary.total_target } ),
              h(antd.Card, { size: "small", title: "人员业绩", style: { marginTop: 12 } },
                h(antd.Table, { size: "small", rowKey: "salesperson", dataSource: perfResult.payload.records, pagination: false, columns: [
                  { title: "人员", dataIndex: "salesperson" }, { title: "营收", dataIndex: "revenue" },
                  { title: "订单", dataIndex: "orders" }, { title: "目标", dataIndex: "target" },
                  { title: "达成率", dataIndex: "attainment", render: function (v) { return v + "%"; } },
                  { title: "状态", dataIndex: "tier", render: function (v) { return h(antd.Tag, { color: v === "达标" ? "green" : v === "接近" ? "orange" : "red" }, v); } }
                ] })
              ),
              reviewRow(perfResult, setPerfResult, "performance", "业绩统计工件", perfResult.payload.count + " 人")
            ) : null
          )
        )};
      }) }
    )));
  }
  Q.registerRoutes("zhiyun-sales-studio", [{ path: "/apps/zhiyun-sales-studio", component: SalesStudio, label: "智能销售中心", icon: "📈", priority: 81 }]);
})();
