// All numeric labels are verbatim facts. Arithmetic only positions SVG geometry.
function ledgerRow(item, element) {
  const row = element('li', 'bank-pie-txn');
  const main = element('div', 'bank-pie-txn-main');
  main.append(element('span', 'bank-pie-merchant', item.counterparty || '未注明交易对手'),
    element('strong', 'bank-pie-txn-amount', `${item.amount_yuan} 元`));
  const meta = element('div', 'bank-pie-txn-meta');
  meta.append(element('time', '', String(item.ts || '').replace('T', ' ')),
    element('span', '', item.channel || ''));
  row.append(main, meta);
  if (item.memo) row.title = String(item.memo);
  return row;
}

function renderLedger(root, data, select, element) {
  root.querySelector?.('.bank-pie-ledger')?.remove();
  if (!data.selected) { delete root.dataset.ledgerSelection; return; }
  const label = data.direction === 'income' ? '收入' : '支出';
  const selectionKey = JSON.stringify([data.direction || 'expense', data.selected]);
  const opening = root.dataset.ledgerSelection !== selectionKey;
  root.dataset.ledgerSelection = selectionKey;
  const panel = element('section', 'bank-pie-ledger' + (opening ? ' is-opening' : ''));
  panel.setAttribute('aria-label', `${data.selected}${label}明细`);
  const header = element('div', 'bank-pie-ledger-head');
  header.append(element('strong', '', `${data.selected} · ${label}明细`));
  const close = element('button', 'bank-pie-close', '收起');
  close.type = 'button';
  close.onclick = event => select(null, event?.detail === 0);
  header.append(close);
  panel.append(header);
  const detail = data.detail;
  if (!detail) panel.append(element('p', 'bank-pie-ledger-note', '正在读取明细…'));
  else if (!detail.ok) panel.append(element('p', 'bank-pie-ledger-note', detail.message || '暂时无法读取明细。'));
  else {
    panel.append(element('p', 'bank-pie-ledger-note', `${data.period} · ${detail.count} 笔 · ${label} ${detail.amount_yuan} 元`));
    if (!detail.items?.length) panel.append(element('p', 'bank-pie-ledger-note', `该分类在此账期暂无${label}明细。`));
    else {
      const list = element('ul', 'bank-pie-ledger-scroll');
      list.tabIndex = 0;
      list.setAttribute('aria-label', '交易明细，可上下滚动');
      detail.items.forEach(item => list.append(ledgerRow(item, element)));
      panel.append(list);
    }
  }
  root.append(panel);
}

