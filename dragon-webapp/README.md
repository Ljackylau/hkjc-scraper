# Dragon Racing Lab — Cloudflare Worker

- 主頁：自動讀取HKJC下一賽日，固定 V2.1-auto 每場最多3匹；首次完整輸出寫入D1後鎖定。
- 歷史頁：9月9日正式第二版核對、9月6日重建審計。

模型使用近績、評分、評分變化、負磅、檔位及晨操／試閘資料完整度。未能可靠自動辨識步速時不加分。

## 首次部署

1. Cloudflare建立D1 database：dragon-racing-db。
2. 將database id填入 wrangler.jsonc。
3. GitHub repository Settings → Secrets and variables → Actions加入 CLOUDFLARE_API_TOKEN 及 CLOUDFLARE_ACCOUNT_ID。
4. 將PR合併到main，再於Actions執行 Deploy Dragon Web App。

每6小時檢查新賽日；開網站亦會即時同步。9月6日R1–R8有快照及重建選擇；R9–R10冇T−3，唔計入第二版正式命中率。
