const OUTCOMES = {
  answered: { label: 'Answered', help: 'One or more corpus questions directly answer this query.' },
  related_only: { label: 'Related only', help: 'Nearby material exists, but it must not be presented as an answer.' },
  unanswered: { label: 'Unanswered', help: 'No useful answered or related question exists in the corpus.' },
};

const state = {
  document: null,
  corpus: [],
  selectedId: null,
  filter: 'all',
  search: '',
  dirty: false,
  migrationPending: false,
};

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value = '') => String(value).replace(/[&<>'"]/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[char]));

function inferOutcome(item) {
  if (OUTCOMES[item.expected_outcome]) return item.expected_outcome;
  return item.expected_answers?.length ? 'answered' : 'unanswered';
}

function migrateDocument(document) {
  document.queries.forEach(item => {
    item.expected_outcome = inferOutcome(item);
    item.expected_answers ||= [];
    const hadRelatedField = Array.isArray(item.expected_related);
    item.expected_related ||= [];
    const hadOptionalAnswers = item.expected_answers.some(answer => answer.required === false);
    if (!hadRelatedField || hadOptionalAnswers || (item.expected_outcome === 'related_only' && item.expected_answers.length)) {
      state.migrationPending = true;
    }
    if (item.expected_outcome === 'related_only') {
      item.expected_related.push(...item.expected_answers.map(answer => ({ ...answer, required: false })));
      item.expected_answers = [];
    } else {
      item.expected_related.push(...item.expected_answers.filter(answer => answer.required === false).map(answer => ({ ...answer, required: false })));
      item.expected_answers = item.expected_answers.filter(answer => answer.required !== false).map(answer => ({ ...answer, required: true }));
    }
    item.description ||= '';
  });
  return document;
}

function markDirty() {
  state.dirty = true;
  $('#save-button').disabled = false;
  $('#save-state').textContent = 'Unsaved changes';
  renderSummary();
}

function toast(message, isError = false) {
  const node = $('#toast');
  node.textContent = message;
  node.className = `toast show${isError ? ' error' : ''}`;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.className = 'toast', 4200);
}

function renderSummary() {
  const queries = state.document?.queries || [];
  const count = outcome => queries.filter(item => item.expected_outcome === outcome).length;
  $('#summary').innerHTML = [
    ['Total tests', queries.length],
    ['Answered', count('answered')],
    ['Related only', count('related_only')],
    ['Unanswered', count('unanswered')],
  ].map(([label, value]) => `<div class="stat"><strong>${value}</strong><span>${label}</span></div>`).join('');
}

function renderFilters() {
  $('#outcome-filters').innerHTML = ['all', ...Object.keys(OUTCOMES)].map(value => {
    const label = value === 'all' ? 'All' : OUTCOMES[value].label;
    return `<button class="filter ${state.filter === value ? 'active' : ''}" data-filter="${value}">${label}</button>`;
  }).join('');
  document.querySelectorAll('[data-filter]').forEach(button => button.onclick = () => {
    state.filter = button.dataset.filter;
    renderFilters();
    renderList();
  });
}

function filteredQueries() {
  const needle = state.search.toLowerCase();
  return state.document.queries.filter(item =>
    (state.filter === 'all' || item.expected_outcome === state.filter) &&
    (!needle || item.query.toLowerCase().includes(needle) || item.description.toLowerCase().includes(needle))
  );
}

function renderList() {
  const items = filteredQueries();
  $('#query-list').innerHTML = items.length ? items.map(item => `
    <button class="query-row ${item.id === state.selectedId ? 'active' : ''}" data-id="${escapeHtml(item.id)}">
      <span class="badge ${item.expected_outcome}">${OUTCOMES[item.expected_outcome].label}</span>
      <p>${escapeHtml(item.query)}</p>
    </button>
  `).join('') : '<div class="empty-state"><p>No matching tests.</p></div>';
  document.querySelectorAll('.query-row').forEach(row => row.onclick = () => {
    state.selectedId = row.dataset.id;
    renderList();
    renderEditor();
  });
}

function selectedQuery() {
  return state.document.queries.find(item => item.id === state.selectedId);
}

function renderEditor() {
  const item = selectedQuery();
  if (!item) {
    $('#editor').className = 'editor empty';
    $('#editor').innerHTML = '<div class="empty-state"><h2>Select a test question</h2><p>Classify what search should do, then select expected matches from the source corpus.</p></div>';
    return;
  }
  const hasMatchesWarning = (item.expected_outcome === 'answered' && item.expected_answers.length === 0) ||
    (item.expected_outcome === 'related_only' && item.expected_related.length === 0);
  $('#editor').className = 'editor';
  $('#editor').innerHTML = `
    <div class="editor-header">
      <div><p class="eyebrow">${escapeHtml(item.id)}</p><h2>Edit expected behavior</h2></div>
      <button id="delete-query" class="danger">Delete test</button>
    </div>
    <div class="form-grid">
      <div class="field full-span"><label for="question-text">User question</label><textarea id="question-text">${escapeHtml(item.query)}</textarea></div>
      <div class="field full-span"><label for="description">Evaluator note</label><input id="description" value="${escapeHtml(item.description)}" placeholder="What behavior does this test protect?" /></div>
      <div class="field full-span"><span class="label">Expected search outcome</span><div class="outcome-options">
        ${Object.entries(OUTCOMES).map(([value, meta]) => `<button class="outcome-card ${item.expected_outcome === value ? 'selected' : ''}" data-outcome="${value}"><strong>${meta.label}</strong><span>${meta.help}</span></button>`).join('')}
      </div></div>
    </div>
    ${item.expected_outcome !== 'unanswered' ? `
      <div class="matches">
        <div class="matches-header">
          <div><h3>${item.expected_outcome === 'answered' ? 'Expected answers' : 'Related questions'}</h3><p class="helper">Search the curated corpus and add the questions search should retrieve.</p></div>
          <div class="corpus-search-wrap">
            <div class="search-controls"><input id="corpus-search" type="search" placeholder="Search 519 corpus questions…" autocomplete="off" /><button id="semantic-search" class="semantic-button" title="Use GPT-5.6 Sol for semantic ranking">Search with Sol</button></div>
            <div id="semantic-status" class="semantic-status"></div><div id="corpus-results"></div>
          </div>
        </div>
        <div id="answer-match-section" class="match-section"><h4>Expected answers</h4><p class="helper">Direct answers that search should return as answers.</p><div id="answer-match-list" class="match-list"></div></div>
        <div id="related-match-section" class="match-section"><h4>Related</h4><p class="helper">Relevant questions that should appear as related, not as answers.</p><div id="related-match-list" class="match-list"></div></div>
        ${hasMatchesWarning ? `<div class="warning">${item.expected_outcome === 'answered' ? 'Answered tests need at least one expected answer' : 'Related-only tests need at least one related question'} before saving.</div>` : ''}
      </div>` : '<div class="warning">Unanswered means neither a direct answer nor a useful related question should be returned.</div>'}
  `;

  $('#question-text').oninput = event => { item.query = event.target.value; markDirty(); renderList(); };
  $('#description').oninput = event => { item.description = event.target.value; markDirty(); };
  $('#delete-query').onclick = () => {
    if (!confirm(`Delete “${item.query}”?`)) return;
    state.document.queries = state.document.queries.filter(query => query.id !== item.id);
    state.selectedId = null;
    markDirty(); renderSummary(); renderList(); renderEditor();
  };
  document.querySelectorAll('[data-outcome]').forEach(button => button.onclick = () => {
    item.expected_outcome = button.dataset.outcome;
    if (item.expected_outcome === 'unanswered') {
      item.expected_answers = [];
      item.expected_related = [];
    } else if (item.expected_outcome === 'related_only') {
      item.expected_related.push(...item.expected_answers.map(answer => ({ ...answer, required: false })));
      item.expected_answers = [];
    }
    markDirty(); renderSummary(); renderFilters(); renderList(); renderEditor();
  });
  if (item.expected_outcome !== 'unanswered') {
    renderMatches(item);
    $('#corpus-search').oninput = event => renderCorpusResults(item, event.target.value);
    $('#corpus-search').onfocus = event => renderCorpusResults(item, event.target.value);
    $('#semantic-search').onclick = () => runSemanticSearch(item);
  }
}

async function runSemanticSearch(item) {
  const button = $('#semantic-search');
  const input = $('#corpus-search');
  const status = $('#semantic-status');
  const question = input.value.trim() || item.query.trim();
  if (!question) { toast('Enter a question to search for.', true); return; }
  input.value = question;
  button.disabled = true;
  button.textContent = 'Searching…';
  status.className = 'semantic-status working';
  status.textContent = 'GPT-5.6 Sol is ranking the corpus…';
  $('#corpus-results').className = '';
  $('#corpus-results').innerHTML = '';
  try {
    const response = await fetch('/api/semantic-search', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question })
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Semantic search failed');
    renderSemanticResults(item, result.matches || []);
    status.className = 'semantic-status success';
    status.textContent = `${result.matches.length} AI-ranked match${result.matches.length === 1 ? '' : 'es'} from ${result.model}.`;
  } catch (error) {
    status.className = 'semantic-status error';
    status.textContent = `Sol search failed: ${error.message} Showing local matches instead.`;
    toast(error.message, true);
    renderCorpusResults(item, question);
  } finally {
    button.disabled = false;
    button.textContent = 'Search with Sol';
  }
}

