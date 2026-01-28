# 贡献指南

感谢您对 BI-Agent 项目的关注！我们欢迎所有形式的贡献。

## 如何贡献

### 报告问题

如果您发现了 bug 或有功能建议，请通过 GitHub Issues 提交：

1. 检查是否已有相关 issue
2. 如果没有，创建新的 issue
3. 提供清晰的问题描述、复现步骤和预期行为

### 提交代码

1. **Fork 项目**
   ```bash
   git clone https://github.com/your-username/BI-Agent.git
   cd BI-Agent
   ```

2. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **开发**
   - 遵循项目的代码风格
   - 添加必要的测试
   - 更新相关文档

4. **提交**
   ```bash
   git add .
   git commit -m "feat: 添加新功能描述"
   ```

5. **推送并创建 Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

### 代码规范

- 使用 Python 3.10+
- 遵循 PEP 8 代码风格
- 使用类型提示（Type Hints）
- 添加必要的文档字符串
- 保持代码简洁和可读性

### Commit 信息规范

我们使用约定式提交（Conventional Commits）：

- `feat:` 新功能
- `fix:` 修复 bug
- `docs:` 文档更新
- `style:` 代码格式调整
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建/工具相关

### 测试

在提交 PR 前，请确保：

- 所有测试通过
- 代码通过 lint 检查
- 新功能有相应的测试覆盖

## 问题反馈

如果您有任何问题或建议，欢迎通过以下方式联系：

- GitHub Issues
- Pull Requests

再次感谢您的贡献！
