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

/** Envoie la requête ; toute réponse en erreur devient une ApiError (et 401 déconnecte). */
async function send(path: string, options: { method?: string; body?: Body } = {}): Promise<Response> {
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

  if (!response.ok) {
    const error = toApiError(response.status, await response.json().catch(() => null));
    if (error.kind === "unauthorized" && token) onUnauthorized();
    throw error;
  }
  return response;
}

/** Appel JSON classique : renvoie la réponse décodée (rien pour un 204). */
export async function api<T>(path: string, options: { method?: string; body?: Body } = {}): Promise<T> {
  const response = await send(path, options);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * Télécharge un fichier protégé par le jeton (export CSV).
 * Un simple lien <a href> n'enverrait pas l'en-tête Authorization : on récupère donc
 * le fichier avec fetch, puis on le « clique » depuis la mémoire du navigateur.
 */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const blob = await (await send(path)).blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
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

export interface ThresholdStats {
  recall: number;            // part des pannes détectées (0 à 1)
  precision: number;         // part des alertes qui étaient de vraies pannes
  missed_failures: number;   // pannes manquées sur le jeu de test
  false_alarms: number;      // fausses alertes sur le jeu de test
}

/** Réglages de l'usine (GET/PUT /org/settings). */
export interface OrgSettings {
  cost_ratio: number;          // une panne manquée coûte N fois une fausse alerte
  alert_open_k: number;        // mesures hautes d'affilée pour ouvrir une alerte
  alert_close_k: number;       // mesures basses d'affilée pour la fermer
  alert_close_factor: number;  // seuil bas = facteur × seuil haut
  model_version: string;
  threshold_high: number;
  threshold_low: number;
  expected: ThresholdStats & { evaluated_on: number };
}

export type SettingsInput = Pick<OrgSettings, "cost_ratio" | "alert_open_k" | "alert_close_k" | "alert_close_factor">;

/** Aperçu sans enregistrer (GET /org/settings/preview). */
export interface ThresholdPreview extends ThresholdStats { cost_ratio: number; threshold: number; }

export type Usage = Omit<Organization, "id" | "name" | "my_role">;

export const orgApi = {
  get: () => api<Organization>("/org"),
  settings: () => api<OrgSettings>("/org/settings"),
  updateSettings: (input: SettingsInput) => api<OrgSettings>("/org/settings", { method: "PUT", body: { json: input } }),
  preview: (costRatio: number) => api<ThresholdPreview>(`/org/settings/preview?cost_ratio=${encodeURIComponent(costRatio)}`),
  /** Propriétaire seulement ; paiement simulé. */
  changePlan: (plan: Organization["plan"]) => api<Usage>("/org/plan", { method: "PUT", body: { json: { plan } } }),
};

// ---------- Modèle d'IA de l'usine (app/api/v1/models_api.py) ----------

export interface ModelJob {
  id: string;
  version: number;
  name: string;
  status: "training" | "active" | "rejected" | "failed" | "retired";
  message: string | null;     // explication écrite par le serveur (en français)
  created_at: string;
  finished_at: string | null;
}

export interface ModelsOverview { current_model: string; custom_model_allowed: boolean; history: ModelJob[]; }

export const modelsApi = {
  overview: () => api<ModelsOverview>("/org/models"),
  retrain: () => api<ModelJob>("/org/models/retrain", { method: "POST" }),
};

// ---------- Export CSV (app/api/v1/export.py, plan Pro) ----------

export const exportApi = {
  measures: () => downloadFile("/export/mesures.csv", `maintai_mesures_${today()}.csv`),
  alerts: () => downloadFile("/export/alertes.csv", `maintai_alertes_${today()}.csv`),
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

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
  /** Nouvelle clé (montrée une seule fois) ; l'ancienne cesse de fonctionner. */
  rotateKey: (id: string) =>
    api<MachineWithKey>(`/machines/${encodeURIComponent(id)}/api-key/rotate`, { method: "POST" }),
  /** Bloque la clé tout de suite (ex. boîtier volé). */
  revokeKey: (id: string) => api<Machine>(`/machines/${encodeURIComponent(id)}/api-key/revoke`, { method: "POST" }),
  /** Archive : plus de mesures acceptées, une place du plan est libérée, l'historique est gardé. */
  archive: (id: string) => api<void>(`/machines/${encodeURIComponent(id)}`, { method: "DELETE" }),
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
