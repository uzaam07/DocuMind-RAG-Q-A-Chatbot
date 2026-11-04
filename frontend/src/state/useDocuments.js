import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client.js';
import { useScope } from './scope.jsx';

const POLL_MS = 1500;

function mergeDocs(current, incoming) {
  const byId = new Map(incoming.map((doc) => [doc.id, doc]));
  const kept = current.filter((doc) => !byId.has(doc.id));
  return [...incoming, ...kept].sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
}

/** Document list with polling while anything is still processing. */
export function useDocuments() {
  const scope = useScope();
  const [docs, setDocs] = useState([]);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState(null);
  const pruneRef = useRef(scope.prune);
  pruneRef.current = scope.prune;

  const load = useCallback(async (signal) => {
    try {
      const list = await api.listDocuments(signal);
      setDocs(list);
      setStatus('ready');
      setError(null);
      pruneRef.current(new Set(list.map((doc) => doc.id)));
    } catch (err) {
      if (err.name === 'AbortError') return;
      setError(err.message);
      setStatus((current) => (current === 'ready' ? 'ready' : 'error'));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const processing = docs.some((doc) => doc.status === 'processing');
  useEffect(() => {
    if (!processing) return undefined;
    const controller = new AbortController();
    const timer = setInterval(() => load(controller.signal), POLL_MS);
    return () => {
      clearInterval(timer);
      controller.abort();
    };
  }, [processing, load]);

  const retryLoad = useCallback(() => {
    setStatus('loading');
    load();
  }, [load]);

  const upload = useCallback(async (files) => {
    const created = await api.uploadDocuments(files);
    setDocs((current) => mergeDocs(current, created));
    return created;
  }, []);

  const loadSamples = useCallback(async () => {
    const created = await api.loadSampleDocuments();
    setDocs((current) => mergeDocs(current, created));
    return created;
  }, []);

  const reindex = useCallback(async (id) => {
    const updated = await api.reindexDocument(id);
    setDocs((current) => mergeDocs(current, [updated]));
  }, []);

  const remove = useCallback(async (id) => {
    await api.deleteDocument(id);
    setDocs((current) => current.filter((doc) => doc.id !== id));
    scope.prune(new Set(docs.filter((doc) => doc.id !== id).map((doc) => doc.id)));
  }, [docs, scope]);

  return { docs, status, error, retryLoad, upload, loadSamples, reindex, remove };
}
