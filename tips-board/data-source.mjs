export const RAW='https://raw.githubusercontent.com/Ljackylau/hkjc-scraper/tips-data/records/';
const validSha=sha=>/^[a-f0-9]{40}$/.test(sha||'');
export const revisionBase=sha=>RAW.replace('/tips-data/records/','/'+sha+'/records/');

export async function freshJson(url,fetcher=fetch){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
 try{
  const response=await fetcher(url+(url.includes('?')?'&':'?')+'v='+Date.now(),{cache:'no-store',signal:controller.signal});
  if(!response.ok)throw Error('HTTP '+response.status);
  return await response.json();
 }finally{clearTimeout(timer)}
}

export async function resolveDataSource({fetcher=fetch,saved,fallback}){
 try{
  const value=await freshJson('https://api.github.com/repos/Ljackylau/hkjc-scraper/git/refs/heads/tips-data',fetcher);
  const sha=value.object?.sha;if(!validSha(sha))throw Error('無效資料版本');
  return {base:revisionBase(sha),sha,version:sha,notice:''};
 }catch{
  // Mobile networks can block/rate-limit GitHub's API while raw data remains
  // reachable. Try the current branch before reusing an immutable old commit.
  try{
   const latest=await freshJson(RAW+'latest.json',fetcher);
   if(!/^\d{4}-\d{2}-\d{2}$/.test(latest?.date||'')||!Array.isArray(latest.races))throw Error('無效賽日資料');
   return {base:RAW,sha:null,version:latest.updated_at||latest.date+':'+Date.now(),notice:'版本查詢暫時不可用；已直接讀取最新公開資料，稍後會再核對版本。'};
  }catch{
   const sha=validSha(saved)?saved:fallback;
   if(!validSha(sha))throw Error('最新資料暫時無法連線');
   return {base:revisionBase(sha),sha:null,version:sha,notice:'最新資料暫時無法連線；現顯示'+(validSha(saved)?'本機上次成功核對的存檔':'備用存檔')+'，可能未包含最新貼士。回到此頁或按「重新讀取」會再試。'};
  }
 }
}
