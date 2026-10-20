"""Happy Valley H=0/1 trial. Uses pre-race tips and prior-day jockey/draw ranks."""
HV_METHOD = 'hv-h01-trial-20261021'
EXPERTS = ('ball', 'ma', 'computer')

def choose_hv(r):
    sources = [r.get('tips', {}).get(k, {}) for k in EXPERTS]
    def state(kind, reason):
        r['selection'] = None
        r['hv_plan_state'], r['hv_plan_reason'] = kind, reason
    if any(s.get('status') not in ('ready', 'absent') or
           s.get('source_date') not in (None, r.get('date')) for s in sources):
        r['score'] = None
        state('pending', '待確認三個專家來源')
        return
    h = r['score'] = sum(bool(s.get('horses')) for s in sources)
    if h > 1:
        return
    r['selection'] = None
    r.pop('hv_plan_state', None)
    r.pop('hv_plan_reason', None)
    field = {int(x['no']): x for x in r.get('horses', [])}
    scratched = set(map(int, r.get('scratched', []) + (r.get('result') or {}).get('withdrawn', [])))
    def active(n):
        return n in field and n not in scratched
    if h == 0:
        m, b = r.get('tips', {}).get('meiji', {}), r.get('banker_initial', {})
        if m.get('status') != 'ready' or not m.get('horses') or m.get('source_date') not in (None, r.get('date')):
            state('pending', '待明治朗首選')
            return
        numbers = list(map(int, b.get('numbers', [])))
        if (b.get('status') != 'ready' or b.get('as_of_race_no') != 0 or b.get('reason') != 'initial'
            or b.get('date') != r.get('date') or b.get('venue') != 'HV'
            or b.get('race') != r.get('race') or len(numbers) != 5 or len(set(numbers)) != 5):
            state('pending', '待膽拖網同場初版推介')
            return
        if int(m['horses'][0]['no']) in numbers[:3]:
            state('skip', '明治朗首選在膽拖初版前三內，本場不買')
            return
        j = r.get('draw_top5', {})
        if (j.get('status') != 'ready' or j.get('method_version') != 'jockey_draw_only_v3'
            or len(j.get('riders', [])) < 2 or j.get('before_date') not in (None, r.get('date'))):
            state('pending', '待同檔騎師榜第2名')
            return
        rider = j['riders'][1]
        no = int(rider['no'])
        if not active(no):
            state('skip', 'J2退出或不在出賽名單，本場不買')
            return
        horse = field[no]
        if (horse.get('draw') is not None and int(horse['draw']) != int(rider['draw'])
            or horse.get('jockey_id') and rider.get('jockey_id') and horse['jockey_id'] != rider['jockey_id']):
            state('pending', 'J2與最新排位不符，待重新排名')
            return
        pool, roles = 'P', '明治首選不在初版前三 → J2位置'
    else:
        tip = next(s for s in sources if s.get('horses'))
        no = int(tip['horses'][0]['no'])
        if not active(no):
            state('skip', '專家原首選退出或不在出賽名單，本場不買')
            return
        pool, roles = 'W', '唯一專家原首選獨贏'
    r['hv_plan_state'], r['hv_plan_reason'] = 'ready', roles
    r['selection'] = {'horses': [{'no': no, 'name': field[no]['name']}],
                      'main': [pool], 'optional': [], 'method': HV_METHOD, 'roles': roles}