function renderSemanticResults(item, matches) {
  const node = $('#corpus-results');
  const selected = new Set([...item.expected_answers, ...item.expected_related].map(answer => answer.question));
  const available = matches.filter(match => !selected.has(match.question));
  node.className = 'corpus-results semantic-results';
  node.innerHTML = available.length
    ? available.map(match => `<button class="corpus-option" data-corpus-index="${match.index}"><span class="ai-badge">Sol</span>${escapeHtml(match.question)}</button>`).join('')
    : '<div class="corpus-empty">Sol found no additional meaningful matches.</div>';
  bindCorpusOptions(item);
}

function renderMatches(item) {
  const answerSection = $('#answer-match-section');
  const answerList = $('#answer-match-list');
  const relatedList = $('#related-match-list');
  answerSection.style.display = item.expected_outcome === 'answered' ? '' : 'none';
  answerList.innerHTML = item.expected_answers.length ? item.expected_answers.map((answer, index) => `
    <div class="match-row">
      <div class="match-question">${escapeHtml(answer.question)}</div>
      <input class="compact rank" data-index="${index}" type="number" min="1" value="${answer.min_rank || index + 1}" title="Maximum acceptable rank" />
      <label class="required-wrap"><input class="required" data-kind="answer" data-index="${index}" type="checkbox" checked /> Required</label>
      <button class="icon-button remove-match" data-kind="answer" data-index="${index}" title="Remove">×</button>
    </div>
  `).join('') : '<p class="helper">No direct answers selected yet.</p>';
  relatedList.innerHTML = item.expected_related.length ? item.expected_related.map((answer, index) => `
    <div class="match-row related-match-row">
      <div class="match-question">${escapeHtml(answer.question)}</div>
      <input class="compact related-rank" data-index="${index}" type="number" min="1" value="${answer.min_rank || index + 1}" title="Maximum acceptable related rank" />
      <label class="required-wrap"><input class="required" data-kind="related" data-index="${index}" type="checkbox" /> Required</label>
      <button class="icon-button remove-match" data-kind="related" data-index="${index}" title="Remove">×</button>
    </div>
  `).join('') : '<p class="helper">No related questions selected yet.</p>';
  document.querySelectorAll('.rank').forEach(input => input.onchange = () => {
    item.expected_answers[Number(input.dataset.index)].min_rank = Math.max(1, Number(input.value) || 1); markDirty();
  });
  document.querySelectorAll('.related-rank').forEach(input => input.onchange = () => {
    item.expected_related[Number(input.dataset.index)].min_rank = Math.max(1, Number(input.value) || 1); markDirty();
  });
  document.querySelectorAll('.required').forEach(input => input.onchange = () => {
    const index = Number(input.dataset.index);
    if (input.dataset.kind === 'answer' && !input.checked) {
      const [answer] = item.expected_answers.splice(index, 1);
      item.expected_related.push({ ...answer, required: false });
    } else if (input.dataset.kind === 'related' && input.checked) {
      const [answer] = item.expected_related.splice(index, 1);
      item.expected_answers.push({ ...answer, required: true });
    }
    markDirty(); renderEditor();
  });
  document.querySelectorAll('.remove-match').forEach(button => button.onclick = () => {
    const collection = button.dataset.kind === 'answer' ? item.expected_answers : item.expected_related;
    collection.splice(Number(button.dataset.index), 1); markDirty(); renderEditor();
  });
}

