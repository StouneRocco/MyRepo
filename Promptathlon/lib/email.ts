type DecisionEmailInput = {
  to: string;
  firstName: string;
  status: "ACCEPTED" | "REJECTED";
  homeTeam: string;
  awayTeam: string;
  matchDateTime: Date;
  venue: string;
};

export async function sendDecisionEmail(input: DecisionEmailInput): Promise<void> {
  const apiKey = process.env.BREVO_API_KEY;
  const senderEmail = process.env.BREVO_SENDER_EMAIL;
  const senderName = process.env.BREVO_SENDER_NAME || "JDA — Accréditations presse";

  if (!apiKey || !senderEmail) {
    throw new Error("Email non configuré : BREVO_API_KEY et BREVO_SENDER_EMAIL sont requis.");
  }

  const date = new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "full",
    timeStyle: "short",
    timeZone: process.env.APP_TIMEZONE || "Europe/Paris",
  }).format(input.matchDateTime);
  const accepted = input.status === "ACCEPTED";
  const subject = accepted
    ? `Accréditation confirmée — ${input.homeTeam} / ${input.awayTeam}`
    : `Réponse à votre demande d’accréditation — ${input.homeTeam} / ${input.awayTeam}`;
  const htmlContent = accepted
    ? `<p>Bonjour ${escapeHtml(input.firstName)},</p><p>Votre demande d’accréditation est acceptée.</p><p><strong>Match :</strong> ${escapeHtml(input.homeTeam)} — ${escapeHtml(input.awayTeam)}<br><strong>Date et heure :</strong> ${escapeHtml(date)}<br><strong>Lieu :</strong> ${escapeHtml(input.venue)}</p><p>La JDA vous remercie.</p>`
    : `<p>Bonjour ${escapeHtml(input.firstName)},</p><p>Nous sommes désolés de vous informer que votre demande d’accréditation n’a pas pu être retenue, compte tenu du nombre important de demandes reçues.</p><p>Merci de votre compréhension.<br>La JDA</p>`;

  const response = await fetch("https://api.brevo.com/v3/smtp/email", {
    method: "POST",
    headers: { "api-key": apiKey, "content-type": "application/json", accept: "application/json" },
    body: JSON.stringify({
      sender: { email: senderEmail, name: senderName },
      to: [{ email: input.to, name: input.firstName }],
      subject,
      htmlContent,
      tags: ["promptathlon", "accreditation-decision"],
    }),
    cache: "no-store",
  });
  if (!response.ok) {
    const detail = (await response.text()).slice(0, 300);
    throw new Error(`Brevo a refusé l’envoi (${response.status}) : ${detail}`);
  }
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char] || char);
}
