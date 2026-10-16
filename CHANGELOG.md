# Changelog

## 1.1.0

- 新增 `engine=aivoice2`，通过 AIVoiceBridge 1.1.0 连接二代 DLL API。
- 二代使用实际声库 ID，支持原生风格 JSON 和标准/关西日语词典；排除未暴露的一代停顿参数。
- 增加 `voices`、`health`、`parameters` 命令，并保留 HTTP 桥的错误代码及错误说明。
- 清空二代声库配置时删除旧默认，空风格对象明确重置风格；拒绝无效权重和词典。
- 保留一代配置、旧命令及缺少 engine 的旧配置行为；更新迁移说明与验收工具。
