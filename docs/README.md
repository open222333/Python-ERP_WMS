# docs/ 文件索引

本目錄存放專案的延伸文件，與根目錄 `CLAUDE.md`（精簡版開發指引）互補。

| 文件 | 用途 | 維護時機 |
|---|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | 架構參考：模組一覽、資料庫關聯圖、Redis key、索引、外送對應解析順序、實作備忘（常見坑）、k6/seed 測試工具 | 架構、資料模型或關鍵流程改動時同步更新 |
| [`API.md`](API.md) | 全部後端 API 端點參考表：方法、路徑、說明、權限（admin/operator/cashier/JWT/公開）。依 Blueprint 分節 | 新增或改動任何 API 端點時**同步更新** |
| [`PAGES.md`](PAGES.md) | 前端頁面對照表：路由、對應 Vue 檔案、功能說明。分「獨立頁面」與「後台 `/admin/*`」兩節 | 新增頁面或改動路由時更新（記得同步 `frontend/src/config/nav.ts`） |
| [`FIXES.md`](FIXES.md) | Bug / 安全修復歷史記錄。**這些問題已修復，做程式碼審查或掃描時勿重複回報**。修改處在程式碼中以 `# [OPT]` / `// [OPT]` 註解標記 | 每次修復 bug 或安全問題時追加一筆 |
| [`OPTIMIZATION_REPORT.md`](OPTIMIZATION_REPORT.md) | 優化項目追蹤：已完成的定點修復與大型重構（`# [REFACTOR]` 標記）、**未完成項目的實作規格**（pydantic 驗證層、Change Streams、虛擬滾動）、收尾與部署注意事項 | 完成或新增優化項目時更新狀態；接續未完成工作前先讀此檔 |

## 快速導引

- **要接續未完成的優化工作** → 讀 `OPTIMIZATION_REPORT.md` 的「未完成項目與未來調整細項」
- **要新增/修改 API** → 先查 `API.md` 現有慣例，改完更新表格
- **懷疑發現 bug** → 先查 `FIXES.md` 是否已修復
- **找某個功能的前端入口** → 查 `PAGES.md`
- **資料庫結構、模組關聯、常見陷阱** → 查 `ARCHITECTURE.md`
- **Build 與測試指令、制度引用、只讀邊界** → 根目錄 `CLAUDE.md`
