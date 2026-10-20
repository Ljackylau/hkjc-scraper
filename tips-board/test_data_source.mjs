import assert from 'node:assert/strict';
import {RAW,revisionBase,resolveDataSource} from './data-source.mjs';
const saved='a'.repeat(40),fresh='b'.repeat(40),fallback='c'.repeat(40),calls=[];
let source=await resolveDataSource({saved,fallback,fetcher:async(url,options)=>{
 calls.push(url);assert.equal(options.cache,'no-store');
 return {ok:true,json:async()=>({object:{sha:fresh}})};
}});
assert.equal(source.base,revisionBase(fresh));assert.equal(source.sha,fresh);
source=await resolveDataSource({saved,fallback,fetcher:async(url)=>{
 calls.push(url);
 if(url.includes('api.github.com'))return {ok:false,status:403};
 return {ok:true,json:async()=>({date:'2026-10-21',races:[{race:1}]})};
}});
assert.equal(source.base,RAW,'API failure must not trap mobile on its old saved SHA');
assert.equal(source.sha,null,'an unpinned branch is never recorded as a verified SHA');
assert.match(source.notice,/直接讀取最新/);
source=await resolveDataSource({saved,fallback,fetcher:async()=>{throw Error('offline')}});
assert.equal(source.base,revisionBase(saved));assert.match(source.notice,/可能未包含最新/);
source=await resolveDataSource({saved:'invalid',fallback,fetcher:async()=>({ok:true,json:async()=>({})})});
assert.equal(source.base,revisionBase(fallback));assert.match(source.notice,/備用存檔/);
assert(calls.every(u=>/[?&]v=\d+/.test(u)));
console.log('PASS: current revision, API-blocked mobile fallback to live data, labelled offline archive, invalid responses.');
