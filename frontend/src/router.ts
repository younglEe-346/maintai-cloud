// Navigation minimale, sans bibliothèque : la page courante est écrite après le # de l'adresse
// (ex. http://localhost:5173/#/machines). Le bouton « Précédent » du navigateur fonctionne,
// et recharger la page garde l'écran ouvert.
import { useEffect, useState } from "react";

export type Route = { page: "machines" } | { page: "machine"; id: string } | { page: "alerts" };

const DEFAULT_ROUTE: Route = { page: "machines" };

export function parseHash(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  switch (parts[0]) {
    case "machines": return parts[1] ? { page: "machine", id: decodeURIComponent(parts[1]) } : { page: "machines" };
    case "alerts": return { page: "alerts" };
    default: return DEFAULT_ROUTE;
  }
}

export function hrefFor(route: Route): string {
  return route.page === "machine" ? `#/machines/${encodeURIComponent(route.id)}` : `#/${route.page}`;
}

/** Entrée du menu à mettre en valeur (le détail d'une machine appartient à « Machines »). */
export function menuPage(route: Route): string {
  return route.page === "machine" ? "machines" : route.page;
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
