import { Link } from 'react-router-dom'

// Brutalist launcher (Uiverse.io / 0xnihilism), Gemini variant — this chat is
// powered by the Gemini API. Links to the API-key / MCP-connector setup.
// Hover choreography lives in the `.brutalist-button*` rules in index.css.
export function GeminiBadge() {
  return (
    <Link
      to="/app/settings?tab=api-keys"
      className="brutalist-button gemini"
      aria-label="This chat is powered by the Gemini API — open connector settings"
      title="Powered by the Gemini API"
    >
      <span className="brutalist-logo" aria-hidden="true">
        <svg className="brutalist-icon" viewBox="0 0 24 24">
          <path d="M12 2c.6 5.2 4.8 9.4 10 10-5.2.6-9.4 4.8-10 10-.6-5.2-4.8-9.4-10-10 5.2-.6 9.4-4.8 10-10Z" />
        </svg>
      </span>
      <span className="button-text" aria-hidden="true">
        <span>Powered by</span>
        <span>Gemini</span>
      </span>
    </Link>
  )
}
