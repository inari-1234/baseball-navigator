#!/usr/bin/env python3
"""Local rule engine for Home Run High Authority v1.3.
Input: state JSON-like dict. Output: traceable recommendation.
This is not a game simulator; it selects actions from verified local facts and live deltas.
"""

def recommend_activity(state, activities):
    cheer=state['cheer_points']; pts=state['research_points']; need=max(0,20-cheer)
    available=set(state.get('current_activities',[]))
    cand=[]
    reserves={'study':30,'sports':60,'fun':15,'nature':17}
    key={'勉強':'study','スポーツ':'sports','遊び':'fun','自然':'nature'}
    for a in activities:
        if a['name'] not in available: continue
        k=key.get(a['resource']); cost=int(a['cost']) if str(a['cost']).isdigit() else 0
        remain=pts.get(k,0)-cost if k else 0
        reserve_penalty=20 if k and remain<reserves.get(k,0) else 0
        strategic_penalty=15 if a['resource']=='スポーツ' else 0
        # empirical cheer is only evidence, never expected fixed value
        empirical=0
        if a.get('empirical_cheer_samples'):
            try: empirical=max(int(x) for x in str(a['empirical_cheer_samples']).split(';') if x)
            except: pass
        threshold_risk=8 if empirical and empirical < need else 0
        score=50-reserve_penalty-strategic_penalty-threshold_risk
        if a['resource']=='遊び': score+=15
        cand.append((score,a['name'], {'remain':remain,'need_cheer':need,'random':True,'empirical':empirical}))
    cand.sort(reverse=True)
    if not cand: return {'primary':'no activity','reason':'no available candidates'}
    top=cand[0]
    return {'primary':top[1],'score':top[0],'trace':top[2],'fallback':'実行後に応援ptを再確認。20未満なら時間/試合/資源を再評価し固定連打しない。','all_candidates':cand}

def recommend_opponent(state):
    hist=state.get('opponent_history',{})
    grade_pen={'F':0,'E':8,'D':14,'C':20,'B':26,'A':32,'S':40}
    rows=[]
    for o in state.get('current_opponent_menu',[]):
        if not o.get('first_win'): continue
        score=50-grade_pen.get(o.get('grade'),10)
        h=hist.get(o['school'],{})
        score-=15*h.get('losses',0)
        if o['school']=='貞京第五高校': score+=10 # chain value
        if o['school']=='調子商業高校': score+=5 # safe unresolved first win
        rows.append((score,o['school'],o))
    rows.sort(reverse=True)
    return {'primary':rows[0][1] if rows else None,'all_candidates':rows,'fallback':'安全優先なら実機敗戦歴の少ない/低ランク未勝利校。ルート速度優先時はchain価値を上げる。'}

def recommend(state, activities):
    if state.get('decision_type')=='activity': return recommend_activity(state,activities)
    if state.get('decision_type')=='opponent': return recommend_opponent(state)
    return {'primary':'ingest live delta','reason':'decision_type required'}