function renderCorpusResults(item, term) {
  const node = $('#corpus-results');
  const needle = normalizeSearchText(term);
  if (needle.length < 2) { node.className = ''; node.innerHTML = ''; return; }
  const selected = new Set([...item.expected_answers, ...item.expected_related].map(answer => answer.question));
  const results = state.corpus
    .filter(candidate => !selected.has(candidate.question))
    .map(candidate => ({ candidate, score: corpusMatchScore(needle, candidate.question) }))
    .filter(result => result.score > 0)
    .sort((left, right) => right.score - left.score || left.candidate.question.length - right.candidate.question.length)
    .slice(0, 12);
  node.className = 'corpus-results';
  node.innerHTML = results.length
    ? results.map(({ candidate }) => `<button class="corpus-option" data-corpus-index="${state.corpus.indexOf(candidate)}">${escapeHtml(candidate.question)}</button>`).join('')
    : '<div class="corpus-empty">No likely corpus matches. Try two or three important words.</div>';
  bindCorpusOptions(item);
}

function bindCorpusOptions(item) {
  document.querySelectorAll('.corpus-option').forEach(button => button.onclick = () => {
    const candidate = state.corpus[Number(button.dataset.corpusIndex)];
    if (item.expected_outcome === 'related_only') {
      item.expected_related.push({ question: candidate.question, url_pattern: 'youtube.com', min_rank: item.expected_related.length + 1, required: false });
    } else {
      item.expected_answers.push({ question: candidate.question, url_pattern: 'youtube.com', min_rank: item.expected_answers.length + 1, required: true });
    }
    item.max_results_to_check = Math.max(item.max_results_to_check || 0, item.expected_answers.length + item.expected_related.length);
    item.min_relevant_count = item.expected_answers.length;
    markDirty(); renderEditor();
  });
}

