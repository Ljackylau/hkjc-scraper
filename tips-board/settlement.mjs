// Use official paid combinations, including dead heats, rather than inferring payout from rank.
export function settle(pool,selected,result){
 const nos=[...new Set(selected.map(Number))];
 const bets=pool==='W'||pool==='P'?nos.map(n=>[n]):nos.flatMap((n,i)=>nos.slice(i+1).map(m=>[n,m]));
 if(result?.pool_status?.[pool]==='not_offered')return{status:'not_offered',total:bets.length,hits:[],refunds:0};
 if(!result?.dividends?.[pool]?.length)return{status:'pending',total:bets.length,hits:[],refunds:0};
 const key=c=>[...c].sort((a,b)=>a-b).join(',');
 const wanted=new Set(bets.map(key)),withdrawn=new Set((result.withdrawn||[]).map(Number));
 const paid=result.dividends[pool],hits=[];
 for(const row of paid){const combo=String(row.combination).split(/[,，]/).map(s=>Number(s.trim()));if(combo.some(n=>!Number.isInteger(n)||n<=0)||!wanted.has(key(combo)))continue;const amount=Number(row.dividend_hkd);if(!Number.isFinite(amount)||amount<0)continue;hits.push({horses:combo,dividend:amount,multiple:amount/10})}
 const refunds=bets.filter(c=>c.some(n=>withdrawn.has(n))).length;
 return{status:hits.length?'hit':refunds===bets.length?'refund':'miss',total:bets.length,hits,refunds};
}
