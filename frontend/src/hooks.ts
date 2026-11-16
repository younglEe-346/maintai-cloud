// Petits « hooks » React partagés par plusieurs écrans.
import { useEffect, useRef } from "react";

/**
 * Appelle `load` tout de suite, puis toutes les `ms` millisecondes.
 * - pas d'appel quand l'onglet est caché (inutile de charger l'API pour rien) ;
 * - rechargement immédiat quand l'utilisateur revient sur l'onglet ;
 * - jamais deux chargements en même temps (si l'API est lente, on saute un tour).
 */
export function usePolling(load: () => Promise<void>, ms: number): void {
  const loadRef = useRef(load);
  // toujours la dernière version de `load`, sans relancer le minuteur
  useEffect(() => { loadRef.current = load; });

  useEffect(() => {
    let running = false;
    const tick = async () => {
      if (running || document.hidden) return;
      running = true;
      try { await loadRef.current(); } finally { running = false; }
    };
    void tick();
    const timer = window.setInterval(() => void tick(), ms);
    const onVisible = () => { if (!document.hidden) void tick(); };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [ms]);
}

/** Lance `fn` après `ms` millisecondes ; annulé si le composant disparaît avant. */
export function useTimeout(): (fn: () => void, ms: number) => void {
  const timers = useRef<number[]>([]);
  useEffect(() => () => timers.current.forEach((id) => window.clearTimeout(id)), []);
  return (fn, ms) => { timers.current.push(window.setTimeout(fn, ms)); };
}
