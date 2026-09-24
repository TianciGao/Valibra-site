# BIRD-Interact 四维框架设计与评测分析
<page url="https://app.notion.com/p/3e5c6fba6efe8039b955c477fbebe2c3">русский</page>
<callout icon="💡" color="gray_bg">
	## 摘要
	我们在原 BIRD-Interact Agent 的基础上增加了数据库信息整理与检查流程，将<span color="red">表范围</span>、<span color="red">连接关系</span>、<span color="red">字段对应</span>和<span color="red">业务知识</span>保存为四维信息。检查通过后，原 BIRD-Interact Agent (我们简称为 Main agent) 据此编写 SQL 并只保留提交和执行SQL工具；主流程失败时，在剩余预算内启动原 Agent 补救。
	Full 测试集 600 题评测中，P1 通过数由 144 增至 150，总 Reward 由 124.5 增至 127.5，P2 通过数由 79 降至 75。
	总 token 由基线的 8,227 万增至 10,326 万，增加约 25.5%。因此，本轮结果体现了流程管理上的进展，但尚未表现出整体性能和成本优势。
	<unknown url="https://app.notion.com/p/3e3c6fba6efe80828c18d9b4ca6961e9#3e3c6fba6efe8086848cd4c1d55a0bc8" alt="external_object_instance"/>