const SEARCH_STOPWORDS = new Set([
  'a', 'an', 'and', 'are', 'as', 'at', 'be', 'can', 'do', 'does', 'for', 'from',
  'how', 'i', 'if', 'in', 'is', 'it', 'of', 'on', 'or', 'that', 'the', 'there',
  'this', 'to', 'was', 'what', 'when', 'where', 'which', 'who', 'why', 'with', 'you'
]);

const SEARCH_SYNONYMS = {
  proof: ['know', 'evidence', 'demonstrate'],
  know: ['proof', 'evidence'],
  real: ['reality', 'true', 'truth'],
  reality: ['real', 'true', 'truth'],
};

function normalizeSearchText(value) {
  return String(value).toLowerCase().normalize('NFKD').replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
}

function meaningfulTokens(value) {
  return [...new Set(normalizeSearchText(value).split(' ').filter(token => token.length > 1 && !SEARCH_STOPWORDS.has(token)))];
}

function corpusMatchScore(normalizedQuery, question) {
  const normalizedQuestion = normalizeSearchText(question);
  if (normalizedQuestion.includes(normalizedQuery)) return 1000 + normalizedQuery.length;

  const queryTokens = meaningfulTokens(normalizedQuery);
  const questionTokens = meaningfulTokens(normalizedQuestion);
  if (!queryTokens.length) return 0;

  let matched = 0;
  let score = 0;
  for (const queryToken of queryTokens) {
    let best = 0;
    const alternatives = new Set([queryToken, ...(SEARCH_SYNONYMS[queryToken] || [])]);
    for (const questionToken of questionTokens) {
      if (queryToken === questionToken) best = Math.max(best, 8);
      else if (alternatives.has(questionToken)) best = Math.max(best, 7);
      else if (queryToken.length >= 4 && questionToken.length >= 4 &&
        (queryToken.startsWith(questionToken) || questionToken.startsWith(queryToken))) best = Math.max(best, 5);
    }
    if (best) matched += 1;
    score += best;
  }

  const coverage = matched / queryTokens.length;
  if (matched === 0 || (queryTokens.length > 2 && coverage < 0.25)) return 0;
  return score + coverage * 20 + (matched >= 2 ? 6 : 0);
}

