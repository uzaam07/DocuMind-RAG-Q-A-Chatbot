import { useCallback, useEffect, useRef, useState } from 'react';
import { api, askStream } from '../api/client.js';

const CUT_OFF = 'The connection closed before the answer finished. Ask again to retry.';

function fromHistory(message) {
  return {
    key: message.id,
    id: message.id,
    role: message.role,
    content: message.content,
    citations: message.citations || [],
    meta: message.meta || null,
    feedback: message.feedback || null,
    status: 'done',
    stage: null,
    error: null,
  };
}

function announcement(done) {
  if (done.not_found) return 'No answer found in the selected documents.';
  const count = done.counts?.used ?? 0;
  return `Answer ready with ${count} ${count === 1 ? 'source' : 'sources'}.`;
}

/** Message history for one session plus the streaming ask loop. */
export function useConversation(sessionId, { onFinished } = {}) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(null);
  const [streaming, setStreaming] = useState(false);
  const [announce, setAnnounce] = useState('');
  const [revealKey, setRevealKey] = useState(null);
  const [reloadTick, setReloadTick] = useState(0);
  const controllerRef = useRef(null);
  const adoptedRef = useRef(null);
  const counterRef = useRef(0);
  const finishedRef = useRef(onFinished);
  finishedRef.current = onFinished;

  useEffect(() => {
    if (sessionId && adoptedRef.current === sessionId) {
      adoptedRef.current = null;
      return undefined;
    }
    controllerRef.current?.abort();
    setRevealKey(null);
    if (!sessionId) {
      setMessages([]);
      setLoadError(null);
      setLoading(false);
      return undefined;
    }
    const controller = new AbortController();
    setMessages([]);
    setLoading(true);
    setLoadError(null);
    api
      .listMessages(sessionId, controller.signal)
      .then((list) => {
        setMessages(list.map(fromHistory));
        setLoading(false);
      })
      .catch((err) => {
        if (err.name === 'AbortError') return;
        setLoadError(err.message);
        setLoading(false);
      });
    return () => controller.abort();
  }, [sessionId, reloadTick]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  /** Marks a freshly created session so the history fetch does not wipe the live turn. */
  const adopt = useCallback((id) => {
    adoptedRef.current = id;
  }, []);

  const reload = useCallback(() => setReloadTick((tick) => tick + 1), []);

  const send = useCallback(async (id, question, { docIds, mode }) => {
    counterRef.current += 1;
    const n = counterRef.current;
    const assistantKey = `live-a-${n}`;
    const user = {
      key: `live-u-${n}`, id: null, role: 'user', content: question, citations: [], meta: null, status: 'done', stage: null, error: null,
    };
    const assistant = {
      key: assistantKey, id: null, role: 'assistant', content: '', citations: [], meta: null, status: 'streaming', stage: null, error: null,
    };
    setMessages((current) => [...current, user, assistant]);
    setStreaming(true);
    setAnnounce('');
    const controller = new AbortController();
    controllerRef.current = controller;
    const patch = (change) =>
      setMessages((current) => current.map((m) => (m.key === assistantKey ? { ...m, ...change(m) } : m)));

    let finished = false;
    try {
      await askStream(id, { question, doc_ids: docIds, mode }, controller.signal, (name, data) => {
        if (name === 'stage') patch(() => ({ stage: data.stage }));
        else if (name === 'citations') {
          patch(() => ({ citations: data.citations || [] }));
          setRevealKey(assistantKey);
        } else if (name === 'token') patch((m) => ({ content: m.content + data.text }));
        else if (name === 'done') {
          finished = true;
          patch(() => ({ id: data.message_id, content: data.answer, meta: data, status: 'done', stage: null }));
          setAnnounce(announcement(data));
        } else if (name === 'error') {
          finished = true;
          patch(() => ({ status: 'error', error: data.message, stage: null }));
          setAnnounce(`Answer failed. ${data.message}`);
        }
      });
      if (!finished) {
        patch(() => ({ status: 'error', error: CUT_OFF, stage: null }));
        setAnnounce(`Answer failed. ${CUT_OFF}`);
      }
    } catch (err) {
      if (err.name === 'AbortError') patch(() => ({ status: 'stopped', stage: null }));
      else {
        patch(() => ({ status: 'error', error: err.message, stage: null }));
        setAnnounce(`Answer failed. ${err.message}`);
      }
    } finally {
      if (controllerRef.current === controller) {
        controllerRef.current = null;
        setStreaming(false);
        finishedRef.current?.();
      }
    }
  }, []);

  const stop = useCallback(() => controllerRef.current?.abort(), []);

  /** Drops a failed turn and asks the same question again. */
  const retry = useCallback((id, assistantKey, options) => {
    const index = messages.findIndex((m) => m.key === assistantKey);
    const question = index > 0 ? messages[index - 1].content : null;
    if (!question) return;
    setMessages((current) => current.filter((_, i) => i !== index && i !== index - 1));
    send(id, question, options);
  }, [messages, send]);

  return { messages, loading, loadError, streaming, announce, revealKey, adopt, reload, send, stop, retry };
}
