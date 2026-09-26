> 历史集成记录。当前技能已融合为 `skills/unified-impact-evaluation`；执行与打包以该目录 SKILL.md 和当前 README 为准，本文历史安装位置和验证结果不代表当前状态。

# v19独立Skill交付

名称：`unified-impact-evaluation`。

已将原交付包的25个Python/JSON运行文件原样封装，保留SHA256来源清单；提供独立Skill入口、输入检查、原引擎执行、运行完整性验证。源项目交付包不改动，网站当前适配器不切换。

- 维护目录：`skills/unified-impact-evaluation`。
- 本机安装：`C:/Users/29821/.codex/skills/unified-impact-evaluation`。
- 便携包：`dist/unified-impact-evaluation.zip`。
- 校验记录：`docs/v19-skill-verification.json`。

## 后续调用

在Codex中可使用：

> 使用 $unified-impact-evaluation 检查指定工作区JSON，说明是否满足正式评价的输入条件。

明确要运行评价时，再提供工作区及输出目录，由该技能调用原v19引擎。模型服务配置通过 `V19_BASE_URL`、`V19_MODEL`、`V19_API_KEY` 环境变量提供。这个路径是Codex调用已有工具，而不是将原工具的评判模型自动替换为Codex。

本Skill接受准备好的工作区JSON，不直接接受裸PDF。P02交付快照可用于离线检查；P01、P06需要补冻结成果。原来源路径失效时需补齐或映射原件。

## 验证范围

已验证25个代码/数据文件与源交付逐字节一致；P02输入门槛通过，P01/P06被阻止。用明确标注的离线模型替身走通35次维度调用、5次成果综合、1次项目综合，验证特定层、全局层及协同输出都保留；没有发起模型服务请求，也没有将模拟结果作为真实科研评价交付。

旧P02保存结果缺当前G/L字段，包装器能识别并拒绝将其作为完整的当前分级结果。离线inspect无需安装模型SDK，现有检查报告不可被覆盖。

真实供应商连接、模型费用和真实评判质量留待后续实际运行时验证。本轮只封装与离线测试。

## 重打包

```powershell
python scripts/package-skill.py --skill unified-impact-evaluation
# 首次安装可加 --install；已有同名技能不会被自动覆盖
python scripts/verify-v19-skill.py
```

两套技能独立存在：吴老师v2侧重成果定位和六级管理者报告，v19保持原七维/双层口径。不得将两套L级编号直接互换。
