# frontend-agent

`frontend-agent` 是 PM-Agent 项目文件可靠上传的独立联调客户端，也是正式新建项目界面的先驱实现。

## 功能

- 打开系统目录选择器并选择项目根目录；
- 取消、移除和重新选择目录；
- 校验单文件 50 MB、单次 5000 个文件和 1 GB 限制；
- 创建项目和文件上传批次；
- 以 3 个并发逐文件上传；
- 网络失败后在 1 秒、3 秒自动重试；
- 展示 Java 后台 RabbitMQ 重试和失败文件；
- 手动立即重试失败文件。

## 启动

```bash
pnpm install
pnpm dev
```

默认地址为 `http://localhost:5174`，`/api` 代理到 `http://localhost:8080`。

## 登录令牌

Java 文件接口要求登录。可以在浏览器控制台写入已有令牌：

```javascript
localStorage.setItem('pm-agent-token', 'Bearer <token>')
```

也可以在本地环境变量中配置 `VITE_PM_AGENT_TOKEN`。不要提交真实令牌或本地 `.env`。

## 验证

```bash
pnpm typecheck
pnpm build
```

手动验收时至少选择一个文本文件、一个图片和一个 PDF。文本文件应允许解析，图片和 PDF 应上传但标记为不参与解析。
