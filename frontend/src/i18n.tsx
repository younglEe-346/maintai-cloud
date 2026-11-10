// Traductions français / anglais, sans bibliothèque : un dictionnaire par langue.
// Ajouter un texte = ajouter la même clé dans `fr` et dans `en` (TypeScript vérifie).
import { createContext, useContext, useState, type ReactNode } from "react";
import { ApiError } from "./api";

const fr = {
  "app.name": "MaintAI Cloud",
  "app.tagline": "Maintenance prédictive pour vos machines",
  "lang.switch": "English",
  "common.loading": "Chargement…",
  "common.retry": "Réessayer",
  "common.serverSays": "Message du serveur :",

  "auth.loginTab": "Se connecter",
  "auth.registerTab": "Créer une usine",
  "auth.loginTitle": "Connexion",
  "auth.loginHelp": "Entrez l'e-mail et le mot de passe de votre compte.",
  "auth.registerTitle": "Inscrire votre usine",
  "auth.registerHelp": "Vous créez l'espace de votre usine (plan Gratuit) et vous en devenez le propriétaire. Vous pourrez inviter votre équipe ensuite.",
  "auth.orgName": "Nom de l'usine",
  "auth.orgNameHint": "2 à 100 caractères, unique sur la plateforme.",
  "auth.fullName": "Votre nom complet",
  "auth.email": "E-mail",
  "auth.password": "Mot de passe",
  "auth.passwordHint": "8 caractères minimum.",
  "auth.passwordConfirm": "Confirmer le mot de passe",
  "auth.submitLogin": "Se connecter",
  "auth.submitRegister": "Créer mon usine",
  "auth.submitting": "Envoi…",
  "auth.noAccount": "Pas encore de compte ?",
  "auth.haveAccount": "Déjà un compte ?",
  "auth.invited": "Invité par votre équipe ? Utilisez le lien reçu par e-mail.",
  "auth.logout": "Se déconnecter",
  "auth.sessionExpired": "Votre session a expiré : reconnectez-vous.",

  "valid.required": "Ce champ est obligatoire.",
  "valid.email": "Adresse e-mail invalide.",
  "valid.orgName": "Le nom doit faire entre 2 et 100 caractères.",
  "valid.password": "Le mot de passe doit faire au moins 8 caractères.",
  "valid.passwordMatch": "Les deux mots de passe ne sont pas identiques.",

  "home.superadminTitle": "Compte super-administrateur",
  "home.superadminText": "Ce compte n'appartient à aucune usine. Pour suivre les usines et les workers, utilisez pour l'instant le tableau de bord Streamlit (http://localhost:8501).",
  "role.owner": "propriétaire",
  "role.admin": "administrateur",
  "role.member": "membre",
  "plan.FREE": "Gratuit",
  "plan.PRO": "Pro",

  "nav.machines": "Machines",
  "header.org": "{org} · {role}",

  "machines.title": "Machines",
  "machines.intro": "Chaque machine de l'usine envoie ses mesures à MaintAI avec sa propre clé d'API.",
  "machines.usage": "{count} / {max} machines actives (plan {plan})",
  "machines.limitReached": "Limite de votre plan atteinte : archivez une machine ou passez au plan Pro pour en ajouter.",
  "machines.addTitle": "Ajouter une machine",
  "machines.name": "Nom de la machine",
  "machines.nameHint": "Par exemple « Tour CN 1 » ou « Fraiseuse atelier B ».",
  "machines.nameTooLong": "100 caractères maximum.",
  "machines.add": "Ajouter",
  "machines.adding": "Ajout…",
  "machines.memberOnly": "Seuls le propriétaire et les administrateurs peuvent ajouter des machines.",
  "machines.emptyTitle": "Aucune machine pour l'instant",
  "machines.emptyText": "Ajoutez votre première machine avec le formulaire ci-dessus. Vous recevrez une clé d'API : c'est elle que le capteur (ou le simulateur) utilise pour envoyer les mesures.",
  "machines.emptyMember": "Un propriétaire ou un administrateur de l'usine doit d'abord en ajouter une.",
  "machines.listTitle": "Machines de l'usine",
  "machines.colName": "Nom",
  "machines.colStatus": "État",
  "machines.colKey": "Clé d'API",
  "machines.colCreated": "Ajoutée le",
  "machines.keyHelp": "Seul le début de chaque clé est affiché : la clé complète n'est jamais conservée.",
  "status.ACTIVE": "Active",
  "status.ARCHIVED": "Archivée",
  "key.active": "en service",
  "key.revoked": "révoquée",

  "newKey.title": "Machine « {name} » ajoutée",
  "newKey.label": "Clé d'API",
  "newKey.warning": "Copiez cette clé maintenant : elle ne sera plus jamais affichée. Si vous la perdez, il faudra en créer une nouvelle.",
  "newKey.copy": "Copier",
  "newKey.copied": "Copiée !",
  "newKey.copyFailed": "Copie impossible : sélectionnez la clé puis Ctrl+C.",
  "newKey.howTo": "La machine l'envoie dans l'en-tête x-api-key de chaque lot de mesures (POST /api/v1/mesures).",
  "newKey.confirm": "J'ai copié la clé et je l'ai rangée en lieu sûr.",
  "newKey.close": "Fermer",

  "error.network": "Impossible de joindre l'API. Vérifiez qu'elle est lancée (docker compose up -d) et qu'elle autorise cette adresse (ALLOWED_ORIGINS).",
  "error.unauthorized": "Vous n'êtes pas connecté ou votre session a expiré.",
  "error.forbidden": "Votre rôle ne permet pas cette action.",
  "error.notFound": "Élément introuvable.",
  "error.conflict": "Cette action est en conflit avec l'état actuel.",
  "error.validation": "Certains champs ne sont pas valides.",
  "error.quota": "La limite de votre plan est atteinte.",
  "error.server": "Erreur du serveur. Réessayez dans un instant.",
  "error.other": "La requête a échoué.",
};