</callout>
## 一、框架设计与实现
### 1. 总体架构
框架先整理信息，再检查是否足以编写 SQL。Check 负责指出缺口并申请补查；Gate 负责判断新证据是否要求重做字段对应或表范围。只有检查通过、且不再需要重做时，才进入正常 Main。主流程无法继续时，另行判断能否启动原 Agent 补救。
![总体流程：Check 补查、Gate 分流、临时重做与最终补救](assets/notion-zh-1.svg)
“四维”指四类信息，Structure 同时整理表和连接关系；Check 负责检查，不属于四维信息本身。
这里的“重新 Grounding”是依据新证据修订信息，不是固定把四个维度完整跑两遍。图中区分了两种循环：**Check 补查后再检查**，以及 **Gate 指定范围后重新整理信息**。两者都受预算、重复请求和调用上限约束。\[C07、C08、C17–C20\]
### 2. 四维信息及其来源
<table fit-page-width="true" header-row="true">
<tr>
<td>维度</td>
<td>作用</td>
<td>负责环节</td>
<td>调用工具——信息来源</td>
<td>保存内容</td>
</tr>
<tr>
<td>tables</td>
<td>确定查询范围</td>
<td>Structure</td>
<td>`get_schema`：建表信息、主外键、样例行</td>
<td>候选表名，不要求 SQL 使用全部候选表</td>
</tr>
<tr>
<td>join_keys</td>
<td>确定表间连接关系</td>
<td>Structure</td>
<td>schema 中的键与关系</td>
<td>如 [A.id](http://A.id) = B.a_id</td>
</tr>
<tr>
<td>column_mapping</td>
<td>将请求中的短语对应到字段</td>
<td>Mapping</td>
<td>`get_all_column_meanings`，结合请求、表范围和澄清</td>
<td>请求短语 → 字段或完整 JSON 路径</td>
</tr>
<tr>
<td>domain_knowledge</td>
<td>补充业务定义和公式</td>
<td>Knowledge</td>
<td>`get_all_knowledge_definitions`，结合请求和字段</td>
<td>官方定义原文及类别</td>
</tr>
</table>
<callout icon="💡" color="gray_bg">
	运行程序按顺序安排前期取证，三个工具各消耗 1 Bird-Coin，再将结果交给相应阶段判断。各阶段并不自由调用全部工具。\[C01–C05\]
	字段对应与计算关系分别处理。例如，cost → MaintCost 表示字段对应；用户回答“maintenance cost（维护成本）”用于明确其意图。请求中的 ratio of A to B （明确A与B之比）可以授权除法，但不能据此推断 A、B 内部还包含哪些成本项。一个短语关联多个字段，也不自动表示相加、相除或取最大值。
	Knowledge 输出的 ID 是当次检索目录的索引，正式保存的是定义内容。四维项尚未处理时用 null 表示，已检查且不需要时用 \[\] 表示。Mapping 另行记录四类未解决项：用户意图不明、缺少业务计算规则、表范围不足、缺少直接字段说明。阈值、筛选值和输出要求不统一归入这份列表。\[C02、C04\]
</callout>
### 3. Check 的检查范围与补查权限
Check 判断现有信息是否足以支持 SQL 编写，不直接验证最终答案。\[C06\]
<table fit-page-width="true" header-row="true">
<tr>
<td>检查内容</td>
<td>典型缺口</td>
</tr>
<tr>
<td>字段语义</td>
<td>将面板接收的辐照误对应为水平面辐照</td>
</tr>
<tr>
<td>公式及所需字段</td>
<td>已取得衰减公式，但缺少初始值或当前值的字段对应</td>
</tr>
<tr>
<td>筛选条件</td>
<td>“严重”“很多”“失败”尚未落实为类别或边界</td>
</tr>
<tr>
<td>输出要求</td>
<td>实体 ID、名称、汇总粒度或最新记录的选择方式未明确</td>
</tr>
</table>
存在缺口时，Check 返回说明，每次最多申请一个补查动作：
<table fit-page-width="true" header-row="true">
<tr>
<td>工具</td>
<td>用途</td>
<td>Bird-Coin</td>
</tr>
<tr>
<td>get_column_meaning</td>
<td>查询单个字段的含义、枚举或 JSON 路径</td>
<td>0.5</td>
</tr>
<tr>
<td>get_all_external_knowledge_names</td>
<td>查找可能相关的业务规则名称</td>
<td>0.5</td>
</tr>
<tr>
<td>get_knowledge_definition</td>
<td>取得具体规则</td>
<td>0.5</td>
</tr>
<tr>
<td>execute_sql</td>
<td>在已有范围内执行受限制的只读查证</td>
<td>1</td>
</tr>
<tr>
<td>ask_user</td>
<td>明确用户意图、阈值或分类选择</td>
<td>2</td>
</tr>
</table>
用户回答可以明确需求，但不能替代数据库字段事实。补查还需通过重复请求、SQL 形式和预算校验，通常要求付费后至少保留 6 Coin。P2 请求本题 P1 已成功取得的完全相同字段说明时，先尝试零成本复用，再检查付费预算。\[C06、C07\]
Check 具有有限修正权限：可根据单条新字段说明修正相应字段，也可根据刚取得的官方定义追加知识。它不能修改表和连接关系，也不能替 Mapping 清除未解决项。\[C06\]
### 4. Gate 分流与信息重做
**Gate 既可能收到完成的 Check，也可能收到未完成的 Check，但并非每次 Check 都交给 Gate。** 本轮评测已启用 Final Gate，普通检查的分流条件如下：\[C17\]
<table fit-page-width="true" header-row="true">
<tr>
<td>Check 结果</td>
<td>接下来做什么</td>
</tr>
<tr>
<td>完成（complete）</td>
<td>进入 Gate，确认新信息是否要求修订四维信息</td>
</tr>
<tr>
<td>未完成，且申请了工具（next_tool 非空）</td>
<td>先校验并执行补查，再 Check；暂不进入 Gate</td>
</tr>
<tr>
<td>未完成，但没有下一项工具（next_tool = null）</td>
<td>进入 Gate，判断已有新证据是否足以支持重做，或应当结束</td>
</tr>
</table>
工具请求不合法、重复或预算不足时，程序也可能直接结束主流程，不必先经过 Gate。草稿提问后的用户回答另有保护：旧草稿已丢弃，需要通过 Gate 建立新草稿，不能直接继续旧草稿。\[C07、C10、C17\]
Gate 收到的不只是“通过／未通过”标记，还包括原请求、追问、当前四维信息、用户澄清、schema、当前表范围内的字段说明、Check 的缺口说明及工具调用记录。P2 还携带仍待 Mapping 处理的项目及证据是否更新的信息。Gate 只决定重做范围，不自行补查或改写四维信息。\[C18\]
<table fit-page-width="true" header-row="true">
<tr>
<td>Gate 决定</td>
<td>程序的实际处理</td>
</tr>
<tr>
<td>不重做（NO_REGROUND）且 Check 已完成</td>
<td>进入正常 Main</td>
</tr>
<tr>
<td>不重做（NO_REGROUND）但 Check 未完成</td>
<td>**结束主流程，不进入正常 Main**</td>
</tr>
<tr>
<td>重做字段（REGROUND_MAPPING）</td>
<td>临时执行 Mapping → Knowledge → Check</td>
</tr>
<tr>
<td>重做范围（REGROUND_STRUCTURE）</td>
<td>临时执行 Structure → Mapping → Knowledge → Check</td>
</tr>
<tr>
<td>结束（TERMINAL）</td>
<td>结束主流程，检查补救条件</td>
</tr>
</table>
**“不重做”不等于“检查通过”。** Gate 判断的是有没有依据重新整理信息；没有新证据时，重跑不能凭空补齐缺口。程序仍要求 Check 完成，才允许进入正常 Main。\[C19\]
重做先在临时草稿中进行，原来的正式信息保持不变。草稿 Check 完成且提交校验通过后，才一次性更新正式信息并进入 Main；这条路径不再固定追加一次 Gate。草稿 Check 未完成时，处理如下：\[C20\]
- 仍可查询字段说明或官方知识：在预算允许时继续补查，再 Check；每份草稿最多安排 8 次这类查询。
- 需要询问用户：校验通过后，先丢弃草稿再发问；收到回答后经 Gate 重新建立草稿。\[C10\]
- 没有可执行的补查、达到上限或校验失败：丢弃草稿，结束主流程，再判断能否补救。草稿内不是所有 Check 工具都可用，例如 execute_sql 不在这一补查分支的允许范围。
因此，Check 一直未完成不会无限循环，也不会把未通过检查的信息直接交给正常 Main。它最终会触及证据、工具、预算或调用上限，结束主流程；**能否补救是下一层独立判断，不是必然发生。**
近期保留的两项改动主要解决了修订过程中的信息管理问题：
- 后续取得公式后，由 Mapping 重新判断并清除过时的未解决项，避免其他阶段已有足够证据却无权更新的情况。
- P2 默认保留已有知识，将新选择的知识追加并去重。Provider 未返回旧知识不再视为删除；受授权的主动删除尚未实现。\[C11\]
同一未解决项在证据和输入均未变化时，不允许无限重试。\[C08\]
### 5. Main 的实际输入与职责
Main 接收原请求、P2 追问、四维摘要、已回答澄清、剩余预算，以及结果类型、显示精度、排序敏感性等公开执行要求和字段的安全引用形式。\[C09\]
四维与澄清摘要默认限制为 4,096 字符、1,024 个本地估算 token、96 项，优先保留澄清。完整 schema、全部字段说明、规则目录、Check 推理和补查历史不直接传入 Main。因此，正式保存的信息可能多于 Main 实际收到的内容。\[C09\]
Main 提示词中的原文要求为：
> “Final Grounding State 和已回答澄清是语义权威。不要重新研究 schema、column meaning 或 business semantics”
Main 仅可使用 execute_sql 和 submit_sql，负责候选 SQL 的验证、实现修正和提交。与原 Agent 相比，它的职责已明显收窄。本轮使用 leaderboard 配置，部分研究型检查只记录审计，不实施拦截，因此提示词要求也不等同于程序强制约束。\[C09、C13\]
### 6. 最终补救
补救由外层运行程序在主流程返回后启动，不是 Gate 直接调用另一个 Agent。本轮已启用补救功能；在任务未完成、阶段和余额有效、余额至少 3 Coin，且本题尚未补救过时，系统启动一次独立的原 Agent 会话。不满足条件则直接返回本题已有结果。Grounding 未完成或正常 Main 未完成任务，都可能到达这个检查点。\[C12\]
补救恢复原来的九个工具，沿用本题数据库、剩余预算和已通过的 P1 产物，不重置预算，也不返回四维主流程。它不要求失败的 Grounding 先通过 Check，否则就失去了独立补救的意义。
补救输入包括原请求、追问、澄清、已通过的 P1 SQL、公开执行要求、余额，以及标为“非权威提示”的失败四维信息。当前代码仍发送 non_authoritative_failed_4d_state_hint；此前删除该提示的讨论方案并未体现在本轮实现中。\[C12\]
补救可以重新查证和解释语义，但可能重复取证，也可能受前序错误提示影响。其贡献在成绩分析中单独统计。
从代码看，这里并非“未完成后没有出口”，而是刻意将信息不足挡在正常 Main 之外，同时保留独立补救。原图的问题是没有展开 Check 的两种出口，也没有区分普通检查与草稿检查。设计上的代价则是：重复或预算限制可能在信息补齐前终止主流程，最后能否完成任务取决于剩余预算和补救能力。退出机制完整，并不代表信息一定能够补齐。
## 二、实际案例分析
本节按“实际输入 → 模型输出 → 校验结果 → 四维变化 → SQL 与结果”展开。先展示主流程两阶段全通过的 cybermarket_pattern_10，再对照依靠补救完成的 solar_panel_7，以及失败的 hulushows_12。S / D 状态编号分别在各案例内使用。
<details>
<summary><span color="red">**1. cybermarket_pattern_10：主流程两阶段全通过的四维演化记录**</span></summary>
	原始问题：
	```plain text
What's the average keyword-hit density in our message threads?
	```
	请求释义：我们的消息线程中，关键词命中密度的平均值是多少？初始预算 16 Coin。
	结果：**正常主流程 P1、P2 均通过，没有启动 fallback；1 次草稿提交，0 次回滚。** 这里的“完全成功”指本题归档中的完整评测通过，不表示所有中间模型输出都直接被接受。
	> 归档来源：`research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10`。这是本次 Full600 最终计分轨迹，不是历史阶段级试验，也不是本次重新补跑。S 表示正式状态，D 表示临时草稿；编号仅用于本案例。用户澄清、Check 工具证据、未解决项和预算均在四维之外单独保存。
	#### 顺序总览
	<table fit-page-width="true" header-row="true">
<tr>
<td>步骤</td>
<td>模型提出了什么</td>
<td>校验、落盘与后续</td>
</tr>
<tr>
<td>1</td>
<td>Structure：确定通信记录表</td>
<td>格式通过，服务层 accepted，rev0 → rev1。 S1 / rev1</td>
</tr>
<tr>
<td>2</td>
<td>Mapping：识别出缺少派生规则</td>
<td>格式通过，服务层 accepted，rev1 → rev2。 S2 / rev2</td>
</tr>
<tr>
<td>3</td>
<td>Knowledge：取得 SSD 公式，但不能越权补字段</td>
<td>知识被接受，rev2 → rev3；模型同时提出的字段映射被权限保护忽略。 S3 / rev3</td>
</tr>
<tr>
<td>4</td>
<td>Check #1：先确认业务知识名称</td>
<td>Check 返回 incomplete，四维更新为 noop；申请的工具通过校验并实际执行。 S3 / rev3</td>
</tr>
<tr>
<td>5</td>
<td>Check #2：补查 SSD 的具体定义</td>
<td>Check 返回 incomplete，四维 noop；get_knowledge_definition 通过校验并执行。 S3 / rev3</td>
</tr>
<tr>
<td>6</td>
<td>Check #3：公式已知，但操作数字段仍待 Mapping 处理</td>
<td>incomplete 且 next_tool=null；四维 noop，进入 Gate。 S3 / rev3</td>
</tr>
<tr>
<td>7</td>
<td>Gate：仅重做字段，不扩展表范围</td>
<td>REGROUND_MAPPING，以正式 rev3 建立临时草稿。 S3 / rev3</td>
</tr>
<tr>
<td>8</td>
<td>草稿 Mapping：把公式操作数落实到字段</td>
<td>草稿 accepted，private rev3 → rev4；正式版本暂时仍为 rev3。 D4 / private rev4</td>
</tr>
<tr>
<td>9</td>
<td>草稿 Knowledge：复核并保留已有公式</td>
<td>草稿 noop，private rev4 不变。 D4 / private rev4</td>
</tr>
<tr>
<td>10</td>
<td>草稿 Check：完整性通过，统一提交</td>
<td>Check complete、next_tool=null；草稿 Check 为 noop，随后提交成功。 S4 / rev4</td>
</tr>
<tr>
<td>11</td>
<td>P1 Main：平均 SSD</td>
<td>execute_sql = 0.084；首次 submit_sql 通过，余额 8 Coin。</td>
</tr>
<tr>
<td>12</td>
<td>P2 Structure → Mapping → Knowledge → Check → Gate</td>
<td>沿用 S4，Check complete，Gate NO_REGROUND。</td>
</tr>
<tr>
<td>13</td>
<td>P2 Main：SSD 标准差</td>
<td>execute_sql = 0.160；首次 submit_sql 通过，余额 4 Coin，任务完成。</td>
</tr>
	</table>
	<details>
	<summary>状态版本与 SHA（正式状态 / 草稿边界）</summary>
		<table fit-page-width="true" header-row="true">
<tr>
<td>状态</td>
<td>对应内容</td>
<td>SHA256</td>
</tr>
<tr>
<td>S1 / rev1</td>
<td>表范围</td>
<td>b63cdfc7e3ff505c30d67bdc290d3113f079262388a7486f0ea81dc3c90c78e8</td>
</tr>
<tr>
<td>S2 / rev2</td>
<td>空映射 + 未解决项</td>
<td>9b0a4905f780e35f445eda5dadfd0c95b50b815459b62450e68be355af14f3de</td>
</tr>
<tr>
<td>S3 / rev3</td>
<td>加入 SSD 公式</td>
<td>17bb970eefa30ceb07124fc4483b8a0bf889afe51ad517043b9cac86d3be70d4</td>
</tr>
<tr>
<td>S4 / rev4（提交前为 D4）</td>
<td>补齐字段对应</td>
<td>fd5225e3c64646e6bc678d4a4bb97fafc087a2879d1249f466409ce203bc1009</td>
</tr>
		</table>
	</details>
	#### 0. 初始状态 S0 / rev0
	```json
{
  "column_mapping": null,
  "domain_knowledge": null,
  "join_keys": null,
  "tables": null
}
	```
	四维均为 null，表示尚未整理。以下按日志展示模型候选和实际保存状态，不把候选输出直接当成已经生效的状态。
	#### 1. Structure：确定通信记录表
	实际输入：官方 schema 与原始问题。
	本轮请求字段：`current_state`、`query`、`schema`。
	模型候选输出（完整结构化正文，仅调整缩进）：
	```json
{
  "tables": [
    "communications"
  ],
  "join_keys": []
}
	```
	校验与实际处理：格式通过，服务层 accepted，rev0 → rev1。
	四维变化：tables 从 null 变为 communications；join_keys 从 null 变为 \[\]；其余维度仍为 null。
	只需 communications 一张表。\[\] 表示已检查且无须连接，不是尚未处理。
	实际正式状态 S1 / rev1：
	```json
{
  "column_mapping": null,
  "domain_knowledge": null,
  "join_keys": [],
  "tables": [
    "communications"
  ]
}
	```
	来源：`provider_audits/01_sql-grounding-20260908T054947076628Z-3af683ab8dce-8e7ea924.json`（相对本案例归档目录）。
	#### 2. Mapping：识别出缺少派生规则
	实际输入：字段说明、原始问题与 S1。
	本轮请求字段：`column_meanings`、`current_state`、`query`、`unresolved_mappings`。
	模型候选输出（完整结构化正文，仅调整缩进）：
	```json
{
  "tables": [
    "communications"
  ],
  "join_keys": [],
  "column_mapping": [],
  "unresolved_mappings": [
    {
      "phrase": "keyword-hit density",
      "reason": "derived_rule_required"
    }
  ]
}
	```
	校验与实际处理：格式通过，服务层 accepted，rev1 → rev2。
	四维变化：column_mapping 从 null 变为 \[\]；其他三维不变。框架外新增 keyword-hit density / derived_rule_required 未解决项。
	字段名看似相关，但尚未确定‘密度’的业务计算规则。Mapping 暂不写入未经确认的计算字段。
	实际正式状态 S2 / rev2：
	```json
{
  "column_mapping": [],
  "domain_knowledge": null,
  "join_keys": [],
  "tables": [
    "communications"
  ]
}
	```
	来源：`provider_audits/02_sql-grounding-20260908T055001432883Z-f28cd8c99e21-7fd30e05.json`（相对本案例归档目录）。
	#### 3. Knowledge：取得 SSD 公式，但不能越权补字段
	实际输入：知识目录、相关字段说明、S2 与未解决项。
	本轮请求字段：`current_state`、`knowledge_definitions`、`query`、`relevant_column_meanings`、`unresolved_mappings`。
	模型候选输出（完整结构化正文，仅调整缩进）：
	```json
{
  "column_mapping": [
    {
      "phrase": "keyword-hit density",
      "targets": [
        "communications.communication_details ->> 'keyword_match_count'",
        "communications.communication_details ->> 'msg_count_total'"
      ]
    }
  ],
  "selected_knowledge_ids": [
    8
  ]
}
	```
	校验与实际处理：知识被接受，rev2 → rev3；模型同时提出的字段映射被权限保护忽略。
	四维变化：domain_knowledge 增加 SSD = keyword_matches / total_messages；column_mapping 仍为 \[\]。
	注意候选输出与正式状态不同：虽然 Knowledge 提出了两个字段，它不能替 Mapping 消除派生规则缺口。审计记录 knowledge_unauthorized_omission_mapping_ignored。知识 ID 8 是本次目录索引，正式保存的是公式原文。
	实际正式状态 S3 / rev3：
	```json
{
  "column_mapping": [],
  "domain_knowledge": [
    {
      "content": "SSD = \\frac{\\text{keyword\\_matches}}{\\text{total\\_messages}}",
      "kind": "business_rule"
    }
  ],
  "join_keys": [],
  "tables": [
    "communications"
  ]
}
	```
	来源：`provider_audits/03_sql-grounding-20260908T055029576609Z-abc0ffcb44fd-6cb170b0.json`（相对本案例归档目录）。
	#### 4. Check #1：先确认业务知识名称
	实际输入：S3、未解决项与此前官方取证记录。
	本轮请求字段：`answered_clarifications`、`check_context`、`current_state`、`previous_official_calls`、`query`、`unresolved_mappings`。
	模型候选输出（完整结构化正文，仅调整缩进）：
	```json
{
  "status": "incomplete",
  "clarification_route": "none",
  "missing_information": "unresolved mapping for 'keyword-hit density' requires a derived rule; need to check if Official external knowledge defines 'keyword-hit density' or confirms it equals the SSD formula",
  "next_tool": {
    "tool_name": "get_all_external_knowledge_names",
    "arguments": {},
    "user_clarification_request": null
  },
  "column_mapping": [],
  "domain_knowledge": [
    {
      "content": "SSD = \\frac{\\text{keyword\\_matches}}{\\text{total\\_messages}}",
      "kind": "business_rule"
    }
  ]
}
	```
	校验与实际处理：Check 返回 incomplete，四维更新为 noop；申请的工具通过校验并实际执行。
	四维变化：四维保持 S3；工具结果进入 Check 上下文。
	此时不进入 Gate。get_all_external_knowledge_names 返回目录，包含 Suspicion Signal Density；花费 0.5 Coin，余额 13 → 12.5。
	操作后状态：S3 / rev3，完整内容与上方同名快照一致。
	<details>
	<summary>本次官方补查的真实参数与返回</summary>
		```json
{
  "tool": "get_all_external_knowledge_names",
  "args": {},
  "result": "[\"Marketplace Risk Score (MRS)\", \"Transaction Velocity Rate\", \"Compliance Efficiency Index (CEI)\", \"Data Protection Efficiency\", \"Anonymity Cost Index\", \"Buyer Risk Dollar Ratio\", \"Platform Liquidity Rate\", \"Threat Handling Rate\", \"Suspicion Signal Density\", \"Wallet Turnover Rate\", \"High Risk Vendor\", \"Cross-Border Transaction\", \"Advanced Verification Tier\", \"Escrow Compliance\", \"Premium Authentication\", \"Traceable Communication\", \"Suspicious Buyer\", \"Secure Platform\", \"Fraud-Flagged Transaction\", \"Tier-3 Escalation Case\", \"Platform Operational Status\", \"Vendor Access Levels\", \"Buyer Authentication Levels\", \"Product Categories\", \"Shipping Route Complexity\", \"Session Anonymity Levels\", \"Alert Severity Levels\", \"Escrow Usage States\", \"Language Patterns\", \"Spend Pattern Categories\"]",
  "budget_before": 13,
  "budget_after": 12.5
}
		```
	</details>
	来源：`provider_audits/04_sql-grounding-20260908T055040508708Z-bf361510421d-f8792a80.json`（相对本案例归档目录）。
	#### 5. Check #2：补查 SSD 的具体定义
	实际输入：S3 与刚取得的知识名称目录。
	本轮请求字段：`answered_clarifications`、`current_state`、`latest_tool`、`previous_official_calls`、`query`、`unresolved_mappings`。
	模型候选输出（完整结构化正文，仅调整缩进）：
	```json
{
  "status": "incomplete",
  "clarification_route": "none",
  "missing_information": "SSD formula operands (keyword_matches, total_messages) are not yet mapped to columns in the communications table; need Official definition of Suspicion Signal Density to confirm operands and identify required columns.",
  "next_tool": {
    "tool_name": "get_knowledge_definition",
    "arguments": {
      "knowledge_name": "Suspicion Signal Density"
    },
    "user_clarification_request": null
  },
  "column_mapping": [],
  "domain_knowledge": [
    {
      "content": "SSD = \\frac{\\text{keyword\\_matches}}{\\text{total\\_messages}}",
      "kind": "business_rule"
    }
  ]
}
	```
	校验与实际处理：Check 返回 incomplete，四维 noop；get_knowledge_definition 通过校验并执行。
	四维变化：四维仍为 S3；补查带来的描述与定义保存在外部证据上下文。
	返回的描述为 Keyword hits per message volume in communication.，使‘关键词命中密度’与 SSD 对应；花费 0.5 Coin，余额 12.5 → 12。公式此前已经入库，这次属于重复确认，并非首次获得公式。
	操作后状态：S3 / rev3，完整内容与上方同名快照一致。
	<details>
	<summary>本次官方补查的真实参数与返回</summary>
		```json
{
  "tool": "get_knowledge_definition",
  "args": {
    "knowledge_name": "Suspicion Signal Density"
  },
  "result": "{\n  \"id\": 8,\n  \"knowledge\": \"Suspicion Signal Density\",\n  \"description\": \"Keyword hits per message volume in communication.\",\n  \"definition\": \"SSD = \\\\frac{\\\\text{keyword\\\\_matches}}{\\\\text{total\\\\_messages}}\"\n}",
  "budget_before": 12.5,
  "budget_after": 12
}
		```
	</details>
	来源：`provider_audits/05_sql-grounding-20260908T055056174433Z-87e0924333c4-044a61a1.json`（相对本案例归档目录）。
	#### 6. Check #3：公式已知，但操作数字段仍待 Mapping 处理
	实际输入：S3、具体 SSD 定义与尚未清除的未解决项。
	本轮请求字段：`answered_clarifications`、`current_state`、`latest_tool`、`previous_official_calls`、`query`、`unresolved_mappings`。
	模型候选输出（完整结构化正文，仅调整缩进）：
	```json
{
  "status": "incomplete",
  "clarification_route": "none",
  "missing_information": "SSD formula obtained, but its operands (keyword_matches, total_messages) are not yet grounded to columns in the communications table; Mapping needs to re-evaluate with the now-known formula to map these operands.",
  "next_tool": null,
  "column_mapping": [],
  "domain_knowledge": [
    {
      "kind": "business_rule",
      "content": "SSD = \\frac{\\text{keyword\\_matches}}{\\text{total\\_messages}}"
    }
  ]
}
	```
	校验与实际处理：incomplete 且 next_tool=null；四维 noop，进入 Gate。
	四维变化：四维保持 S3，column_mapping 仍为空。
	这一步体现未完成的 Check 也能进入 Gate：没有继续申请工具，但已有证据可用于重做字段映射。
	操作后状态：S3 / rev3，完整内容与上方同名快照一致。
	来源：`provider_audits/06_sql-grounding-20260908T055121384161Z-ddfc2eb674ee-352ae014.json`（相对本案例归档目录）。
	#### 7. Gate：仅重做字段，不扩展表范围
	实际输入：S3、Check 缺口、已有 schema / 字段 / 官方知识等 Gate 上下文。
	本轮请求字段：`current_state`、`final_gate_context`、`query`。
	模型候选输出（完整结构化正文，仅调整缩进）：
	```json
{
  "decision": "REGROUND_MAPPING",
  "reason": "New Official knowledge introduced the SSD formula (keyword_matches / total_messages), which defines SQL-relevant operands that the current empty column_mapping has not yet grounded. The schema confirms the required carriers (keyword_match_count, msg_count_total) exist within communications.communication_details, so the needed columns are still in the current table scope. No table or join-scope change is required. The current Mapping is incomplete because it was produced before the formula was known; Mapping must re-evaluate to map these operands."
}
	```
	校验与实际处理：REGROUND_MAPPING，以正式 rev3 建立临时草稿。
	四维变化：Gate 自己不改四维；正式状态继续保持 S3。
	两个操作数都在 communications.communication_details 内，因此无需 REGROUND_STRUCTURE。
	操作后状态：S3 / rev3，完整内容与上方同名快照一致。
	来源：`provider_audits/07_sql-grounding-20260908T055202840805Z-3003797761f1-41b8ddad.json`（相对本案例归档目录）。
	#### 8. 草稿 Mapping：把公式操作数落实到字段
	实际输入：S3 的草稿、字段说明、公式与 regrounding_context。
	本轮请求字段：`column_meanings`、`current_state`、`query`、`regrounding_context`、`unresolved_mappings`。
	模型候选输出（完整结构化正文，仅调整缩进）：
	```json
{
  "tables": [
    "communications"
  ],
  "join_keys": [],
  "column_mapping": [
    {
      "phrase": "keyword-hit density",
      "targets": [
        "communications.communication_details ->> 'keyword_match_count'",
        "communications.communication_details ->> 'msg_count_total'"
      ]
    }
  ],
  "unresolved_mappings": []
}
	```
	校验与实际处理：草稿 accepted，private rev3 → rev4；正式版本暂时仍为 rev3。
	四维变化：草稿 column_mapping 增加 keyword-hit density → keyword_match_count、msg_count_total；框架外未解决项清空。
	公式提供除法关系，字段映射提供分子和分母对应的 JSON 路径。不是仅因一个短语关联两个字段，就自行推断相除。
	临时草稿 D4 / private rev4：
	```json
{
  "column_mapping": [
    {
      "phrase": "keyword-hit density",
      "targets": [
        "communications.communication_details ->> 'keyword_match_count'",
        "communications.communication_details ->> 'msg_count_total'"
      ]
    }
  ],
  "domain_knowledge": [
    {
      "content": "SSD = \\frac{\\text{keyword\\_matches}}{\\text{total\\_messages}}",
      "kind": "business_rule"
    }
  ],
  "join_keys": [],
  "tables": [
    "communications"
  ]
}
	```
	来源：`provider_audits/08_sql-grounding-20260908T055220030358Z-69ec8999589f-8ee237a8.json`（相对本案例归档目录）。
	#### 9. 草稿 Knowledge：复核并保留已有公式
	实际输入：D4、同一知识目录、字段说明与重做上下文。
	本轮请求字段：`current_state`、`knowledge_definitions`、`query`、`regrounding_context`、`relevant_column_meanings`、`unresolved_mappings`。
	模型候选输出（完整结构化正文，仅调整缩进）：
	```json
{
  "column_mapping": [
    {
      "phrase": "keyword-hit density",
      "targets": [
        "communications.communication_details ->> 'keyword_match_count'",
        "communications.communication_details ->> 'msg_count_total'"
      ]
    }
  ],
  "selected_knowledge_ids": [
    8
  ]
}
	```
	校验与实际处理：草稿 noop，private rev4 不变。
	四维变化：四维与 D4 完全相同，保留知识 ID 8 对应的公式。
	无需增加其他业务规则，也没有把已有公式删掉。
	操作后状态：D4 / private rev4，完整内容与上方同名快照一致。
	来源：`provider_audits/09_sql-grounding-20260908T055248511390Z-adeed203cc13-329fff6e.json`（相对本案例归档目录）。
	#### 10. 草稿 Check：完整性通过，统一提交
	实际输入：D4、已补查证据与已清空的未解决项。
	本轮请求字段：`answered_clarifications`、`check_context`、`current_state`、`previous_official_calls`、`query`、`regrounding_context`、`unresolved_mappings`。
	模型候选输出（完整结构化正文，仅调整缩进）：
	```json
{
  "status": "complete",
  "clarification_route": "none",
  "missing_information": null,
  "next_tool": null,
  "column_mapping": [
    {
      "phrase": "keyword-hit density",
      "targets": [
        "communications.communication_details ->> 'keyword_match_count'",
        "communications.communication_details ->> 'msg_count_total'"
      ]
    }
  ],
  "domain_knowledge": [
    {
      "content": "SSD = \\frac{\\text{keyword\\_matches}}{\\text{total\\_messages}}",
      "kind": "business_rule"
    }
  ]
}
	```
	校验与实际处理：Check complete、next_tool=null；草稿 Check 为 noop，随后提交成功。
	四维变化：将 D4 一次性提交为正式 S4 / rev4；正式版本只增加 1。
	审计确认 committed=true、rolled_back=false、formal_state_unchanged_before_commit=true。草稿内没有新增官方工具调用；通过后进入正常 Main，不再追加一次固定 Gate。
	实际正式状态 S4 / rev4：
	```json
{
  "column_mapping": [
    {
      "phrase": "keyword-hit density",
      "targets": [
        "communications.communication_details ->> 'keyword_match_count'",
        "communications.communication_details ->> 'msg_count_total'"
      ]
    }
  ],
  "domain_knowledge": [
    {
      "content": "SSD = \\frac{\\text{keyword\\_matches}}{\\text{total\\_messages}}",
      "kind": "business_rule"
    }
  ],
  "join_keys": [],
  "tables": [
    "communications"
  ]
}
	```
	<details>
	<summary>草稿提交审计（原文）</summary>
		```json
{
  "base_revision": 3,
  "committed": true,
  "committed_revision": 4,
  "decision": "REGROUND_MAPPING",
  "draft_stages": [
    {
      "changed_dimensions": [
        "column_mapping"
      ],
      "error_type": null,
      "knowledge_omission_mapping_ignored": [],
      "knowledge_preserved_by_default_refs": [],
      "knowledge_retirement_audit_sidecar": null,
      "private_revision_after": 4,
      "private_revision_before": 3,
      "stage": "mapping",
      "state_sha256": "fd5225e3c64646e6bc678d4a4bb97fafc087a2879d1249f466409ce203bc1009",
      "status": "accepted"
    },
    {
      "changed_dimensions": [],
      "error_type": null,
      "knowledge_omission_mapping_ignored": [],
      "knowledge_preserved_by_default_refs": [],
      "knowledge_retirement_audit_sidecar": null,
      "private_revision_after": 4,
      "private_revision_before": 4,
      "stage": "knowledge",
      "state_sha256": "fd5225e3c64646e6bc678d4a4bb97fafc087a2879d1249f466409ce203bc1009",
      "status": "noop"
    },
    {
      "changed_dimensions": [],
      "error_type": null,
      "knowledge_omission_mapping_ignored": [],
      "knowledge_preserved_by_default_refs": [],
      "knowledge_retirement_audit_sidecar": null,
      "private_revision_after": 4,
      "private_revision_before": 4,
      "stage": "check",
      "state_sha256": "fd5225e3c64646e6bc678d4a4bb97fafc087a2879d1249f466409ce203bc1009",
      "status": "noop"
    }
  ],
  "formal_revision_delta": 1,
  "formal_state_unchanged_before_commit": true,
  "official_call_count": 0,
  "phase": 1,
  "rolled_back": false
}
		```
	</details>
	来源：`provider_audits/10_sql-grounding-20260908T055301118859Z-09f775f5f854-53d3de54.json`（相对本案例归档目录）。
	#### P1 Main：计算平均密度并提交
	Main 实际接收 S4 的字段映射和 SSD 公式、原请求，以及标量结果、保留 3 位小数等公开执行要求。可用工具为 execute_sql、submit_sql；进入 Main 时余额 12 Coin。
	<details>
	<summary>P1 Main 的真实注入上下文（原文）</summary>
		```plain text
[VALIBRA SQL WRITER CONTEXT BEGIN]
Phase: 1
Original Query: What's the average keyword-hit density in our message threads?
Follow-up: none
Final Grounding State and answered Clarifications:
[VALIBRA DATABASE GROUNDING]

Tables:
- "communications"

Relations:
- []

Column mappings:
- {"phrase":"keyword-hit density","targets":["communications.communication_details ->> 'keyword_match_count'","communications.communication_details ->> 'msg_count_total'"]}

Domain knowledge:
- {"content":"SSD = \\frac{\\text{keyword\\_matches}}{\\text{total\\_messages}}","kind":"business_rule"}
[MAIN EXECUTION ENVELOPE]
{"action_intent":"RESULT_QUERY","decimal_places":3,"order_sensitive":false,"response_type":"scalar","task_category":"Query"}
Authority limits: response_type fixes only result shape; decimal_places fixes only displayed precision; order_sensitive only says row order affects evaluation and does not supply a direction, sort key, aggregation, projection, or business rule; task_category does not override the Query's requested action. action_intent is derived only from explicit Query wording. When it is not RESULT_QUERY, the final SQL must implement that SQL action; an ordinary SELECT is not an equivalent substitute. RESULT_QUERY does not authorize inventing a management action. No object name, function signature, or hidden action detail is supplied beyond what the Query states.
[SQL-SAFE CANONICAL REFERENCES]
{"omitted":0,"references":[{"kind":"target","reference":"communications.communication_details ->> 'keyword_match_count'","sql":"\"communications\".\"communication_details\" ->> 'keyword_match_count'"},{"kind":"target","reference":"communications.communication_details ->> 'msg_count_total'","sql":"\"communications\".\"communication_details\" ->> 'msg_count_total'"},{"kind":"table","reference":"communications","sql":"\"communications\""}],"version":"sql-safe-identifier-overlay/v1"}
Authority limits: these are quoting-safe renderings of existing validated State references only; they add no table, column, JSON key, formula, predicate, aggregation, ordering, or output rule.
Remaining Bird-Coin: 12
[VALIBRA SQL WRITER CONTEXT END]
		```
	</details>
	```sql
SELECT ROUND(AVG(("communications"."communication_details" ->> 'keyword_match_count')::numeric / NULLIF(("communications"."communication_details" ->> 'msg_count_total')::numeric, 0)), 3) AS avg_keyword_hit_density
FROM "communications";
	```
	执行结果：
	```plain text
avg_keyword_hit_density
-----------------------
0.084
	```
	提交反馈：
	```plain text
Phase 1 correct! (Reward: 0.7). Moving to Phase 2.
Reward: 0.7
Follow-up question: Return the standard deviation of SSD across all communications, rounded to 3 decimal places.
Budget remaining: 8.0 bird-coins
	```
	逐条计算 keyword_match_count / msg_count_total 后取平均，使用 numeric，并用 NULLIF 防止分母为零。这里不是先汇总分子、分母再相除。P1 执行花费 1 Coin，提交花费 3 Coin，余额由 12 降至 8。
	#### P2 追问
	```plain text
Return the standard deviation of SSD across all communications, rounded to 3 decimal places.
	```
	释义：返回全部通信记录中 SSD 的标准差，保留 3 位小数。下列五个步骤为 P2 的真实调用，未省略为“直接沿用”。
	#### 11. P2 Structure：沿用表范围
	实际输入：P1 成功后的追问、S4 和已有 schema。
	本轮请求字段：`current_state`、`follow_up`、`query`、`schema`、`user_clarifications`。
	模型候选输出（完整结构化正文，仅调整缩进）：
	```json
{
  "tables": [
    "communications"
  ],
  "join_keys": []
}
	```
	校验与实际处理：输出与现有状态一致；下一轮实际输入确认状态仍为 S4。
	四维变化：tables、join_keys 不变。
	P2 只改变统计方式，没有引入新实体或连接。
	操作后状态：S4 / rev4，完整内容与上方同名快照一致。
	来源：`provider_audits/11_sql-grounding-20260908T055414314649Z-0ffa6a243468-9e096ba8.json`（相对本案例归档目录）。
	#### 12. P2 Mapping：沿用两个计算字段
	实际输入：P2 追问、S4、字段说明与空的未解决项。
	本轮请求字段：`column_meanings`、`current_state`、`follow_up`、`query`、`unresolved_mappings`、`user_clarifications`。
	模型候选输出（完整结构化正文，仅调整缩进）：
	```json
{
  "tables": [
    "communications"
  ],
  "join_keys": [],
  "column_mapping": [
    {
      "phrase": "keyword-hit density",
      "targets": [
        "communications.communication_details ->> 'keyword_match_count'",
        "communications.communication_details ->> 'msg_count_total'"
      ]
    }
  ],
  "unresolved_mappings": []
}
	```
	校验与实际处理：输出与现有映射一致；下一轮实际输入确认状态仍为 S4。
	四维变化：column_mapping 不变，未解决项仍为空。
	仍用关键词命中次数和消息总量计算逐条 SSD，变化的是后续聚合方式。
	操作后状态：S4 / rev4，完整内容与上方同名快照一致。
	来源：`provider_audits/12_sql-grounding-20260908T055416510584Z-0fa4119f15ac-eda0b180.json`（相对本案例归档目录）。
	#### 13. P2 Knowledge：保留 SSD 公式
	实际输入：P2 追问、S4 与知识目录。
	本轮请求字段：`current_state`、`follow_up`、`knowledge_definitions`、`query`、`relevant_column_meanings`、`unresolved_mappings`、`user_clarifications`。
	模型候选输出（完整结构化正文，仅调整缩进）：
	```json
{
  "column_mapping": [
    {
      "phrase": "keyword-hit density",
      "targets": [
        "communications.communication_details ->> 'keyword_match_count'",
        "communications.communication_details ->> 'msg_count_total'"
      ]
    }
  ],
  "selected_knowledge_ids": [
    8
  ]
}
	```
	校验与实际处理：仍选择 ID 8；下一轮实际输入确认状态不变。
	四维变化：domain_knowledge 不变。
	不因追问由平均数改为标准差，就重写密度定义。
	操作后状态：S4 / rev4，完整内容与上方同名快照一致。
	来源：`provider_audits/13_sql-grounding-20260908T055425714919Z-e72f76912c58-7c29a04d.json`（相对本案例归档目录）。
	#### 14. P2 Check：确认现有信息足够
	实际输入：P2 请求、S4 与已取得的官方证据。
	本轮请求字段：`answered_clarifications`、`check_context`、`check_evidence_context`、`current_state`、`follow_up`、`previous_official_calls`、`query`、`unresolved_mappings`、`user_clarifications`。
	模型候选输出（完整结构化正文，仅调整缩进）：
	```json
{
  "status": "complete",
  "clarification_route": "none",
  "missing_information": null,
  "next_tool": null,
  "column_mapping": [
    {
      "phrase": "keyword-hit density",
      "targets": [
        "communications.communication_details ->> 'keyword_match_count'",
        "communications.communication_details ->> 'msg_count_total'"
      ]
    }
  ],
  "domain_knowledge": [
    {
      "kind": "business_rule",
      "content": "SSD = \\frac{\\text{keyword\\_matches}}{\\text{total\\_messages}}"
    }
  ]
}
	```
	校验与实际处理：complete、next_tool=null，阶段检查通过。
	四维变化：四维保持 S4。
	没有再补查，也没有再询问用户。
	操作后状态：S4 / rev4，完整内容与上方同名快照一致。
	来源：`provider_audits/14_sql-grounding-20260908T055436395489Z-282dfd1014c7-8fc41b60.json`（相对本案例归档目录）。
	#### 15. P2 Gate：不必再次重做
	实际输入：完成的 Check、S4 与 P2 聚合要求。
	本轮请求字段：`current_state`、`final_gate_context`、`follow_up`、`query`、`user_clarifications`。
	模型候选输出（完整结构化正文，仅调整缩进）：
	```json
{
  "decision": "NO_REGROUND",
  "reason": "The follow-up changes the aggregation from average to standard deviation, which is a clarification overlay and does not invalidate the existing tables, join_keys, or column_mapping. The required operands (keyword_match_count and msg_count_total) and formula (SSD) are already correctly mapped in the current State."
}
	```
	校验与实际处理：NO_REGROUND，且 Check 已 complete，因此进入正常 Main。
	四维变化：四维保持 S4 / rev4，最终运行状态为 DONE。
	Gate 判断追问只改变聚合，不使已有字段或公式失效；不是用 NO_REGROUND 代替完整性检查。
	操作后状态：S4 / rev4，完整内容与上方同名快照一致。
	来源：`provider_audits/15_sql-grounding-20260908T055449261760Z-77cde8847db3-8c1e79b9.json`（相对本案例归档目录）。
	#### P2 Main：计算标准差并完成任务
	Main 接收同一 S4 与 P2 追问，进入时余额 8 Coin。聚合由 AVG 改为 STDDEV，公式和字段不变。
	<details>
	<summary>P2 Main 的真实注入上下文（原文）</summary>
		```plain text
[VALIBRA SQL WRITER CONTEXT BEGIN]
Phase: 2
Original Query: What's the average keyword-hit density in our message threads?
Follow-up: Return the standard deviation of SSD across all communications, rounded to 3 decimal places.
Final Grounding State and answered Clarifications:
[VALIBRA DATABASE GROUNDING]

Tables:
- "communications"

Relations:
- []

Column mappings:
- {"phrase":"keyword-hit density","targets":["communications.communication_details ->> 'keyword_match_count'","communications.communication_details ->> 'msg_count_total'"]}

Domain knowledge:
- {"content":"SSD = \\frac{\\text{keyword\\_matches}}{\\text{total\\_messages}}","kind":"business_rule"}
[MAIN EXECUTION ENVELOPE]
{"action_intent":"RESULT_QUERY","decimal_places":3,"order_sensitive":false,"response_type":"scalar","task_category":"Query"}
Authority limits: response_type fixes only result shape; decimal_places fixes only displayed precision; order_sensitive only says row order affects evaluation and does not supply a direction, sort key, aggregation, projection, or business rule; task_category does not override the Query's requested action. action_intent is derived only from explicit Query wording. When it is not RESULT_QUERY, the final SQL must implement that SQL action; an ordinary SELECT is not an equivalent substitute. RESULT_QUERY does not authorize inventing a management action. No object name, function signature, or hidden action detail is supplied beyond what the Query states.
[SQL-SAFE CANONICAL REFERENCES]
{"omitted":0,"references":[{"kind":"target","reference":"communications.communication_details ->> 'keyword_match_count'","sql":"\"communications\".\"communication_details\" ->> 'keyword_match_count'"},{"kind":"target","reference":"communications.communication_details ->> 'msg_count_total'","sql":"\"communications\".\"communication_details\" ->> 'msg_count_total'"},{"kind":"table","reference":"communications","sql":"\"communications\""}],"version":"sql-safe-identifier-overlay/v1"}
Authority limits: these are quoting-safe renderings of existing validated State references only; they add no table, column, JSON key, formula, predicate, aggregation, ordering, or output rule.
Remaining Bird-Coin: 8
[VALIBRA SQL WRITER CONTEXT END]
		```
	</details>
	```sql
SELECT ROUND(STDDEV(("communications"."communication_details" ->> 'keyword_match_count')::numeric / NULLIF(("communications"."communication_details" ->> 'msg_count_total')::numeric, 0)), 3) AS std_ssd
FROM "communications";
	```
	执行结果：
	```plain text
std_ssd
-------
0.160
	```
	提交反馈：
	```plain text
Phase 2 correct! (Reward: 0.3). Task finished.
Reward: 0.3
Budget remaining: 4.0 bird-coins
	```
	执行花费 1 Coin，提交花费 3 Coin，余额 8 → 7 → 4。最终 P1、P2 均通过，总 Reward = 1.0。
	#### 最终状态与结果核对
	```json
{
  "focus_dimension": "none",
  "grounding_revision": 4,
  "grounding_state": {
    "column_mapping": [
      {
        "phrase": "keyword-hit density",
        "targets": [
          "communications.communication_details ->> 'keyword_match_count'",
          "communications.communication_details ->> 'msg_count_total'"
        ]
      }
    ],
    "domain_knowledge": [
      {
        "content": "SSD = \\frac{\\text{keyword\\_matches}}{\\text{total\\_messages}}",
        "kind": "business_rule"
      }
    ],
    "join_keys": [],
    "tables": [
      "communications"
    ]
  },
  "stage": "DONE"
}
	```
	<table fit-page-width="true" header-row="true">
<tr>
<td>检查项</td>
<td>归档事实</td>
</tr>
<tr>
<td>P1 / P2</td>
<td>true / true；两阶段均仅提交 1 次</td>
</tr>
<tr>
<td>主流程 / 补救</td>
<td>primary_full=true；fallback=false</td>
</tr>
<tr>
<td>正式版本</td>
<td>rev4；P2 未增加新版本</td>
</tr>
<tr>
<td>草稿</td>
<td>1 次成功提交；0 次回滚</td>
</tr>
<tr>
<td>预算</td>
<td>初始 16，消耗 12，剩余 4 Bird-Coin</td>
</tr>
<tr>
<td>官方工具 / Grounding</td>
<td>9 次官方工具调用；15 次独立 Grounding 调用</td>
</tr>
<tr>
<td>同题基线</td>
<td>同样 Full PASS，Reward 1.0；本题净增分为 0</td>
</tr>
	</table>
	这个案例完整展示了：Mapping 先保留公式缺口，Knowledge 取得规则，Check 补查后把控制交给 Gate，再由有权修改字段的 Mapping 完成修订；草稿通过后统一提交，P2 复用已确认的语义信息。Knowledge 的越权字段建议没有直接生效，但主流程仍完成了任务。
	需要保留的限制：Check 在公式已入库后又查询名称与具体定义，存在重复取证。本题补全审计用量为 92,709 token，基线为 43,733 token；Bird-Coin 为 12 对 10。它是机制跑通的成功示例，不是成本更低或成绩提升的证据。
	<details>
	<summary>来源与请求索引（便于复核）</summary>
		所有路径均相对项目根目录。原始模型推理、连接配置和凭据不复制到 Notion；下面展示的是完整结构化输出，schema / 字段 / 知识目录等长输入保留在归档请求中。
		`research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/official_result.json:1`：原请求、追问、SQL、执行反馈与最终成绩。
		`research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/private_final_state.json:1`：权限保护、正式状态、草稿提交、阶段结果与 Main 请求。
		`baseline/framework_analysis_20260914/task_comparison.json`：任务 cybermarket_pattern_10 的最终计分记录，primary_full=true、fallback=false。
		1. `research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/provider_audits/01_sql-grounding-20260908T054947076628Z-3af683ab8dce-8e7ea924.json:1`
			阶段：`structure`；Prompt SHA256：`04fe3f57e52e09c4ad41e059afd8a211f9808f54f7cfca15e67524594b0f61e1`；Request SHA256：`3af683ab8dcedaf803cc5cfc9fb89c3c7a3749e9bfc7fcb67aabd1a0252ea2a8`。
		2. `research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/provider_audits/02_sql-grounding-20260908T055001432883Z-f28cd8c99e21-7fd30e05.json:1`
			阶段：`mapping`；Prompt SHA256：`a1bad3f28e8328fefea85c87b7092c0069649a0f4d73f2ad7a3135a0d37ac60b`；Request SHA256：`f28cd8c99e215cc87cf059a7718ec31eb6abacdfe50111087151e4de70ede800`。
		3. `research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/provider_audits/03_sql-grounding-20260908T055029576609Z-abc0ffcb44fd-6cb170b0.json:1`
			阶段：`knowledge`；Prompt SHA256：`02a8adcb72c1dcb1ee817c3ca1dc0bb6be5d2dd6521b1ea67a0f8a6dd986cfa7`；Request SHA256：`abc0ffcb44fd65a4613c23f7c440b008e8e5c6ccc76feec85fe9c0559e280163`。
		4. `research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/provider_audits/04_sql-grounding-20260908T055040508708Z-bf361510421d-f8792a80.json:1`
			阶段：`check`；Prompt SHA256：`d70eedd5785774cec00fa681e8c76f862a41fb5755d3a2af10c5634f29892d44`；Request SHA256：`bf361510421d5ef079fdfb2b55e6973ed7d4a3747c5627f276d46526b62e480e`。
		5. `research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/provider_audits/05_sql-grounding-20260908T055056174433Z-87e0924333c4-044a61a1.json:1`
			阶段：`check`；Prompt SHA256：`d70eedd5785774cec00fa681e8c76f862a41fb5755d3a2af10c5634f29892d44`；Request SHA256：`87e0924333c4af879c404fd8d17763fdf77bf268e5ee66bd7f81b1f6d29831d2`。
		6. `research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/provider_audits/06_sql-grounding-20260908T055121384161Z-ddfc2eb674ee-352ae014.json:1`
			阶段：`check`；Prompt SHA256：`d70eedd5785774cec00fa681e8c76f862a41fb5755d3a2af10c5634f29892d44`；Request SHA256：`ddfc2eb674ee2d0d018eccd29f615d902ba7e109db2080b135988e5b73d8823b`。
		7. `research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/provider_audits/07_sql-grounding-20260908T055202840805Z-3003797761f1-41b8ddad.json:1`
			阶段：`final_gate`；Prompt SHA256：`bbd960f1a14fb13746f7bd50a703dc9b874b411c7aa3cfc404fe6ba2a9960cda`；Request SHA256：`3003797761f1d4dfb94e914f6cbec5ea9a15d7e8a5cf0d08bb51f4ae93ba016a`。
		8. `research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/provider_audits/08_sql-grounding-20260908T055220030358Z-69ec8999589f-8ee237a8.json:1`
			阶段：`mapping`；Prompt SHA256：`964f4bbf552b80fc0bb6fe5aa1fe7fbd3d410d7196435a454dda80cabedbe9e0`；Request SHA256：`69ec8999589f5975e2a97d73c4e7a27c4a78dd30eba3b4b413f94b3f80892b47`。
		9. `research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/provider_audits/09_sql-grounding-20260908T055248511390Z-adeed203cc13-329fff6e.json:1`
			阶段：`knowledge`；Prompt SHA256：`02a8adcb72c1dcb1ee817c3ca1dc0bb6be5d2dd6521b1ea67a0f8a6dd986cfa7`；Request SHA256：`adeed203cc13f3bc21061ece95cadcd46b37edea6bc958116fcf6e114089c026`。
		10. `research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/provider_audits/10_sql-grounding-20260908T055301118859Z-09f775f5f854-53d3de54.json:1`
			阶段：`check`；Prompt SHA256：`d70eedd5785774cec00fa681e8c76f862a41fb5755d3a2af10c5634f29892d44`；Request SHA256：`09f775f5f854b2abcf7e152efceb74599a81c362f6eea312743e3890cc0fac57`。
		11. `research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/provider_audits/11_sql-grounding-20260908T055414314649Z-0ffa6a243468-9e096ba8.json:1`
			阶段：`structure`；Prompt SHA256：`04fe3f57e52e09c4ad41e059afd8a211f9808f54f7cfca15e67524594b0f61e1`；Request SHA256：`0ffa6a243468607d2304f0dad7f17ef9768f131b5a59611b1ab0a4760b10bbbc`。
		12. `research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/provider_audits/12_sql-grounding-20260908T055416510584Z-0fa4119f15ac-eda0b180.json:1`
			阶段：`mapping`；Prompt SHA256：`a1bad3f28e8328fefea85c87b7092c0069649a0f4d73f2ad7a3135a0d37ac60b`；Request SHA256：`0fa4119f15ac658bc5a980db962aa24fc17077bb6b8577ffc394a030a41cdf76`。
		13. `research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/provider_audits/13_sql-grounding-20260908T055425714919Z-e72f76912c58-7c29a04d.json:1`
			阶段：`knowledge`；Prompt SHA256：`02a8adcb72c1dcb1ee817c3ca1dc0bb6be5d2dd6521b1ea67a0f8a6dd986cfa7`；Request SHA256：`e72f76912c582479162dcee16cccb3f3c1b63ff2e47b5d6f5d1432a36b05063b`。
		14. `research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/provider_audits/14_sql-grounding-20260908T055436395489Z-282dfd1014c7-8fc41b60.json:1`
			阶段：`check`；Prompt SHA256：`d70eedd5785774cec00fa681e8c76f862a41fb5755d3a2af10c5634f29892d44`；Request SHA256：`282dfd1014c769443d46d45bc9b7b89ab5db240f47c97549c493778155ec0a43`。
		15. `research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/76_cybermarket_pattern_10/provider_audits/15_sql-grounding-20260908T055449261760Z-77cde8847db3-8c1e79b9.json:1`
			阶段：`final_gate`；Prompt SHA256：`bbd960f1a14fb13746f7bd50a703dc9b874b411c7aa3cfc404fe6ba2a9960cda`；Request SHA256：`77cde8847db3570a3b5cdd05d269e8a2f6deb2bd722b66277ffc01d9d50f7517`。
	</details>
</details>
<details>
<summary><span color="red">**2. solar_panel_7：四维修订、草稿回滚与独立补救**</span></summary>
	原始问题：
	```plain text
When our panels have bad busbar corrosion, how much does their quality drop?
	```
	请求释义：<span color="red">面板汇流条</span><span color="red">`腐蚀严重`</span><span color="red">时，</span><span color="red">`质量下降`</span><span color="red">多少？</span>初始预算 18 Coin。质量指标与 bad 的等级均有歧义。
	> 来源：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:6`。以下使用本次 Full600 的同一条轨迹。S 表示正式状态，D 表示临时草稿。状态内容直接取自下一轮真实请求中的 current_state，并与最终审计进行过核对。
	#### 顺序总览
	<table fit-page-width="true" header-row="true">
	<colgroup>
	<col width="52">
	<col>
	<col width="365">
	</colgroup>
<tr>
<td>步骤</td>
<td>模型提出的内容</td>
<td>实际处理与保存</td>
</tr>
<tr>
<td>1</td>
<td>结构提取：确定相关表和连接关系</td>
<td>格式和服务层接受，正式状态更新为 S1 / rev1。</td>
</tr>
<tr>
<td>2</td>
<td>字段映射：腐蚀字段明确，质量指标仍不明确</td>
<td>接受，正式状态更新为 S2 / rev2。没有把未知指标擅自落实到某个字段。</td>
</tr>
<tr>
<td>3</td>
<td>知识选择：加入腐蚀等级定义</td>
<td>接受，正式状态更新为 S3 / rev3。</td>
</tr>
<tr>
<td>4</td>
<td>Check #1：询问 quality drop 的具体含义</td>
<td>请求通过并实际执行，花费 2 Coin，余额 15 → 13。</td>
</tr>
<tr>
<td>5</td>
<td>Check #2：用户回答后，需要补充字段对应</td>
<td>返回 incomplete、next_tool=null、restart_grounding，转交 Gate。</td>
</tr>
<tr>
<td>6</td>
<td>Gate：只重做字段，不重做表范围</td>
<td>REGROUND_MAPPING；以正式 rev3 为基础创建临时草稿。</td>
</tr>
<tr>
<td>7</td>
<td>草稿 Mapping：把 fill factor 差值落实到字段</td>
<td>草稿接受，D4 / private rev4；正式状态仍为 S3。</td>
</tr>
<tr>
<td>8</td>
<td>草稿 Knowledge：补齐 Fill Factor 定义</td>
<td>草稿接受，D5 / private rev5；正式状态仍为 S3。</td>
</tr>
<tr>
<td>9</td>
<td>草稿 Check：需要确认 bad，但提问交接失败</td>
<td>Check 本身为 noop；后续提问交接被 AtomicDraftClarificationNotUnresolved 拒绝。未实际问用户、未扣提问费；正式状态保持 S3。</td>
</tr>
	</table>
	#### 0. 初始状态 S0 / rev0
	```json
{
  "column_mapping": null,
  "domain_knowledge": null,
  "join_keys": null,
  "tables": null
}
	```
	四维均为 null，表示尚未整理。<span color="blue">*用户澄清、预算、Check 结果与未解决项单独保存，不并入这四个维度。*</span>
	#### 1. 结构提取：确定相关表和连接关系
	读取原请求和官方 schema，提出两张表及一条连接关系。
	本轮输入字段：`current_state`、`query`、`schema`。
	模型的结构化输出（原文截取，仅调整缩进）：
	```json
{
  "tables": [
    "mechanical_condition", # 机械状况
    "electrical_performance"  # 电气性能
  ],
  "join_keys": [
    "mechanical_condition.snapmk = electrical_performance.snaplink"
  ]
}
	```
	**四维变化：** tables、join_keys 从 null 变为具体内容；其余两维仍为 null。
	**校验与实际处理：** 格式和服务层接受，正式状态更新为 S1 / rev1。
	<details color="red">
	<summary>实际保留的四维内容</summary>
		```json
{
  "column_mapping": null,
  "domain_knowledge": null,
  "join_keys": [
    "mechanical_condition.snapmk = electrical_performance.snaplink"
  ],
  "tables": [
    "electrical_performance",
    "mechanical_condition"
  ]
}
		```
		![](assets/notion-zh-2.png)
		证据：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:18`；完整输入 `baseline/framework_analysis_20260914/solar_panel_7_01_structure_input.json:1`；System Prompt `baseline/framework_analysis_20260914/prompt_structure_04fe3f57e5.txt:1`。
	</details>
	#### 2. 字段映射：腐蚀字段明确，质量指标仍不明确
	字段说明包含腐蚀等级以及多种电气指标。模型只确定 busbar corrosion 的字段，把 quality drop 留作用户意图歧义。
	本轮输入字段：`column_meanings`、`current_state`、`query`、`unresolved_mappings`。
	模型的结构化输出（原文，仅调整缩进）：
	```json
{
  "tables": [
    "electrical_performance",
    "mechanical_condition"
  ],
  "join_keys": [
    "mechanical_condition.snapmk = electrical_performance.snaplink"
  ],
  "column_mapping": [
    {
      "phrase": "busbar corrosion", # 母线腐蚀
      "targets": [
        "mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"
      ]
    }
  ],
  "unresolved_mappings": [
    {
      "phrase": "quality drop",
      "reason": "ambiguous_user_intent"
    }
  ]
}
	```
	![](assets/notion-zh-3.png)
	**四维变化：** 新增腐蚀字段映射；框架外 unresolved_mappings 新增 quality drop。
	**校验与实际处理：** 接受，正式状态更新为 S2 / rev2。没有把未知指标擅自落实到某个字段。
	<details color="red">
	<summary>实际保留的四维内容</summary>
		```json
{
  "column_mapping": [
    {
      "phrase": "busbar corrosion",
      "targets": [
        "mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"
      ]
    }
  ],
  "domain_knowledge": null,
  "join_keys": [
    "mechanical_condition.snapmk = electrical_performance.snaplink"
  ],
  "tables": [
    "electrical_performance",
    "mechanical_condition"
  ]
}
		```
		证据：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:42`；完整输入 `baseline/framework_analysis_20260914/solar_panel_7_02_mapping_input.json:1`；System Prompt `baseline/framework_analysis_20260914/prompt_mapping_a1bad3f28e.txt:1`。
	</details>
	#### 3. 知识选择：加入腐蚀等级定义
	读取官方知识目录，选择 ID46（Busbar Corrosion Severity）。
	![](assets/notion-zh-4.png)
	本轮输入字段：`current_state`、`knowledge_definitions`、`query`、`relevant_column_meanings`、`unresolved_mappings`。
	模型的结构化输出（原文，仅调整缩进）：
	```json
{
  "column_mapping": [
    {
      "phrase": "busbar corrosion",
      "targets": [
        "mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"
      ]
    }
  ],
  "selected_knowledge_ids": [
    46
  ]
}
	```
	**四维变化：** domain_knowledge 从 null 变为腐蚀定义原文。ID46 是此次目录编号，不是状态中的永久身份。
	**校验与实际处理：** 接受，正式状态更新为 S3 / rev3。
	<details color="red">
	<summary>实际保留的四维内容</summary>
		```json
{
  "column_mapping": [
    {
      "phrase": "busbar corrosion",
      "targets": [
        "mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"
      ]
    }
  ],
  "domain_knowledge": [
    {
      "content": "Describes the extent of corrosion on the metallic strips (busbars) that conduct electricity within a solar panel. Levels can range from 'None' to 'Light' (minor discoloration), 'Visible' (clear corrosion affecting small areas), and 'Severe' (widespread corrosion that can disrupt conductivity and reduce power output).",
      "kind": "business_rule"
    }
  ],
  "join_keys": [
    "mechanical_condition.snapmk = electrical_performance.snaplink"
  ],
  "tables": [
    "electrical_performance",
    "mechanical_condition"
  ]
}
		```
		证据：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:157`；完整输入 `baseline/framework_analysis_20260914/solar_panel_7_03_knowledge_input.json:1`；System Prompt `baseline/framework_analysis_20260914/prompt_knowledge_02a8adcb72.txt:1`。
	</details>
	#### 4. Check #1：询问 quality drop 的具体含义
	四维信息仍不足以确定质量指标，Check 申请 ask_user。
	本轮输入字段：`answered_clarifications`、`check_context`、`current_state`、`previous_official_calls`、`query`、`unresolved_mappings`。
	模型的结构化输出（原文，仅调整缩进）：
	```json
{
  "status": "incomplete",
  "clarification_route": "none",
  "missing_information": "The phrase 'quality drop' is ambiguous: it is unclear which specific quality metric (e.g., power output, efficiency, performance ratio, quality grade) the user means, and what threshold or comparison defines a 'drop'.",
  "next_tool": {
    "tool_name": "ask_user",
    "arguments": {
      "question": "When you say 'quality drop', which specific aspect of panel quality are you referring to? For example, are you asking about a decrease in power output, a reduction in efficiency, a change in quality grade, or another quality metric? Please also specify what level of change or threshold you would consider a meaningful 'drop'."
    },
    "user_clarification_request": {
      "phrase": "quality drop",
      "kind": "user_intent",
      "requirement_type": null,
      "related_mapping_phrases": []
    }
  },
  "column_mapping": [
    {
      "phrase": "busbar corrosion",
      "targets": [
        "mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"
      ]
    }
  ],
  "domain_knowledge": [
    {
      "kind": "business_rule",
      "content": "Describes the extent of corrosion on the metallic strips (busbars) that conduct electricity within a solar panel. Levels can range from 'None' to 'Light' (minor discoloration), 'Visible' (clear corrosion affecting small areas), and 'Severe' (widespread corrosion that can disrupt conductivity and reduce power output)."
    }
  ]
}
	```
	**四维变化：** 四维不变，仍为 S3；提问和回答保存在框架外。
	**校验与实际处理：** 请求通过并实际执行，花费 2 Coin，余额 15 → 13。
	<details>
	<summary><span color="red">实际保留的四维内容</span></summary>
		```json
{
  "column_mapping": [
    {
      "phrase": "busbar corrosion",
      "targets": [
        "mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"
      ]
    }
  ],
  "domain_knowledge": [
    {
      "content": "Describes the extent of corrosion on the metallic strips (busbars) that conduct electricity within a solar panel. Levels can range from 'None' to 'Light' (minor discoloration), 'Visible' (clear corrosion affecting small areas), and 'Severe' (widespread corrosion that can disrupt conductivity and reduce power output).",
      "kind": "business_rule"
    }
  ],
  "join_keys": [
    "mechanical_condition.snapmk = electrical_performance.snaplink"
  ],
  "tables": [
    "electrical_performance",
    "mechanical_condition"
  ]
}
		```
		证据：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:580`；完整输入 `baseline/framework_analysis_20260914/solar_panel_7_04_check_input.json:1`；System Prompt `baseline/framework_analysis_20260914/prompt_check_d70eedd578.txt:1`。
	</details>
	实际用户回答：
	```plain text
By "quality drop," I'm referring to the degradation of the panel's electrical performance characteristics, specifically the fill factor. The fill factor is a key indicator of how well a solar panel converts sunlight into electricity. When I ask how much quality drops, I'm measuring the difference between the panel's initial fill factor (when it was new or at baseline) and its current fill factor (at the time of measurement). A larger difference indicates greater degradation in the panel's ability to perform efficiently. This metric directly reflects the panel's electrical quality decline over time due to aging and environmental stress factors like the busbar corrosion you mentioned.
	```
	回答明确了“<span color="red">初始值 − 当前值</span>”，但没有确认 bad 对应 Severe。这两处歧义不能合并视为已解决。
	#### 5. Check #2：用户回答后，需要补充字段对应
	用户明确为初始 fill factor 与当前 fill factor 的差。Check 判断这两个操作数尚未进入 Mapping。
	本轮输入字段：`answered_clarifications`、`current_state`、`latest_user_answer`、`previous_official_calls`、`query`、`unresolved_mappings`、`user_clarifications`。
	模型的结构化输出（原文，仅调整缩进）：
	```json
{
  "status": "incomplete",
  "clarification_route": "restart_grounding",
  "missing_information": "User clarified 'quality drop' as the difference between initial fill factor and current fill factor in electrical_performance. This introduces new concepts (fill factor, baseline/initial fill factor, current fill factor, and their difference) not yet grounded in column_mapping. A new Grounding cycle is needed to map these concepts to fields in electrical_performance.",
  "next_tool": null,
  "column_mapping": [
    {
      "phrase": "busbar corrosion",
      "targets": [
        "mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"
      ]
    }
  ],
  "domain_knowledge": [
    {
      "kind": "business_rule",
      "content": "Describes the extent of corrosion on the metallic strips (busbars) that conduct electricity within a solar panel. Levels can range from 'None' to 'Light' (minor discoloration), 'Visible' (clear corrosion affecting small areas), and 'Severe' (widespread corrosion that can disrupt conductivity and reduce power output)."
    }
  ]
}
	```
	**四维变化：** 四维仍为 S3；新用户回答可见，但不能仅凭 Check 把 Mapping 未解决项清空。
	**校验与实际处理：** 返回 incomplete、next_tool=null、restart_grounding，转交 Gate。
	<details>
	<summary><span color="red">实际保留的四维内容</span></summary>
		```json
{
  "column_mapping": [
    {
      "phrase": "busbar corrosion",
      "targets": [
        "mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"
      ]
    }
  ],
  "domain_knowledge": [
    {
      "content": "Describes the extent of corrosion on the metallic strips (busbars) that conduct electricity within a solar panel. Levels can range from 'None' to 'Light' (minor discoloration), 'Visible' (clear corrosion affecting small areas), and 'Severe' (widespread corrosion that can disrupt conductivity and reduce power output).",
      "kind": "business_rule"
    }
  ],
  "join_keys": [
    "mechanical_condition.snapmk = electrical_performance.snaplink"
  ],
  "tables": [
    "electrical_performance",
    "mechanical_condition"
  ]
}
		```
		证据：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:631`；完整输入 `baseline/framework_analysis_20260914/solar_panel_7_05_check_input.json:1`；System Prompt `baseline/framework_analysis_20260914/prompt_check_d70eedd578.txt:1`。
	</details>
	#### 6. Gate：只重做字段，不重做表范围
	新回答涉及的字段位于已有表范围内，无须增加表或连接。
	本轮输入字段：`current_state`、`final_gate_context`、`query`、`user_clarifications`。
	模型的结构化输出（原文，仅调整缩进）：
	```json
{
  "decision": "REGROUND_MAPPING",
  "reason": "User clarification redefines 'quality drop' as the difference between initial fill factor and current fill factor, introducing new SQL-relevant operands (fill_factor_initial, fill_factor_now, and their computed difference) not yet present in column_mapping. The schema confirms these fields exist in electrical_performance.elec_perf_snapshot -> 'iv_curve', which is already within the current tables and join scope. No new tables or join paths are needed."
}
	```
	也就是说：根据用户的明确定义，“质量下降”（quality drop）被界定为初始填充因子与当前填充因子之差；这引入了新的 SQL 相关操作数（`fill_factor_initial`、`fill_factor_now` 及其计算差值），而这些操作数此前并未包含在 `column_mapping` 中。经确认，这些字段存在于 `electrical_performance.elec_perf_snapshot -> 'iv_curve'` 中，该路径已涵盖在当前的表结构及连接（join）范围内，因此无需新增表或连接路径。
	**四维变化：** 四维仍为 S3。Gate 只决定范围，不直接改状态。
	**校验与实际处理：** REGROUND_MAPPING；以正式 rev3 为基础创建临时草稿。
	<details>
	<summary><span color="red">实际保留的四维内容</span></summary>
		```json
{
  "column_mapping": [
    {
      "phrase": "busbar corrosion",
      "targets": [
        "mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"
      ]
    }
  ],
  "domain_knowledge": [
    {
      "content": "Describes the extent of corrosion on the metallic strips (busbars) that conduct electricity within a solar panel. Levels can range from 'None' to 'Light' (minor discoloration), 'Visible' (clear corrosion affecting small areas), and 'Severe' (widespread corrosion that can disrupt conductivity and reduce power output).",
      "kind": "business_rule"
    }
  ],
  "join_keys": [
    "mechanical_condition.snapmk = electrical_performance.snaplink"
  ],
  "tables": [
    "electrical_performance",
    "mechanical_condition"
  ]
}
		```
		证据：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:705`；完整输入 `baseline/framework_analysis_20260914/solar_panel_7_06_final_gate_input.json:1`；System Prompt `baseline/framework_analysis_20260914/prompt_final_gate_bbd960f1a1.txt:1`。
	</details>
	#### 7. 草稿 Mapping：把 fill factor 差值落实到字段
	读取用户回答和已有字段说明，给 quality drop 增加初始与当前 fill factor 两个字段。
	本轮输入字段：`column_meanings`、`current_state`、`query`、`regrounding_context`、`unresolved_mappings`、`user_clarifications`。
	模型的结构化输出（原文，仅调整缩进）：
	```json
{
  "tables": [
    "electrical_performance",
    "mechanical_condition"
  ],
  "join_keys": [
    "mechanical_condition.snapmk = electrical_performance.snaplink"
  ],
  "column_mapping": [
    {
      "phrase": "busbar corrosion",
      "targets": [
        "mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"
      ]
    },
    {
      "phrase": "quality drop",
      "targets": [
        "electrical_performance.elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_initial'",
        "electrical_performance.elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_now'"
      ]
    }
  ],
  "unresolved_mappings": []
}
	```
	**四维变化：** 草稿新增 quality drop 映射；草稿 unresolved_mappings 清空。
	**校验与实际处理：** 草稿接受，D4 / private rev4；正式状态仍为 S3。
	<details>
	<summary><span color="red">检查／修改后的草稿内容（尚未提交）</span></summary>
		```json
{
  "column_mapping": [
    {
      "phrase": "busbar corrosion",
      "targets": [
        "mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"
      ]
    },
    {
      "phrase": "quality drop",
      "targets": [
        "electrical_performance.elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_initial'",
        "electrical_performance.elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_now'"
      ]
    }
  ],
  "domain_knowledge": [
    {
      "content": "Describes the extent of corrosion on the metallic strips (busbars) that conduct electricity within a solar panel. Levels can range from 'None' to 'Light' (minor discoloration), 'Visible' (clear corrosion affecting small areas), and 'Severe' (widespread corrosion that can disrupt conductivity and reduce power output).",
      "kind": "business_rule"
    }
  ],
  "join_keys": [
    "mechanical_condition.snapmk = electrical_performance.snaplink"
  ],
  "tables": [
    "electrical_performance",
    "mechanical_condition"
  ]
}
		```
		证据：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:892`；完整输入 `baseline/framework_analysis_20260914/solar_panel_7_07_mapping_input.json:1`；System Prompt `baseline/framework_analysis_20260914/prompt_mapping_964f4bbf55.txt:1`。
	</details>
	#### 8. 草稿 Knowledge：补齐 Fill Factor 定义
	选择 ID42（Fill Factor）和 ID46（腐蚀等级）。
	![](assets/notion-zh-5.png)
	本轮输入字段：`current_state`、`knowledge_definitions`、`query`、`regrounding_context`、`relevant_column_meanings`、`unresolved_mappings`、`user_clarifications`。
	模型的结构化输出（原文，仅调整缩进）：
	```json
{
  "column_mapping": [
    {
      "phrase": "busbar corrosion",
      "targets": [
        "mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"
      ]
    },
    {
      "phrase": "quality drop",
      "targets": [
        "electrical_performance.elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_initial'",
        "electrical_performance.elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_now'"
      ]
    }
  ],
  "selected_knowledge_ids": [
    42,
    46
  ]
}
	```
	**四维变化：** 草稿新增 Fill Factor 原文，保留腐蚀定义。
	**校验与实际处理：** 草稿接受，D5 / private rev5；正式状态仍为 S3。
	<details>
	<summary><span color="red">检查／修改后的草稿内容（尚未提交）</span></summary>
		```json
{
  "column_mapping": [
    {
      "phrase": "busbar corrosion",
      "targets": [
        "mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"
      ]
    },
    {
      "phrase": "quality drop",
      "targets": [
        "electrical_performance.elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_initial'",
        "electrical_performance.elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_now'"
      ]
    }
  ],
  "domain_knowledge": [
    {
      "content": "A measure of the 'squareness' of the current-voltage (IV) curve, indicating the quality of the solar cell. It is the ratio of the maximum actual power to the theoretical maximum power. A higher value (e.g., >0.8) indicates a higher quality cell with low internal power losses.",
      "kind": "business_rule"
    },
    {
      "content": "Describes the extent of corrosion on the metallic strips (busbars) that conduct electricity within a solar panel. Levels can range from 'None' to 'Light' (minor discoloration), 'Visible' (clear corrosion affecting small areas), and 'Severe' (widespread corrosion that can disrupt conductivity and reduce power output).",
      "kind": "business_rule"
    }
  ],
  "join_keys": [
    "mechanical_condition.snapmk = electrical_performance.snaplink"
  ],
  "tables": [
    "electrical_performance",
    "mechanical_condition"
  ]
}
		```
		证据：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:1052`；完整输入 `baseline/framework_analysis_20260914/solar_panel_7_08_knowledge_input.json:1`；System Prompt `baseline/framework_analysis_20260914/prompt_knowledge_02a8adcb72.txt:1`。
	</details>
	#### 9. 草稿 Check：需要确认 bad，但提问交接失败
	Check 提出：bad 是只包括 Severe，还是也包括 Visible。问题合理，但没有填写分类问题所需的类型与关联短语。
	本轮输入字段：`answered_clarifications`、`check_context`、`current_state`、`previous_official_calls`、`query`、`regrounding_context`、`unresolved_mappings`、`user_clarifications`。
	模型的结构化输出（原文，仅调整缩进）：
	```json
{
  "status": "incomplete",
  "clarification_route": "none",
  "missing_information": "The query refers to 'bad busbar corrosion' but does not specify which corrosion levels qualify as 'bad'. Busbar corrosion is tracked as None, Light, Visible, and Severe. It is unclear whether 'bad' means only Severe, or also includes Visible.",
  "next_tool": {
    "tool_name": "ask_user",
    "arguments": {
      "question": "When you say 'bad busbar corrosion,' which specific corrosion levels are you referring to? Busbar corrosion is tracked as None, Light (minor discoloration), Visible (clear corrosion affecting small areas), and Severe (widespread corrosion that can disrupt conductivity and reduce power output). Should 'bad' include only Severe corrosion, or also Visible corrosion?"
    },
    "user_clarification_request": {
      "phrase": "bad busbar corrosion",
      "kind": "user_intent",
      "requirement_type": null,
      "related_mapping_phrases": []
    }
  },
  "column_mapping": [
    {
      "phrase": "busbar corrosion",
      "targets": [
        "mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"
      ]
    },
    {
      "phrase": "quality drop",
      "targets": [
        "electrical_performance.elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_initial'",
        "electrical_performance.elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_now'"
      ]
    }
  ],
  "domain_knowledge": [
    {
      "content": "A measure of the 'squareness' of the current-voltage (IV) curve, indicating the quality of the solar cell. It is the ratio of the maximum actual power to the theoretical maximum power. A higher value (e.g., >0.8) indicates a higher quality cell with low internal power losses.",
      "kind": "business_rule"
    },
    {
      "content": "Describes the extent of corrosion on the metallic strips (busbars) that conduct electricity within a solar panel. Levels can range from 'None' to 'Light' (minor discoloration), 'Visible' (clear corrosion affecting small areas), and 'Severe' (widespread corrosion that can disrupt conductivity and reduce power output).",
      "kind": "business_rule"
    }
  ]
}
	```
	**四维变化：** Check 候选未改四维；随后整个 D5 草稿被丢弃。
	**校验与实际处理：** Check 本身为 noop；后续提问交接被 AtomicDraftClarificationNotUnresolved 拒绝。未实际问用户、未扣提问费；正式状态保持 S3。
	<details>
	<summary><span color="red">展开此步检查／修改后的草稿内容（尚未提交）</span></summary>
		```json
{
  "column_mapping": [
    {
      "phrase": "busbar corrosion",
      "targets": [
        "mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"
      ]
    },
    {
      "phrase": "quality drop",
      "targets": [
        "electrical_performance.elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_initial'",
        "electrical_performance.elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_now'"
      ]
    }
  ],
  "domain_knowledge": [
    {
      "content": "A measure of the 'squareness' of the current-voltage (IV) curve, indicating the quality of the solar cell. It is the ratio of the maximum actual power to the theoretical maximum power. A higher value (e.g., >0.8) indicates a higher quality cell with low internal power losses.",
      "kind": "business_rule"
    },
    {
      "content": "Describes the extent of corrosion on the metallic strips (busbars) that conduct electricity within a solar panel. Levels can range from 'None' to 'Light' (minor discoloration), 'Visible' (clear corrosion affecting small areas), and 'Severe' (widespread corrosion that can disrupt conductivity and reduce power output).",
      "kind": "business_rule"
    }
  ],
  "join_keys": [
    "mechanical_condition.snapmk = electrical_performance.snaplink"
  ],
  "tables": [
    "electrical_performance",
    "mechanical_condition"
  ]
}
		```
		证据：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:1510`；完整输入 `baseline/framework_analysis_20260914/solar_panel_7_09_check_input.json:1`；System Prompt `baseline/framework_analysis_20260914/prompt_check_d70eedd578.txt:1`。
	</details>
	#### 10. 回滚后的正式状态与补救输入
	最终审计确认 formal_state_unchanged=true，正式版本为 3。草稿新增的 fill factor 映射和定义均未提交；用户澄清仍保留。该题没有进入正常 Main。
	```json
{
  "formal_revision": 3,
  "formal_state_sha256": "2a66fa9b33e74467e63a10d1d927f746c516bfdc9b89cd6a1e0baddb0fe4b7be",
  "draft_stages": [
    {
      "stage": "mapping",
      "revision": 4,
      "state_sha256": "b2ff43eac52b5588981f1d696936dbd0e705fdead362ecd685b1b57ed01389df",
      "status": "accepted"
    },
    {
      "stage": "knowledge",
      "revision": 5,
      "state_sha256": "1c8d44b20f1ebc7910ca932b9c544b5a852c3ba75cd5fd49bde922e0358c920c",
      "status": "accepted"
    },
    {
      "stage": "check",
      "revision": 5,
      "state_sha256": "1c8d44b20f1ebc7910ca932b9c544b5a852c3ba75cd5fd49bde922e0358c920c",
      "status": "noop"
    }
  ],
  "rolled_back": true
}
	```
	<details>
	<summary>原 Agent 补救实际收到的输入</summary>
		```plain text
ONE-TIME NATIVE A-INTERACT FALLBACK

The Valibra path has ended in a terminal failure. You now have one independent native A-Interact attempt in the same Official task and DB session. Solve the current phase and submit the best SQL you can.

Hard boundaries:
- The remaining Bird-Coin shown below is the real inherited ledger; it has not been reset.
- Preserve any accepted phase-1 artifact and the current Official DB state.
- Answered clarifications are binding user intent. Do not ask the same question again.
- The four-dimensional State is explicitly non-authoritative because the Valibra path failed. You may use it as a hint, correct it, or discard it.
- Do not infer benchmark/reference-only facts and do not return to Valibra.

FALLBACK CONTEXT (lawful task/session data):
{"accepted_phase_1_sql": null, "answered_clarifications": [{"answer": "By \"quality drop,\" I'm referring to the degradation of the panel's electrical performance characteristics, specifically the fill factor. The fill factor is a key indicator of how well a solar panel converts sunlight into electricity. When I ask how much quality drops, I'm measuring the difference between the panel's initial fill factor (when it was new or at baseline) and its current fill factor (at the time of measurement). A larger difference indicates greater degradation in the panel's ability to perform efficiently. This metric directly reflects the panel's electrical quality decline over time due to aging and environmental stress factors like the busbar corrosion you mentioned.", "phase": 1, "phrase": "quality drop", "question": "When you say 'quality drop', which specific aspect of panel quality are you referring to? For example, are you asking about a decrease in power output, a reduction in efficiency, a change in quality grade, or another quality metric? Please also specify what level of change or threshold you would consider a meaningful 'drop'."}], "current_phase": 1, "database": "solar_panel", "non_authoritative_failed_4d_state_hint": {"column_mapping": [{"phrase": "busbar corrosion", "targets": ["mechanical_condition.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion'"]}], "domain_knowledge": [{"content": "Describes the extent of corrosion on the metallic strips (busbars) that conduct electricity within a solar panel. Levels can range from 'None' to 'Light' (minor discoloration), 'Visible' (clear corrosion affecting small areas), and 'Severe' (widespread corrosion that can disrupt conductivity and reduce power output).", "kind": "business_rule"}], "join_keys": ["mechanical_condition.snapmk = electrical_performance.snaplink"], "tables": ["electrical_performance", "mechanical_condition"]}, "official_follow_up": null, "original_query": "When our panels have bad busbar corrosion, how much does their quality drop?", "public_execution_envelope": {"action_intent": "RESULT_QUERY", "decimal_places": 3, "order_sensitive": false, "response_type": "scalar", "task_category": "Query"}, "remaining_bird_coin": 13.0, "task_id": "solar_panel_7"}
		```
	</details>
	补救恢复原 Agent 的九个工具，继承 13 Coin 与已回答澄清，失败四维只作非权威提示。输入不是 D5；本题 P1 尚未通过，因此没有已通过的 P1 SQL。
	来源：`baseline/framework_analysis_20260914/solar_panel_7_当前_agent_06_request.json:1`；最终审计 `baseline/framework_analysis_20260914/solar_panel_7_evidence.md:1612`。
	#### 11. 实际工具与预算流水
	此表按真实工具顺序列出。预算仅反映 Bird-Coin，不等同于模型 token 费用。
	<table fit-page-width="true" header-row="true">
<tr>
<td>序号 / 阶段</td>
<td>工具</td>
<td>主要内容</td>
<td>余额变化</td>
</tr>
<tr>
<td>1 / P1</td>
<td>`get_schema`</td>
<td>按工具取得官方资料</td>
<td>18 → 17</td>
</tr>
<tr>
<td>2 / P1</td>
<td>`get_all_column_meanings`</td>
<td>按工具取得官方资料</td>
<td>17 → 16</td>
</tr>
<tr>
<td>3 / P1</td>
<td>`get_all_knowledge_definitions`</td>
<td>按工具取得官方资料</td>
<td>16 → 15</td>
</tr>
<tr>
<td>4 / P1</td>
<td>`ask_user`</td>
<td>澄清 quality drop</td>
<td>15 → 13</td>
</tr>
<tr>
<td>5 / P1</td>
<td>`get_schema`</td>
<td>按工具取得官方资料</td>
<td>13 → 12</td>
</tr>
<tr>
<td>6 / P1</td>
<td>`get_all_external_knowledge_names`</td>
<td>按工具取得官方资料</td>
<td>12 → 11.5</td>
</tr>
<tr>
<td>7 / P1</td>
<td>`get_knowledge_definition`</td>
<td>Busbar Corrosion Severity</td>
<td>11.5 → 11</td>
</tr>
<tr>
<td>8 / P1</td>
<td>`get_knowledge_definition`</td>
<td>IV Curve Fill Factor</td>
<td>11 → 10.5</td>
</tr>
<tr>
<td>9 / P1</td>
<td>`execute_sql`</td>
<td>完整 SQL 见下方候选记录</td>
<td>10.5 → 9.5</td>
</tr>
<tr>
<td>10 / P1</td>
<td>`execute_sql`</td>
<td>完整 SQL 见下方候选记录</td>
<td>9.5 → 8.5</td>
</tr>
<tr>
<td>11 / P1</td>
<td>`submit_sql`</td>
<td>Phase 1 correct! (Reward: 0.7). Moving to Phase 2.</td>
<td>8.5 → 5.5</td>
</tr>
<tr>
<td>12 / P2</td>
<td>`get_knowledge_definition`</td>
<td>Current Degradation Factor</td>
<td>5.5 → 5</td>
</tr>
<tr>
<td>13 / P2</td>
<td>`execute_sql`</td>
<td>完整 SQL 见下方候选记录</td>
<td>5 → 4</td>
</tr>
<tr>
<td>14 / P2</td>
<td>`submit_sql`</td>
<td>Phase 2 correct! (Reward: 0.3). Task finished.</td>
<td>4 → 1</td>
</tr>
	</table>
	#### 12. 逐次 SQL、反馈与后续变化
	以下 SQL 来自工具记录，没有补写未执行的候选。执行结果仅节选前 450 字符；提交反馈完整保留。
	<details>
	<summary>当前 工具 #9 / P1 / execute_sql；余额 10.5 → 9.5</summary>
		```sql
SELECT ROUND(AVG(
  (elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_initial')::numeric -
  (elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_now')::numeric
), 3) AS avg_quality_drop
FROM electrical_performance ep
JOIN mechanical_condition mc ON ep.snaplink = mc.snapmk
WHERE mc.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion' = 'Severe';
		```
		反馈：
		```plain text
avg_quality_drop
----------------
0.051
		```
		来源：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:1898`。
	</details>
	<details>
	<summary>当前 工具 #10 / P1 / execute_sql；余额 9.5 → 8.5</summary>
		```sql
SELECT COUNT(*) AS panel_count,
  ROUND(AVG((elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_initial')::numeric), 3) AS avg_initial,
  ROUND(AVG((elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_now')::numeric), 3) AS avg_now
FROM electrical_performance ep
JOIN mechanical_condition mc ON ep.snaplink = mc.snapmk
WHERE mc.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion' = 'Severe';
		```
		反馈：
		```plain text
panel_count | avg_initial | avg_now
-----------------------------------
366 | 0.799 | 0.748
		```
		来源：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:1917`。
	</details>
	<details>
	<summary>当前 工具 #11 / P1 / submit_sql；余额 8.5 → 5.5</summary>
		```sql
SELECT ROUND(AVG(
  (elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_initial')::numeric -
  (elec_perf_snapshot -> 'iv_curve' ->> 'fill_factor_now')::numeric
), 3) AS avg_quality_drop
FROM electrical_performance ep
JOIN mechanical_condition mc ON ep.snaplink = mc.snapmk
WHERE mc.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion' = 'Severe';
		```
		反馈：
		```plain text
Phase 1 correct! (Reward: 0.7). Moving to Phase 2.
Reward: 0.7
Follow-up question: For panels experiencing 'Severe' busbar corrosion, what is the average Current Degradation Factor? Only consider snapshots with known initial and current Imp values, where the initial value is greater than zero. Give the result to 4 decimal places.
Budget remaining: 5.5 bird-coins
		```
		来源：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:1936`。
	</details>
	<details>
	<summary>当前 工具 #13 / P2 / execute_sql；余额 5 → 4</summary>
		```sql
SELECT ROUND(AVG(
  ((elec_perf_snapshot -> 'iv_curve' ->> 'imp_initial_a')::numeric -
   (elec_perf_snapshot -> 'iv_curve' ->> 'imp_now_a')::numeric) /
  (elec_perf_snapshot -> 'iv_curve' ->> 'imp_initial_a')::numeric
), 4) AS avg_current_degradation_factor
FROM electrical_performance ep
JOIN mechanical_condition mc ON ep.snaplink = mc.snapmk
WHERE mc.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion' = 'Severe'
  AND (elec_perf_snapshot -> 'iv_curve' ->> 'imp_initial_a') IS NOT NULL
  AND (elec_perf_snapshot -> 'iv_curve' ->> 'imp_now_a') IS NOT NULL
  AND (elec_perf_snapshot -> 'iv_curve' ->> 'imp_initial_a')::numeric > 0;
		```
		反馈：
		```plain text
avg_current_degradation_factor
------------------------------
0.1019
		```
		来源：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:1974`。
	</details>
	<details>
	<summary>当前 工具 #14 / P2 / submit_sql；余额 4 → 1</summary>
		```sql
SELECT ROUND(AVG(
  ((elec_perf_snapshot -> 'iv_curve' ->> 'imp_initial_a')::numeric -
   (elec_perf_snapshot -> 'iv_curve' ->> 'imp_now_a')::numeric) /
  (elec_perf_snapshot -> 'iv_curve' ->> 'imp_initial_a')::numeric
), 4) AS avg_current_degradation_factor
FROM electrical_performance ep
JOIN mechanical_condition mc ON ep.snaplink = mc.snapmk
WHERE mc.mech_health_snapshot -> 'module_surface' ->> 'busbar_corrosion' = 'Severe'
  AND (elec_perf_snapshot -> 'iv_curve' ->> 'imp_initial_a') IS NOT NULL
  AND (elec_perf_snapshot -> 'iv_curve' ->> 'imp_now_a') IS NOT NULL
  AND (elec_perf_snapshot -> 'iv_curve' ->> 'imp_initial_a')::numeric > 0;
		```
		反馈：
		```plain text
Phase 2 correct! (Reward: 0.3). Task finished.
Reward: 0.3
Budget remaining: 1.0 bird-coins
		```
		来源：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:1993`。
	</details>
	P1 先执行 fill_factor_initial − fill_factor_now 的平均差值，结果为 0.051；补查样本数和均值后提交通过。P2 由同一个补救 Agent 继续，不是重新进入四维框架。
	P2 追问与工具返回的原文：
	```plain text
Phase 1 correct! (Reward: 0.7). Moving to Phase 2.
Reward: 0.7
Follow-up question: For panels experiencing 'Severe' busbar corrosion, what is the average Current Degradation Factor? Only consider snapshots with known initial and current Imp values, where the initial value is greater than zero. Give the result to 4 decimal places.
Budget remaining: 5.5 bird-coins
	```
	```plain text
{
  "id": 15,
  "knowledge": "Current Degradation Factor",
  "description": "Quantifies the decline in a panel's maximum power point current (Imp) over time.",
  "definition": "The fractional loss of current-producing capability, calculated as: $I_{deg} = \\frac{I_{initial} - I_{now}}{I_{initial}}$."
}
	```
	取得 Current Degradation Factor 公式后，补救使用 (Imp_initial − Imp_now) / Imp_initial，添加非空、初始值大于零及 Severe 条件，执行结果 0.1019，提交通过。最终余额 1 Coin。
	#### 13. 同题基线与结论
	基线最终 FAIL，当前 Full PASS。但当前得分来自独立补救，不是草稿提交成功。基线也曾按澄清生成初始 fill factor 减当前 fill factor，首次提交失败后又改换解释。报告中记录的 float / numeric 评测差异仅为离线证据，不能认定是唯一原因。补救把 bad 解释成 Severe 虽命中参考答案，本轮并无用户对该等级的明确确认。
	<details>
	<summary>基线 工具 #10 / P1 / submit_sql（历史基线对照）</summary>
		```sql
SELECT 
  AVG(((ep.elec_perf_snapshot->'iv_curve'->>'fill_factor_initial')::float) - 
      ((ep.elec_perf_snapshot->'iv_curve'->>'fill_factor_now')::float)) AS avg_fill_factor_drop
FROM mechanical_condition mc
JOIN electrical_performance ep ON mc.snapmk = ep.snaplink
WHERE mc.mech_health_snapshot->'module_surface'->>'busbar_corrosion' = 'Severe';
		```
		```plain text
SQL failed Phase 1. Your SQL is not correct.
Budget remaining: 6.5 bird-coins
		```
		来源：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:2212`。
	</details>
	<details>
	<summary>基线 工具 #15 / P1 / submit_sql（历史基线对照）</summary>
		```sql
SELECT 
  ROUND(AVG(
    (((ep.elec_perf_snapshot->'iv_curve'->>'fill_factor_initial')::float) - 
     ((ep.elec_perf_snapshot->'iv_curve'->>'fill_factor_now')::float)) /
    NULLIF((ep.elec_perf_snapshot->'iv_curve'->>'fill_factor_initial')::float, 0) * 100
  )::numeric, 2) AS avg_fill_factor_drop_pct
FROM mechanical_condition mc
JOIN electrical_performance ep ON mc.snapmk = ep.snaplink
WHERE mc.mech_health_snapshot->'module_surface'->>'busbar_corrosion' = 'Severe';
		```
		```plain text
SQL failed Phase 1. Your SQL is not correct.
Budget remaining: -1 bird-coins
		```
		来源：`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:2307`。
	</details>
	<details>
	<summary>复核索引：每次 Provider 请求、Prompt 与完整输入</summary>
		- `01_sql-grounding-20260907T201727310759Z-0af8d934026e-b7e5a530.json: structure`
			- /home/user/code/BIRD-Interact/BIRD-Interact-ADK-agent-research/research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/07_solar_panel_7/provider_audits/01_sql-grounding-20260907T201727310759Z-0af8d934026e-b7e5a530.json:1；Prompt SHA256：04fe3f57e52e09c4ad41e059afd8a211f9808f54f7cfca15e67524594b0f61e1
			- 输入：`baseline/framework_analysis_20260914/solar_panel_7_01_structure_input.json:1`
			- Prompt：`baseline/framework_analysis_20260914/prompt_structure_04fe3f57e5.txt:1`
		- `02_sql-grounding-20260907T201731403784Z-11f1e8d891aa-830e85f7.json: mapping`
			- /home/user/code/BIRD-Interact/BIRD-Interact-ADK-agent-research/research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/07_solar_panel_7/provider_audits/02_sql-grounding-20260907T201731403784Z-11f1e8d891aa-830e85f7.json:1；Prompt SHA256：a1bad3f28e8328fefea85c87b7092c0069649a0f4d73f2ad7a3135a0d37ac60b
			- 输入：`baseline/framework_analysis_20260914/solar_panel_7_02_mapping_input.json:1`
			- Prompt：`baseline/framework_analysis_20260914/prompt_mapping_a1bad3f28e.txt:1`
		- `03_sql-grounding-20260907T201754132274Z-a954af165c27-7dba6a9e.json: knowledge`
			- /home/user/code/BIRD-Interact/BIRD-Interact-ADK-agent-research/research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/07_solar_panel_7/provider_audits/03_sql-grounding-20260907T201754132274Z-a954af165c27-7dba6a9e.json:1；Prompt SHA256：02a8adcb72c1dcb1ee817c3ca1dc0bb6be5d2dd6521b1ea67a0f8a6dd986cfa7
			- 输入：`baseline/framework_analysis_20260914/solar_panel_7_03_knowledge_input.json:1`
			- Prompt：`baseline/framework_analysis_20260914/prompt_knowledge_02a8adcb72.txt:1`
		- `04_sql-grounding-20260907T201830413815Z-484ea7e81529-34eb4cdb.json: check`
			- /home/user/code/BIRD-Interact/BIRD-Interact-ADK-agent-research/research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/07_solar_panel_7/provider_audits/04_sql-grounding-20260907T201830413815Z-484ea7e81529-34eb4cdb.json:1；Prompt SHA256：d70eedd5785774cec00fa681e8c76f862a41fb5755d3a2af10c5634f29892d44
			- 输入：`baseline/framework_analysis_20260914/solar_panel_7_04_check_input.json:1`
			- Prompt：`baseline/framework_analysis_20260914/prompt_check_d70eedd578.txt:1`
		- `05_sql-grounding-20260907T201916050319Z-ab472995171c-d25f66d4.json: check`
			- /home/user/code/BIRD-Interact/BIRD-Interact-ADK-agent-research/research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/07_solar_panel_7/provider_audits/05_sql-grounding-20260907T201916050319Z-ab472995171c-d25f66d4.json:1；Prompt SHA256：d70eedd5785774cec00fa681e8c76f862a41fb5755d3a2af10c5634f29892d44
			- 输入：`baseline/framework_analysis_20260914/solar_panel_7_05_check_input.json:1`
			- Prompt：`baseline/framework_analysis_20260914/prompt_check_d70eedd578.txt:1`
		- `06_sql-grounding-20260907T201925484567Z-1dcdf1f5aefc-fb55b587.json: final_gate`
			- /home/user/code/BIRD-Interact/BIRD-Interact-ADK-agent-research/research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/07_solar_panel_7/provider_audits/06_sql-grounding-20260907T201925484567Z-1dcdf1f5aefc-fb55b587.json:1；Prompt SHA256：bbd960f1a14fb13746f7bd50a703dc9b874b411c7aa3cfc404fe6ba2a9960cda
			- 输入：`baseline/framework_analysis_20260914/solar_panel_7_06_final_gate_input.json:1`
			- Prompt：`baseline/framework_analysis_20260914/prompt_final_gate_bbd960f1a1.txt:1`
		- `07_sql-grounding-20260907T201930585152Z-d4a6d866e143-7c9afded.json: mapping`
			- /home/user/code/BIRD-Interact/BIRD-Interact-ADK-agent-research/research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/07_solar_panel_7/provider_audits/07_sql-grounding-20260907T201930585152Z-d4a6d866e143-7c9afded.json:1；Prompt SHA256：964f4bbf552b80fc0bb6fe5aa1fe7fbd3d410d7196435a454dda80cabedbe9e0
			- 输入：`baseline/framework_analysis_20260914/solar_panel_7_07_mapping_input.json:1`
			- Prompt：`baseline/framework_analysis_20260914/prompt_mapping_964f4bbf55.txt:1`
		- `08_sql-grounding-20260907T202011467806Z-20cb4a3c9898-740fde5f.json: knowledge`
			- /home/user/code/BIRD-Interact/BIRD-Interact-ADK-agent-research/research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/07_solar_panel_7/provider_audits/08_sql-grounding-20260907T202011467806Z-20cb4a3c9898-740fde5f.json:1；Prompt SHA256：02a8adcb72c1dcb1ee817c3ca1dc0bb6be5d2dd6521b1ea67a0f8a6dd986cfa7
			- 输入：`baseline/framework_analysis_20260914/solar_panel_7_08_knowledge_input.json:1`
			- Prompt：`baseline/framework_analysis_20260914/prompt_knowledge_02a8adcb72.txt:1`
		- `09_sql-grounding-20260907T202025935278Z-986a534e4dd6-0dd68ac6.json: check`
			- /home/user/code/BIRD-Interact/BIRD-Interact-ADK-agent-research/research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/07_solar_panel_7/provider_audits/09_sql-grounding-20260907T202025935278Z-986a534e4dd6-0dd68ac6.json:1；Prompt SHA256：d70eedd5785774cec00fa681e8c76f862a41fb5755d3a2af10c5634f29892d44
			- 输入：`baseline/framework_analysis_20260914/solar_panel_7_09_check_input.json:1`
			- Prompt：`baseline/framework_analysis_20260914/prompt_check_d70eedd578.txt:1`
	</details>
	本节展示每次模型的完整结构化输出、状态快照与关键执行输入；大段 schema、字段目录和知识目录不重复展开，完整原文保留在上述本地输入文件中。
</details>
<details>
<summary><span color="red">**3. hulushows_12：字段已对应，但类别证据未传入 Main**</span></summary>
	原始问题：
	```plain text
List the shows with one of the main types like drama, comedy or animated stuff. Give me their ID, the name, and show what they fall under. Alphabetize them.
	```
	问题释义：列出戏剧、喜剧或动画<span color="red">等主要类别</span>的节目，返回 ID、名称与类别，并按名称排序。初始预算 20 Coin。
	来源：*`baseline/framework_analysis_20260914/hulushows_12_evidence.md:6`**。以下使用本次 Full600 的同一条轨迹。S 表示正式状态，D 表示临时草稿。状态内容直接取自下一轮真实请求中的 current_state，并与最终审计核对*
	#### 顺序总览
	<table fit-page-width="true" header-row="true">
	<colgroup>
	<col width="53">
	<col>
	<col width="368">
	</colgroup>
<tr>
<td>步骤</td>
<td>模型提出的内容</td>
<td>实际处理与保存</td>
</tr>
<tr>
<td>1</td>
<td>结构提取：单表即可回答</td>
<td>接受，S1 / rev1。</td>
</tr>
<tr>
<td>2</td>
<td>字段映射：名称和类别字段均已确定</td>
<td>接受，S2 / rev2。本轮不是旧实验中的 canonical_name 误选。</td>
</tr>
<tr>
<td>3</td>
<td>知识选择：没有保留业务定义</td>
<td>接受，S3 / rev3。字段说明中的枚举没有因此成为四维状态的一部分。</td>
</tr>
<tr>
<td>4</td>
<td>Check：尚未落实类别取值，却判断完成</td>
<td>检查流程通过，但通过不代表 Animated 已有证据支持。</td>
</tr>
<tr>
<td>5</td>
<td>Gate：不重做，进入正常 Main</td>
<td>NO_REGROUND，且 Check 已完成，因此进入 Main。</td>
</tr>
	</table>
	#### 0. 初始状态 S0 / rev0
	```json
{
  "column_mapping": null,
  "domain_knowledge": null,
  "join_keys": null,
  "tables": null
}
	```
	四维均为 null，表示尚未整理。用户澄清、预算、Check 结果与未解决项单独保存，不并入这四个维度。
	#### 1. 结构提取：单表即可回答
	官方 schema 支持从 core 取得节目 ID、名称及类别，无须连接。
	本轮输入字段：`current_state`、`query`、`schema`。
	模型的结构化输出（原文，仅调整缩进）：
	```json
{
  "tables": [
    "core"
  ],
  "join_keys": []
}
	```
	**四维变化：** tables 变为 core；join_keys 变为 \[\]；其余两维为 null。
	**校验与实际处理：** 接受，S1 / rev1。
	<details>
	<summary><span color="red">实际保留的四维内容</span></summary>
		```json
{
  "column_mapping": null,
  "domain_knowledge": null,
  "join_keys": [],
  "tables": [
    "core"
  ]
}
		```
		证据：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:18`；完整输入 `baseline/framework_analysis_20260914/hulushows_12_01_structure_input.json:1`；System Prompt `baseline/framework_analysis_20260914/prompt_structure_04fe3f57e5.txt:1`。
	</details>
	#### 2. 字段映射：名称和类别字段均已确定
	Mapping 将 the name 对应 content_title，将 main types 与 what they fall under 对应 Primary_Genre。
	本轮输入字段：`column_meanings`、`current_state`、`query`、`unresolved_mappings`。
	模型的结构化输出（原文，仅调整缩进）：
	```json
{
  "tables": [
    "core"
  ],
  "join_keys": [],
  "column_mapping": [
    {
      "phrase": "their ID",
      "targets": [
        "core.content_key"
      ]
    },
    {
      "phrase": "the name",
      "targets": [
        "core.content_title"
      ]
    },
    {
      "phrase": "main types",
      "targets": [
        "core.genreclass -> 'Primary_Genre'"
      ]
    },
    {
      "phrase": "what they fall under",
      "targets": [
        "core.genreclass -> 'Primary_Genre'"
      ]
    }
  ],
  "unresolved_mappings": []
}
	```
	**四维变化：** 新增四组映射，unresolved_mappings=\[\]。
	**校验与实际处理：** 接受，S2 / rev2。本轮不是旧实验中的 canonical_name 误选。
	<details>
	<summary><span color="red">实际保留的四维内容</span></summary>
		```json
{
  "column_mapping": [
    {
      "phrase": "main types",
      "targets": [
        "core.genreclass -> 'Primary_Genre'"
      ]
    },
    {
      "phrase": "the name",
      "targets": [
        "core.content_title"
      ]
    },
    {
      "phrase": "their ID",
      "targets": [
        "core.content_key"
      ]
    },
    {
      "phrase": "what they fall under",
      "targets": [
        "core.genreclass -> 'Primary_Genre'"
      ]
    }
  ],
  "domain_knowledge": null,
  "join_keys": [],
  "tables": [
    "core"
  ]
}
		```
		证据：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:42`；完整输入 `baseline/framework_analysis_20260914/hulushows_12_02_mapping_input.json:1`；System Prompt `baseline/framework_analysis_20260914/prompt_mapping_a1bad3f28e.txt:1`。
	</details>
	#### 3. 知识选择：没有保留业务定义
	已提供知识目录，模型返回 selected_knowledge_ids=\[\]。
	本轮输入字段：`current_state`、`knowledge_definitions`、`query`、`relevant_column_meanings`、`unresolved_mappings`。
	模型的结构化输出（原文，仅调整缩进）：
	```json
{
  "column_mapping": [
    {
      "phrase": "main types",
      "targets": [
        "core.genreclass -> 'Primary_Genre'"
      ]
    },
    {
      "phrase": "the name",
      "targets": [
        "core.content_title"
      ]
    },
    {
      "phrase": "their ID",
      "targets": [
        "core.content_key"
      ]
    },
    {
      "phrase": "what they fall under",
      "targets": [
        "core.genreclass -> 'Primary_Genre'"
      ]
    }
  ],
  "selected_knowledge_ids": []
}
	```
	**四维变化：** domain_knowledge 从 null 变为 \[\]；字段对应保持不变。
	**校验与实际处理：** 接受，S3 / rev3。字段说明中的枚举没有因此成为四维状态的一部分。
	<details>
	<summary><span color="red">实际保留的四维内容</span></summary>
		```json
{
  "column_mapping": [
    {
      "phrase": "main types",
      "targets": [
        "core.genreclass -> 'Primary_Genre'"
      ]
    },
    {
      "phrase": "the name",
      "targets": [
        "core.content_title"
      ]
    },
    {
      "phrase": "their ID",
      "targets": [
        "core.content_key"
      ]
    },
    {
      "phrase": "what they fall under",
      "targets": [
        "core.genreclass -> 'Primary_Genre'"
      ]
    }
  ],
  "domain_knowledge": [],
  "join_keys": [],
  "tables": [
    "core"
  ]
}
		```
		证据：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:85`；完整输入 `baseline/framework_analysis_20260914/hulushows_12_03_knowledge_input.json:1`；System Prompt `baseline/framework_analysis_20260914/prompt_knowledge_02a8adcb72.txt:1`。
	</details>
	#### 4. Check：尚未落实类别取值，却判断完成
	Check 返回 complete、missing_information=null、next_tool=null，没有申请补查或用户澄清。
	本轮输入字段：`answered_clarifications`、`check_context`、`current_state`、`previous_official_calls`、`query`、`unresolved_mappings`。
	模型的结构化输出（原文，仅调整缩进）：
	```json
{
  "status": "complete",
  "clarification_route": "none",
  "missing_information": null,
  "next_tool": null,
  "column_mapping": [
    {
      "phrase": "main types",
      "targets": [
        "core.genreclass -> 'Primary_Genre'"
      ]
    },
    {
      "phrase": "the name",
      "targets": [
        "core.content_title"
      ]
    },
    {
      "phrase": "their ID",
      "targets": [
        "core.content_key"
      ]
    },
    {
      "phrase": "what they fall under",
      "targets": [
        "core.genreclass -> 'Primary_Genre'"
      ]
    }
  ],
  "domain_knowledge": []
}
	```
	**四维变化：** 四维不变，仍为 S3；没有新增类别取值证据。
	**校验与实际处理：** 检查流程通过，但通过不代表 Animated 已有证据支持。
	<details>
	<summary><span color="red">实际保留的四维内容</span></summary>
		```json
{
  "column_mapping": [
    {
      "phrase": "main types",
      "targets": [
        "core.genreclass -> 'Primary_Genre'"
      ]
    },
    {
      "phrase": "the name",
      "targets": [
        "core.content_title"
      ]
    },
    {
      "phrase": "their ID",
      "targets": [
        "core.content_key"
      ]
    },
    {
      "phrase": "what they fall under",
      "targets": [
        "core.genreclass -> 'Primary_Genre'"
      ]
    }
  ],
  "domain_knowledge": [],
  "join_keys": [],
  "tables": [
    "core"
  ]
}
		```
		证据：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:695`；完整输入 `baseline/framework_analysis_20260914/hulushows_12_04_check_input.json:1`；System Prompt `baseline/framework_analysis_20260914/prompt_check_d70eedd578.txt:1`。
	</details>
	#### 5. Gate：不重做，进入正常 Main
	Gate 认为表、字段均有效，没有新证据要求重做。其理由把类别值归为澄清层参数，但本次没有已回答澄清。
	本轮输入字段：`current_state`、`final_gate_context`、`query`。
	模型的结构化输出（原文，仅调整缩进）：
	```json
{
  "decision": "NO_REGROUND",
  "reason": "Final check is complete with no missing information. All mapped concepts (Primary_Genre, content_title, content_key) are confirmed valid against the schema in the core table. No new evidence or clarification invalidates the current tables, join_keys, or column_mapping. The query's filter values (drama, comedy, animated) are literal parameters that belong to a clarification overlay and do not trigger re-Grounding."
}
	```
	**四维变化：** 四维仍为 S3，没有草稿。
	**校验与实际处理：** NO_REGROUND，且 Check 已完成，因此进入 Main。
	<details>
	<summary><span color="red">实际保留的四维内容</span></summary>
		```json
{
  "column_mapping": [
    {
      "phrase": "main types",
      "targets": [
        "core.genreclass -> 'Primary_Genre'"
      ]
    },
    {
      "phrase": "the name",
      "targets": [
        "core.content_title"
      ]
    },
    {
      "phrase": "their ID",
      "targets": [
        "core.content_key"
      ]
    },
    {
      "phrase": "what they fall under",
      "targets": [
        "core.genreclass -> 'Primary_Genre'"
      ]
    }
  ],
  "domain_knowledge": [],
  "join_keys": [],
  "tables": [
    "core"
  ]
}
		```
		证据：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:751`；完整输入 `baseline/framework_analysis_20260914/hulushows_12_05_final_gate_input.json:1`；System Prompt `baseline/framework_analysis_20260914/prompt_final_gate_bbd960f1a1.txt:1`。
	</details>
	#### 6. Main 实际收到的信息
	```plain text
[VALIBRA SQL WRITER CONTEXT BEGIN]
Phase: 1
Original Query: List the shows with one of the main types like drama, comedy or animated stuff. Give me their ID, the name, and show what they fall under. Alphabetize them.
Follow-up: none
Final Grounding State and answered Clarifications:
[VALIBRA DATABASE GROUNDING]

Tables:
- "core"

Relations:
- []

Column mappings:
- {"phrase":"main types","targets":["core.genreclass -> 'Primary_Genre'"]}
- {"phrase":"the name","targets":["core.content_title"]}
- {"phrase":"their ID","targets":["core.content_key"]}
- {"phrase":"what they fall under","targets":["core.genreclass -> 'Primary_Genre'"]}

Domain knowledge:
- []
[MAIN EXECUTION ENVELOPE]
{"action_intent":"RESULT_QUERY","decimal_places":null,"order_sensitive":true,"response_type":"table","task_category":"Query"}
Authority limits: response_type fixes only result shape; decimal_places fixes only displayed precision; order_sensitive only says row order affects evaluation and does not supply a direction, sort key, aggregation, projection, or business rule; task_category does not override the Query's requested action. action_intent is derived only from explicit Query wording. When it is not RESULT_QUERY, the final SQL must implement that SQL action; an ordinary SELECT is not an equivalent substitute. RESULT_QUERY does not authorize inventing a management action. No object name, function signature, or hidden action detail is supplied beyond what the Query states.
[SQL-SAFE CANONICAL REFERENCES]
{"omitted":0,"references":[{"kind":"target","reference":"core.content_key","sql":"\"core\".\"content_key\""},{"kind":"target","reference":"core.content_title","sql":"\"core\".\"content_title\""},{"kind":"target","reference":"core.genreclass -> 'Primary_Genre'","sql":"\"core\".\"genreclass\" -> 'Primary_Genre'"},{"kind":"table","reference":"core","sql":"\"core\""}],"version":"sql-safe-identifier-overlay/v1"}
Authority limits: these are quoting-safe renderings of existing validated State references only; they add no table, column, JSON key, formula, predicate, aggregation, ordering, or output rule.
Remaining Bird-Coin: 17
[VALIBRA SQL WRITER CONTEXT END]
	```
	Main 只能执行和提交 SQL。上面的实际输入包含 Primary_Genre 字段，却没有 Animation and Cartoons 的枚举说明，也没有用户澄清。Mapping 曾看到枚举，不等于 Main 收到了枚举。
	<details>
	<summary>本次 Main 的完整 System Prompt</summary>
		```plain text
Grounding 已完成，数据库语义结果视为本 phase 的最终结果。
你的任务是根据 Original Query、可选 Follow-up、Final Grounding State 和已回答澄清写 PostgreSQL SQL。

Final Grounding State 和已回答澄清是语义权威。不要重新研究 schema、column meaning 或 business semantics；
不要自行替换、删除或重新解释其中的字段、阈值、公式、过滤条件或业务概念，也不要根据 execute_sql 结果发明新的语义条件。
State.tables 是允许使用的候选表范围，不代表每张表都必须出现在最终 SQL。

生成第一条 SQL 前，先从 Query / Follow-up、Final Grounding State 和已回答澄清固定本 phase 的 Answer Contract：
结果的 entity / aggregation grain、只输出用户要求的列、明确要求的 aggregation / grouping / ordering / rounding、
predicate 的方向 / 运算符 / 边界，以及公式的精确 operands 与 NULL 语义。后续 candidate 必须保持这份合同；
无诊断的 submit_sql FAIL 不能授权改变它。NULL 处理属于公式语义，除非合同明确允许，否则不要用 COALESCE 等改写公式。

必须在 SQL 中完整落实 column_mapping 和 domain_knowledge 已给出的公式、阈值、过滤条件、多字段共同计算及聚合语义。
当一个 mapping 的多个 targets 共同参与同一计算或判断时，必须共同使用；需要按实体或分组键聚合时，先正确聚合，再排序或比较。

每次 execute_sql 的 SQL 都必须是可以直接 submit 的完整 task-answer candidate；不得执行诊断查询、数据探针或局部片段。
execute_sql 只用于验证和修正 JOIN、JSON path、CAST、NULL、aggregation、GROUP BY、ORDER BY、latest-row 等 SQL 实现问题，
不能用于新的语义探索。不要重复执行相同 SQL 或语义等价的无效查询；返回 0 rows 不能成为更换冻结阈值或业务规则的理由。
当 SQL 已与冻结 State 一致、成功 execute 且没有新的实现问题时，应立即 submit_sql，不要为了再次确认而继续 execute_sql。
剩余预算有限时，应提交当前最佳且与 State 一致的 SQL，而不是继续探索。

submit_sql 失败后的收口合同：
如果已提交的 candidate SQL 曾成功 execute，而 Official submit 只返回没有具体诊断的 FAIL，该 FAIL 只表示本次提交未通过；
它不是 Frozen State、已回答澄清、冻结阈值、业务规则或字段语义错误的证据，先前成功 execute 的结果仍是有效的 SQL 实现证据。
此时只能根据 Query / Follow-up、Frozen State、已回答澄清和已有 execute / submit history 重新审查已提交 SQL。
禁止重新查询 schema、DISTINCT values、枚举 JSON keys、row/data sampling、验证 frozen literals，或寻找新的业务规则和字段含义。
只有能够指出具体的 SQL implementation hypothesis 时，才可形成 materially different 且与 State 一致的新 candidate；
允许的假设仅限 JOIN、aggregation grain、projection / result shape、CAST / NULL、GROUP BY / ORDER BY、latest-row handling 等实现问题。
一次只修正一个能够明确指出的 Answer Contract / implementation mismatch；下一次 execute 仍必须是完整答案 SQL，不能先发探针。
不得执行只是为了“看看数据”的 SQL，也不得重复执行相同或语义等价的 candidate。
若形成了有具体实现理由的新 candidate，只做必要的 implementation validation，然后尽快 submit_sql。
若找不到具体 implementation mismatch，不要返回数据库探索；保持冻结语义，不发明新字段、条件、阈值、公式或业务规则。

不要查询 information_schema / pg_catalog；不要 SELECT *；不要提出新问题；最终用 submit_sql 提交。

[VALIBRA SQL WRITER CONTEXT BEGIN]
Phase: 1
Original Query: List the shows with one of the main types like drama, comedy or animated stuff. Give me their ID, the name, and show what they fall under. Alphabetize them.
Follow-up: none
Final Grounding State and answered Clarifications:
[VALIBRA DATABASE GROUNDING]

Tables:
- "core"

Relations:
- []

Column mappings:
- {"phrase":"main types","targets":["core.genreclass -> 'Primary_Genre'"]}
- {"phrase":"the name","targets":["core.content_title"]}
- {"phrase":"their ID","targets":["core.content_key"]}
- {"phrase":"what they fall under","targets":["core.genreclass -> 'Primary_Genre'"]}

Domain knowledge:
- []
[MAIN EXECUTION ENVELOPE]
{"action_intent":"RESULT_QUERY","decimal_places":null,"order_sensitive":true,"response_type":"table","task_category":"Query"}
Authority limits: response_type fixes only result shape; decimal_places fixes only displayed precision; order_sensitive only says row order affects evaluation and does not supply a direction, sort key, aggregation, projection, or business rule; task_category does not override the Query's requested action. action_intent is derived only from explicit Query wording. When it is not RESULT_QUERY, the final SQL must implement that SQL action; an ordinary SELECT is not an equivalent substitute. RESULT_QUERY does not authorize inventing a management action. No object name, function signature, or hidden action detail is supplied beyond what the Query states.
[SQL-SAFE CANONICAL REFERENCES]
{"omitted":0,"references":[{"kind":"target","reference":"core.content_key","sql":"\"core\".\"content_key\""},{"kind":"target","reference":"core.content_title","sql":"\"core\".\"content_title\""},{"kind":"target","reference":"core.genreclass -> 'Primary_Genre'","sql":"\"core\".\"genreclass\" -> 'Primary_Genre'"},{"kind":"table","reference":"core","sql":"\"core\""}],"version":"sql-safe-identifier-overlay/v1"}
Authority limits: these are quoting-safe renderings of existing validated State references only; they add no table, column, JSON key, formula, predicate, aggregation, ordering, or output rule.
Remaining Bird-Coin: 17
[VALIBRA SQL WRITER CONTEXT END]
		```
	</details>
	来源：`baseline/framework_analysis_20260914/hulushows_12_当前_agent_04_request.json:1`。
	#### 7. 实际工具与预算流水
	此表按真实工具顺序列出。预算仅反映 Bird-Coin，不等同于模型 token 费用。
	<table fit-page-width="true" header-row="true">
<tr>
<td>序号 / 阶段</td>
<td>工具</td>
<td>主要内容</td>
<td>余额变化</td>
</tr>
<tr>
<td>1 / P1</td>
<td>`get_schema`</td>
<td>按工具取得官方资料</td>
<td>20 → 19</td>
</tr>
<tr>
<td>2 / P1</td>
<td>`get_all_column_meanings`</td>
<td>按工具取得官方资料</td>
<td>19 → 18</td>
</tr>
<tr>
<td>3 / P1</td>
<td>`get_all_knowledge_definitions`</td>
<td>按工具取得官方资料</td>
<td>18 → 17</td>
</tr>
<tr>
<td>4 / P1</td>
<td>`execute_sql`</td>
<td>完整 SQL 见下方候选记录</td>
<td>17 → 16</td>
</tr>
<tr>
<td>5 / P1</td>
<td>`execute_sql`</td>
<td>完整 SQL 见下方候选记录</td>
<td>16 → 15</td>
</tr>
<tr>
<td>6 / P1</td>
<td>`submit_sql`</td>
<td>SQL failed Phase 1. Your SQL is not correct.</td>
<td>15 → 12</td>
</tr>
<tr>
<td>7 / P1</td>
<td>`execute_sql`</td>
<td>完整 SQL 见下方候选记录</td>
<td>12 → 11</td>
</tr>
<tr>
<td>8 / P1</td>
<td>`execute_sql`</td>
<td>完整 SQL 见下方候选记录</td>
<td>11 → 10</td>
</tr>
<tr>
<td>9 / P1</td>
<td>`submit_sql`</td>
<td>SQL failed Phase 1. Your SQL is not correct.</td>
<td>10 → 7</td>
</tr>
<tr>
<td>10 / P1</td>
<td>`execute_sql`</td>
<td>完整 SQL 见下方候选记录</td>
<td>7 → 6</td>
</tr>
<tr>
<td>11 / P1</td>
<td>`execute_sql`</td>
<td>完整 SQL 见下方候选记录</td>
<td>6 → 5</td>
</tr>
<tr>
<td>12 / P1</td>
<td>`execute_sql`</td>
<td>完整 SQL 见下方候选记录</td>
<td>5 → 4</td>
</tr>
<tr>
<td>13 / P1</td>
<td>`execute_sql`</td>
<td>完整 SQL 见下方候选记录</td>
<td>4 → 3</td>
</tr>
<tr>
<td>14 / P1</td>
<td>`execute_sql`</td>
<td>完整 SQL 见下方候选记录</td>
<td>3 → 2</td>
</tr>
<tr>
<td>15 / P1</td>
<td>`submit_sql`</td>
<td>SQL failed Phase 1. Your SQL is not correct.</td>
<td>2 → -1</td>
</tr>
	</table>
	#### 8. 逐次 SQL、反馈与后续变化
	以下 SQL 来自工具记录，没有补写未执行的候选。执行结果仅节选前 450 字符；提交反馈完整保留。
	<details>
	<summary>当前 工具 #4 / P1 / execute_sql；余额 17 → 16</summary>
		```sql
SELECT "core"."content_key", "core"."content_title", "core"."genreclass" -> 'Primary_Genre' AS primary_genre
FROM "core"
WHERE "core"."genreclass" -> 'Primary_Genre' IN ('Drama', 'Comedy', 'Animated')
ORDER BY "core"."content_title";
		```
		反馈：
		```plain text
SQL Error: SQL error: invalid input syntax for type json
LINE 3: WHERE "core"."genreclass" -> 'Primary_Genre' IN ('Drama', 'C...
                                                         ^
DETAIL:  Token "Drama" is invalid.
CONTEXT:  JSON data, line 1: Drama

		```
		来源：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:983`。
	</details>
	<details>
	<summary>当前 工具 #5 / P1 / execute_sql；余额 16 → 15</summary>
		```sql
SELECT "core"."content_key", "core"."content_title", "core"."genreclass" ->> 'Primary_Genre' AS primary_genre
FROM "core"
WHERE "core"."genreclass" ->> 'Primary_Genre' IN ('Drama', 'Comedy', 'Animated')
ORDER BY "core"."content_title";
		```
		反馈：
		```plain text
content_key | content_title | primary_genre ------------------------------------------- 936702 | American Dad! | Comedy 53 | American Dad! | Comedy 863650 | American Dad! | Comedy 154477 | Arrested Development | Comedy 189954 | Arrested Development | Comedy 117953 | Arrested Development | Comedy 833436 | Arrested Development | Comedy 103439 | Arrested Development | Comedy 572877 | Arrested Development | Comedy 51 | Arrested Development | Comedy 9
		```
		来源：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:1002`。
	</details>
	<details>
	<summary>当前 工具 #6 / P1 / submit_sql；余额 15 → 12</summary>
		```sql
SELECT "core"."content_key", "core"."content_title", "core"."genreclass" ->> 'Primary_Genre' AS primary_genre
FROM "core"
WHERE "core"."genreclass" ->> 'Primary_Genre' IN ('Drama', 'Comedy', 'Animated')
ORDER BY "core"."content_title";
		```
		反馈：
		```plain text
SQL failed Phase 1. Your SQL is not correct.
Budget remaining: 12.0 bird-coins
		```
		来源：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:1021`。
	</details>
	<details>
	<summary>当前 工具 #7 / P1 / execute_sql；余额 12 → 11</summary>
		```sql
SELECT "core"."content_key", "core"."content_title", "core"."genreclass" -> 'Primary_Genre' AS "Primary_Genre"
FROM "core"
WHERE "core"."genreclass" ->> 'Primary_Genre' IN ('drama', 'comedy', 'animated')
ORDER BY "core"."content_title"
		```
		反馈：
		```plain text
Query executed, empty result set.
		```
		来源：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:1040`。
	</details>
	<details>
	<summary>当前 工具 #8 / P1 / execute_sql；余额 11 → 10</summary>
		```sql
SELECT "core"."content_key", "core"."content_title", "core"."genreclass" -> 'Primary_Genre' AS "Primary_Genre"
FROM "core"
WHERE "core"."genreclass" ->> 'Primary_Genre' IN ('Drama', 'Comedy', 'Animated')
ORDER BY "core"."content_title"
		```
		反馈：
		```plain text
content_key | content_title | Primary_Genre ------------------------------------------- 936702 | American Dad! | Comedy 53 | American Dad! | Comedy 863650 | American Dad! | Comedy 154477 | Arrested Development | Comedy 189954 | Arrested Development | Comedy 117953 | Arrested Development | Comedy 833436 | Arrested Development | Comedy 103439 | Arrested Development | Comedy 572877 | Arrested Development | Comedy 51 | Arrested Development | Comedy 9
		```
		来源：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:1059`。
	</details>
	<details>
	<summary>当前 工具 #9 / P1 / submit_sql；余额 10 → 7</summary>
		```sql
SELECT "core"."content_key", "core"."content_title", "core"."genreclass" -> 'Primary_Genre' AS "Primary_Genre"
FROM "core"
WHERE "core"."genreclass" ->> 'Primary_Genre' IN ('Drama', 'Comedy', 'Animated')
ORDER BY "core"."content_title"
		```
		反馈：
		```plain text
SQL failed Phase 1. Your SQL is not correct.
Budget remaining: 7.0 bird-coins
		```
		来源：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:1078`。
	</details>
	<details>
	<summary>当前 工具 #10 / P1 / execute_sql；余额 7 → 6</summary>
		```sql
SELECT "core"."content_key", "core"."content_title", "core"."genreclass" -> 'Primary_Genre' AS "Primary_Genre"
FROM "core"
WHERE "core"."genreclass" ->> 'Primary_Genre' IN ('Drama', 'Comedy', 'Animation')
ORDER BY "core"."content_title"
		```
		反馈：
		```plain text
content_key | content_title | Primary_Genre ------------------------------------------- 936702 | American Dad! | Comedy 53 | American Dad! | Comedy 863650 | American Dad! | Comedy 154477 | Arrested Development | Comedy 189954 | Arrested Development | Comedy 117953 | Arrested Development | Comedy 833436 | Arrested Development | Comedy 103439 | Arrested Development | Comedy 572877 | Arrested Development | Comedy 51 | Arrested Development | Comedy 9
		```
		来源：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:1097`。
	</details>
	<details>
	<summary>当前 工具 #11 / P1 / execute_sql；余额 6 → 5</summary>
		```sql
SELECT "core"."content_key", "core"."content_title", "core"."genreclass" ->> 'Primary_Genre'
FROM "core"
WHERE "core"."genreclass" ->> 'Primary_Genre' IN ('Drama', 'Comedy', 'Animated')
ORDER BY "core"."content_title"
		```
		反馈：
		```plain text
content_key | content_title | ?column? -------------------------------------- 936702 | American Dad! | Comedy 53 | American Dad! | Comedy 863650 | American Dad! | Comedy 154477 | Arrested Development | Comedy 189954 | Arrested Development | Comedy 117953 | Arrested Development | Comedy 833436 | Arrested Development | Comedy 103439 | Arrested Development | Comedy 572877 | Arrested Development | Comedy 51 | Arrested Development | Comedy 912972 | Ar
		```
		来源：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:1116`。
	</details>
	<details>
	<summary>当前 工具 #12 / P1 / execute_sql；余额 5 → 4</summary>
		```sql
SELECT DISTINCT "core"."content_key", "core"."content_title", "core"."genreclass" ->> 'Primary_Genre' AS "Primary_Genre"
FROM "core"
WHERE "core"."genreclass" ->> 'Primary_Genre' IN ('Drama', 'Comedy', 'Animated')
ORDER BY "core"."content_title"
		```
		反馈：
		```plain text
content_key | content_title | Primary_Genre ------------------------------------------- 53 | American Dad! | Comedy 863650 | American Dad! | Comedy 936702 | American Dad! | Comedy 51 | Arrested Development | Comedy 103439 | Arrested Development | Comedy 117953 | Arrested Development | Comedy 154477 | Arrested Development | Comedy 189954 | Arrested Development | Comedy 299270 | Arrested Development | Comedy 572877 | Arrested Development | Comedy 8
		```
		来源：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:1135`。
	</details>
	<details>
	<summary>当前 工具 #13 / P1 / execute_sql；余额 4 → 3</summary>
		```sql
SELECT "core"."content_key", "core"."content_title", "core"."genreclass" -> 'Primary_Genre'
FROM "core"
WHERE "core"."genreclass" ->> 'Primary_Genre' IN ('Drama', 'Comedy', 'Animated')
ORDER BY "core"."content_title", "core"."content_key"
		```
		反馈：
		```plain text
content_key | content_title | ?column? -------------------------------------- 53 | American Dad! | Comedy 863650 | American Dad! | Comedy 936702 | American Dad! | Comedy 51 | Arrested Development | Comedy 103439 | Arrested Development | Comedy 117953 | Arrested Development | Comedy 154477 | Arrested Development | Comedy 189954 | Arrested Development | Comedy 299270 | Arrested Development | Comedy 572877 | Arrested Development | Comedy 833436 | Ar
		```
		来源：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:1154`。
	</details>
	<details>
	<summary>当前 工具 #14 / P1 / execute_sql；余额 3 → 2</summary>
		```sql
SELECT "core"."content_key", "core"."content_title", "core"."genreclass" -> 'Primary_Genre' AS "Primary_Genre"
FROM "core"
WHERE "core"."genreclass" ->> 'Primary_Genre' IN ('Drama', 'Comedy', 'Animated')
ORDER BY "core"."content_title" ASC, "core"."content_key" ASC
		```
		反馈：
		```plain text
content_key | content_title | Primary_Genre ------------------------------------------- 53 | American Dad! | Comedy 863650 | American Dad! | Comedy 936702 | American Dad! | Comedy 51 | Arrested Development | Comedy 103439 | Arrested Development | Comedy 117953 | Arrested Development | Comedy 154477 | Arrested Development | Comedy 189954 | Arrested Development | Comedy 299270 | Arrested Development | Comedy 572877 | Arrested Development | Comedy 8
		```
		来源：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:1173`。
	</details>
	<details>
	<summary>当前 工具 #15 / P1 / submit_sql；余额 2 → -1</summary>
		```sql
SELECT "core"."content_key", "core"."content_title", "core"."genreclass" -> 'Primary_Genre'
FROM "core"
WHERE "core"."genreclass" ->> 'Primary_Genre' IN ('Drama', 'Comedy', 'Animated')
ORDER BY "core"."content_title"
		```
		反馈：
		```plain text
SQL failed Phase 1. Your SQL is not correct.
Budget remaining: -1 bird-coins
		```
		来源：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:1192`。
	</details>
	第一次 SQL 用 JSON 运算符 `->` 直接与文本比较，报类型错误。改为 `->>` 后可执行，但类别仍写成 Animated，首次提交失败。后续尝试小写、Animation、DISTINCT、投影和排序调整，最终第三次提交仍使用 Animated，P1 未通过。
	这不是“完全没有信息”：名称、ID 和类别字段已经正确保存。缺口在于用户短语与真实类别取值未落实，Check 却完成；Main 又没有收到先前字段说明中的枚举。P1 未通过，未进入 P2；余额不足，没有启动补救。
	#### 9. 同题基线与结论
	基线通过 DISTINCT 查询得到实际枚举，并读取 Genre Hierarchy Format 与 Animation Families。其 P1 使用 Animation and Cartoons，首次提交通过，P2 也通过。当前不是名称字段回归，而是类别条件证据在交接时缺失。animated stuff 是否包括 Anime 仍有歧义，不能把基线命中参考答案等同于唯一语义证明。
	<details>
	<summary>基线 工具 #8 / P1 / submit_sql（历史基线对照）</summary>
		```sql
SELECT content_key, content_title, genreclass->>'Primary_Genre' AS primary_genre
FROM core
WHERE genreclass->>'Primary_Genre' IN ('Drama', 'Comedy', 'Animation and Cartoons')
ORDER BY content_title;
		```
		```plain text
Phase 1 correct! (Reward: 0.7). Moving to Phase 2.
Reward: 0.7
Follow-up question: Instead of showing the genre, show the company name that made it.
Budget remaining: 11.5 bird-coins
		```
		来源：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:1377`。
	</details>
	<details>
	<summary>基线 工具 #9 / P2 / submit_sql（历史基线对照）</summary>
		```sql
SELECT c.content_key, c.content_title, co.company_name
FROM core c
JOIN companies co ON c.studiolink = co.entity_key
WHERE c.genreclass->>'Primary_Genre' IN ('Drama', 'Comedy', 'Animation and Cartoons')
ORDER BY c.content_title;
		```
		```plain text
Phase 2 correct! (Reward: 0.3). Task finished.
Reward: 0.3
Budget remaining: 8.5 bird-coins
		```
		来源：`baseline/framework_analysis_20260914/hulushows_12_evidence.md:1396`。
	</details>
	<details>
	<summary>复核索引：每次 Provider 请求、Prompt 与完整输入</summary>
		- `01_sql-grounding-20260908T011817271654Z-3097a4e1012f-ceb12637.json: structure`
			- /home/user/code/BIRD-Interact/BIRD-Interact-ADK-agent-research/research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/42_hulushows_12/provider_audits/01_sql-grounding-20260908T011817271654Z-3097a4e1012f-ceb12637.json:1；Prompt SHA256：04fe3f57e52e09c4ad41e059afd8a211f9808f54f7cfca15e67524594b0f61e1
			- 输入：`baseline/framework_analysis_20260914/hulushows_12_01_structure_input.json:1`
			- Prompt：`baseline/framework_analysis_20260914/prompt_structure_04fe3f57e5.txt:1`
		- `02_sql-grounding-20260908T011821906747Z-ee753358f5db-9675a362.json: mapping`
			- /home/user/code/BIRD-Interact/BIRD-Interact-ADK-agent-research/research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/42_hulushows_12/provider_audits/02_sql-grounding-20260908T011821906747Z-ee753358f5db-9675a362.json:1；Prompt SHA256：a1bad3f28e8328fefea85c87b7092c0069649a0f4d73f2ad7a3135a0d37ac60b
			- 输入：`baseline/framework_analysis_20260914/hulushows_12_02_mapping_input.json:1`
			- Prompt：`baseline/framework_analysis_20260914/prompt_mapping_a1bad3f28e.txt:1`
		- `03_sql-grounding-20260908T011845888665Z-87852f5a1b08-5d40a0b3.json: knowledge`
			- /home/user/code/BIRD-Interact/BIRD-Interact-ADK-agent-research/research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/42_hulushows_12/provider_audits/03_sql-grounding-20260908T011845888665Z-87852f5a1b08-5d40a0b3.json:1；Prompt SHA256：02a8adcb72c1dcb1ee817c3ca1dc0bb6be5d2dd6521b1ea67a0f8a6dd986cfa7
			- 输入：`baseline/framework_analysis_20260914/hulushows_12_03_knowledge_input.json:1`
			- Prompt：`baseline/framework_analysis_20260914/prompt_knowledge_02a8adcb72.txt:1`
		- `04_sql-grounding-20260908T011850156480Z-09be065a6a5f-a2b20acb.json: check`
			- /home/user/code/BIRD-Interact/BIRD-Interact-ADK-agent-research/research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/42_hulushows_12/provider_audits/04_sql-grounding-20260908T011850156480Z-09be065a6a5f-a2b20acb.json:1；Prompt SHA256：d70eedd5785774cec00fa681e8c76f862a41fb5755d3a2af10c5634f29892d44
			- 输入：`baseline/framework_analysis_20260914/hulushows_12_04_check_input.json:1`
			- Prompt：`baseline/framework_analysis_20260914/prompt_check_d70eedd578.txt:1`
		- `05_sql-grounding-20260908T011913061479Z-f4e5856df3a6-f50efc9d.json: final_gate`
			- /home/user/code/BIRD-Interact/BIRD-Interact-ADK-agent-research/research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/tasks/42_hulushows_12/provider_audits/05_sql-grounding-20260908T011913061479Z-f4e5856df3a6-f50efc9d.json:1；Prompt SHA256：bbd960f1a14fb13746f7bd50a703dc9b874b411c7aa3cfc404fe6ba2a9960cda
			- 输入：`baseline/framework_analysis_20260914/hulushows_12_05_final_gate_input.json:1`
			- Prompt：`baseline/framework_analysis_20260914/prompt_final_gate_bbd960f1a1.txt:1`
	</details>
	本节展示每次模型的完整结构化输出、状态快照与关键执行输入；大段 schema、字段目录和知识目录不重复展开，完整原文保留在上述本地输入文件中。
	### 4. 案例小结
	cybermarket_pattern_10 展示本次 Full600 中正常主流程的完整成功链路：公式取证、字段重做、草稿提交及 P1/P2 通过，均未依靠补救。它与下述两题分别对应“主流程成功”“主流程失败后补救成功”和“最终失败”，但不构成三种路径成功率的统计比较。
	solar7 说明，澄清保留和草稿隔离正常工作后，补救仍能继续完成任务；hulu12 则说明，前序已取得的信息可能在交接时丢失，Check 也未必能识别这一缺口。两题均不适合将最终成败单独归于 Main。
	历史阶段级实验还跑通过 solar7 P2 的完整修订流程：取得新公式、重做 Mapping、保留旧知识并追加新知识、Check 通过、统一提交；cybermarket_10 也有同类结果。这些实验支持相关机制保留，但属于从历史输入起跑的局部真实模型测试，应与本次 Full600 结果分别记录。\[E04\]
</details>
## 三、600 题成绩与成本
<file src="https://app.notion.com/p/3e3c6fba6efe80828c18d9b4ca6961e9#3e3c6fba6efe806d8e23ead248baff6c">glm52_full600_baseline_score_table.xlsx</file>
<file src="https://app.notion.com/p/3e3c6fba6efe80828c18d9b4ca6961e9#3e3c6fba6efe8006b4ead03fbbafbb27">current_candidate_full600_baseline_format.xlsx</file>
### 1. 比较范围
本报告比较项目归档的<span color="red"> GLM-5.2 Full600</span> 基线与当前结果。两侧为相同的 600 题、22 个数据库领域，数据文件 SHA 一致，采用<span color="red"> a-interact / stress</span>；用户模拟器为 `Claude Haiku 4.5`，使用 <span color="red">v2 提示词</span>。\[D01\]
### 2. 总体成绩
<table fit-page-width="true" header-row="true">
<tr>
<td>指标</td>
<td>基线</td>
<td>当前</td>
<td>变化</td>
</tr>
<tr>
<td>P1 通过</td>
<td>144 / 600，24.00%</td>
<td>150 / 600，25.00%</td>
<td>+6 题，+1.00 个百分点</td>
</tr>
<tr>
<td>P1、P2 全通过</td>
<td>79 / 600，13.17%</td>
<td>75 / 600，12.50%</td>
<td>−4 题，−0.67 个百分点</td>
</tr>
<tr>
<td>仅 P1 通过</td>
<td>65</td>
<td>75</td>
<td>+10</td>
</tr>
<tr>
<td>两阶段均未通过</td>
<td>456</td>
<td>450</td>
<td>−6</td>
</tr>
<tr>
<td>总 Reward</td>
<td>124.5</td>
<td>127.5</td>
<td>+3.0，约 +2.41%</td>
</tr>
<tr>
<td>P1 通过后最终完成 P2</td>
<td>79 / 144，54.86%</td>
<td>75 / 150，50.00%</td>
<td>下降</td>
</tr>
</table>
a-interact 的 P1 权重为 0.7，P2 为 0.3，故 Reward = 0.7 × P1通过题数 + 0.3 × 全通过题数。\[C14\]
当前系统的 P1 和加权总分略有提高，但完整任务通过数下降，尚未体现全面改善。\[D02\]
### 3. 新增能力与原有能力的损失
<table fit-page-width="true" header-row="true">
<colgroup>
<col width="154">
<col width="180">
<col width="215">
<col width="153">
</colgroup>
<tr>
<td>基线结果 → 当前结果</td>
<td>Valibra未通过</td>
<td>Valibra仅 P1 通过</td>
<td>Valibra全通过</td>
</tr>
<tr>
<td>基线未通过</td>
<td>416</td>
<td><span color="red">23</span></td>
<td>17</td>
</tr>
<tr>
<td>基线仅 P1 通过</td>
<td><span color="red">19</span></td>
<td>39</td>
<td>7</td>
</tr>
<tr>
<td>基线全通过</td>
<td>15</td>
<td>13</td>
<td>51</td>
</tr>
</table>
代表性改善包括 solar_panel_7、crypto_exchange_1、crypto_exchange_M_3 从 FAIL 到 Full，以及 cybermarket_pattern_M_9 从仅 P1 到 Full。退化包括 solar_panel_1、hulushows_5、hulushows_12 从 Full 到 FAIL，以及 solar_panel_12 从 Full 到仅 P1。
按领域，Reward 增加较多的是 crypto_exchange（+1.8），cross_border、reverse_logistics、museum_artifact（各 +1.4）；减少较多的是 exchange_traded_funds（−2.4）、labor_certification_applications（−1.7）、virtual_idol（−1.4）和 hulushows（−1.3）。Excel 附件列出全部 94 道变化题和 22 个领域。上述分布不直接说明各题具有共同原因。\[D02\]
### 4. 主流程与补救的贡献
<table fit-page-width="true" header-row="true">
<tr>
<td>当前系统的内部结果</td>
<td>数量</td>
</tr>
<tr>
<td>P1 Grounding 检查通过，并实际产生 Main 请求</td>
<td>256 / 600</td>
</tr>
<tr>
<td>主流程 P1 最终通过</td>
<td><span color="red">84</span></td>
</tr>
<tr>
<td>主流程 P2 实际产生 Main 请求</td>
<td>62</td>
</tr>
<tr>
<td>主流程两阶段全通过</td>
<td>42</td>
</tr>
<tr>
<td>补救额外取得的 P1 通过</td>
<td><span color="red">66</span></td>
</tr>
<tr>
<td>补救额外取得的全通过</td>
<td>33</td>
</tr>
</table>
最终 P1 通过数为 84 + 66 = 150，全通过数为 42 + 33 = 75。两项成功中均有 44% 由补救取得，表明当前系统仍较依赖原 Agent 的补救能力。\[D02\]
进入 Main 不代表交接信息一定完整。本次未逐题人工核定 600 题的信息质量，因此不报告“有效交接率”。84/256 仅是观察到的主流程 P1 成功率，不能解释为信息充分时 Main 的能力上限。
### 5. Token 用量复核
旧成绩表读取结果中的 combined 字段，该字段只汇总原 Agent 和用户模拟器用量。独立 Grounding 客户端的用量另行记录，未计入旧表。\[C16\]
本次重新归属并去重了 5,884 份 Grounding 审计，覆盖 6,100 次实际尝试。一个任务目录中的 17 份异题副本已排除；另有 7 题运行计数少于审计记录一份，按实际用量计入。20 次尝试未返回 usage，其费用未知。\[D03\]
用量按每次尝试累加。有 18 份审计最终超时、顶层汇总为空，但此前尝试已报告 614,748 token，仍计入下表。\[D03\]
<table fit-page-width="true" header-row="true">
<tr>
<td>用量口径</td>
<td>基线</td>
<td>当前</td>
</tr>
<tr>
<td>旧成绩表：原 Agent + 用户模拟器</td>
<td>82,272,142</td>
<td>55,130,814</td>
</tr>
<tr>
<td>旧表未含的独立 Grounding</td>
<td>0</td>
<td>48,127,666</td>
</tr>
<tr>
<td>补全后已报告总 token</td>
<td>82,272,142</td>
<td>103,258,480</td>
</tr>
<tr>
<td>补全后输入 token</td>
<td>74,548,984</td>
<td>79,026,960</td>
</tr>
<tr>
<td>补全后输出 token，含推理</td>
<td>7,723,158</td>
<td>24,231,520</td>
</tr>
<tr>
<td>其中推理 token，已包含在输出中</td>
<td>6,572,141</td>
<td>22,230,788</td>
</tr>
<tr>
<td>已报告缓存命中输入，已包含在输入中</td>
<td>49,947,520</td>
<td>32,011,264</td>
</tr>
</table>
补计后，总量增加 25.51%，输入增加 6.01%，输出增加 213.75%。推理 token 已计入输出，缓存 token 已计入输入，均不重复相加。
Grounding 共消耗约 4,813 万 token：Check 1,749 万、Knowledge 1,050 万、Mapping 867 万、Gate 611 万、Structure 537 万。原 Agent 的自由探索用量虽有减少，新增整理和复核阶段的消耗更大，尤其体现在推理输出上。
### 6. 研究收获与后续方向
四维信息和草稿管理提高了过程的可追溯性，也解决了知识丢失、修改权限交接等实际问题。不过，这些改进主要作用于流程可靠性，不能保证字段选择和业务条件判断正确。
此前的失败实验明确了部分限制。将 Failed、High 强制转换为 SQL 等号约束，虽通过了工程验证，却分别遗漏了完整 OR 条件和选错目标字段，最终回滚。合法枚举不足以证明完整业务条件。\[E06\] 加强修饰语提示只改善了两个目标中的一个；名称角色提示改善了两个样例，却使正常样例退化；独立语义检查器对四个错误样例全部放行。\[E07\] 继续增加提示词或检查模型，尚无可靠的收益依据。
本轮探索验证了信息整理、权限交接和失败恢复的工程价值，但较小的得分增益尚不足以抵消成本增加和原有能力损失。下一阶段应以降低重复工作、减少信息丢失和保留正常路径为主，暂不扩大状态结构或叠加语义审核机制。
<details>
<summary>实现与证据索引</summary>
	源码路径以下均相对项目根目录：`/home/user/code/BIRD-Interact/BIRD-Interact-ADK-agent-research`。链接定位至实际起始行；同一项列出多个位置时，分别对应提示词、处理逻辑或校验。源码 17/17 与 Full600 冻结清单一致；后续修改文件会改变行号。
	### 代码位置
	<table fit-page-width="true" header-row="true">
<tr>
<td>编号</td>
<td>内容</td>
<td>文件与行</td>
</tr>
<tr>
<td>C01</td>
<td>原 Agent 提示词、九个工具及价格</td>
<td>`system_agent/agent.py:50`；固定前期取证 `valibra_agent/grounding_callbacks.py:274`</td>
</tr>
<tr>
<td>C02</td>
<td>四维数据结构、未解决项、null 与空集合</td>
<td>`valibra_agent/sql_grounding/models.py:325`</td>
</tr>
<tr>
<td>C03</td>
<td>Structure 提示词</td>
<td>`valibra_agent/sql_grounding/updater.py:163`</td>
</tr>
<tr>
<td>C04</td>
<td>Mapping 提示词；请求显式给定的外层运算</td>
<td>`valibra_agent/sql_grounding/updater.py:205`；`valibra_agent/sql_grounding/updater.py:245`</td>
</tr>
<tr>
<td>C05</td>
<td>Knowledge 选规则、有限修正的提示词</td>
<td>`valibra_agent/sql_grounding/updater.py:358`</td>
</tr>
<tr>
<td>C06</td>
<td>Check 完整性判断、补查工具、有限修改权限</td>
<td>`valibra_agent/sql_grounding/updater.py:421`；真实修正校验 `valibra_agent/sql_grounding/service.py:1487`</td>
</tr>
<tr>
<td>C07</td>
<td>Check 重复请求与 6 Coin 门槛；P2 字段说明复用</td>
<td>`valibra_agent/grounding_callbacks.py:5945`；`valibra_agent/grounding_callbacks.py:5752`</td>
</tr>
<tr>
<td>C08</td>
<td>Gate 四路选择、重做范围、重复尝试限制、草稿提交</td>
<td>`valibra_agent/sql_grounding/updater.py:684`；`valibra_agent/grounding_callbacks.py:4371`；`valibra_agent/grounding_callbacks.py:4717`；`valibra_agent/sql_grounding/service.py:323`</td>
</tr>
<tr>
<td>C09</td>
<td>Main 两工具提示词、摘要限长、实际注入、过滤历史</td>
<td>`valibra_agent/grounding_callbacks.py:285`；`valibra_agent/sql_grounding/prompt_view.py:17`；`valibra_agent/grounding_callbacks.py:10046`；`valibra_agent/grounding_callbacks.py:9916`</td>
</tr>
<tr>
<td>C10</td>
<td>草稿内分类提问的校验及“先丢弃、再发问”</td>
<td>`valibra_agent/grounding_callbacks.py:4133`</td>
</tr>
<tr>
<td>C11</td>
<td>P2 保留旧知识、合并、去重</td>
<td>`valibra_agent/sql_grounding/service.py:1027`</td>
</tr>
<tr>
<td>C12</td>
<td>fallback 条件、真实输入、原 Agent 启动</td>
<td>`valibra_agent/fallback/ainteract_fallback.py:72`；`valibra_agent/fallback/ainteract_fallback.py:199`；`valibra_agent/adk_runtime.py:132`</td>
</tr>
<tr>
<td>C13</td>
<td>leaderboard 与研究配置的区别</td>
<td>`valibra_agent/runtime_profile.py:15`；`valibra_agent/grounding_callbacks.py:1739`</td>
</tr>
<tr>
<td>C14</td>
<td>评分、P1/P2 切换、数值预处理与默认评测</td>
<td>`db_environment/server.py:397`；`shared/db_utils.py:274`；`shared/db_utils.py:395`</td>
</tr>
<tr>
<td>C15</td>
<td>benchmark 删除指定知识的真实过滤代码</td>
<td>`db_environment/server.py:273`</td>
</tr>
<tr>
<td>C16</td>
<td>旧结果总 token 漏掉独立 Grounding 的边界</td>
<td>`orchestrator/ainteract.py:165`；原 Agent usage 汇总 `system_agent/callbacks.py:105`；Grounding 独立汇总 `valibra_agent/sql_grounding/updater.py:1340`</td>
</tr>
<tr>
<td>C17</td>
<td>Check 进入 Gate 的条件；草稿回答后必须重新建立草稿</td>
<td>`valibra_agent/grounding_callbacks.py:5363`；`valibra_agent/grounding_callbacks.py:5298`</td>
</tr>
<tr>
<td>C18</td>
<td>Gate 实际接收的信息包及只做路由的职责</td>
<td>`valibra_agent/grounding_callbacks.py:3719`；`valibra_agent/sql_grounding/updater.py:684`</td>
</tr>
<tr>
<td>C19</td>
<td>NO_REGROUND 仍要求 Check 完成；TERMINAL 结束主流程</td>
<td>`valibra_agent/grounding_callbacks.py:4824`；`valibra_agent/grounding_callbacks.py:3867`</td>
</tr>
<tr>
<td>C20</td>
<td>草稿完成后提交；未完成时的有限补查及回滚</td>
<td>`valibra_agent/grounding_callbacks.py:4109`；`valibra_agent/grounding_callbacks.py:4288`；`valibra_agent/grounding_callbacks.py:3954`</td>
</tr>
	</table>
	### 日志与统计位置
	<table fit-page-width="true" header-row="true">
<tr>
<td>编号</td>
<td>内容</td>
<td>文件与行 / 表页</td>
</tr>
<tr>
<td>E01</td>
<td>solar7 本次全过程，含基线对照</td>
<td>`baseline/framework_analysis_20260914/solar_panel_7_evidence.md:6`；重做 `baseline/framework_analysis_20260914/solar_panel_7_evidence.md:892`；失败提问 `baseline/framework_analysis_20260914/solar_panel_7_evidence.md:1510`；SQL `baseline/framework_analysis_20260914/solar_panel_7_evidence.md:1898`</td>
</tr>
<tr>
<td>E02</td>
<td>hulu12 本次全过程，含基线对照</td>
<td>`baseline/framework_analysis_20260914/hulushows_12_evidence.md:6`；Check `baseline/framework_analysis_20260914/hulushows_12_evidence.md:695`；逐次 SQL `baseline/framework_analysis_20260914/hulushows_12_evidence.md:983`；真实 Main 输入 `baseline/framework_analysis_20260914/hulushows_12_当前_agent_04_request.json:1`</td>
</tr>
<tr>
<td>E03</td>
<td>hulu12 旧 paired 轨迹，不能混成本次 600 题</td>
<td>`research-runtime/hulushows_12_baseline_recovery_forensic_r2_20260907T081345Z/report.md:33`</td>
</tr>
<tr>
<td>E04</td>
<td>历史阶段级成功：知识保留、Gate→草稿提交</td>
<td>`research-runtime/p2_knowledge_preserve_stage_local_live_20260906T185025Z/adjudication.md:44`；`research-runtime/final_gate_mapping_owner_transition_r1_stage_local_20260906T221819Z/summary.md:16`</td>
</tr>
<tr>
<td>E05</td>
<td>真实数值预处理函数的离线比较</td>
<td>`baseline/framework_analysis_20260914/evaluator_numeric_check.json:1`；不含 DB 重跑</td>
</tr>
<tr>
<td>E06</td>
<td>literal 强制约束失败及回滚</td>
<td>`research-runtime/check_resolved_literal_executable_carrier_r1_20260907T000000Z/adjudication.md:25`</td>
</tr>
<tr>
<td>E07</td>
<td>语义 Prompt/verifier 的失败实验</td>
<td>`research-runtime/mapping_modifier_decision_discipline_r1_targeted_20260906T194925Z/analysis.md:5`；`research-runtime/mapping_query_role_aware_name_resolution_r1_20260907T103351Z/corrected_summary.md:1`；`research-runtime/mapping_semantic_decision_verifier_shadow_r1_20260907T120808Z/analysis.md:5`</td>
</tr>
<tr>
<td>D01</td>
<td>数据、模型、配置冻结记录</td>
<td>`/home/user/code/BIRD-Interact/baseline-runs/glm52_full600_20260830T130201Z/control/frozen_run_manifest.json:12`；`research-runtime/current_candidate_full_first200_e2e_20260907T190414Z/run_manifest.json:1`</td>
</tr>
<tr>
<td>D02</td>
<td>600 条对照、47 增/47 减、领域、分账</td>
<td>`baseline/framework_analysis_20260914/600题对照_含完整Token审计.xlsx`；`baseline/framework_analysis_20260914/task_comparison.json:1`</td>
</tr>
<tr>
<td>D03</td>
<td>token 汇总、来源检查、异常、可重建脚本</td>
<td>`baseline/framework_analysis_20260914/audit_summary.json:1`；`baseline/framework_analysis_20260914/grounding_audit_index.csv:1`；`baseline/framework_analysis_20260914/collect_evidence.py:1`</td>
</tr>
	</table>
	附录中的案例证据文件保留了源日志路径和 Prompt SHA，并分别导出了完整 System Prompt、User payload、Main 请求与所有 SQL。它们用于组内复核；其中包含基准任务和样例数据，不建议将整个证据目录直接作为公开发布包。
</details>
