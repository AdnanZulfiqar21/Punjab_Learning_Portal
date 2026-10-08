// Help on native (P15.S3): open a request, read replies and answer them. A question report opened from a written
// result carries its reference; the server resolves it to the exact question version and keeps your identity from
// the subject reviewer who handles it.
import { Stack, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ScrollView, View } from "react-native";
import type { SupportTicket } from "@portal/contracts";

import { Button, Choices, Field, FormError } from "@/components/form";
import { Card, ErrorState, Loading, Notice, T } from "@/components/ui";
import { Space } from "@/constants/theme";
import { useRequest } from "@/hooks/use-request";
import { useTheme } from "@/hooks/use-theme";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const CATEGORIES = [
  ["account", "Account"],
  ["access", "Plan or trial"],
  ["technical", "Technical"],
  ["academic_report", "Problem with a question"],
  ["other", "Other"],
] as const;
type Category = (typeof CATEGORIES)[number][0];
const STATUS: Record<string, string> = { open: "Open", in_progress: "In progress", waiting_learner: "Waiting for you", resolved: "Resolved" };
const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

export default function HelpScreen() {
  const { state } = useAuth();
  const c = useTheme();
  const params = useLocalSearchParams<{ attempt?: string; position?: string }>();
  return (
    <ScrollView style={{ backgroundColor: c.background }} contentContainerStyle={{ padding: Space.lg, gap: Space.lg }} keyboardShouldPersistTaps="handled">
      <Stack.Screen options={{ title: "Help" }} />
      {state.status === "loading" && <Loading label="Checking your sign-in" />}
      {state.status !== "loading" && state.status !== "signed_in" && <Notice title="Sign in to get help">Open the Account tab to sign in.</Notice>}
      {state.status === "signed_in" && <Help token={state.token} attempt={params.attempt} position={params.position ? Number(params.position) : undefined} />}
    </ScrollView>
  );
}

function Help({ token, attempt, position }: { token: string; attempt?: string; position?: number }) {
  const list = useRequest((signal) => api.tickets(token, signal), [token]);
  const [category, setCategory] = useState<Category>(attempt ? "academic_report" : "technical");
  const [subject, setSubject] = useState(attempt && position ? `Question ${position} of my written test` : "");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function open() {
    setBusy(true);
    setError(null);
    try {
      await api.openTicket(token, {
        category,
        subject: subject.trim(),
        body: body.trim(),
        ...(attempt && category === "academic_report" ? { reference: { kind: "written_attempt", id: attempt, position } } : {}),
      });
      setSent(true);
      setBody("");
      list.retry();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't send your request.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ gap: Space.lg }}>
      <T variant="title">Help</T>
      <Card label="Ask for help">
        <View style={{ gap: Space.sm }}>
          <Choices label="What is it about?" options={CATEGORIES} selected={[category]} onToggle={setCategory} />
          {attempt && category === "academic_report" && <T variant="small">This report is linked to question {position} of your written test.</T>}
          <Field label="Subject" value={subject} onChangeText={setSubject} maxLength={200} />
          <Field label="What happened?" value={body} onChangeText={setBody} multiline maxLength={4000} />
          <FormError message={error} />
          {sent && <T variant="small">Sent. We&apos;ll reply here.</T>}
          <Button label="Send" onPress={() => void open()} busy={busy} disabled={subject.trim().length < 3 || body.trim().length < 5} />
        </View>
      </Card>
      <T variant="heading" accessibilityRole="header">
        Your requests
      </T>
      {list.state.status === "loading" && <Loading label="Loading your requests" />}
      {list.state.status === "error" && <ErrorState error={list.state.error} onRetry={list.retry} />}
      {list.state.status === "success" && list.state.data.length === 0 && <T variant="muted">No requests yet.</T>}
      {list.state.status === "success" && list.state.data.map((t) => <Ticket key={t.id} token={token} ticket={t} onChange={list.retry} />)}
    </View>
  );
}

function Ticket({ token, ticket, onChange }: { token: string; ticket: SupportTicket; onChange: () => void }) {
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    setBusy(true);
    setError(null);
    try {
      await api.replyTicket(token, ticket.id, reply.trim());
      setReply(""); // only cleared once it has arrived
      onChange();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't send your reply.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card label={ticket.subject}>
      <View style={{ gap: Space.xs }}>
        <T style={{ fontWeight: "600" }}>{ticket.subject}</T>
        <T variant="small">
          {STATUS[ticket.status] ?? ticket.status} · updated {when(ticket.updated_at)}
        </T>
        {ticket.messages.map((m, i) => (
          <T key={i} variant="small">
            {m.from_staff ? "Support" : "You"} · {when(m.created_at)}: {m.body}
          </T>
        ))}
        {ticket.status !== "resolved" && (
          <>
            <Field label={`Reply to "${ticket.subject}"`} value={reply} onChangeText={setReply} multiline maxLength={4000} />
            <FormError message={error} />
            <Button variant="secondary" label="Send reply" onPress={() => void send()} busy={busy} disabled={!reply.trim()} />
          </>
        )}
      </View>
    </Card>
  );
}