type Key = keyof typeof fr;

const en: Record<Key, string> = {
  "app.name": "MaintAI Cloud",
  "app.tagline": "Predictive maintenance for your machines",
  "lang.switch": "Français",
  "common.loading": "Loading…",
  "common.retry": "Try again",
  "common.serverSays": "Server message:",

  "auth.loginTab": "Sign in",
  "auth.registerTab": "Create a factory",
  "auth.loginTitle": "Sign in",
  "auth.loginHelp": "Enter your account e-mail and password.",
  "auth.registerTitle": "Register your factory",
  "auth.registerHelp": "You create your factory's space (Free plan) and become its owner. You can invite your team afterwards.",
  "auth.orgName": "Factory name",
  "auth.orgNameHint": "2 to 100 characters, unique on the platform.",
  "auth.fullName": "Your full name",
  "auth.email": "E-mail",
  "auth.password": "Password",
  "auth.passwordHint": "At least 8 characters.",
  "auth.passwordConfirm": "Confirm password",
  "auth.submitLogin": "Sign in",
  "auth.submitRegister": "Create my factory",
  "auth.submitting": "Sending…",
  "auth.noAccount": "No account yet?",
  "auth.haveAccount": "Already have an account?",
  "auth.invited": "Invited by your team? Use the link you received by e-mail.",
  "auth.logout": "Sign out",
  "auth.sessionExpired": "Your session has expired: please sign in again.",

  "valid.required": "This field is required.",
  "valid.email": "Invalid e-mail address.",
  "valid.orgName": "The name must be 2 to 100 characters long.",
  "valid.password": "The password must be at least 8 characters long.",
  "valid.passwordMatch": "The two passwords do not match.",

  "home.superadminTitle": "Super-administrator account",
  "home.superadminText": "This account does not belong to any factory. To monitor factories and workers, use the Streamlit dashboard for now (http://localhost:8501).",
  "role.owner": "owner",
  "role.admin": "administrator",
  "role.member": "member",
  "plan.FREE": "Free",
  "plan.PRO": "Pro",

  "nav.machines": "Machines",
  "header.org": "{org} · {role}",

  "machines.title": "Machines",
  "machines.intro": "Each machine in the factory sends its measurements to MaintAI with its own API key.",
  "machines.usage": "{count} / {max} active machines ({plan} plan)",
  "machines.limitReached": "Your plan's limit is reached: archive a machine or upgrade to the Pro plan to add more.",
  "machines.addTitle": "Add a machine",
  "machines.name": "Machine name",
  "machines.nameHint": "For example \"CNC lathe 1\" or \"Milling machine, shop B\".",
  "machines.nameTooLong": "100 characters maximum.",
  "machines.add": "Add",
  "machines.adding": "Adding…",
  "machines.memberOnly": "Only the owner and administrators can add machines.",
  "machines.emptyTitle": "No machines yet",
  "machines.emptyText": "Add your first machine with the form above. You will get an API key: the sensor (or the simulator) uses it to send measurements.",
  "machines.emptyMember": "An owner or administrator of the factory must add one first.",
  "machines.listTitle": "Factory machines",
  "machines.colName": "Name",
  "machines.colStatus": "Status",
  "machines.colKey": "API key",
  "machines.colCreated": "Added on",
  "machines.keyHelp": "Only the start of each key is shown: the full key is never stored.",
  "status.ACTIVE": "Active",
  "status.ARCHIVED": "Archived",
  "key.active": "in use",
  "key.revoked": "revoked",

  "newKey.title": "Machine \"{name}\" added",
  "newKey.label": "API key",
  "newKey.warning": "Copy this key now: it will never be shown again. If you lose it, you will have to create a new one.",
  "newKey.copy": "Copy",
  "newKey.copied": "Copied!",
  "newKey.copyFailed": "Copy failed: select the key and press Ctrl+C.",
  "newKey.howTo": "The machine sends it in the x-api-key header of each batch of measurements (POST /api/v1/mesures).",
  "newKey.confirm": "I have copied the key and stored it somewhere safe.",
  "newKey.close": "Close",

  "error.network": "Cannot reach the API. Check that it is running (docker compose up -d) and that it allows this address (ALLOWED_ORIGINS).",
  "error.unauthorized": "You are not signed in or your session has expired.",
  "error.forbidden": "Your role does not allow this action.",
  "error.notFound": "Item not found.",
  "error.conflict": "This action conflicts with the current state.",
  "error.validation": "Some fields are not valid.",
  "error.quota": "Your plan's limit has been reached.",
  "error.server": "Server error. Please try again in a moment.",
  "error.other": "The request failed.",
};

