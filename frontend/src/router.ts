// Navigation minimale, sans bibliothèque : la page courante est écrite après le # de l'adresse
// (ex. http://localhost:5173/#/machines). Le bouton « Précédent » du navigateur fonctionne,
// et recharger la page garde l'écran ouvert.
import { useEffect, useState } from "react";

export type Route = { page: "machines" };

const DEFAULT_ROUTE: Route = { page: "machines" };

export function parseHash(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  switch (parts[0]) {
    case "machines": return { page: "machines" };
    default: return DEFAULT_ROUTE;
  }
}

export function hrefFor(route: Route): string {
  return `#/${route.page}`;
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
