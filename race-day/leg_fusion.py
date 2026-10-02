"""Freeze the researched fourth-leg cold replacement before publication.

Keep the original F2 + banker QP2 selection unless the frozen cold v2 horse
has 10 < predeadline WIN <= 30 and is neither banker nor an original leg.
No new requests, model fitting or race outcomes are used here.
"""
import math
from datetime import datetime

METHOD = 'f2_qp1_cold_10_30_exploratory_2026_10_02'
APPLY_FROM = '2026-10-02'
COLD_POLICY = 'cold_top2_priority_v2_exploratory_2026-10-02'


def _clock(value):
    at = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if at.tzinfo is None:
        raise ValueError('Missing timezone')
    return at


def apply(tip):
    """Return final legs with audit metadata; repeat calls retain the lock."""
    if tip.get('legs_method') == METHOD or tip.get('status') != 'ready':
        return tip
    try:
        original = list(map(int, tip.get('legs', [])))
        banker = int(tip['banker'])
    except (TypeError, ValueError, KeyError):
        return tip
    if tip.get('legs_status') != 'ready' or len(original) != 4 or len(set(original)) != 4 or banker in original:
        return tip
    output = {**tip, 'legs_method': METHOD, 'legs_original': original,
              'legs_original_method': tip.get('legs_method'),
              'legs_original_qp': list(tip.get('legs_qp', [])),
              'legs_fusion_changed': False, 'legs_added': None, 'legs_removed': None,
              'legs_cold': [], 'legs_fusion_win': None}

    def keep(code, reason):
        return {**output, 'legs_fusion_reason_code': code, 'legs_fusion_reason': reason}

    if tip.get('cold_policy') != COLD_POLICY or tip.get('cold_status') != 'ready':
        return keep('cold_unavailable', '冷馬資料未就緒，保留原四腳')
    candidates = tip.get('cold') or []
    if not isinstance(candidates, (list, tuple)) or len(candidates) != 1:
        return keep('cold_not_single', '未有單匹冷馬，保留原四腳')
    try:
        freeze = _clock(tip['freeze'])
        if _clock(tip['cold_freeze']) != freeze:
            return keep('cold_cutoff_mismatch', '冷馬截止時間不符，保留原四腳')
        stamps = [tip['cold_received_at'], tip['cold_fct_received_at'],
                  tip['cold_sources']['historical_prepared_at']]
        if any(_clock(stamp) > freeze for stamp in stamps):
            return keep('cold_after_deadline', '冷馬資料遲於截止，保留原四腳')
        horse = int(candidates[0])
        win = float(tip['cold_win'])
        if not math.isfinite(win):
            raise ValueError('Nonfinite WIN')
        active = set(map(int, tip.get('leg_scores', {})))
    except (ValueError, TypeError, KeyError, AttributeError):
        return keep('cold_invalid', '冷馬資料無效，保留原四腳')
    output['legs_fusion_win'] = win
    if not 10 < win <= 30:
        return keep('cold_win_outside_gate', '冷馬WIN不在10至30倍範圍，保留原四腳')
    if horse == banker:
        return keep('cold_is_banker', '冷馬已是主膽，保留原四腳')
    if horse in original:
        return keep('cold_already_selected', '冷馬已在原四腳內，保留原四腳')
    if horse not in active:
        return keep('cold_outside_field', '冷馬不在有效出馬名單，保留原四腳')
    final = original[:3] + [horse]
    return {**output, 'legs': final, 'legs_qp': [original[2]], 'legs_cold': [horse],
            'golden': [h for h in tip.get('golden', []) if int(h) in final],
            'legs_fusion_changed': True, 'legs_added': horse, 'legs_removed': original[3],
            'legs_fusion_reason_code': 'cold_replaces_fourth',
            'legs_fusion_reason': f'第四腳換入冷馬{horse}號（截止WIN {win:g}倍）；原{original[3]}號'}


def note(tip, label=None):
    if tip.get('legs_method') != METHOD:
        return ''
    if tip.get('legs_fusion_changed') and label is not None:
        return (f'第四腳換入冷馬{label(tip["legs_added"])}'
                f'（截止WIN {tip["legs_fusion_win"]:g}倍）；原{label(tip["legs_removed"])}')
    return tip.get('legs_fusion_reason', '')
