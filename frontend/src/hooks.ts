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

const ACTIVITY_EVENTS = ["pointerdown", "pointermove", "keydown", "wheel", "touchstart"] as const;

/**
 * Appelle `onIdle` une seule fois quand l'utilisateur est resté `ms` millisecondes sans rien faire
 * (clic, souris, touche, molette, toucher). Le rafraîchissement automatique des écrans ne compte PAS comme une activité.
 * - la durée est mesurée avec l'horloge (`Date.now`) : un ordinateur mis en veille puis rouvert est déconnecté tout de suite ;
 * - ne fait rien tant que `enabled` est faux (personne n'est connecté).
 */
export function useIdleTimeout(onIdle: () => void, ms: number, enabled: boolean): void {
  const onIdleRef = useRef(onIdle);
  // toujours la dernière version de `onIdle`, sans relancer le compteur
  useEffect(() => { onIdleRef.current = onIdle; });

  useEffect(() => {
    if (!enabled) return;
    let lastActivity = Date.now();
    let fired = false;
    const check = () => {
      if (!fired && Date.now() - lastActivity >= ms) {
        fired = true;
        onIdleRef.current();
      }
    };
    const touch = () => { lastActivity = Date.now(); };
    const timer = window.setInterval(check, Math.min(ms, 1000));
    ACTIVITY_EVENTS.forEach((name) => window.addEventListener(name, touch, { passive: true }));
    document.addEventListener("visibilitychange", check);   // retour sur l'onglet après une longue absence
    return () => {
      window.clearInterval(timer);
      ACTIVITY_EVENTS.forEach((name) => window.removeEventListener(name, touch));
      document.removeEventListener("visibilitychange", check);
    };
  }, [ms, enabled]);
}
