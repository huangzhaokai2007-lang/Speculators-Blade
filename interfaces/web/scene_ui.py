"""Small contextual controls; all selection validation and facts belong to agent."""
import streamlit as st

from agent import scene_flow


def accept(executor, session: str, turn) -> None:
    import card_binding_ui, card_lock_ui, card_lost_ui, card_limit_ui
    if turn.ask == 'scene_reset':
        state = st.session_state.get('lock-view')
        if state:
            card_lock_ui._cancel_preview(executor, session, state)
        card_lock_ui.reset()
        card_lost_ui.reset()
        card_limit_ui.reset()
        card_binding_ui.reset()
        st.session_state['bound-card-query'] = False
        return
    context = executor.submit(scene_flow.context, session).result()
    card_id = context.get('card_id')
    if turn.intent == 'card_query' and card_id:
        state = card_binding_ui._state(executor, session)
        state['selected'] = card_id
    if card_id and turn.ask in ('card_lock', 'card_unlock'):
        card_lock_ui.open_card(executor, session, card_id,
                               'unlock' if turn.ask == 'card_unlock' else 'lock', inline=True)
        st.session_state['bound-card-query'] = True


def render(executor, session: str, ask, *, show_scope: bool = True) -> None:
    context = executor.submit(scene_flow.context, session).result()
    if not context.get('intent'):
        return
    with st.container(key='scene-context'):
        parts = [context[k] for k in ('period', 'category', 'counterparty') if context.get(k)]
        card = next((r for r in context.get('candidates', {}).get('card', [])
                     if r.get('card_id') == context.get('card_id')), None)
        if card:
            parts.append(card.get('card_no_mask', ''))
        if parts and show_scope:
            st.caption(' › '.join(parts))
        #: 2026-11-01（用户要求删掉）：这里原本挂一个「选择项目继续查看」下拉 + 「查看所选详情」按钮，
        #: 和上面的卡片/明细表功能重叠，观感也突兀。需要看某一笔时直接在卡片里点（或说「第 3 笔」）。
        #: 保留下来的只有上面那行范围面包屑（period › category › 对手方）。
