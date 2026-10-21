// Manually verified official results survive an older live collector's writes.
// Only results are merged; selections, source timestamps and locks are untouched.
export function mergeManualResults(meeting,overlay){
 if(!meeting?.races||!/^\d{4}-\d{2}-\d{2}$/.test(meeting.date||''))return meeting;
 const entry=overlay?.meetings?.find(m=>m.date===meeting.date&&m.venue===meeting.venue);
 if(!entry)return meeting;
 const copy=structuredClone(meeting);
 for(const race of copy.races){
  const result=entry.races?.[race.race];
  if(!result||result.verified_date!==copy.date||result.verified_race!==race.race||!result.horses?.length||!result.dividends)continue;
  if(result.horses.some(h=>!race.horses.some(f=>Number(f.no)===Number(h.no))))continue;
  race.result=structuredClone(result);
 }
 return copy;
}
