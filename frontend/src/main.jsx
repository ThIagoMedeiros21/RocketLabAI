import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';

const examples = ['Os 15 filmes com maior faturamento em reais', 'Os 10 filmes mais populares lançados após o ano 2000', 'Quantos filmes existem no banco?'];
function format(value, column) {
  if (value === null) return 'Não informado';
  if (typeof value !== 'number') return String(value);
  if (column.endsWith('_brl')) return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
  return new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 }).format(value);
}
function App() {
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [answer, setAnswer] = useState(null);
  const [error, setError] = useState('');
  const [asked, setAsked] = useState('');
  useEffect(() => {
    if (!busy) return;
    const start = Date.now();
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [busy]);
  async function submit(event) {
    event.preventDefault();
    if (busy || !question.trim()) return;
    setBusy(true); setSeconds(0); setAnswer(null); setError(''); setAsked(question.trim());
    try {
      const response = await fetch('/api/perguntar', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pergunta: question.trim() }),
      });
      const data = await response.json().catch(() => { throw new Error('A API local não respondeu. Confira o terminal da API.'); });
      if (!response.ok) throw new Error(data.erro || 'Não foi possível consultar.');
      setAnswer(data);
    } catch (e) { setError(e.message || 'Não foi possível conectar à API local.'); }
    finally { setBusy(false); }
  }
  return <div className="layout">
    <aside><a className="brand" href="/">◉ <span>CineData<span className="brand-small">EXPLORADOR DE CINEMA</span></span></a>
      <div className="nav-active">✦ &nbsp; Explorar catálogo</div>
      <div className="aside-note"><span className="dot"/> Execução local<p>Seu catálogo, suas perguntas.<br/>Processamento na sua máquina.</p></div>
    </aside>
    <main><header><span>WORKSPACE / EXPLORAR</span><span className="badge">CineData + IA</span></header>
      <section className="intro"><span className="eyebrow">LUZ, CÂMERA, DADOS.</span><h1>Uma boa pergunta.<br/><span>Milhares de histórias.</span></h1><p>Explore filmes, bilheterias e avaliações usando suas próprias palavras.</p></section>
      <form onSubmit={submit}><label htmlFor="question">O que você quer descobrir?</label><textarea id="question" maxLength={2000} value={question} disabled={busy} onChange={e => setQuestion(e.target.value)} placeholder="Ex.: Quais filmes tiveram a maior bilheteria em reais?" required/>
        <div className="form-bottom"><span>Cada consulta é independente.</span><button disabled={busy || !question.trim()}>{busy ? 'Consultando…' : 'Consultar catálogo ↗'}</button></div></form>
      {!answer && !busy && !error && <section className="suggestions"><h2>UM PONTO DE PARTIDA</h2><div>{examples.map((text, i) => <button key={text} onClick={() => setQuestion(text)}><span>0{i + 1} ↗</span>{text}</button>)}</div></section>}
      {busy && <div role="status" className="status"><span className="spinner"/> Aguardando o agente local · {seconds}s<p>A geração pode levar alguns minutos. A resposta aparecerá aqui quando estiver pronta.</p></div>}
      {error && <div role="alert" className="error">{error}</div>}
      {answer && <section className="result"><div className="result-heading"><h2>Resultado da consulta</h2><span className="badge">{seconds}s</span></div><p className="asked">{asked}</p><p>{answer.esclarecimento || answer.resposta}</p>
        {answer.resultado && <><div className="table-wrap"><table><thead><tr>{answer.resultado.colunas.map((c, i) => <th key={i}>{c.replaceAll('_', ' ')}</th>)}</tr></thead><tbody>{answer.resultado.linhas.map((row, i) => <tr key={i}>{row.map((v, j) => <td key={j}>{format(v, answer.resultado.colunas[j])}</td>)}</tr>)}</tbody></table></div><p className="footnote">{answer.resultado.linhas.length ? `${answer.resultado.linhas.length} registros exibidos` : 'Nenhum registro encontrado.'}{answer.resultado.truncado ? ' · Existem mais registros; o resultado foi limitado.' : ''}</p></>}
        {answer.sql && <details><summary>Ver SQL executado</summary><pre>{answer.sql}</pre></details>}
      </section>}
      <footer>CINEDATA <span>Resultados do seu banco · Confira o SQL para validar a interpretação.</span></footer>
    </main></div>;
}
createRoot(document.getElementById('root')).render(<App/>);
