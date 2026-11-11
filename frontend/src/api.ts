// Tous les appels à l'API FastAPI passent par ce fichier.
// - l'adresse de l'API vient de VITE_API_URL (fichier .env), sinon http://localhost:8000/api/v1 ;
// - le jeton JWT est gardé dans le navigateur (localStorage) et ajouté à chaque requête ;
// - toute erreur devient une ApiError avec un code clair, traduit ensuite par l'interface.

export const API_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

const TOKEN_KEY = "maintai.token";

export const tokenStore = {
  get(): string | null {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set(token: string): void {
    try { localStorage.setItem(TOKEN_KEY, token); } catch { /* navigateur privé : session non conservée */ }
  },
  clear(): void {
    try { localStorage.removeItem(TOKEN_KEY); } catch { /* rien à faire */ }
  },
};

/** Erreur d'un champ renvoyée par FastAPI (code 422). */
export interface FieldError { field: string; message: string; }

/** Erreur lisible : `kind` choisit le message traduit, `detail` est le texte du serveur. */
export class ApiError extends Error {
  kind: "network" | "unauthorized" | "forbidden" | "notFound" | "conflict" | "validation" | "quota" | "server" | "other";
  status: number;
  detail: string;
  fields: FieldError[];

  constructor(status: number, detail: string, fields: FieldError[] = []) {
    super(detail || `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
    this.fields = fields;
    this.kind =
      status === 0 ? "network"
      : status === 401 ? "unauthorized"
      : status === 403 ? "forbidden"
      : status === 404 ? "notFound"
      : status === 409 || status === 410 ? "conflict"
      : status === 422 ? "validation"
      : status === 402 || status === 429 ? "quota"
      : status >= 500 ? "server"
      : "other";
  }
}

/** Appelé quand le serveur répond 401 (jeton expiré) : l'application déconnecte l'utilisateur. */
let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(handler: () => void): void { onUnauthorized = handler; }

type Body = { json: unknown } | { form: Record<string, string> } | undefined;

export async function api<T>(path: string, options: { method?: string; body?: Body } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = tokenStore.get();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (options.body && "json" in options.body) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body.json);
  } else if (options.body && "form" in options.body) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    body = new URLSearchParams(options.body.form).toString();
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { method: options.method ?? "GET", headers, body });
  } catch {
    // API éteinte, mauvaise adresse ou origine refusée par le CORS
    throw new ApiError(0, "");
  }

  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = toApiError(response.status, data);
    if (error.kind === "unauthorized" && token) onUnauthorized();
    throw error;
  }
  return data as T;
}

function toApiError(status: number, data: unknown): ApiError {
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return new ApiError(status, detail);
  if (Array.isArray(detail)) {
    // Format FastAPI : [{ loc: ["body", "password"], msg: "..." }, ...]
    const fields = detail.map((d: { loc?: unknown[]; msg?: string }) => ({
      field: String(d.loc?.[d.loc.length - 1] ?? ""),
      message: d.msg ?? "",
    }));
    return new ApiError(status, "", fields);
  }
  return new ApiError(status, "");
}

// ---------- Types et appels de l'authentification (app/api/v1/auth.py) ----------

export interface Token { access_token: string; token_type: string; }

export interface Me {
  id: string;
  email: string;
  full_name: string | null;
  role: "owner" | "admin" | "member";
  is_superadmin: boolean;
  organization: { id: string; name: string; plan: "FREE" | "PRO" } | null;
}

export interface RegisterInput { org_name: string; full_name: string; email: string; password: string; }

export const authApi = {
  /** POST /auth/login : formulaire OAuth2, username = e-mail. */
  login: (email: string, password: string) =>
    api<Token>("/auth/login", { method: "POST", body: { form: { username: email, password } } }),
  /** POST /auth/register : crée l'usine (plan Gratuit) et son propriétaire. */
  register: (input: RegisterInput) =>
    api<Token>("/auth/register", { method: "POST", body: { json: input } }),
  /** GET /auth/me : qui est connecté. */
  me: () => api<Me>("/auth/me"),
};

// ---------- Usine : plan et consommation (app/api/v1/organization.py) ----------

export interface Organization {
  id: string;
  name: string;
  my_role: Me["role"];
  plan: "FREE" | "PRO";
  plan_label: string;
  limits: { max_machines: number; max_measures_per_day: number; custom_model: boolean; export: boolean };
  machines: number;        // machines actives
  measures_today: number;
}

export const orgApi = {
  get: () => api<Organization>("/org"),
};

export type FailureMode = "TWF" | "HDF" | "PWF" | "OSF" | "RNF";

// ---------- Machines (app/api/v1/machines.py, schémas MachineResponse / MachineWithKey) ----------

export interface Machine {
  id: string;
  name: string;
  status: "ACTIVE" | "ARCHIVED";
  created_at: string;
  api_key_prefix: string;          // début de la clé, pour la reconnaître
  api_key_created_at: string | null;
  api_key_revoked_at: string | null;
}

/** Réponse de création : la seule fois où la clé complète est envoyée. */
export interface MachineWithKey extends Machine { api_key: string; warning: string; }

/** Les 5 mesures envoyées par une machine (app/ml/features.py, RAW_FEATURES). */
export const SENSORS = ["air_temp", "process_temp", "rotational_speed", "torque", "tool_wear"] as const;
export type Sensor = typeof SENSORS[number];

export interface Prediction {
  risk_score: number;               // 0 à 1
  decision: boolean;                // vrai si risque >= seuil
  threshold: number;
  model_version: string;
  probable_mode: FailureMode | null;                           // seulement si décision = alerte
  mode_probabilities: Partial<Record<FailureMode, number>> | null;
  flagged_modes: FailureMode[] | null;                         // modes au-dessus de leur propre seuil
  explanation: string | null;
  contributions: Record<Sensor, number> | null;                // + = fait monter le risque
  base_risk: number | null;                                    // risque d'une machine normale
  reference: Record<Sensor, number> | null;                    // valeurs normales
}

export interface Measure extends Record<Sensor, number> {
  id: string;
  message_id: string;
  timestamp: string;
  label_failure: boolean | null;
  label_modes: FailureMode[] | null;
  prediction: Prediction | null;    // null tant que le worker n'a pas calculé
}

export const machinesApi = {
  list: () => api<Machine[]>("/machines"),
  /** Dernières mesures, les plus récentes d'abord, avec leur prédiction. */
  measures: (id: string, limit = 200) =>
    api<Measure[]>(`/machines/${encodeURIComponent(id)}/mesures?limit=${limit}`),
  create: (name: string) => api<MachineWithKey>("/machines", { method: "POST", body: { json: { name } } }),
};

// ---------- Alertes (app/api/v1/alerts.py, schéma AlertResponse) ----------

export interface Alert {
  id: string;
  machine_id: string;
  status: "OPEN" | "ACKNOWLEDGED" | "CLOSED";
  risk_score: number;              // risque à l'ouverture (0 à 1)
  peak_risk_score: number | null;  // risque maximal pendant l'alerte
  last_risk_score: number | null;  // dernier risque reçu
  probable_mode: FailureMode | null;
  details: string | null;          // explication écrite par le worker (en français)
  model_version: string | null;
  created_at: string;
  closed_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by_name: string | null;
  ack_comment: string | null;
}

export const alertsApi = {
  /** status=active : ouvertes ou acquittées ; CLOSED : historique. */
  list: (status: "active" | "CLOSED", limit = 50) =>
    api<Alert[]>(`/alerts?status=${status}&limit=${limit}`),
  /** Le nom de la personne qui acquitte vient de son compte (côté API), seul le commentaire est envoyé. */
  acknowledge: (id: string, comment: string) =>
    api<Alert>(`/alerts/${encodeURIComponent(id)}/acknowledge`, { method: "POST", body: { json: { comment } } }),
};

/** L'API renvoie des dates UTC sans fuseau ("2026-11-10T23:31:00") : on ajoute le Z. */
export function parseApiDate(value: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`);
}
