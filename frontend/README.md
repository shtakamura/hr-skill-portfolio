# HR Skill Portfolio Frontend

## ローカル起動

```powershell
cd C:\hr-skill-portfolio\frontend
npm.cmd install
npm.cmd run dev
```

Vite の起動後、表示された URL をブラウザで開きます。既定では `http://localhost:5173/` です。

## ビルド

```powershell
cd C:\hr-skill-portfolio\frontend
npm.cmd run build
```

現在はモックデータを `src/data/positionMockData.ts` から取得しています。将来は `src/services/positionService.ts` の `getDepartments()` を API Gateway 経由の `GET /positions` へ差し替える想定です。

## 画面

- ポジション一覧: `http://localhost:5173/positions`
- 人材サーチャート: `http://localhost:5173/positions/P002-03/search-chart`

人材サーチャートのスキルプロファイルとカバー度の高いポジションは、`src/services/skillProfileService.ts` 経由でAPIから取得します。