// Écran 6 : équipe de l'usine. Membres et rôles, invitations par e-mail.
// Règles (les mêmes que l'API, app/api/v1/organization.py) :
// - propriétaire : invite des administrateurs ou des membres, change les rôles, retire n'importe qui ;
// - administrateur : invite des membres, retire des membres ;
// - membre : voit seulement la liste de l'équipe.
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ApiError, parseApiDate, teamApi, type Invitation, type Member, type TeamRole } from "../api";
import { useAuth } from "../auth";
import { useI18n, type TranslationKey } from "../i18n";
import {
  Badge, Button, Card, EmptyState, ErrorBox, Field, Notice, PageHeader, SelectField, Spinner, inputClass, table,
} from "../components/ui";
import ConfirmAction from "../components/ConfirmAction";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function TeamPage() {
  const { t } = useI18n();
  const { me } = useAuth();
  const canInvite = me?.role === "owner" || me?.role === "admin";

  const [members, setMembers] = useState<Member[] | null>(null);
  const [invitations, setInvitations] = useState<Invitation[] | null>(null);
  const [loadError, setLoadError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      // Les invitations ne sont visibles que du propriétaire et des administrateurs (403 sinon).
      const [m, i] = await Promise.all([teamApi.members(), canInvite ? teamApi.invitations() : Promise.resolve([])]);
      setMembers(m);
      setInvitations(i);
    } catch (err) {
      setLoadError(err);
    }
  }, [canInvite]);

  useEffect(() => { void load(); }, [load]);

  return (
    <div className="space-y-6">
      <PageHeader title={t("team.title")} intro={t("team.intro")} />
      <RolesHelp />
      {canInvite ? <InviteForm onInvited={load} /> : <Notice>{t("team.memberOnly")}</Notice>}
      {loadError != null && <ErrorBox error={loadError} onRetry={() => void load()} />}
      {members == null ? (loadError == null && <Spinner />) : (
        <>
          <MembersTable members={members} onChanged={load} />
          {canInvite && invitations && <InvitationsTable invitations={invitations} onChanged={load} />}
        </>
      )}
    </div>
  );
}

function RolesHelp() {
  const { t } = useI18n();
  const roles: ["owner" | "admin" | "member", TranslationKey][] = [
    ["owner", "team.roleOwnerHelp"], ["admin", "team.roleAdminHelp"], ["member", "team.roleMemberHelp"],
  ];
  return (
    <Card>
      <h2 className="text-lg font-semibold">{t("team.rolesTitle")}</h2>
      <ul className="mt-2 space-y-1 text-sm">
        {roles.map(([role, help]) => (
          <li key={role}><span className="font-medium capitalize">{t(`role.${role}`)}</span> — {t(help)}</li>
        ))}
      </ul>
    </Card>
  );
}

function InviteForm({ onInvited }: { onInvited: () => Promise<void> }) {
  const { t } = useI18n();
  const { me } = useAuth();
  const isOwner = me?.role === "owner";
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<TeamRole>("member");
  const [fieldError, setFieldError] = useState<string>();
  const [apiError, setApiError] = useState<unknown>(null);
  const [result, setResult] = useState<{ email: string; sent: boolean } | null>(null);
  const [sending, setSending] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setApiError(null);
    setResult(null);
    const clean = email.trim().toLowerCase();
    if (!EMAIL_RE.test(clean)) return setFieldError(t("valid.email"));
    setFieldError(undefined);
    setSending(true);
    try {
      const inv = await teamApi.invite(clean, role);
      setResult({ email: inv.email, sent: inv.email_sent });
      setEmail("");
      setRole("member");
      await onInvited();
    } catch (err) {
      if (err instanceof ApiError && err.kind === "validation") setFieldError(t("valid.email"));
      setApiError(err);
    } finally {
      setSending(false);
    }
  }

  return (
    <Card>
      <form onSubmit={submit} noValidate className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">{t("team.inviteTitle")}</h2>
          <p className="text-sm text-ink-muted">{t("team.inviteIntro")}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-[1fr_14rem_auto] sm:items-start">
          <Field id="invite-email" label={t("auth.email")} type="email" autoComplete="off" value={email}
            onChange={(e) => setEmail(e.target.value)} error={fieldError} placeholder="prenom.nom@usine.fr" />
          <SelectField id="invite-role" label={t("team.role")} value={role}
            onChange={(e) => setRole(e.target.value as TeamRole)}
            hint={isOwner ? undefined : t("team.adminInviteOwnerOnly")}>
            <option value="member">{t("role.member")}</option>
            <option value="admin" disabled={!isOwner}>{t("role.admin")}</option>
          </SelectField>
          <Button type="submit" disabled={sending} className="sm:mt-6">{sending ? t("team.inviting") : t("team.invite")}</Button>
        </div>
        {result && (result.sent
          ? <Notice tone="success">{t("team.invited", { email: result.email })} {t("team.mailpitHint")}</Notice>
          : <Notice tone="warning">{t("team.invitedNoMail", { email: result.email })}</Notice>)}
        {apiError != null && <ErrorBox error={apiError} />}
      </form>
    </Card>
  );
}

