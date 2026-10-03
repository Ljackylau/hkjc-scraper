# 推介圖片

入口：`race-day/pick-images.html`；賽日頁標題下有「推介圖片」連結。

一鍵產生四張1125×1100 PNG：膽馬獨贏100、膽馬位置300、冷馬獨贏50、冷馬位置150。每張的細節投注及金額相符，每組合共600。可逐張下載、長按儲存、下載含四張PNG的ZIP，或在支援檔案分享的瀏覽器使用分享按鈕。圖片明示「投注計劃／未提交」，不宣稱注項已接納。

同一組四張共用編號，從7720起，每次成功生成一组加3。PNG及ZIP生成完成後才保存下一個編號。重下載及取消分享不加號。使用同源localStorage保存，支援Web Locks時序列化跨分頁生成；不同裝置或瀏覽器、清除網站資料均不共享這個計數器。儲存失敗或計數器損壞會報錯，不靜默重設。

「查看圖片版面示例」可在未有當日推介時預覽及下載四張示例圖，逐張清楚標示「版面示例／虛構資料」，使用「示例」編號且不遞增正式編號。

頁面沿用原 `LiveTips.validate`，讀取資料分支當日 `hkjc-early/status.json`、`hkjc-late/status.json` 的 `independent_tips`。主膽、冷馬和馬名來自同一已鎖定快照；名字採用HKJC `runner_rows[][2]`。`hkjc_shadow.py` 在status新增 `venue`，所以新賽日需用更新後的main版本啟動Runner。沒有重新計算或更改揀膽、冷馬、選腳方法。

自動選擇現在之後最早開跑的一場。只限香港當日，不退回上個賽日或已開跑場次；近場未齊資料亦不改取較後場。當沒有冷馬、缺主膽／馬名、收到時間過截止、場次或場地不符、開跑時間改動不符或推介是歷史重建時，不產生四張。以原始截止前名單檢查當時標示的退賽，並非實時退賽監察服務。

每15秒檢查資料；開跑前280秒內約每2秒檢查。點擊生成時再讀最新資料，在匯出完成後再次核對未開跑。生成只在瀏覽器本機執行。

主站在T−3:10鎖定快照；只要已公開並通過驗證，圖片頁即啟用，不額外等到T−3:00。此設定避免新增固定延遲，但不保證上游取得／發布資料的時間。

驗證：

```bash
node --check race-day/pick-images.js
node --check race-day/pick-images-page.js
node race-day/test_pick_images.js
python -m unittest discover -s race-day -p 'test_*.py' -v
```

手機分享採用[Web Share API](https://developer.mozilla.org/en-US/docs/Web/API/Navigator/share)，按 `canShare({files})` 顯示；不支援則使用PNG／ZIP下載。跨分頁鎖採用[Web Locks](https://www.w3.org/TR/web-locks/)。
