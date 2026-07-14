# 简易学生管理系统 Demo

本目录是 PM-Agent 第一版项目分析能力的测试样本，不是生产项目。当前完成度约为 **50%**：已实现学生列表、姓名查询、详情和新增的前后端联调；编辑、删除、课程成绩、登录鉴权等能力仅保留设计。

## 目录

```text
project_test/
├── backend/                 Spring Boot 后端
├── frontend/                React + TypeScript 前端
├── database/                MySQL 建表与演示数据
└── docs/
    ├── 开发文档.md
    └── 接口文档.md
```

## 快速启动

### 后端

```bash
cd backend
mvn spring-boot:run
```

后端默认运行在 `http://localhost:18080`，开发环境使用内存 H2 数据库，无需提前安装 MySQL。

### 前端

```bash
cd frontend
pnpm install
pnpm dev
```

前端默认运行在 `http://localhost:15173`，并将 `/api` 代理到后端。

## 演示路径

1. 打开前端首页，查看预置学生。
2. 输入姓名关键字执行查询。
3. 点击学生行查看详情。
4. 点击“录入学生”新增记录，列表会自动刷新。

## 重要警告

本项目故意包含安全性和工程规范问题，用来测试 PM-Agent 是否能识别风险。不得将本目录代码复制到生产系统，具体测试点见 [开发文档](docs/开发文档.md)。