export default function ({ parentElement, data, setStateValue = () => {} }) {
  const root = parentElement.querySelector('.bank-pie');
  const active = document.activeElement;
  const restoreFocus = root.dataset.focusTarget || (root.contains?.(active) && active?.getAttribute('aria-label'));
  delete root.dataset.focusTarget;
  const ns = 'http://www.w3.org/2000/svg';
  const colors = ['#a49be0', '#7e9fac', '#b3bda0', '#c5a888', '#8b9bc5', '#b08f9e', '#8caeaa'];
  const element = (tag, cls, text) => {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = String(text);
    return node;
  };
  const svgElement = (tag, attrs = {}) => {
    const node = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
  };
  root.replaceChildren();
  root.dataset.phase = 'waiting';
  const paths = [], entries = [];
  let selected = data.selected || null;
  let direction = data.direction || 'expense';
  const isSelected = item => item.category === selected && item.direction === direction;
  const highlight = hovered => {
    const target = hovered || paths.find(isSelected);
    paths.forEach(item => {
      const match = target && item.category === target.category && item.direction === target.direction;
      item.path.classList.toggle('is-muted', Boolean(target) && !match);
      item.path.classList.toggle('is-highlighted', Boolean(match));
      item.path.setAttribute('aria-pressed', String(isSelected(item)));
    });
    entries.forEach(item => {
      item.node.classList.toggle('is-muted', Boolean(target) &&
        !(item.category === target.category && item.direction === target.direction));
      item.node.setAttribute('aria-pressed', String(isSelected(item)));
    });
  };
  const select = (category, keyboard = false, nextDirection = direction) => {
    const previous = selected;
    const previousLabel = direction === 'income' ? '收入' : '支出';
    selected = category === selected && nextDirection === direction ? null : category;
    direction = nextDirection;
    const focusTarget = selected ? 'ledger' : `查看${previous}${previousLabel}明细`;
    if (keyboard) root.dataset.focusTarget = focusTarget;
    highlight();
    renderLedger(root, { ...data, selected, direction, detail: null }, select, element);
    // Preserve the expense selection payload for existing sessions.
    setStateValue('selected', keyboard || (selected && direction === 'income')
      ? { category: selected, direction, ...(keyboard ? { focus_target: focusTarget,
          focus_id: `${Date.now()}:${Math.random()}` } : {}) } : selected);
  };
  const renderPie = (groups, side, total) => {
    const label = side === 'income' ? '收入' : '支出';
    const rows = groups.map((group, index) => ({ group, index,
      weight: Number(String(group.amount_yuan ?? '').replaceAll(',', '')) }));
    const positive = rows.filter(row => Number.isFinite(row.weight) && row.weight > 0);
    // This denominator is for geometry only; labels remain verbatim facts.
    const denominator = positive.reduce((sum, row) => sum + row.weight, 0);
    if (!denominator) return null;
    const layout = element('div', 'bank-pie-layout');
    const figure = element('figure', 'bank-pie-figure');
    const svg = svgElement('svg', { viewBox: '0 0 240 240', role: 'group', 'aria-label': `${label}分类饼图` });
    const defs = svgElement('defs');
    const maskId = `pie-mask-${side}-${data.animation_id}`;
    const mask = svgElement('mask', { id: maskId, maskUnits: 'userSpaceOnUse', x: 0, y: 0, width: 240, height: 240 });
    const sweep = svgElement('circle', { cx: 120, cy: 120, r: 52, fill: 'none', stroke: 'white',
      'stroke-width': 104, pathLength: 1, 'stroke-dasharray': 1, transform: 'rotate(-90 120 120)', class: 'bank-pie-sweep' });
    mask.append(sweep);
    defs.append(mask);
    svg.append(defs, svgElement('circle', { cx: 120, cy: 120, r: 104, fill: '#191b20' }));
    const slices = svgElement('g', { mask: `url(#${maskId})` });
    let angle = -Math.PI / 2;
    positive.forEach(({ group, index, weight }) => {
      const next = angle + (weight / denominator) * Math.PI * 2;
      const point = a => `${120 + 104 * Math.cos(a)} ${120 + 104 * Math.sin(a)}`;
      const attrs = { fill: colors[index % colors.length], stroke: '#0b0c0e', 'stroke-width': 1.5,
        'vector-effect': 'non-scaling-stroke', tabindex: 0, class: 'bank-pie-slice' };
      const path = positive.length === 1 ? svgElement('circle', { ...attrs, cx: 120, cy: 120, r: 104 })
        : svgElement('path', { ...attrs, d: `M120 120 L${point(angle)} A104 104 0 ${next - angle > Math.PI ? 1 : 0} 1 ${point(next)} Z` });
      const title = svgElement('title');
      title.textContent = `${group.key} · ${group.amount_yuan} 元 · ${group.pct}%`;
      path.append(title);
      paths.push({ path, index, category: group.key, direction: side });
      slices.append(path);
      angle = next;
    });
    svg.append(slices);
    figure.append(svg);
    const details = element('div', 'bank-pie-details');
    const legend = element('ul', 'bank-pie-legend');
    legend.setAttribute('aria-label', side === 'income' ? '收入分类金额与占比' : '分类金额与占比');
    rows.forEach(({ group, index }) => {
      const row = element('li');
      row.tabIndex = 0;
      const dot = element('i', 'bank-pie-dot');
      dot.style.backgroundColor = colors[index % colors.length];
      row.append(dot, element('span', '', group.key), element('span', 'bank-pie-value', `${group.amount_yuan} 元`),
        element('span', 'bank-pie-pct', `${group.pct}%`));
      const item = { node: row, category: group.key, direction: side };
      entries.push(item);
      const targets = [row, paths.find(p => p.direction === side && p.index === index)?.path].filter(Boolean);
      targets.forEach(node => {
        node.setAttribute('role', 'button');
        node.setAttribute('aria-label', `查看${group.key}${label}明细`);
        node.setAttribute('aria-pressed', String(isSelected(item)));
        node.onclick = () => select(group.key, false, side);
        node.onkeydown = event => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            select(group.key, true, side);
          }
        };
        node.onpointerenter = node.onfocus = () => highlight(item);
        node.onpointerleave = node.onblur = () => highlight();
      });
      legend.append(row);
    });
    details.append(legend);
    if (total != null) {
      const totalNode = element('p', 'bank-pie-total', `${label}合计`);
      totalNode.append(element('strong', '', `${total} 元`));
      details.append(totalNode);
    }
    layout.append(figure, details);
    sweep.onanimationend = () => { root.dataset.phase = 'done'; };
    return layout;
  };
  const expense = renderPie(data.groups || [], 'expense', data.total);
  const income = renderPie(data.income_groups || [], 'income', data.income_total);
  if (expense && income) {
    const pair = element('div', 'bank-pie-pair');
    pair.append(expense, income);
    root.append(pair);
  } else if (expense || income) root.append(expense || income);
  else {
    root.append(element('p', '', '该账期暂无支出分类。'));
    root.dataset.phase = 'done';
    return;
  }
  highlight();
  renderLedger(root, data, select, element);
  const focusKey = `bank-pie-focus:${data.animation_id}`;
  let needsFocus = Boolean(data.focus_id);
  try { needsFocus &&= sessionStorage.getItem(focusKey) !== data.focus_id; } catch (_) { /* optional storage */ }
  const focusTarget = needsFocus ? data.focus_target : restoreFocus;
  if (focusTarget) {
    const target = ['ledger', '交易明细，可上下滚动'].includes(focusTarget)
      ? root.querySelector('.bank-pie-ledger-scroll') || root.querySelector('.bank-pie-close')
      : paths.find(item => item.path.getAttribute('aria-label') === focusTarget)?.path;
    requestAnimationFrame(() => {
      target?.focus({ preventScroll: true });
      if (needsFocus) try { sessionStorage.setItem(focusKey, data.focus_id); } catch (_) { /* optional storage */ }
    });
  }
  const storageKey = `bank-pie-played:${data.animation_id}`;
  let played = false;
  try { played = sessionStorage.getItem(storageKey) === '1'; } catch (_) { /* storage may be unavailable */ }
  if (played || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    root.dataset.phase = 'done';
    return;
  }
  const observer = new IntersectionObserver(entries => {
    if (!entries.some(entry => entry.isIntersecting)) return;
    root.dataset.phase = 'playing';
    try { sessionStorage.setItem(storageKey, '1'); } catch (_) { /* no business state is stored */ }
    observer.disconnect();
  }, { threshold: .2 });
  observer.observe(root);
  return () => observer.disconnect();
}
