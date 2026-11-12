// Écran 1 : connexion et inscription d'une usine.
// Les règles des champs reprennent celles de l'API (RegisterIn dans app/api/v1/auth.py),
// pour prévenir l'utilisateur avant même d'envoyer la requête.
import { useState, type FormEvent } from "react";
import { ApiError } from "../api";
import { useAuth } from "../auth";
import { useI18n, type TranslationKey } from "../i18n";
import { Button, ErrorBox, Field, Notice } from "../components/ui";

type Mode = "login" | "register";
type Errors = Partial<Record<string, TranslationKey>>;

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function AuthPage() {
  const { t } = useI18n();
  const { expired } = useAuth();
  const [mode, setMode] = useState<Mode>("login");

  return (
    <div className="mx-auto max-w-md px-4 py-10">
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold">{t("app.name")}</h1>
        <p className="text-slate-500">{t("app.tagline")}</p>
      </div>

      <div className="mb-4 grid grid-cols-2 rounded-lg bg-slate-200 p-1" role="tablist">
        {(["login", "register"] as const).map((m) => (
          <button
            key={m}
            role="tab"
            aria-selected={mode === m}
            onClick={() => setMode(m)}
            className={`rounded-md py-2 text-sm font-medium ${mode === m ? "bg-white shadow" : "text-slate-600"}`}
          >
            {t(m === "login" ? "auth.loginTab" : "auth.registerTab")}
          </button>
        ))}
      </div>

      <div className="rounded-lg bg-white p-6 shadow">
        {expired && mode === "login" && <div className="mb-4"><Notice tone="warning">{t("auth.sessionExpired")}</Notice></div>}
        {mode === "login" ? <LoginForm /> : <RegisterForm />}
      </div>

      <p className="mt-4 text-center text-sm text-slate-500">{t("auth.invited")}</p>
    </div>
  );
}

function LoginForm() {
  const { t } = useI18n();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Errors>({});
  const [apiError, setApiError] = useState<unknown>(null);
  const [sending, setSending] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const found: Errors = {};
    if (!EMAIL_RE.test(email.trim())) found.email = "valid.email";
    if (!password) found.password = "valid.required";
    setErrors(found);
    setApiError(null);
    if (Object.keys(found).length) return;

    setSending(true);
    try {
      await login(email.trim(), password);
    } catch (err) {
      setApiError(err);
    } finally {
      setSending(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">{t("auth.loginTitle")}</h2>
        <p className="text-sm text-slate-500">{t("auth.loginHelp")}</p>
      </div>
      <Field id="login-email" label={t("auth.email")} type="email" autoComplete="email"
        value={email} onChange={(e) => setEmail(e.target.value)} error={errors.email && t(errors.email)} />
      <Field id="login-password" label={t("auth.password")} type="password" autoComplete="current-password"
        value={password} onChange={(e) => setPassword(e.target.value)} error={errors.password && t(errors.password)} />
      {apiError != null && <ErrorBox error={apiError} />}
      <Button type="submit" disabled={sending} className="w-full">
        {sending ? t("auth.submitting") : t("auth.submitLogin")}
      </Button>
    </form>
  );
}

function RegisterForm() {
  const { t } = useI18n();
  const { register } = useAuth();
  const [form, setForm] = useState({ org_name: "", full_name: "", email: "", password: "", confirm: "" });
  const [errors, setErrors] = useState<Errors>({});
  const [apiError, setApiError] = useState<unknown>(null);
  const [sending, setSending] = useState(false);

  // Mise à jour « fonctionnelle » : on part toujours de la dernière valeur du formulaire.
  const set = (name: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((prev) => ({ ...prev, [name]: e.target.value }));

  function validate(): Errors {
    const found: Errors = {};
    const org = form.org_name.trim();
    if (org.length < 2 || org.length > 100) found.org_name = "valid.orgName";
    if (!form.full_name.trim()) found.full_name = "valid.required";
    if (!EMAIL_RE.test(form.email.trim())) found.email = "valid.email";
    if (form.password.length < 8) found.password = "valid.password";
    if (form.confirm !== form.password) found.confirm = "valid.passwordMatch";
    return found;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    const found = validate();
    setErrors(found);
    setApiError(null);
    if (Object.keys(found).length) return;

    setSending(true);
    try {
      await register({
        org_name: form.org_name.trim(), full_name: form.full_name.trim(),
        email: form.email.trim(), password: form.password,
      });
    } catch (err) {
      // Champ refusé par l'API (422) : on l'affiche sous le bon champ.
      if (err instanceof ApiError && err.fields.length) {
        const fromApi: Errors = {};
        for (const f of err.fields) fromApi[f.field] = f.field === "email" ? "valid.email" : "valid.required";
        setErrors(fromApi);
      }
      setApiError(err);
    } finally {
      setSending(false);
    }
  }

  const err = (name: string) => errors[name] && t(errors[name]!);

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">{t("auth.registerTitle")}</h2>
        <p className="text-sm text-slate-500">{t("auth.registerHelp")}</p>
      </div>
      <Field id="reg-org" label={t("auth.orgName")} hint={t("auth.orgNameHint")} autoComplete="organization"
        value={form.org_name} onChange={set("org_name")} error={err("org_name")} />
      <Field id="reg-name" label={t("auth.fullName")} autoComplete="name"
        value={form.full_name} onChange={set("full_name")} error={err("full_name")} />
      <Field id="reg-email" label={t("auth.email")} type="email" autoComplete="email"
        value={form.email} onChange={set("email")} error={err("email")} />
      <Field id="reg-password" label={t("auth.password")} hint={t("auth.passwordHint")} type="password"
        autoComplete="new-password" value={form.password} onChange={set("password")} error={err("password")} />
      <Field id="reg-confirm" label={t("auth.passwordConfirm")} type="password" autoComplete="new-password"
        value={form.confirm} onChange={set("confirm")} error={err("confirm")} />
      {apiError != null && <ErrorBox error={apiError} />}
      <Button type="submit" disabled={sending} className="w-full">
        {sending ? t("auth.submitting") : t("auth.submitRegister")}
      </Button>
    </form>
  );
}
