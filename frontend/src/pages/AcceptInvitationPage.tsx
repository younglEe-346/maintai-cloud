// Page ouverte depuis le lien de l'e-mail d'invitation : http://localhost:5173/?invitation=<jeton>
// Le collègue invité choisit son nom et son mot de passe ; son compte est créé dans l'usine
// avec le rôle prévu, puis il est connecté directement.
import { useEffect, useState, type FormEvent } from "react";
import { ApiError, authApi, parseApiDate, type InvitationInfo } from "../api";
import { useAuth } from "../auth";
import { useI18n, type TranslationKey } from "../i18n";
import { Button, Card, ErrorBox, Field, Notice, Spinner } from "../components/ui";

/** Jeton présent dans l'adresse (?invitation=...), ou null. */
export function readInvitationToken(): string | null {
  return new URLSearchParams(window.location.search).get("invitation");
}

/** Retire ?invitation=... de l'adresse sans recharger la page (le jeton ne doit pas traîner). */
export function clearInvitationFromUrl(): void {
  const url = new URL(window.location.href);
  url.searchParams.delete("invitation");
  window.history.replaceState(null, "", url.pathname + url.search + url.hash);
}

/** Message clair selon la réponse de l'API (app/api/v1/auth.py, find_valid_invitation). */
function invitationProblem(err: unknown): TranslationKey | null {
  if (!(err instanceof ApiError)) return null;
  if (err.status === 404) return "invite.invalid";
  if (err.status === 410) return "invite.expired";
  if (err.status === 409 && err.detail === "Invitation déjà utilisée") return "invite.used";
  return null;
}

export default function AcceptInvitationPage({ token, onDone }: { token: string; onDone: () => void }) {
  const { t, formatDate } = useI18n();
  const { status, me, logout } = useAuth();
  const [info, setInfo] = useState<InvitationInfo | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);

  useEffect(() => {
    let cancelled = false;
    authApi.invitationInfo(token)
      .then((i) => { if (!cancelled) setInfo(i); })
      .catch((e: unknown) => { if (!cancelled) setLoadError(e); });
    return () => { cancelled = true; };
  }, [token]);

  const problem = invitationProblem(loadError);

  return (
    <div className="mx-auto max-w-md px-4 py-10">
      <div className="mb-6 text-center">
        <h1 className="text-2xl font-bold">{t("app.name")}</h1>
        <p className="text-ink-muted">{t("invite.title")}</p>
      </div>
      <Card className="space-y-4 p-6">
        {loadError != null ? (
          <>
            {problem ? <Notice tone="warning">{t(problem)}</Notice> : <ErrorBox error={loadError} />}
            <Button variant="secondary" onClick={onDone}>{t("invite.goToLogin")}</Button>
          </>
        ) : info == null ? <Spinner /> : status === "signedIn" && me ? (
          <>
            <Notice tone="warning">{t("invite.alreadySignedIn", { email: me.email })}</Notice>
            <div className="flex flex-wrap gap-2">
              <Button onClick={logout}>{t("auth.logout")}</Button>
              <Button variant="secondary" onClick={onDone}>{t("invite.ignore")}</Button>
            </div>
          </>
        ) : (
          <AcceptForm token={token} info={info} onDone={onDone} />
        )}
        {info && (
          <p className="text-xs text-ink-muted">{t("invite.expires", { date: formatDate(parseApiDate(info.expires_at)) })}</p>
        )}
      </Card>
    </div>
  );
}

function AcceptForm({ token, info, onDone }: { token: string; info: InvitationInfo; onDone: () => void }) {
  const { t } = useI18n();
  const { startSession } = useAuth();
  const [form, setForm] = useState({ full_name: "", password: "", confirm: "" });
  const [errors, setErrors] = useState<Partial<Record<keyof typeof form, TranslationKey>>>({});
  const [apiError, setApiError] = useState<unknown>(null);
  const [sending, setSending] = useState(false);

  const set = (name: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((prev) => ({ ...prev, [name]: e.target.value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    // Mêmes règles que l'API (AcceptInvitationIn).
    const found: typeof errors = {};
    if (!form.full_name.trim()) found.full_name = "valid.required";
    if (form.password.length < 8) found.password = "valid.password";
    if (form.confirm !== form.password) found.confirm = "valid.passwordMatch";
    setErrors(found);
    setApiError(null);
    if (Object.keys(found).length) return;

    setSending(true);
    try {
      const { access_token } = await authApi.acceptInvitation({ token, full_name: form.full_name.trim(), password: form.password });
      onDone();                          // on retire le jeton de l'adresse...
      await startSession(access_token);  // ...et on entre dans l'usine
    } catch (err) {
      setApiError(err);
      setSending(false);
    }
  }

  const err = (name: keyof typeof form) => errors[name] && t(errors[name]!);

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <p className="text-sm">
        {t("invite.intro", { org: info.organization, role: t(`role.${info.role}`) })}
      </p>
      <Field id="inv-email" label={t("auth.email")} value={info.email} readOnly disabled hint={t("invite.emailFixed")} />
      <Field id="inv-name" label={t("auth.fullName")} autoComplete="name" value={form.full_name}
        onChange={set("full_name")} error={err("full_name")} />
      <Field id="inv-password" label={t("auth.password")} hint={t("auth.passwordHint")} type="password"
        autoComplete="new-password" value={form.password} onChange={set("password")} error={err("password")} />
      <Field id="inv-confirm" label={t("auth.passwordConfirm")} type="password" autoComplete="new-password"
        value={form.confirm} onChange={set("confirm")} error={err("confirm")} />
      {apiError != null && (invitationProblem(apiError)
        ? <Notice tone="warning">{t(invitationProblem(apiError)!)}</Notice>
        : <ErrorBox error={apiError} />)}
      <Button type="submit" disabled={sending} className="w-full">{sending ? t("auth.submitting") : t("invite.accept")}</Button>
    </form>
  );
}
