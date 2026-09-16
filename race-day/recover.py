"""Isolated capture of remaining races; never recreates expired snapshots."""
import asyncio, concurrent.futures
import runner as r

async def main():
    date=r.now().date().isoformat()
    if date!='2026-09-16':
        print('One-meeting recovery expired');return
    races=await asyncio.to_thread(r.horse.get_races,date)
    r.setup_data_branch()
    folder=r.REPO/'race-day-data'/date/'recovery';folder.mkdir(parents=True,exist_ok=True)
    states={};ex=concurrent.futures.ThreadPoolExecutor(3)
    tasks=[asyncio.create_task(r.horse_job(x,date,folder,states,ex)) for x in races if x['race_number'] in (7,8)]
    while True:
        finished=all(t.done() for t in tasks)
        r.atomic(folder/'status.json',{'date':date,'phase':'recovery','updated_at':r.now().isoformat(),'state':'finished' if finished else 'running','horse103':states})
        await asyncio.to_thread(r.publish,folder)
        if finished:break
        await asyncio.sleep(15)
    await asyncio.gather(*tasks)
    ex.shutdown()

if __name__=='__main__':asyncio.run(main())
