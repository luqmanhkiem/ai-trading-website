"""Descriptive geometry/structure grades; never a probability or entry filter."""
def grade_zone(entry, stop, target_distance, retests=0, aligned=False):
    if target_distance <= 0 or entry == stop or retests < 0:
        raise ValueError('Invalid zone geometry.')
    rr=target_distance/abs(entry-stop)
    label='High' if not aligned or retests>=2 or rr<.75 else 'Low' if retests==0 and rr>=1.5 else 'Mid'
    return dict(risk_label=label,planned_rr=round(rr,3),risk_reasons=[
        f'TP3 reward / reference stop distance = {rr:.2f}:1 before costs.',
        f'{retests} completed-candle retest episode(s).',
        'Aligned with confirmed structure.' if aligned else 'Structure is unconfirmed or points the other way.'],
        risk_label_note='Relative risk heuristic, not a win probability or recommended position size.')