// Messages connus de l'API (écrits en français) traduits en anglais.
const SERVER_MESSAGES_EN: Record<string, string> = {
  "E-mail ou mot de passe incorrect": "Incorrect e-mail or password",
  "Cet e-mail est déjà utilisé": "This e-mail is already in use",
  "Ce nom d'usine est déjà utilisé": "This factory name is already in use",
  "Identifiants invalides ou session expirée": "Invalid credentials or expired session",
  "Machine introuvable": "Machine not found",
};

export type Lang = "fr" | "en";
const DICTS: Record<Lang, Record<Key, string>> = { fr, en };
const LANG_KEY = "maintai.lang";

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(LANG_KEY);
    if (saved === "fr" || saved === "en") return saved;
  } catch { /* stockage indisponible */ }
  return navigator.language.toLowerCase().startsWith("fr") ? "fr" : "en";
}

interface I18n {
  lang: Lang;
  setLang: (lang: Lang) => void;
  /** Texte traduit ; {nom} est remplacé par vars.nom. */
  t: (key: Key, vars?: Record<string, string>) => string;
  /** Date et heure dans la langue choisie (ex. 10 nov. 2026, 23:31). */
  formatDate: (date: Date) => string;
  /** Message lisible pour une erreur (ApiError ou autre). */
  errorText: (error: unknown) => { title: string; detail: string };
}

const I18nContext = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);
  document.documentElement.lang = lang;

  const setLang = (next: Lang) => {
    setLangState(next);
    try { localStorage.setItem(LANG_KEY, next); } catch { /* rien */ }
  };

  const t: I18n["t"] = (key, vars) =>
    DICTS[lang][key].replace(/\{(\w+)\}/g, (_, name: string) => vars?.[name] ?? "");

  const formatDate: I18n["formatDate"] = (date) =>
    date.toLocaleString(lang === "fr" ? "fr-FR" : "en-GB", { dateStyle: "medium", timeStyle: "short" });

  const errorText: I18n["errorText"] = (error) => {
    if (!(error instanceof ApiError)) return { title: t("error.other"), detail: String(error) };
    const detail = lang === "en" ? SERVER_MESSAGES_EN[error.detail] ?? error.detail : error.detail;
    // Refus simple (400) avec une explication du serveur : l'explication suffit comme titre.
    if (error.kind === "other" && detail) return { title: detail, detail: "" };
    return { title: t(`error.${error.kind}` as Key), detail };
  };

  return <I18nContext.Provider value={{ lang, setLang, t, formatDate, errorText }}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18n {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n doit être utilisé dans <I18nProvider>");
  return ctx;
}

export type TranslationKey = Key;