function nextId() {
  const used = new Set(state.document.queries.map(item => item.id));
  let number = 1;
  while (used.has(`q${number}`)) number += 1;
  return `q${number}`;
}

async function save() {
  const invalid = state.document.queries.find(item => !item.query.trim() ||
    (item.expected_outcome === 'answered' && !item.expected_answers.length) ||
    (item.expected_outcome === 'related_only' && !item.expected_related.length));
  if (invalid) { state.selectedId = invalid.id; renderList(); renderEditor(); toast('Fix the highlighted incomplete test before saving.', true); return; }
  $('#save-button').disabled = true;
  $('#save-state').textContent = 'Saving…';
  state.document.queries.forEach(item => {
    item.expected_answers = item.expected_answers.map(answer => ({ ...answer, required: true }));
    item.expected_related = item.expected_related.map(answer => ({ ...answer, required: false }));
    item.min_relevant_count = item.expected_outcome === 'answered' ? item.expected_answers.length : 0;
    item.max_results_to_check = item.expected_outcome === 'unanswered' ? 0 : item.expected_answers.length + item.expected_related.length;
  });
  try {
    const response = await fetch('/api/golden-set', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(state.document) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.details?.join(' ') || result.error || 'Save failed');
    state.dirty = false;
    $('#save-state').textContent = 'All changes saved';
    toast('Golden set saved. A timestamped backup was created.');
  } catch (error) {
    $('#save-button').disabled = false;
    $('#save-state').textContent = 'Save failed';
    toast(error.message, true);
  }
}

async function init() {
  try {
    const [documentResponse, corpusResponse] = await Promise.all([fetch('/api/golden-set'), fetch('/api/corpus')]);
    state.document = migrateDocument(await documentResponse.json());
    state.corpus = await corpusResponse.json();
    renderSummary(); renderFilters(); renderList();
    if (state.migrationPending) {
      markDirty();
      $('#save-state').textContent = 'Ready to save Related migration';
    } else {
      $('#save-state').textContent = 'No unsaved changes';
      $('#save-button').disabled = true;
    }
  } catch (error) {
    toast(`Could not load editor data: ${error.message}`, true);
  }
}

$('#query-filter').oninput = event => { state.search = event.target.value; renderList(); };
$('#add-query').onclick = () => {
  const item = { id: nextId(), query: '', description: '', expected_outcome: 'answered', expected_answers: [], expected_related: [], min_relevant_count: 0, max_results_to_check: 0 };
  state.document.queries.push(item); state.selectedId = item.id; state.filter = 'all'; markDirty(); renderSummary(); renderFilters(); renderList(); renderEditor();
  setTimeout(() => $('#question-text')?.focus(), 0);
};
$('#save-button').onclick = save;
window.addEventListener('beforeunload', event => { if (state.dirty) { event.preventDefault(); event.returnValue = ''; } });
init();