function MembersTable({ members, onChanged }: { members: Member[]; onChanged: () => Promise<void> }) {
  const { t, formatDate } = useI18n();
  const { me } = useAuth();

  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">{t("team.membersTitle", { n: String(members.length) })}</h2>
      <div className={table.wrap}>
        <table className={table.table}>
          <thead className={table.head}>
            <tr>
              <th className={table.th}>{t("team.colName")}</th>
              <th className={table.th}>{t("team.role")}</th>
              <th className={table.th}>{t("team.colSince")}</th>
              <th className={table.th}><span className="sr-only">{t("team.colActions")}</span></th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => {
              const isMe = m.id === me?.id;
              // Mêmes règles que l'API : jamais le propriétaire, jamais soi-même ;
              // un administrateur ne retire que des membres.
              const canRemove = !isMe && m.role !== "owner" && (me?.role === "owner" || (me?.role === "admin" && m.role === "member"));
              const canChangeRole = me?.role === "owner" && m.role !== "owner";
              return (
                <tr key={m.id} className={`${table.row} align-top`}>
                  <td className={table.td}>
                    <p className="font-medium">{m.full_name || m.email}{isMe && <span className="text-ink-muted"> ({t("team.you")})</span>}</p>
                    <p className="text-xs text-ink-muted">{m.email}</p>
                  </td>
                  <td className={table.td}>
                    {canChangeRole ? <RoleSelect member={m} onChanged={onChanged} />
                      : <Badge tone={m.role === "owner" ? "info" : "neutral"}>{t(`role.${m.role}`)}</Badge>}
                  </td>
                  <td className={`${table.td} whitespace-nowrap text-ink-soft`}>{formatDate(parseApiDate(m.created_at))}</td>
                  <td className={`${table.td} min-w-48`}>
                    {canRemove && (
                      <ConfirmAction danger label={t("team.remove")} confirmLabel={t("team.removeConfirm")}
                        help={t("team.removeHelp", { name: m.full_name || m.email })}
                        onConfirm={async () => { await teamApi.remove(m.id); await onChanged(); }} />
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** Liste déroulante du rôle : le changement est enregistré tout de suite. */
function RoleSelect({ member, onChanged }: { member: Member; onChanged: () => Promise<void> }) {
  const { t } = useI18n();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function change(role: TeamRole) {
    setSaving(true);
    setError(null);
    try {
      await teamApi.changeRole(member.id, role);
      await onChanged();
    } catch (err) {
      setError(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-1">
      <label htmlFor={`role-${member.id}`} className="sr-only">{t("team.roleOf", { name: member.full_name || member.email })}</label>
      <select id={`role-${member.id}`} value={member.role} disabled={saving}
        onChange={(e) => void change(e.target.value as TeamRole)} className={`${inputClass()} w-auto py-1`}>
        <option value="member">{t("role.member")}</option>
        <option value="admin">{t("role.admin")}</option>
      </select>
      {saving && <p className="text-xs text-ink-muted">{t("common.working")}</p>}
      {error != null && <ErrorBox error={error} />}
    </div>
  );
}

type InvitationState = "pending" | "accepted" | "revoked" | "expired";

function stateOf(i: Invitation): InvitationState {
  if (i.accepted_at) return "accepted";
  if (i.revoked_at) return "revoked";
  return parseApiDate(i.expires_at) < new Date() ? "expired" : "pending";
}

const STATE_TONE = { pending: "info", accepted: "success", revoked: "neutral", expired: "warning" } as const;

function InvitationsTable({ invitations, onChanged }: { invitations: Invitation[]; onChanged: () => Promise<void> }) {
  const { t, formatDate } = useI18n();
  return (
    <section className="space-y-2">
      <h2 className="text-lg font-semibold">{t("team.invitationsTitle")}</h2>
      {invitations.length === 0 ? <EmptyState title={t("team.noInvitations")}>{t("team.noInvitationsText")}</EmptyState> : (
        <div className={table.wrap}>
          <table className={table.table}>
            <thead className={table.head}>
              <tr>
                <th className={table.th}>{t("auth.email")}</th>
                <th className={table.th}>{t("team.role")}</th>
                <th className={table.th}>{t("team.colStatus")}</th>
                <th className={table.th}>{t("team.colExpires")}</th>
                <th className={table.th}><span className="sr-only">{t("team.colActions")}</span></th>
              </tr>
            </thead>
            <tbody>
              {invitations.map((i) => {
                const state = stateOf(i);
                return (
                  <tr key={i.id} className={`${table.row} align-top`}>
                    <td className={`${table.td} font-medium`}>{i.email}</td>
                    <td className={table.td}>{t(`role.${i.role}`)}</td>
                    <td className={table.td}><Badge tone={STATE_TONE[state]}>{t(`team.state.${state}`)}</Badge></td>
                    <td className={`${table.td} whitespace-nowrap text-ink-soft`}>{formatDate(parseApiDate(i.expires_at))}</td>
                    <td className={`${table.td} min-w-48`}>
                      {state === "pending" && (
                        <ConfirmAction label={t("team.revoke")} confirmLabel={t("team.revokeConfirm")}
                          help={t("team.revokeHelp", { email: i.email })}
                          onConfirm={async () => { await teamApi.revoke(i.id); await onChanged(); }} />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
